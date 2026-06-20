"""
LangGraph workflow for the AI Career assistant.

parse_resume_node, parse_jd_node, and match_node call real agents.
rewrite_node, interview_node, and review_node remain placeholders for Phase 4/5.

Error handling model
--------------------
Every real-agent node catches exceptions internally and writes the error into
state["error"].  A dedicated check_error() routing function sits after each
such node and diverts to error_handler_node when an error is detected.
error_handler_node logs the error and transitions the workflow to END cleanly.

The graph is compiled with a MemorySaver checkpointer so any run can be
inspected or resumed via a thread_id.

Run from agent-service/ (no real files needed — uses placeholder nodes):
    PYTHONPATH=. python app/graph/workflow.py

Run with real agents (requires ANTHROPIC_API_KEY and an actual resume file):
    ANTHROPIC_API_KEY=<key> PYTHONPATH=. python app/graph/workflow.py <resume.pdf> "<jd text>"
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.jd_agent import JDAgent
from app.agents.match_agent import MatchAgent
from app.agents.resume_agent import ResumeAgent
from app.agents.rewrite_agent import RewriteAgent
from app.graph.state import JobHelperState
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_FAILED_RUN_MODEL = "claude-haiku-4-5-20251001"


# =============================================================================
# Internal helpers
# =============================================================================

def _failed_agent_run(agent_name: str, error_message: str) -> dict:
    """Build a failed agent_run entry without a real Claude call."""
    return log_agent_run(
        agent_name=agent_name,
        input_summary="(failed before agent call)",
        output_summary="(no output — node failed)",
        status="error",
        duration_ms=0,
        token_count=0,
        model_name=_FAILED_RUN_MODEL,
        error_message=error_message,
    )


# =============================================================================
# Retry wrapper
# =============================================================================

def retry_node(node_fn, max_retries: int = 2, delay_seconds: float = 1.0):
    """
    Wrap a node function with automatic retry logic.

    If the node writes state["error"], the wrapper retries the node up to
    max_retries times (with delay_seconds sleep between attempts).  The
    original state (not the error state) is used for each retry so transient
    failures don't leave stale partial updates.

    On success after retries, the wrapper:
      - Tags the last agent_run entry with {"retry_count": N}.
      - Merges retry_counts[node_name] = N back into state.

    After exhausting all retries, the error is kept in the returned dict so
    _check_error() can route the workflow to error_handler.

    Args:
        node_fn:       The original node function (state -> dict).
        max_retries:   Maximum number of re-attempts after the first failure.
        delay_seconds: Seconds to sleep between attempts.

    Returns:
        A wrapped node function with the same __name__ as node_fn.
    """
    def _wrapped(state: JobHelperState) -> dict:
        node_name = node_fn.__name__
        result = node_fn(state)

        if not result.get("error"):
            return result

        # --- one or more retries ---
        retry_counts = dict(state.get("retry_counts") or {})
        # Accumulate failed agent_run entries across attempts
        accumulated_runs = list(result.get("agent_runs", state.get("agent_runs", [])))

        for attempt in range(1, max_retries + 1):
            logger.warning(
                "[workflow] %s failed (attempt %d/%d), retrying in %.1fs — %s",
                node_name, attempt, max_retries, delay_seconds, result.get("error"),
            )
            time.sleep(delay_seconds)

            retry_counts[node_name] = attempt
            # Retry with original state inputs + updated retry_counts + accumulated runs
            retry_state = {
                **state,
                "agent_runs":   accumulated_runs,
                "retry_counts": retry_counts,
                "error":        None,
            }
            result = node_fn(retry_state)

            accumulated_runs = list(result.get("agent_runs", accumulated_runs))

            if not result.get("error"):
                # Tag the last successful run with retry metadata
                if accumulated_runs:
                    last_run = dict(accumulated_runs[-1])
                    last_run["retry_count"] = attempt
                    accumulated_runs = accumulated_runs[:-1] + [last_run]
                logger.info("[workflow] %s succeeded on retry %d", node_name, attempt)
                return {
                    **result,
                    "agent_runs":     accumulated_runs,
                    "retry_counts":   retry_counts,
                    "workflow_status": "running",
                }

        # All retries exhausted — propagate the error for routing
        logger.error("[workflow] %s failed after %d retries", node_name, max_retries)
        return {**result, "agent_runs": accumulated_runs, "retry_counts": retry_counts}

    _wrapped.__name__ = node_fn.__name__
    return _wrapped


# =============================================================================
# Degraded-mode helper (match_node fallback)
# =============================================================================

def _compute_degraded_match_result(resume: dict, jd: dict) -> dict:
    """
    Compute basic skill/keyword match scores using pure Python (no Claude call).

    Called when MatchAgent.match() fails completely, so the workflow can still
    produce a usable score and continue routing.  Gap analysis fields are
    replaced with a placeholder indicating the degraded state.
    """
    resume_skill_names = {
        s.get("name", "").lower()
        for s in (resume.get("skills") or [])
    }
    jd_skills = [(s.get("name", ""), s.get("is_required", False))
                 for s in (jd.get("skills") or [])]

    if jd_skills:
        matched_total    = sum(1 for name, _ in jd_skills if name.lower() in resume_skill_names)
        skill_score      = matched_total / len(jd_skills) * 100.0
    else:
        skill_score = 50.0

    jd_keywords   = {k.lower() for k in (jd.get("keywords") or [])}
    resume_text   = (resume.get("summary") or "").lower()
    if jd_keywords:
        matched_kw    = sum(1 for k in jd_keywords if k in resume_text or k in resume_skill_names)
        keyword_score = matched_kw / len(jd_keywords) * 100.0
    else:
        keyword_score = 50.0

    experience_score = 50.0  # neutral — can't compute without Claude
    overall_score    = round(skill_score * 0.5 + keyword_score * 0.3 + experience_score * 0.2, 1)

    return {
        "overall_score":    overall_score,
        "skill_score":      round(skill_score,    1),
        "experience_score": experience_score,
        "keyword_score":    round(keyword_score,  1),
        "gap_analysis": {
            "error":                   "Gap analysis unavailable",
            "missing_required_skills": [],
            "improvement_suggestions": [
                "Gap analysis temporarily unavailable — resume retry or manual review recommended.",
            ],
        },
        "status": "degraded",
    }


# =============================================================================
# Error handler node
# =============================================================================

def error_handler_node(state: JobHelperState) -> dict:
    """
    Terminal error node.

    Logs the error stored in state["error"] and sets current_step="error".
    The graph routes here whenever any upstream node sets state["error"].
    After this node the workflow transitions to END.
    """
    error_msg = state.get("error") or "unknown error"
    logger.error("[workflow] error_handler_node: %s", error_msg)
    return {"current_step": "error", "workflow_status": "failed"}


# =============================================================================
# Real agent nodes
# =============================================================================

def parse_resume_node(state: JobHelperState) -> dict:
    """Call ResumeAgent to parse the uploaded file into a structured dict."""
    file_path = state.get("resume_file_path")
    if not file_path:
        msg = "parse_resume_node: resume_file_path is not set in state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("resume_agent", msg)],
        }

    try:
        agent = ResumeAgent()
        parsed_resume, agent_run = agent.parse(file_path)
        return {
            "current_step":    "parsing_resume",
            "resume":          parsed_resume.model_dump(),
            "resume_raw_text": parsed_resume.raw_text,
            "agent_runs":      state.get("agent_runs", []) + [agent_run],
            "error":           None,
        }
    except Exception as exc:
        msg = f"parse_resume_node failed: {exc}"
        logger.error("[workflow] %s", msg, exc_info=True)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("resume_agent", msg)],
        }


def parse_jd_node(state: JobHelperState) -> dict:
    """Call JDAgent to parse the JD text (or URL) into a structured dict."""
    jd_text = state.get("jd_text")
    if not jd_text:
        msg = "parse_jd_node: jd_text is not set in state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("jd_agent", msg)],
        }

    try:
        agent = JDAgent()
        parsed_jd, agent_run = agent.parse(jd_text)
        return {
            "current_step": "parsing_jd",
            "jd":           parsed_jd.model_dump(),
            "agent_runs":   state.get("agent_runs", []) + [agent_run],
            "error":        None,
        }
    except Exception as exc:
        msg = f"parse_jd_node failed: {exc}"
        logger.error("[workflow] %s", msg, exc_info=True)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("jd_agent", msg)],
        }


def match_node(state: JobHelperState) -> dict:
    """Reconstruct Pydantic models from state dicts and call MatchAgent."""
    if not state.get("resume"):
        msg = "match_node: resume is missing from state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("match_agent", msg)],
        }
    if not state.get("jd"):
        msg = "match_node: jd is missing from state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("match_agent", msg)],
        }

    try:
        resume = ParsedResume.model_validate(state["resume"])
        jd     = ParsedJobDescription.model_validate(state["jd"])

        agent = MatchAgent()
        match_result, agent_run = agent.match(resume, jd)
        return {
            "current_step":   "matching",
            "match_result":   match_result.model_dump(),
            "agent_runs":     state.get("agent_runs", []) + [agent_run],
            "error":          None,
            "workflow_status": "running",
        }
    except Exception as exc:
        # --- degraded mode: fall back to pure-Python scoring ---
        logger.warning(
            "[workflow] match_node full match failed, trying degraded mode: %s", exc,
        )
        try:
            degraded_result = _compute_degraded_match_result(state["resume"], state["jd"])
            degraded_run    = _failed_agent_run("match_agent", f"degraded mode — gap analysis failed: {exc}")
            logger.info("[workflow] match_node degraded mode succeeded (overall_score=%.1f)",
                        degraded_result.get("overall_score", 0))
            return {
                "current_step":   "matching",
                "match_result":   degraded_result,
                "agent_runs":     state.get("agent_runs", []) + [degraded_run],
                "error":          None,
                "workflow_status": "degraded",
            }
        except Exception as deg_exc:
            msg = f"match_node failed (including degraded fallback): {exc} / {deg_exc}"
            logger.error("[workflow] %s", msg, exc_info=True)
            return {
                "current_step": "error",
                "error":        msg,
                "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("match_agent", msg)],
            }


_MAX_REWRITE_COUNT = 2


# =============================================================================
# Rewrite node (Phase 4)
# =============================================================================

def rewrite_node(state: JobHelperState) -> dict:
    """
    Call RewriteAgent to rewrite resume bullets to better match the JD.

    Reads resume, jd, and match_result from state; reconstructs Pydantic models;
    calls RewriteAgent.rewrite(); stores the result in state["rewrite_result"].
    Increments rewrite_count so after_rewrite_router can enforce the loop cap.
    """
    if not state.get("resume"):
        msg = "rewrite_node: resume is missing from state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("rewrite_agent", msg)],
        }
    if not state.get("jd"):
        msg = "rewrite_node: jd is missing from state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("rewrite_agent", msg)],
        }
    if not state.get("match_result"):
        msg = "rewrite_node: match_result is missing from state"
        logger.error("[workflow] %s", msg)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("rewrite_agent", msg)],
        }

    try:
        resume      = ParsedResume.model_validate(state["resume"])
        jd          = ParsedJobDescription.model_validate(state["jd"])
        match_result = state["match_result"]

        agent = RewriteAgent()
        rewrite_result, agent_run = agent.rewrite(resume, jd, match_result)

        rewrite_count = state.get("rewrite_count", 0) + 1
        return {
            "current_step":   "rewriting",
            "rewrite_result": rewrite_result.model_dump(),
            "rewrite_count":  rewrite_count,
            "agent_runs":     state.get("agent_runs", []) + [agent_run],
            "error":          None,
        }
    except Exception as exc:
        msg = f"rewrite_node failed: {exc}"
        logger.error("[workflow] %s", msg, exc_info=True)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("rewrite_agent", msg)],
        }


def interview_node(state: JobHelperState) -> dict:
    """Placeholder — InterviewAgent wired in Phase 5."""
    return {"current_step": "interviewing"}


def review_node(state: JobHelperState) -> dict:
    """Placeholder — CoachAgent wired in Phase 5."""
    # Preserve "degraded" if match ran in degraded mode; otherwise mark completed.
    status = state.get("workflow_status", "running")
    return {
        "current_step":   "reviewing",
        "workflow_status": "completed" if status != "degraded" else "degraded",
    }


# =============================================================================
# Routing functions
# =============================================================================

def _check_error(next_node: str):
    """
    Factory that returns a routing function for a specific next_node.

    The returned function checks state["error"]:
      - error present → "error_handler"
      - no error      → next_node (the normal successor)
    """
    def _router(state: JobHelperState) -> str:
        if state.get("error"):
            return "error_handler"
        return next_node
    _router.__name__ = f"check_error_then_{next_node}"
    return _router


def after_match_router(state: JobHelperState) -> str:
    """
    Route based on overall match score (called only when match_node succeeded):
      < 70  → rewrite  (improve the resume before practising interviews)
      >= 70 → interview (score strong enough, move to mock interview)

    Also respects rewrite_count: if we have already rewritten the maximum number
    of times, skip directly to interview regardless of score.

    The error guard below is never reached in the real graph (because _check_error
    intercepts errors before this function is called), but it preserves correct
    behaviour when after_match_router is called directly in tests.
    """
    if state.get("current_step") == "error":
        return END

    if state.get("rewrite_count", 0) >= _MAX_REWRITE_COUNT:
        return "interview"

    score = (state.get("match_result") or {}).get("overall_score", 0)
    return "rewrite" if score < 70 else "interview"


def after_rewrite_router(state: JobHelperState) -> str:
    """
    Route after rewrite_node:
      - error in state      → error_handler
      - rewrite_count >= 2  → interview  (loop cap reached)
      - re-match score >= 70 → interview
      - otherwise           → match  (re-score the rewritten resume)

    In the real graph the rewrite→match→after_match_router chain handles the
    re-score loop. This router exits the loop early when the cap is reached or
    the rewrite already produced a good enough result based on the *previous*
    match score (avoids an extra Claude call when unnecessary).
    """
    if state.get("error"):
        return "error_handler"

    rewrite_count = state.get("rewrite_count", 0)
    if rewrite_count >= _MAX_REWRITE_COUNT:
        logger.info(
            "[workflow] after_rewrite_router: rewrite_count=%d >= max=%d, routing to interview",
            rewrite_count, _MAX_REWRITE_COUNT,
        )
        return "interview"

    # Route back to match for re-scoring; after_match_router will pick the next step.
    return "match"


# =============================================================================
# Single-node mini-graphs (parse-only pipelines)
# =============================================================================
# These compile separate single-node graphs so callers can run just the resume
# or JD parsing step without invoking the full pipeline.  Using dedicated
# mini-graphs (rather than interrupting the main graph) keeps each function
# self-contained and trivially testable.
# =============================================================================

def _build_parse_resume_graph() -> StateGraph:
    b = StateGraph(JobHelperState)
    b.add_node("parse_resume", retry_node(parse_resume_node))
    b.add_edge(START, "parse_resume")
    b.add_edge("parse_resume", END)
    return b

def _build_parse_jd_graph() -> StateGraph:
    b = StateGraph(JobHelperState)
    b.add_node("parse_jd", retry_node(parse_jd_node))
    b.add_edge(START, "parse_jd")
    b.add_edge("parse_jd", END)
    return b


_parse_resume_graph = _build_parse_resume_graph().compile()
_parse_jd_graph     = _build_parse_jd_graph().compile()


def _empty_state(user_id: str) -> JobHelperState:
    """Minimal blank initial state."""
    return {
        "user_id":            user_id,
        "resume_file_path":   None,
        "jd_text":            None,
        "resume":             None,
        "resume_raw_text":    None,
        "jd":                 None,
        "match_result":       None,
        "rewrite_result":     None,
        "rewrite_count":      0,
        "rewrite_history":    [],
        "interview_messages": [],
        "interview_review":   None,
        "current_step":       "idle",
        "error":              None,
        "retry_counts":       {},
        "workflow_status":    "running",
        "agent_runs":         [],
    }


def run_parse_resume(
    file_path: str,
    user_id: str = "default",
) -> tuple[dict | None, list[dict]]:
    """
    Run only the resume-parsing step and return its output.

    Invokes a dedicated single-node graph (not the full pipeline) so the
    caller gets structured output without triggering JD parsing or matching.

    Args:
        file_path: Absolute path to the resume file (.pdf or .docx).
        user_id:   Caller's user ID (stored in state for observability).

    Returns:
        (parsed_resume_dict, agent_runs_list)

        parsed_resume_dict is None when parsing fails; in that case
        agent_runs_list contains a single entry with status="error".
    """
    initial = _empty_state(user_id)
    initial["resume_file_path"] = file_path

    final = _parse_resume_graph.invoke(initial)

    return final.get("resume"), final.get("agent_runs", [])


def run_parse_jd(
    jd_text: str,
    user_id: str = "default",
) -> tuple[dict | None, list[dict]]:
    """
    Run only the JD-parsing step and return its output.

    Args:
        jd_text: Raw job-description text or a public HTTP/HTTPS URL.
        user_id: Caller's user ID.

    Returns:
        (parsed_jd_dict, agent_runs_list)

        parsed_jd_dict is None when parsing fails; in that case
        agent_runs_list contains a single entry with status="error".
    """
    initial = _empty_state(user_id)
    initial["jd_text"] = jd_text

    final = _parse_jd_graph.invoke(initial)

    return final.get("jd"), final.get("agent_runs", [])


def run_full_pipeline(
    resume_file_path: str,
    jd_text: str,
    user_id: str = "default",
    thread_id: Optional[str] = None,
) -> dict:
    """
    Run the complete workflow: parse_resume → parse_jd → match → route.

    With the current placeholder nodes, the graph ends after the routing
    decision (rewrite or interview placeholders run and fall through to END).
    When Phase 4/5 agents are wired in, those phases run automatically.

    Args:
        resume_file_path: Absolute path to the resume file (.pdf or .docx).
        jd_text:          Raw JD text or a public HTTP/HTTPS URL.
        user_id:          Caller's user ID; used as the default thread_id.
        thread_id:        Explicit checkpoint thread ID. Defaults to user_id.

    Returns:
        Final JobHelperState dict.  Check state["error"] to detect failures;
        it will be None on success and contain the error message on failure.
    """
    return run_workflow(
        user_id=user_id,
        resume_file_path=resume_file_path,
        jd_text=jd_text,
        thread_id=thread_id,
    )


# =============================================================================
# Graph construction — compiled once at module level with MemorySaver
# =============================================================================

_checkpointer = MemorySaver()


def _build_graph() -> StateGraph:
    builder = StateGraph(JobHelperState)

    # --- nodes ---
    builder.add_node("parse_resume",  retry_node(parse_resume_node))
    builder.add_node("parse_jd",      retry_node(parse_jd_node))
    builder.add_node("match",         retry_node(match_node))
    builder.add_node("rewrite",       rewrite_node)
    builder.add_node("interview",     interview_node)
    builder.add_node("review",        review_node)
    builder.add_node("error_handler", error_handler_node)

    # --- entry ---
    builder.add_edge(START, "parse_resume")

    # --- parse_resume → (error_handler | parse_jd) ---
    builder.add_conditional_edges(
        "parse_resume",
        _check_error("parse_jd"),
        {"error_handler": "error_handler", "parse_jd": "parse_jd"},
    )

    # --- parse_jd → (error_handler | match) ---
    builder.add_conditional_edges(
        "parse_jd",
        _check_error("match"),
        {"error_handler": "error_handler", "match": "match"},
    )

    # --- match → (error_handler | after_match_router) ---
    builder.add_conditional_edges(
        "match",
        _check_error("__after_match__"),
        {"error_handler": "error_handler", "__after_match__": "__after_match__"},
    )

    # hidden passthrough node to keep routing logic separate
    builder.add_node("__after_match__", lambda s: {})
    builder.add_conditional_edges(
        "__after_match__",
        after_match_router,
        {"rewrite": "rewrite", "interview": "interview"},
    )

    # --- rewrite: conditional exit from loop ---
    builder.add_conditional_edges(
        "rewrite",
        after_rewrite_router,
        {"match": "match", "interview": "interview", "error_handler": "error_handler"},
    )

    # --- interview path ---
    builder.add_edge("interview",     "review")
    builder.add_edge("review",        END)

    # --- error handler exits ---
    builder.add_edge("error_handler", END)

    return builder


workflow_graph = _build_graph().compile(checkpointer=_checkpointer)


# =============================================================================
# Public helpers
# =============================================================================

def _make_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def run_workflow(
    user_id: str,
    resume_file_path: Optional[str] = None,
    jd_text: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> dict:
    """
    Invoke the workflow graph and return the final state.

    Args:
        user_id:          Caller's user ID. Also used as the thread_id default.
        resume_file_path: Absolute path to the resume file (.pdf or .docx).
        jd_text:          Raw JD text or a public URL to a job posting.
        thread_id:        Checkpoint thread identifier. Defaults to user_id.
                          Pass a unique ID per run to keep separate histories.

    Returns:
        Final JobHelperState as a plain dict.
    """
    tid = thread_id or user_id
    config = _make_config(tid)

    initial_state: JobHelperState = {
        "user_id":            user_id,
        "resume_file_path":   resume_file_path,
        "jd_text":            jd_text,
        "resume":             None,
        "resume_raw_text":    None,
        "jd":                 None,
        "match_result":       None,
        "rewrite_result":     None,
        "rewrite_count":      0,
        "rewrite_history":    [],
        "interview_messages": [],
        "interview_review":   None,
        "current_step":       "idle",
        "error":              None,
        "retry_counts":       {},
        "workflow_status":    "running",
        "agent_runs":         [],
    }

    return workflow_graph.invoke(initial_state, config=config)


def get_workflow_state(thread_id: str) -> dict:
    """
    Return the most recent persisted state for the given thread_id.

    Useful for polling progress or resuming an interrupted workflow.
    Returns a dict with keys: values, next, metadata, created_at.
    """
    config = _make_config(thread_id)
    snapshot = workflow_graph.get_state(config)
    return {
        "values":     snapshot.values,
        "next":       list(snapshot.next),
        "metadata":   snapshot.metadata,
        "created_at": snapshot.created_at,
    }


# =============================================================================
# Main block — smoke test + error-path demo
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) >= 3:
        # Real-agent run
        print("=" * 60)
        print("Real-agent run")
        print("=" * 60)
        final = run_workflow(
            user_id=         "demo-user",
            resume_file_path=sys.argv[1],
            jd_text=         sys.argv[2],
            thread_id=       "demo-thread-real",
        )
        if final.get("error"):
            print(f"ERROR: {final['error']}")
            sys.exit(1)
        match = final.get("match_result") or {}
        print(f"  current_step  : {final['current_step']}")
        print(f"  overall_score : {match.get('overall_score')}")
        print(f"  agent_runs    : {len(final.get('agent_runs', []))} logged")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Happy-path demo (pre-built state, real MatchAgent)
    # ------------------------------------------------------------------
    from app.models.job_description import JDSkillRequirement
    from app.models.resume import ResumeContact, ResumeSkill

    demo_resume = ParsedResume(
        contact=ResumeContact(name="Alex Demo", email="alex@example.com"),
        skills=[
            ResumeSkill(name="Python",     category="language"),
            ResumeSkill(name="FastAPI",    category="framework"),
            ResumeSkill(name="PostgreSQL", category="database"),
        ],
        raw_text="Python FastAPI PostgreSQL Docker REST API",
        parse_confidence=0.90,
    )
    demo_jd = ParsedJobDescription(
        title="Backend Engineer",
        company="Demo Corp",
        skills=[
            JDSkillRequirement(name="Python",  is_required=True,  category="language"),
            JDSkillRequirement(name="FastAPI", is_required=True,  category="framework"),
            JDSkillRequirement(name="Docker",  is_required=False, category="tool"),
        ],
        keywords=["Python", "FastAPI", "REST API"],
        min_years_experience=1,
        raw_text="Backend Engineer Python FastAPI Docker REST API",
        parse_confidence=0.92,
    )

    pre_built: JobHelperState = {
        "user_id":            "demo-user",
        "resume_file_path":   None,
        "jd_text":            None,
        "resume":             demo_resume.model_dump(),
        "resume_raw_text":    demo_resume.raw_text,
        "jd":                 demo_jd.model_dump(),
        "match_result":       None,
        "rewrite_result":     None,
        "rewrite_count":      0,
        "rewrite_history":    [],
        "interview_messages": [],
        "interview_review":   None,
        "current_step":       "parsing_jd",
        "error":              None,
        "retry_counts":       {},
        "workflow_status":    "running",
        "agent_runs":         [],
    }

    print("=" * 60)
    print("[1] Happy-path run (real MatchAgent + placeholder nodes)")
    print("    (uses update_state to inject pre-parsed resume+jd, skipping parse nodes)")
    print("=" * 60)
    THREAD_HAPPY = "demo-happy"
    cfg_happy = _make_config(THREAD_HAPPY)
    # Inject state as if parse_jd just finished successfully.
    # as_node="parse_jd" tells LangGraph that parse_jd was the last node to run,
    # so the graph will resume from the conditional edge that follows it (→ match).
    workflow_graph.update_state(cfg_happy, pre_built, as_node="parse_jd")
    final_state = workflow_graph.invoke(None, config=cfg_happy)
    match_r = final_state.get("match_result") or {}
    print(f"    current_step  : {final_state['current_step']}")
    print(f"    overall_score : {match_r.get('overall_score')}")
    print(f"    agent_runs    : {len(final_state.get('agent_runs', []))} logged")

    # ------------------------------------------------------------------
    # Error-path demo — missing resume_file_path triggers error_handler
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("[2] Error-path run (no resume_file_path → error_handler_node)")
    print("=" * 60)
    THREAD_ERR = "demo-error"
    error_state = run_workflow(user_id="demo-user", jd_text="some JD text", thread_id=THREAD_ERR)
    print(f"    current_step  : {error_state['current_step']}")
    print(f"    error         : {error_state['error']}")
    print(f"    agent_runs    : {len(error_state.get('agent_runs', []))} (failed run logged)")

    snap_err = get_workflow_state(THREAD_ERR)
    print(f"    checkpoint    : step={snap_err['metadata'].get('step')}, next={snap_err['next']}")

    # ------------------------------------------------------------------
    # Mermaid
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Mermaid diagram")
    print("=" * 60)
    print(workflow_graph.get_graph().draw_mermaid())
