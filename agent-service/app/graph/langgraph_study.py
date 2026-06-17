"""
LangGraph Study File — runnable examples for understanding core concepts.

Run from agent-service/:
    PYTHONPATH=. python app/graph/langgraph_study.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# =============================================================================
# Example 1 — Basic State Graph (linear pipeline)
# =============================================================================
# Demonstrates: StateGraph, node functions, simple linear edge wiring.
# =============================================================================

class LinearState(TypedDict):
    messages: list[str]


def greet(state: LinearState) -> LinearState:
    return {"messages": state["messages"] + ["Hello"]}


def ask(state: LinearState) -> LinearState:
    return {"messages": state["messages"] + ["How are you?"]}


def farewell(state: LinearState) -> LinearState:
    return {"messages": state["messages"] + ["Goodbye"]}


def run_example_1() -> None:
    print("=" * 60)
    print("Example 1 — Basic State Graph (linear pipeline)")
    print("=" * 60)

    builder = StateGraph(LinearState)
    builder.add_node("greet",   greet)
    builder.add_node("ask",     ask)
    builder.add_node("farewell", farewell)

    builder.add_edge(START,      "greet")
    builder.add_edge("greet",    "ask")
    builder.add_edge("ask",      "farewell")
    builder.add_edge("farewell", END)

    graph = builder.compile()
    result = graph.invoke({"messages": []})

    print("Final messages:", result["messages"])
    print()


# =============================================================================
# Example 2 — Conditional Branching
# =============================================================================
# Demonstrates: add_conditional_edges, routing function, branching paths.
# =============================================================================

class BranchState(TypedDict):
    number: int
    result: str


def classify(state: BranchState) -> BranchState:
    label = "big" if state["number"] > 10 else "small"
    return {"number": state["number"], "result": label}


def route_after_classify(state: BranchState) -> str:
    return "process_big" if state["result"] == "big" else "process_small"


def process_big(state: BranchState) -> BranchState:
    return {"number": state["number"], "result": state["result"] + " - processed as big number"}


def process_small(state: BranchState) -> BranchState:
    return {"number": state["number"], "result": state["result"] + " - processed as small number"}


def run_example_2() -> None:
    print("=" * 60)
    print("Example 2 — Conditional Branching")
    print("=" * 60)

    builder = StateGraph(BranchState)
    builder.add_node("classify",      classify)
    builder.add_node("process_big",   process_big)
    builder.add_node("process_small", process_small)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {"process_big": "process_big", "process_small": "process_small"},
    )
    builder.add_edge("process_big",   END)
    builder.add_edge("process_small", END)

    graph = builder.compile()

    for number in (5, 15):
        result = graph.invoke({"number": number, "result": ""})
        print(f"  number={number}  →  result='{result['result']}'")

    print()


# =============================================================================
# Example 3 — Loop (multi-turn conversation simulation)
# =============================================================================
# Demonstrates: cycles, conditional back-edges, turn-based state accumulation.
# =============================================================================

_QUESTIONS = [
    "Tell me about yourself.",
    "What's your greatest strength?",
    "Where do you see yourself in 5 years?",
]

_ANSWERS = [
    "I'm a software engineer with 2 years of experience.",
    "My greatest strength is problem-solving under pressure.",
    "I hope to be leading a small engineering team.",
]


class ConversationState(TypedDict):
    messages: list[str]
    turn_count: int
    max_turns: int


def interviewer(state: ConversationState) -> ConversationState:
    question = _QUESTIONS[state["turn_count"] % len(_QUESTIONS)]
    return {
        "messages":    state["messages"] + [f"[Interviewer] {question}"],
        "turn_count":  state["turn_count"],
        "max_turns":   state["max_turns"],
    }


def candidate(state: ConversationState) -> ConversationState:
    answer = _ANSWERS[state["turn_count"] % len(_ANSWERS)]
    return {
        "messages":   state["messages"] + [f"[Candidate]   {answer}"],
        "turn_count":  state["turn_count"],
        "max_turns":   state["max_turns"],
    }


def evaluate(state: ConversationState) -> ConversationState:
    return {
        "messages":   state["messages"],
        "turn_count":  state["turn_count"] + 1,
        "max_turns":   state["max_turns"],
    }


def route_after_evaluate(state: ConversationState) -> str:
    return "interviewer" if state["turn_count"] < state["max_turns"] else END


def run_example_3() -> None:
    print("=" * 60)
    print("Example 3 — Loop (multi-turn conversation simulation)")
    print("=" * 60)

    builder = StateGraph(ConversationState)
    builder.add_node("interviewer", interviewer)
    builder.add_node("candidate",   candidate)
    builder.add_node("evaluate",    evaluate)

    builder.add_edge(START,          "interviewer")
    builder.add_edge("interviewer",  "candidate")
    builder.add_edge("candidate",    "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"interviewer": "interviewer", END: END},
    )

    graph = builder.compile()
    result = graph.invoke({"messages": [], "turn_count": 0, "max_turns": 3})

    print(f"  Completed {result['turn_count']} turn(s).\n")
    for msg in result["messages"]:
        print(f"  {msg}")
    print()


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    run_example_1()
    run_example_2()
    run_example_3()
