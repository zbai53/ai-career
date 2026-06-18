import os
import tempfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agents.match_agent import MatchAgent
from app.agents.resume_agent import UnsupportedFileTypeError, TextExtractionError, ResumeParseError
from app.agents.jd_agent import JDFetchError, JDParseError
from app.graph.workflow import (
    get_workflow_state,
    run_full_pipeline,
    run_parse_jd,
    run_parse_resume,
    run_workflow,
)
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume

app = FastAPI(title="AI Career Agent Service")

_MODEL = "claude-haiku-4-5-20251001"
_ALLOWED_SUFFIXES = {".pdf", ".docx"}


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
        step = final_state.get("current_step", "")
        if step == "error":
            return JSONResponse(
                status_code=500,
                content={
                    "error":      final_state.get("error"),
                    "agent_runs": final_state.get("agent_runs", []),
                },
            )

        routing = None
        match_score = (final_state.get("match_result") or {}).get("overall_score")
        if match_score is not None:
            routing = "interview" if match_score >= 70 else "rewrite"

        return {
            "current_step": step,
            "resume":       final_state.get("resume"),
            "jd":           final_state.get("jd"),
            "match_result": final_state.get("match_result"),
            "routing":      routing,
            "agent_runs":   final_state.get("agent_runs", []),
            "error":        final_state.get("error"),
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

    if final_state.get("error"):
        return JSONResponse(
            status_code=500,
            content={"error": final_state["error"]},
        )

    return final_state


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
