import os
import tempfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.agents.coach_agent import CoachAgent
from app.agents.interview_agent import InterviewAgent
from app.agents.match_agent import MatchAgent
from app.agents.rewrite_agent import RewriteAgent
from app.agents.resume_agent import UnsupportedFileTypeError, TextExtractionError, ResumeParseError
from app.agents.jd_agent import JDFetchError, JDParseError
from app.models.interview import InterviewSessionData
from app.graph.workflow import (
    get_workflow_state,
    run_full_pipeline,
    run_parse_jd,
    run_parse_resume,
    run_workflow,
    workflow_graph,
)
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume

app = FastAPI(title="AI Career Agent Service")

_MODEL = "claude-haiku-4-5-20251001"
_ALLOWED_SUFFIXES = {".pdf", ".docx"}

# In-memory session store (keyed by session_id).
# In production this would be Redis or a DB.
_sessions: dict[str, InterviewSessionData] = {}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class JDParseRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None


class MatchRequest(BaseModel):
    resume: dict
    jd: dict


class WorkflowRunRequest(BaseModel):
    user_id: str
    resume_file_path: Optional[str] = None
    jd_text: Optional[str] = None
    thread_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_AGENT_TO_STEP: dict[str, str] = {
    "resume_agent":    "parse_resume",
    "jd_agent":        "parse_jd",
    "match_agent":     "match",
    "rewrite_agent":   "rewrite",
    "interview_agent": "interview",
    "coach_agent":     "review",
}

_MERMAID_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Career Workflow Graph</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8f9fa;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem;
      margin: 0;
    }}
    h1 {{ color: #343a40; margin-bottom: 1.5rem; }}
    .mermaid {{
      background: #ffffff;
      border: 1px solid #dee2e6;
      border-radius: 8px;
      padding: 2rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.08);
      max-width: 900px;
      width: 100%;
    }}
  </style>
</head>
<body>
  <h1>AI Career Workflow Graph</h1>
  <div class="mermaid">
{diagram}
  </div>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "default" }});
  </script>
</body>
</html>
"""


def _summarize_runs(agent_runs: list[dict]) -> dict:
    """Compute aggregate stats from a list of agent_run dicts."""
    total_duration_ms = sum(r.get("duration_ms", 0) for r in agent_runs)
    total_tokens      = sum(r.get("token_count", 0) for r in agent_runs)
    steps_completed   = [
        _AGENT_TO_STEP.get(r["agent_name"], r["agent_name"])
        for r in agent_runs
        if r.get("status") == "success"
    ]
    return {
        "total_duration_ms": total_duration_ms,
        "total_tokens":      total_tokens,
        "steps_completed":   steps_completed,
    }


def _derive_workflow_status(final_state: dict) -> str:
    """Determine workflow_status from final graph state."""
    stored = final_state.get("workflow_status")
    if stored in ("completed", "degraded", "failed"):
        return stored
    # Fallback: infer from error / current_step
    if final_state.get("error") or final_state.get("current_step") == "error":
        return "failed"
    return "completed"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/llm")
async def health_llm():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(
            status_code=503,
            content={"status": "llm-unavailable", "error": "ANTHROPIC_API_KEY is not set"},
        )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=16,
            messages=[{"role": "user", "content": "Respond with only: ok"}],
        )
        return {"status": "ok", "model": message.model}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "llm-unavailable", "error": str(e)},
        )


# ---------------------------------------------------------------------------
# Workflow visualisation
# ---------------------------------------------------------------------------

@app.get("/api/workflow/visualize")
async def workflow_visualize():
    """Return the Mermaid diagram source of the compiled workflow graph."""
    mermaid = workflow_graph.get_graph().draw_mermaid()
    return {"mermaid": mermaid}


@app.get("/api/workflow/visualize/html", response_class=HTMLResponse)
async def workflow_visualize_html():
    """Return an HTML page that renders the workflow graph via Mermaid JS."""
    mermaid = workflow_graph.get_graph().draw_mermaid()
    html = _MERMAID_HTML_TEMPLATE.format(diagram=mermaid)
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Resume — now backed by the graph's parse_resume_node via run_parse_resume()
# ---------------------------------------------------------------------------

@app.post("/api/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    """
    Parse a resume file and return structured JSON.

    Internally delegates to run_parse_resume() (the graph's parse_resume_node)
    rather than calling ResumeAgent directly.  The response shape is unchanged:
    ParsedResume fields + an "agent_run" key.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported file type '{suffix}'. Upload a .pdf or .docx file."},
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        resume_dict, agent_runs = run_parse_resume(tmp_path)

        if resume_dict is None:
            # parse_resume_node logged the error in agent_runs[0]["error_message"]
            error_msg = (agent_runs[0].get("error_message") if agent_runs else None) or "Resume parsing failed"
            return JSONResponse(status_code=500, content={"error": error_msg})

        # Return same shape as before: ParsedResume fields + agent_run
        agent_run = agent_runs[0] if agent_runs else {}
        return {**resume_dict, "agent_run": agent_run}

    except (UnsupportedFileTypeError, TextExtractionError, ResumeParseError) as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


# ---------------------------------------------------------------------------
# Job Description — now backed by run_parse_jd()
# ---------------------------------------------------------------------------

@app.post("/api/jd/parse")
async def parse_jd(body: JDParseRequest):
    """
    Parse a job description from raw text or a URL.

    Delegates to run_parse_jd() (the graph's parse_jd_node).
    Response shape is unchanged: ParsedJobDescription fields + "agent_run".
    """
    if not body.text and not body.url:
        return JSONResponse(
            status_code=400,
            content={"error": "Provide at least one of 'text' or 'url'."},
        )

    jd_input = body.text or body.url

    try:
        jd_dict, agent_runs = run_parse_jd(jd_input)

        if jd_dict is None:
            error_msg = (agent_runs[0].get("error_message") if agent_runs else None) or "JD parsing failed"
            return JSONResponse(status_code=500, content={"error": error_msg})

        agent_run = agent_runs[0] if agent_runs else {}
        return {**jd_dict, "agent_run": agent_run}

    except (JDFetchError, JDParseError) as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})


