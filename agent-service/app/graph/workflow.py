"""
LangGraph workflow for the AI Career assistant.

parse_resume_node, parse_jd_node, and match_node call real agents.
rewrite_node, interview_node, and review_node remain placeholders for Phase 4/5.

The graph is compiled with a MemorySaver checkpointer, so any run can be
inspected or resumed via a thread_id.

Run from agent-service/ (no real files needed — uses placeholder nodes):
    PYTHONPATH=. python app/graph/workflow.py

Run with real agents (requires ANTHROPIC_API_KEY and an actual resume file):
    ANTHROPIC_API_KEY=<key> PYTHONPATH=. python app/graph/workflow.py <resume.pdf> "<jd text>"
"""

from __future__ import annotations

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


# =============================================================================
# Real agent nodes
# =============================================================================

def parse_resume_node(state: JobHelperState) -> dict:
    """Call ResumeAgent to parse the uploaded file into a structured dict."""
    file_path = state.get("resume_file_path")
    if not file_path:
        return {"current_step": "error", "error": "resume_file_path is not set in state"}

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
        return {"current_step": "error", "error": f"parse_resume_node failed: {exc}"}


def parse_jd_node(state: JobHelperState) -> dict:
    """Call JDAgent to parse the JD text (or URL) into a structured dict."""
    jd_text = state.get("jd_text")
    if not jd_text:
        return {"current_step": "error", "error": "jd_text is not set in state"}

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
        return {"current_step": "error", "error": f"parse_jd_node failed: {exc}"}


def match_node(state: JobHelperState) -> dict:
    """Reconstruct Pydantic models from state dicts and call MatchAgent."""
    if not state.get("resume"):
        return {"current_step": "error", "error": "match_node: resume is missing from state"}
    if not state.get("jd"):
        return {"current_step": "error", "error": "match_node: jd is missing from state"}

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
        return {"current_step": "error", "error": f"match_node failed: {exc}"}


# =============================================================================
# Placeholder nodes (Phase 4 / Phase 5)
# =============================================================================

def rewrite_node(state: JobHelperState) -> dict:
    """Placeholder — RewriteAgent wired in Phase 4."""
    # Simulate a post-rewrite score improvement so the re-match routes to interview.
    updated_match = dict(state.get("match_result") or {})
    updated_match["overall_score"] = 75
    return {"current_step": "rewriting", "match_result": updated_match}


def interview_node(state: JobHelperState) -> dict:
    """Placeholder — InterviewAgent wired in Phase 5."""
    return {"current_step": "interviewing"}


def review_node(state: JobHelperState) -> dict:
    """Placeholder — CoachAgent wired in Phase 5."""
    return {"current_step": "reviewing"}


# =============================================================================
# Routing function
# =============================================================================

def after_match_router(state: JobHelperState) -> str:
    """
    Route based on overall match score:
      < 70  → rewrite  (improve the resume before practising interviews)
      >= 70 → interview (score strong enough, move to mock interview)

    Error state always exits to END so the graph terminates cleanly.
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

    builder.add_node("parse_resume", parse_resume_node)
    builder.add_node("parse_jd",     parse_jd_node)
    builder.add_node("match",        match_node)
    builder.add_node("rewrite",      rewrite_node)
    builder.add_node("interview",    interview_node)
    builder.add_node("review",       review_node)

    builder.add_edge(START,          "parse_resume")
    builder.add_edge("parse_resume", "parse_jd")
    builder.add_edge("parse_jd",     "match")

    builder.add_conditional_edges(
        "match",
        after_match_router,
        {"rewrite": "rewrite", "interview": "interview", END: END},
    )

    builder.add_edge("rewrite",   "match")
    builder.add_edge("interview", "review")
    builder.add_edge("review",    END)

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
# Main block — checkpoint demo (no real files required)
# =============================================================================

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # If a resume file and JD text are passed, run with real agents.
    # Otherwise, demonstrate checkpointing with placeholder-only flow.
    # ------------------------------------------------------------------
    if len(sys.argv) >= 3:
        # Real-agent run
        print("=" * 60)
        print("Real-agent run")
        print("=" * 60)
        final = run_workflow(
            user_id=          "demo-user",
            resume_file_path= sys.argv[1],
            jd_text=          sys.argv[2],
            thread_id=        "demo-thread-real",
        )
        if final.get("error"):
            print(f"ERROR: {final['error']}")
            sys.exit(1)
        match = final.get("match_result") or {}
        print(f"  current_step    : {final['current_step']}")
        print(f"  overall_score   : {match.get('overall_score')}")
        print(f"  agent_runs      : {len(final.get('agent_runs', []))} logged")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Checkpoint demo — placeholder nodes, no API key needed
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Checkpoint demo — placeholder nodes")
    print("=" * 60)

    # Run 1: inject pre-parsed data directly so placeholder match_node
    # has something to work with (simulates state after real parsing).
    from app.models.resume import ResumeContact, ResumeSkill
    from app.models.job_description import JDSkillRequirement

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

    THREAD_ID = "demo-checkpoint-thread"
    config    = _make_config(THREAD_ID)

    # Directly invoke graph with pre-built state (bypasses parse nodes)
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
        "current_step":       "parsing_jd",   # pretend parsing is done
        "error":              None,
        "agent_runs":         [],
    }

    print("\n[1] Running workflow with real MatchAgent + placeholder rewrite/interview/review …")
    final_state = workflow_graph.invoke(pre_built, config=config)

    print(f"\n    current_step  : {final_state['current_step']}")
    match_r = final_state.get("match_result") or {}
    print(f"    overall_score : {match_r.get('overall_score')}")
    print(f"    skill_score   : {match_r.get('skill_score')}")
    print(f"    agent_runs    : {len(final_state.get('agent_runs', []))} logged")

    # ------------------------------------------------------------------
    # Inspect checkpoint
    # ------------------------------------------------------------------
    print("\n[2] Reading checkpoint via get_workflow_state() …")
    snap = get_workflow_state(THREAD_ID)
    print(f"    thread_id     : {THREAD_ID}")
    print(f"    current_step  : {snap['values'].get('current_step')}")
    print(f"    next nodes    : {snap['next']} (empty = workflow complete)")
    print(f"    checkpoint at : {snap['created_at']}")
    print(f"    step count    : {snap['metadata'].get('step')}")

    # ------------------------------------------------------------------
    # Second thread — demonstrates independent checkpoint namespacing
    # ------------------------------------------------------------------
    print("\n[3] Running a second independent thread to show namespace isolation …")
    THREAD_ID_2 = "demo-checkpoint-thread-2"
    config2     = _make_config(THREAD_ID_2)

    pre_built_2 = dict(pre_built)
    pre_built_2["match_result"] = {"overall_score": 85}   # already high score
    final_state_2 = workflow_graph.invoke(pre_built_2, config=config2)

    snap2 = get_workflow_state(THREAD_ID_2)
    print(f"    thread 1 step : {get_workflow_state(THREAD_ID)['values'].get('current_step')}")
    print(f"    thread 2 step : {snap2['values'].get('current_step')}")
    print("    (each thread maintains its own independent checkpoint history)")

    # ------------------------------------------------------------------
    # Mermaid
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Mermaid diagram")
    print("=" * 60)
    print(workflow_graph.get_graph().draw_mermaid())
