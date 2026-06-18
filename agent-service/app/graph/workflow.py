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
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.jd_agent import JDAgent
from app.agents.match_agent import MatchAgent
from app.agents.resume_agent import ResumeAgent
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
    return {"current_step": "error"}


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
            "current_step": "matching",
            "match_result": match_result.model_dump(),
            "agent_runs":   state.get("agent_runs", []) + [agent_run],
            "error":        None,
        }
    except Exception as exc:
        msg = f"match_node failed: {exc}"
        logger.error("[workflow] %s", msg, exc_info=True)
        return {
            "current_step": "error",
            "error":        msg,
            "agent_runs":   state.get("agent_runs", []) + [_failed_agent_run("match_agent", msg)],
        }


# =============================================================================
# Placeholder nodes (Phase 4 / Phase 5)
# =============================================================================

def rewrite_node(state: JobHelperState) -> dict:
    """Placeholder — RewriteAgent wired in Phase 4."""
    updated_match = dict(state.get("match_result") or {})
    updated_match["overall_score"] = 75  # simulate post-rewrite improvement
    return {"current_step": "rewriting", "match_result": updated_match}


def interview_node(state: JobHelperState) -> dict:
    """Placeholder — InterviewAgent wired in Phase 5."""
    return {"current_step": "interviewing"}


def review_node(state: JobHelperState) -> dict:
    """Placeholder — CoachAgent wired in Phase 5."""
    return {"current_step": "reviewing"}


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

    The error guard below is never reached in the real graph (because _check_error
    intercepts errors before this function is called), but it preserves correct
    behaviour when after_match_router is called directly in tests.
    """
    if state.get("current_step") == "error":
        return END

    score = (state.get("match_result") or {}).get("overall_score", 0)
    return "rewrite" if score < 70 else "interview"


# =============================================================================
# Graph construction — compiled once at module level with MemorySaver
# =============================================================================

_checkpointer = MemorySaver()


def _build_graph() -> StateGraph:
    builder = StateGraph(JobHelperState)

    # --- nodes ---
    builder.add_node("parse_resume",  parse_resume_node)
    builder.add_node("parse_jd",      parse_jd_node)
    builder.add_node("match",         match_node)
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

    # --- rewrite loops back to match ---
    builder.add_edge("rewrite",       "match")

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
        "rewrite_history":    [],
        "interview_messages": [],
        "interview_review":   None,
        "current_step":       "idle",
        "error":              None,
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
        "rewrite_history":    [],
        "interview_messages": [],
        "interview_review":   None,
        "current_step":       "parsing_jd",
        "error":              None,
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