# ---------------------------------------------------------------------------
# Match — unchanged (caller already has parsed resume + JD)
# ---------------------------------------------------------------------------

@app.post("/api/match")
async def match_resume_to_jd(body: MatchRequest):
    """
    Score a resume against a job description.

    Calls MatchAgent directly — the caller already holds ParsedResume and
    ParsedJobDescription dicts, so running the full parse pipeline would be
    redundant.  Use POST /api/pipeline/run for the one-shot upload flow.
    """
    try:
        resume = ParsedResume.model_validate(body.resume)
        jd = ParsedJobDescription.model_validate(body.jd)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Validation failed: {exc}"})

    try:
        agent = MatchAgent()
        result, agent_run = agent.match(resume, jd)
        return {**result.model_dump(), "agent_run": agent_run}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Match failed: {exc}"})


# ---------------------------------------------------------------------------
# Rewrite — caller already has parsed resume + JD + match_result
# ---------------------------------------------------------------------------

class RewriteRequest(BaseModel):
    resume: dict
    jd: dict
    match_result: dict


@app.post("/api/rewrite")
async def rewrite_resume(body: RewriteRequest):
    """
    Rewrite resume bullets to better match the JD.

    Accepts already-parsed resume and JD dicts plus the match_result (from
    POST /api/match).  Calls RewriteAgent directly — use POST /api/pipeline/run
    for the one-shot upload flow.

    Returns RewriteResult JSON including the embedded fidelity report.
    """
    try:
        resume = ParsedResume.model_validate(body.resume)
        jd     = ParsedJobDescription.model_validate(body.jd)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Validation failed: {exc}"})

    try:
        agent = RewriteAgent()
        result, agent_run = agent.rewrite(resume, jd, body.match_result)
        return {**result.model_dump(), "agent_run": agent_run}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Rewrite failed: {exc}"})


# ---------------------------------------------------------------------------
# Pipeline — one-shot upload: resume file + JD text → full result
# ---------------------------------------------------------------------------

