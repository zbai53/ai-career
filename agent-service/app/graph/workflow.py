"""
LangGraph workflow for the AI Career assistant.

Nodes are placeholders — they update `current_step` and return state unchanged.
Real agent calls will replace the bodies in Phase 5.

Run from agent-service/:
    PYTHONPATH=. python app/graph/workflow.py
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.state import JobHelperState


# =============================================================================
# Placeholder node functions
# =============================================================================

def parse_resume_node(state: JobHelperState) -> dict:
    print(f"  [node] parse_resume_node  (was: {state['current_step']})")
    return {"current_step": "parsing_resume"}


def parse_jd_node(state: JobHelperState) -> dict:
    print(f"  [node] parse_jd_node      (was: {state['current_step']})")
    return {"current_step": "parsing_jd"}


def match_node(state: JobHelperState) -> dict:
    print(f"  [node] match_node         (was: {state['current_step']})")
    # Placeholder: inject a synthetic match_result so the router has data.
    # Real MatchAgent output replaces this in Phase 5.
    match_result = state.get("match_result") or {"overall_score": 55}
    return {"current_step": "matching", "match_result": match_result}


def rewrite_node(state: JobHelperState) -> dict:
    print(f"  [node] rewrite_node       (was: {state['current_step']})")
    # After a placeholder rewrite, bump the score above 70 so the next
    # match pass routes to interview instead of looping forever.
    updated_match = dict(state.get("match_result") or {})
    updated_match["overall_score"] = 75
    return {"current_step": "rewriting", "match_result": updated_match}


def interview_node(state: JobHelperState) -> dict:
    print(f"  [node] interview_node     (was: {state['current_step']})")
    return {"current_step": "interviewing"}


def review_node(state: JobHelperState) -> dict:
    print(f"  [node] review_node        (was: {state['current_step']})")
    return {"current_step": "reviewing"}


# =============================================================================
# Routing function
# =============================================================================

def after_match_router(state: JobHelperState) -> str:
    """
    Route based on overall match score:
      < 70  → rewrite (improve the resume before practising interviews)
      >= 70 → interview (score is strong enough, move to mock interview)
    """
    score = (state.get("match_result") or {}).get("overall_score", 0)
    destination = "rewrite" if score < 70 else "interview"
    print(f"  [router] after_match_router: score={score} → {destination}")
    return destination


# =============================================================================
# Graph construction
# =============================================================================

def _build_graph() -> StateGraph:
    builder = StateGraph(JobHelperState)

    # Nodes
    builder.add_node("parse_resume", parse_resume_node)
    builder.add_node("parse_jd",     parse_jd_node)
    builder.add_node("match",        match_node)
    builder.add_node("rewrite",      rewrite_node)
    builder.add_node("interview",    interview_node)
    builder.add_node("review",       review_node)

    # Linear entry path
    builder.add_edge(START,          "parse_resume")
    builder.add_edge("parse_resume", "parse_jd")
    builder.add_edge("parse_jd",     "match")

    # Conditional branch after matching
    builder.add_conditional_edges(
        "match",
        after_match_router,
        {"rewrite": "rewrite", "interview": "interview"},
    )

    # Rewrite loops back to match for re-scoring
    builder.add_edge("rewrite", "match")

    # Interview path to coach review then done
    builder.add_edge("interview", "review")
    builder.add_edge("review",    END)

    return builder


workflow_graph = _build_graph().compile()


# =============================================================================
# Main block — demo run + Mermaid export
# =============================================================================

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Run 1: low initial score (55) → triggers rewrite loop → interview
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Demo run — initial score=55 (expect rewrite loop)")
    print("=" * 60)

    initial_state: JobHelperState = {
        "user_id":            "test",
        "resume":             None,
        "resume_raw_text":    None,
        "jd":                 None,
        "match_result":       {"overall_score": 55},
        "rewrite_history":    [],
        "interview_messages": [],
        "interview_review":   None,
        "current_step":       "idle",
        "error":              None,
        "agent_runs":         [],
    }

    result = workflow_graph.invoke(initial_state)
    print(f"\nFinal current_step : {result['current_step']}")
    print(f"Final match score  : {result['match_result']['overall_score']}")

    # ------------------------------------------------------------------
    # Run 2: high initial score (80) → skips rewrite, goes to interview
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Demo run — initial score=80 (expect skip rewrite)")
    print("=" * 60)

    high_score_state: JobHelperState = {**initial_state, "match_result": {"overall_score": 80}}
    result2 = workflow_graph.invoke(high_score_state)
    print(f"\nFinal current_step : {result2['current_step']}")
    print(f"Final match score  : {result2['match_result']['overall_score']}")

    # ------------------------------------------------------------------
    # Mermaid diagram
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Mermaid diagram")
    print("=" * 60)
    print(workflow_graph.get_graph().draw_mermaid())
