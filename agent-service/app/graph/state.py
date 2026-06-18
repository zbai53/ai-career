"""
LangGraph state definition for the AI Career workflow.

JobHelperState flows through every node in the graph. Nodes read what they
need and return a partial dict with only the keys they modify — LangGraph
merges the partial update into the full state automatically.

Lifecycle of each field:

  user_id
      Set at graph entry (by the FastAPI endpoint before invoking the graph).
      Never modified by nodes. Used by service calls that need to scope DB
      writes to a specific user.

  resume
      Populated by the resume-parsing node (ResumeAgent.parse → ParsedResume
      serialised to dict via .model_dump()). Read by the matching node and the
      rewriting node. None until parsing succeeds.

  resume_raw_text
      The untruncated raw text extracted from the uploaded file, stored
      separately so the rewriting node can diff the original against any
      rewritten version without going through the structured resume dict.
      Populated at the same time as `resume`.

  jd
      Populated by the JD-parsing node (JDAgent.parse_text / parse_url →
      ParsedJobDescription serialised to dict). Read by the matching node,
      rewriting node, and interview node. None until parsing succeeds.

  match_result
      Populated by the matching node (MatchAgent.match → MatchResult
      serialised to dict). Read by the rewriting node (to know what skills are
      missing) and the interview node (to select relevant questions). None
      until matching runs.

  rewrite_history
      Each rewriting attempt appends one dict of the form:
          {"attempt": int, "rewritten_resume": dict, "fidelity_score": float,
           "keyword_coverage": float, "agent_run": dict}
      Starts as an empty list. Multiple attempts accumulate here until the
      fidelity threshold is met or the maximum retries are exhausted.

  interview_messages
      Running conversation log for the mock interview. Each element is a dict:
          {"role": "interviewer" | "candidate", "content": str, "turn": int}
      Appended by the interviewer node (question) and expected to be appended
      by the external caller (candidate answer) before the next turn. Starts
      as an empty list.

  interview_review
      Populated by the coach node after the interview ends. Contains the
      structured evaluation produced by CoachAgent (per-question scores,
      overall assessment, improvement suggestions). None until the interview
      is complete and the coach node has run.

  current_step
      A string label tracking where execution currently is. Updated at the
      start of each major node so the frontend can display progress.
      Valid values:
          "idle"            — graph not yet started
          "parsing_resume"  — ResumeAgent running
          "parsing_jd"      — JDAgent running
          "matching"        — MatchAgent running
          "rewriting"       — RewriteAgent running
          "interviewing"    — InterviewAgent running
          "reviewing"       — CoachAgent running
          "done"            — workflow complete
          "error"           — a node encountered an unrecoverable error

  error
      Holds the error message string from the most recent failed node. Reset
      to None when a subsequent node succeeds. The graph's conditional edges
      check this field to decide whether to route to an error-handling node or
      continue normally.

  agent_runs
      Every agent node appends its agent_run dict (produced by log_agent_run)
      here. The Spring Boot backend persists these to the agent_runs table
      after the graph finishes. Starts as an empty list.

  retry_counts
      Maps node_name → number of retries attempted for that node in the
      current run.  E.g. {"parse_resume_node": 1, "match_node": 2}.
      Updated by the retry_node wrapper; absent keys mean zero retries.
      Starts as an empty dict.

  workflow_status
      High-level status of the overall workflow.  Updated by error_handler
      and by nodes that enter a degraded operating mode.
      Valid values:
          "running"   — workflow is in progress (initial value)
          "completed" — workflow finished successfully
          "degraded"  — completed but with reduced quality (e.g. no gap analysis)
          "failed"    — workflow ended in error_handler_node
"""

from __future__ import annotations

from typing import Optional, TypedDict


class JobHelperState(TypedDict):
    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    user_id: str
    """Caller's user ID. Set at graph entry, never modified by nodes."""

    # -------------------------------------------------------------------------
    # Raw inputs (set by the caller before invoking the graph)
    # -------------------------------------------------------------------------
    resume_file_path: Optional[str]
    """Absolute path to the uploaded resume file (.pdf or .docx).
    Set by the FastAPI endpoint; consumed and cleared after parse_resume_node runs."""

    jd_text: Optional[str]
    """Raw job-description text (or a URL string).
    Set by the FastAPI endpoint; consumed after parse_jd_node runs."""

    # -------------------------------------------------------------------------
    # Parsed inputs
    # -------------------------------------------------------------------------
    resume: Optional[dict]
    """ParsedResume serialised to dict. Populated by the resume-parsing node."""

    resume_raw_text: Optional[str]
    """Full untruncated text extracted from the uploaded file. Populated
    alongside `resume`; kept separate for diff / fidelity checking."""

    jd: Optional[dict]
    """ParsedJobDescription serialised to dict. Populated by the JD-parsing node."""

    # -------------------------------------------------------------------------
    # Agent outputs
    # -------------------------------------------------------------------------
    match_result: Optional[dict]
    """MatchResult serialised to dict. Populated by the matching node."""

    rewrite_history: list[dict]
    """Accumulates one entry per rewriting attempt. Starts empty."""

    interview_messages: list[dict]
    """Running conversation log. Each dict has role, content, and turn keys."""

    interview_review: Optional[dict]
    """Structured coach evaluation. Populated after the interview ends."""

    # -------------------------------------------------------------------------
    # Workflow control
    # -------------------------------------------------------------------------
    current_step: str
    """Current workflow stage label (e.g. "matching", "interviewing", "done")."""

    error: Optional[str]
    """Last error message. None when the most recent node succeeded."""

    # -------------------------------------------------------------------------
    # Retry tracking
    # -------------------------------------------------------------------------
    retry_counts: dict
    """Maps node_name → retry count for the current run. Updated by retry_node."""

    workflow_status: str
    """High-level workflow status: 'running', 'completed', 'degraded', or 'failed'."""

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    agent_runs: list[dict]
    """Accumulated agent_run dicts from every node that called an agent."""