@app.post("/api/pipeline/run")
async def pipeline_run(
    file: UploadFile = File(...),
    jd_text: str = Form(...),
    user_id: Optional[str] = Form(default="default"),
):
    """
    One-click endpoint: upload a resume file + paste JD text → get everything.

    Saves the file to a temp path, invokes run_full_pipeline() (which chains
    parse_resume → parse_jd → match → routing), deletes the temp file, and
    returns the full workflow state:

      {
        "current_step":   "reviewing" | "error" | ...,
        "resume":         { ParsedResume fields },
        "jd":             { ParsedJobDescription fields },
        "match_result":   { scores, gap analysis },
        "routing":        "rewrite" | "interview",
        "agent_runs":     [ ... ],
        "error":          null | "<message>"
      }

    This endpoint replaces the three-step (parse resume → parse JD → match)
    flow with a single call for clients that need the full pipeline result.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported file type '{suffix}'. Upload a .pdf or .docx file."},
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        final_state = run_full_pipeline(
            resume_file_path=tmp_path,
            jd_text=jd_text,
            user_id=user_id or "default",
        )

        # Determine the routing decision from the final step label
        step       = final_state.get("current_step", "")
        agent_runs = final_state.get("agent_runs", [])
        stats      = _summarize_runs(agent_runs)

        if step == "error":
            return JSONResponse(
                status_code=500,
                content={
                    "error":           final_state.get("error"),
                    "workflow_status": "failed",
                    "agent_runs":      agent_runs,
                    **stats,
                },
            )

        routing = None
        match_score = (final_state.get("match_result") or {}).get("overall_score")
        if match_score is not None:
            routing = "interview" if match_score >= 70 else "rewrite"

        return {
            "current_step":    step,
            "resume":          final_state.get("resume"),
            "jd":              final_state.get("jd"),
            "match_result":    final_state.get("match_result"),
            "routing":         routing,
            "workflow_status": _derive_workflow_status(final_state),
            "agent_runs":      agent_runs,
            "error":           final_state.get("error"),
            **stats,
        }

    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Pipeline failed: {exc}"})
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


# ---------------------------------------------------------------------------
# Workflow (graph-level, accepts pre-built paths rather than file uploads)
# ---------------------------------------------------------------------------

@app.post("/api/workflow/run")
async def workflow_run(body: WorkflowRunRequest):
    """
    Invoke the full LangGraph workflow with explicit file paths.

    Used by Spring Boot (which has already persisted the file) rather than by
    browser clients.  For browser use, prefer POST /api/pipeline/run.
    """
    try:
        final_state = run_workflow(
            user_id=body.user_id,
            resume_file_path=body.resume_file_path,
            jd_text=body.jd_text,
            thread_id=body.thread_id,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Workflow failed: {exc}"},
        )

    agent_runs = final_state.get("agent_runs", [])
    stats      = _summarize_runs(agent_runs)

    if final_state.get("error"):
        return JSONResponse(
            status_code=500,
            content={
                "error":           final_state["error"],
                "workflow_status": "failed",
                "agent_runs":      agent_runs,
                **stats,
            },
        )

    return {
        **final_state,
        "workflow_status": _derive_workflow_status(final_state),
        **stats,
    }


@app.get("/api/workflow/status/{thread_id}")
async def workflow_status(thread_id: str):
    """Return the current checkpoint state for a running or completed workflow."""
    try:
        snap = get_workflow_state(thread_id)
    except Exception as exc:
        return JSONResponse(
            status_code=404,
            content={"error": f"No checkpoint found for thread_id '{thread_id}': {exc}"},
        )

    state_values = snap["values"]
    return {
        "thread_id":    thread_id,
        "current_step": state_values.get("current_step"),
        "next":         snap["next"],
        "is_complete":  len(snap["next"]) == 0,
        "error":        state_values.get("error"),
        "match_result": state_values.get("match_result"),
        "agent_runs":   len(state_values.get("agent_runs") or []),
        "created_at":   snap["created_at"],
    }


# ---------------------------------------------------------------------------
# RAG — interview question index and search
# ---------------------------------------------------------------------------

class RagSearchRequest(BaseModel):
    query: str
    role: Optional[str] = None
    type: Optional[str] = None
    difficulty: Optional[str] = None
    limit: Optional[int] = 5


@app.post("/api/rag/index")
async def rag_index():
    """
    (Re-)index the built-in interview question bank into Qdrant.

    Idempotent — safe to call multiple times.  Returns the number of questions
    indexed.
    """
    try:
        from app.rag.question_index import index_questions
        count = index_questions()
        return {"status": "ok", "count": count}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Indexing failed: {exc}"})


@app.post("/api/rag/search")
async def rag_search(body: RagSearchRequest):
    """
    Semantic search over the interview question bank.

    Optionally filter by role ("backend" | "frontend" | "general"),
    type ("behavioral" | "technical"), or difficulty ("easy" | "medium" | "hard").
    Returns a ranked list of matching questions with similarity scores.
    """
    try:
        from app.rag.question_index import search_questions
        results = search_questions(
            query=body.query,
            role=body.role,
            type=body.type,
            difficulty=body.difficulty,
            limit=body.limit or 5,
        )
        return results
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Search failed: {exc}"})


# ---------------------------------------------------------------------------
# Interview — multi-turn mock interview
# ---------------------------------------------------------------------------

class InterviewStartRequest(BaseModel):
    jd: dict
    resume: dict
    num_questions: Optional[int] = 5


class InterviewAnswerRequest(BaseModel):
    answer: str


@app.post("/api/interview/start")
async def interview_start(body: InterviewStartRequest):
    """
    Start a new mock interview session.

    Validates the jd and resume dicts, retrieves questions from Qdrant via RAG,
    stores the session in memory, and returns the first question.

    Response: { session_id, first_question, question_number, total_questions,
                type, difficulty }
    """
    try:
        jd     = ParsedJobDescription.model_validate(body.jd)
        resume = ParsedResume.model_validate(body.resume)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Validation failed: {exc}"})

    try:
        agent   = InterviewAgent()
        session = agent.start_session(jd, resume, num_questions=body.num_questions or 5)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Failed to start session: {exc}"})

    _sessions[session.session_id] = session

    # Fetch and return the first question
    first = agent.ask_next(session)
    return {
        "session_id": session.session_id,
        **first,
    }


@app.post("/api/interview/{session_id}/answer")
async def interview_answer(session_id: str, body: InterviewAnswerRequest):
    """
    Submit an answer for the current question in the session.

    Evaluates the answer via Claude, optionally generates a follow-up question,
    then advances to the next question.

    Response: { evaluation, next_question } or { evaluation, done: True } when
    all questions have been answered.
    """
    session = _sessions.get(session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": f"Session '{session_id}' not found"})

    if session.status == "completed":
        return JSONResponse(status_code=409, content={"error": "Session is already completed"})

    # The question the candidate just answered is the one *before* the current index
    # (ask_next already advanced it).  If current_question_index == 0 the caller
    # hasn't called /start yet — treat index-1 defensively.
    answered_idx = session.current_question_index - 1
    if answered_idx < 0 or answered_idx >= len(session.questions):
        return JSONResponse(
            status_code=400,
            content={"error": "No active question to answer. Call /start first."},
        )

    current_question = session.questions[answered_idx].text

    agent = InterviewAgent()

    try:
        evaluation = agent.evaluate_answer(session, current_question, body.answer)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Evaluation failed: {exc}"})

    # Optional follow-up (best-effort; never blocks the response)
    follow_up_text: Optional[str] = None
    try:
        follow_up_text = agent.generate_follow_up(session, current_question, body.answer, evaluation)
    except Exception as exc:
        logger.warning("Follow-up generation failed (non-fatal): %s", exc)

    # Advance to next question
    next_q = agent.ask_next(session)

    response: dict = {"evaluation": evaluation}
    if follow_up_text:
        response["follow_up"] = follow_up_text
    response.update(next_q)  # merges next_question fields or {"done": True, "message": ...}
    return response


@app.get("/api/interview/{session_id}")
async def interview_status(session_id: str):
    """
    Return the current state of an interview session.

    Response includes: session_id, jd_title, status, current_question_index,
    total_questions, questions asked so far (with their texts), and evaluations.
    """
    session = _sessions.get(session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": f"Session '{session_id}' not found"})

    asked = session.questions[: session.current_question_index]
    return {
        "session_id":             session.session_id,
        "jd_title":               session.jd_title,
        "status":                 session.status,
        "current_question_index": session.current_question_index,
        "total_questions":        len(session.questions),
        "questions_asked": [
            {
                "question_number": i + 1,
                "text":            q.text,
                "type":            q.type,
                "difficulty":      q.difficulty,
            }
            for i, q in enumerate(asked)
        ],
        "answers": [a.model_dump() for a in session.answers],
        "started_at": session.started_at,
        "ended_at":   session.ended_at,
    }


class CoachReviewRequest(BaseModel):
    session: dict
    jd: dict
    resume: dict


@app.post("/api/interview/{session_id}/end")
async def interview_end(session_id: str):
    """
    End the session, run CoachAgent review, and return a full summary.

    Marks status as 'completed', computes aggregate scores, then calls
    CoachAgent.review() for a structured performance assessment.

    Response: { session summary fields, average_scores, coach_review }
    """
    from datetime import datetime, timezone

    session = _sessions.get(session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": f"Session '{session_id}' not found"})

    if session.status != "completed":
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc).isoformat()

    answers = session.answers
    if answers:
        avg_relevance     = round(sum(a.relevance_score     for a in answers) / len(answers), 1)
        avg_depth         = round(sum(a.depth_score         for a in answers) / len(answers), 1)
        avg_communication = round(sum(a.communication_score for a in answers) / len(answers), 1)
        avg_overall       = round(sum(a.overall_score       for a in answers) / len(answers), 1)
    else:
        avg_relevance = avg_depth = avg_communication = avg_overall = 0.0

    # Attempt CoachAgent review — non-fatal if it fails
    coach_review_dict: Optional[dict] = None
    coach_agent_run:   Optional[dict] = None

    # We need the JD and resume to call CoachAgent.  They were validated at
    # /start time but not stored in the session.  We can only call CoachAgent
    # from /end if the caller supplies them via /api/coach/review instead.
    # For sessions that have a JD stored in the session, use it directly.
    # For now, skip the automatic call if JD/resume are unavailable.

    response: dict = {
        "session_id":         session.session_id,
        "jd_title":           session.jd_title,
        "status":             session.status,
        "total_questions":    len(session.questions),
        "questions_answered": len(answers),
        "average_scores": {
            "relevance":     avg_relevance,
            "depth":         avg_depth,
            "communication": avg_communication,
            "overall":       avg_overall,
        },
        "questions":  [q.model_dump() for q in session.questions],
        "answers":    [a.model_dump() for a in answers],
        "started_at": session.started_at,
        "ended_at":   session.ended_at,
    }

    return response


@app.post("/api/interview/{session_id}/end-with-review")
async def interview_end_with_review(session_id: str, body: CoachReviewRequest):
    """
    End the session and return the summary + a full CoachAgent review.

    Identical to POST /end, but also accepts jd and resume to run CoachAgent.
    Use this when the caller has the JD and resume available.

    Request body: { jd: dict, resume: dict }
    Response: { session summary, average_scores, coach_review }
    """
    from datetime import datetime, timezone

    session = _sessions.get(session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": f"Session '{session_id}' not found"})

    try:
        jd     = ParsedJobDescription.model_validate(body.jd)
        resume = ParsedResume.model_validate(body.resume)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Validation failed: {exc}"})

    if session.status != "completed":
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc).isoformat()

    answers = session.answers
    if answers:
        avg_relevance     = round(sum(a.relevance_score     for a in answers) / len(answers), 1)
        avg_depth         = round(sum(a.depth_score         for a in answers) / len(answers), 1)
        avg_communication = round(sum(a.communication_score for a in answers) / len(answers), 1)
        avg_overall       = round(sum(a.overall_score       for a in answers) / len(answers), 1)
    else:
        avg_relevance = avg_depth = avg_communication = avg_overall = 0.0

    coach_review_dict: Optional[dict] = None
    if answers:
        try:
            coach_review, _ = CoachAgent().review(session, jd, resume)
            coach_review_dict = coach_review.model_dump()
        except Exception as exc:
            logger.warning("CoachAgent.review() failed in /end-with-review (non-fatal): %s", exc)

    return {
        "session_id":         session.session_id,
        "jd_title":           session.jd_title,
        "status":             session.status,
        "total_questions":    len(session.questions),
        "questions_answered": len(answers),
        "average_scores": {
            "relevance":     avg_relevance,
            "depth":         avg_depth,
            "communication": avg_communication,
            "overall":       avg_overall,
        },
        "questions":    [q.model_dump() for q in session.questions],
        "answers":      [a.model_dump() for a in answers],
        "started_at":   session.started_at,
        "ended_at":     session.ended_at,
        "coach_review": coach_review_dict,
    }


@app.post("/api/coach/review")
async def coach_review(body: CoachReviewRequest):
    """
    Standalone CoachAgent review endpoint.

    Accepts a completed InterviewSessionData dict plus the JD and resume,
    runs CoachAgent.review(), and returns the CoachReview JSON.

    Use this to re-review an existing session or to review a session that
    was run outside the /api/interview/* flow.

    Response: CoachReview fields
    """
    try:
        from app.models.interview import InterviewSessionData as ISD
        session = ISD.model_validate(body.session)
        jd      = ParsedJobDescription.model_validate(body.jd)
        resume  = ParsedResume.model_validate(body.resume)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Validation failed: {exc}"})

    try:
        coach_review_result, agent_run = CoachAgent().review(session, jd, resume)
        return {**coach_review_result.model_dump(), "agent_run": agent_run}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"CoachAgent review failed: {exc}"})


# ---------------------------------------------------------------------------
# Agent-run passthrough
# ---------------------------------------------------------------------------

@app.post("/api/agent-runs")
async def receive_agent_run(body: dict):
    """
    Passthrough endpoint for agent-run records.

    Accepts an agent_run dict (as produced by log_agent_run) and returns it
    as-is. The caller (Spring Boot) is responsible for persisting the record.
    """
    return body
