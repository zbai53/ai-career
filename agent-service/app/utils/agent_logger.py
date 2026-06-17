"""
Lightweight utility for building agent-run log records.

Each call to log_agent_run() returns a plain dict that can be embedded in an
API response or forwarded to the backend for persistence.
"""

from datetime import datetime, timezone


def log_agent_run(
    agent_name: str,
    input_summary: str,
    output_summary: str,
    status: str,
    duration_ms: int,
    token_count: int,
    model_name: str,
    error_message: str | None = None,
) -> dict:
    """
    Build a structured agent-run log record.

    Args:
        agent_name:     Identifier for the agent (e.g. "resume_agent").
        input_summary:  Short description of the input (truncated to 100 chars
                        by convention, but not enforced here).
        output_summary: Short description of what was produced.
        status:         "success" | "error"
        duration_ms:    Wall-clock time the agent took, in milliseconds.
        token_count:    Total tokens consumed (input + output across all LLM
                        calls made during this run).
        model_name:     LLM model identifier (e.g. "claude-haiku-4-5-20251001").
        error_message:  Human-readable error description; None on success.

    Returns:
        dict with all provided fields plus a UTC ISO-8601 ``created_at`` timestamp.
    """
    return {
        "agent_name": agent_name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "status": status,
        "duration_ms": duration_ms,
        "token_count": token_count,
        "model_name": model_name,
        "error_message": error_message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
