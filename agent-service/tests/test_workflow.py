"""
Tests for the LangGraph workflow node functions and routing logic.

All agent calls are mocked — no real Anthropic API calls are made.

Unit tests (TestParseResumeNode, TestParseJdNode, TestMatchNode, TestAfterMatchRouter)
call node functions directly.

Integration tests (TestWorkflowIntegration) invoke the full compiled graph via
run_workflow() and get_workflow_state(), using unique thread_ids to keep the
module-level MemorySaver checkpoint namespaces isolated between tests.
"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.graph.state import JobHelperState
from app.graph.workflow import (
    after_match_router,
    get_workflow_state,
    match_node,
    parse_jd_node,
    parse_resume_node,
    run_full_pipeline,
    run_parse_jd,
    run_parse_resume,
    run_workflow,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides) -> JobHelperState:
    """Return a minimal valid JobHelperState with sensible defaults."""
    state: JobHelperState = {
        "user_id":            "test-user",
        "resume_file_path":   None,
        "jd_text":            None,
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
    state.update(overrides)
    return state


def _fake_agent_run(agent_name: str = "test_agent") -> dict:
    return {
        "agent_name":    agent_name,
        "input_summary": "test input",
        "output_summary": "test output",
        "status":        "success",
        "duration_ms":   100,
        "token_count":   50,
        "model_name":    "claude-haiku-4-5-20251001",
        "error_message": None,
        "created_at":    "2026-06-18T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# parse_resume_node
# ---------------------------------------------------------------------------

class TestParseResumeNode:
    def test_updates_state_with_parsed_resume(self) -> None:
        """Node must populate state['resume'] and set current_step."""
        fake_resume = MagicMock()
        fake_resume.raw_text = "Jane Doe\njane@example.com"
        fake_resume.model_dump.return_value = {
            "contact": {"name": "Jane Doe", "email": "jane@example.com"},
            "skills": [],
            "experience": [],
        }
        fake_run = _fake_agent_run("resume_agent")

        with patch(
            "app.graph.workflow.ResumeAgent"
        ) as MockAgent:
            MockAgent.return_value.parse.return_value = (fake_resume, fake_run)

            state = _base_state(resume_file_path="/tmp/resume.pdf")
            result = parse_resume_node(state)

        assert result["current_step"] == "parsing_resume"
        assert result["resume"] == fake_resume.model_dump.return_value
        assert result["resume_raw_text"] == "Jane Doe\njane@example.com"
        assert result["error"] is None

    def test_appends_agent_run_to_list(self) -> None:
        """agent_run from ResumeAgent must be appended to existing list."""
        fake_resume = MagicMock()
        fake_resume.raw_text = "text"
        fake_resume.model_dump.return_value = {}
        fake_run = _fake_agent_run("resume_agent")
        existing_run = _fake_agent_run("prior_agent")

        with patch("app.graph.workflow.ResumeAgent") as MockAgent:
            MockAgent.return_value.parse.return_value = (fake_resume, fake_run)

            state = _base_state(
                resume_file_path="/tmp/resume.pdf",
                agent_runs=[existing_run],
            )
            result = parse_resume_node(state)

        assert len(result["agent_runs"]) == 2
        assert result["agent_runs"][0] == existing_run
        assert result["agent_runs"][1] == fake_run

    def test_returns_error_when_file_path_missing(self) -> None:
        """Node must not call ResumeAgent when resume_file_path is None."""
        with patch("app.graph.workflow.ResumeAgent") as MockAgent:
            result = parse_resume_node(_base_state())

        assert result["current_step"] == "error"
        assert result["error"] is not None
        MockAgent.assert_not_called()

    def test_returns_error_on_agent_exception(self) -> None:
        """Any exception from ResumeAgent must be caught and stored in error."""
        with patch("app.graph.workflow.ResumeAgent") as MockAgent:
            MockAgent.return_value.parse.side_effect = RuntimeError("PDF corrupt")

            state = _base_state(resume_file_path="/tmp/bad.pdf")
            result = parse_resume_node(state)

        assert result["current_step"] == "error"
        assert "PDF corrupt" in result["error"]


# ---------------------------------------------------------------------------
# parse_jd_node
# ---------------------------------------------------------------------------

class TestParseJdNode:
    def test_updates_state_with_parsed_jd(self) -> None:
        """Node must populate state['jd'] and set current_step."""
        fake_jd = MagicMock()
        fake_jd.model_dump.return_value = {
            "title": "Backend Engineer",
            "company": "Acme",
            "skills": [],
        }
        fake_run = _fake_agent_run("jd_agent")

        with patch("app.graph.workflow.JDAgent") as MockAgent:
            MockAgent.return_value.parse.return_value = (fake_jd, fake_run)

            state = _base_state(jd_text="We are hiring a backend engineer with Python skills.")
            result = parse_jd_node(state)

        assert result["current_step"] == "parsing_jd"
        assert result["jd"] == fake_jd.model_dump.return_value
        assert result["error"] is None

    def test_appends_agent_run_to_list(self) -> None:
        fake_jd = MagicMock()
        fake_jd.model_dump.return_value = {}
        fake_run = _fake_agent_run("jd_agent")

        with patch("app.graph.workflow.JDAgent") as MockAgent:
            MockAgent.return_value.parse.return_value = (fake_jd, fake_run)

            state = _base_state(jd_text="some jd text", agent_runs=[_fake_agent_run()])
            result = parse_jd_node(state)

        assert len(result["agent_runs"]) == 2

    def test_returns_error_when_jd_text_missing(self) -> None:
        with patch("app.graph.workflow.JDAgent") as MockAgent:
            result = parse_jd_node(_base_state())

        assert result["current_step"] == "error"
        assert result["error"] is not None
        MockAgent.assert_not_called()

    def test_returns_error_on_agent_exception(self) -> None:
        with patch("app.graph.workflow.JDAgent") as MockAgent:
            MockAgent.return_value.parse.side_effect = ValueError("JD too short")

            state = _base_state(jd_text="short")
            result = parse_jd_node(state)

        assert result["current_step"] == "error"
        assert "JD too short" in result["error"]


# ---------------------------------------------------------------------------
# match_node
# ---------------------------------------------------------------------------

class TestMatchNode:
    def _fake_match_result(self, score: float = 72.0) -> MagicMock:
        fake = MagicMock()
        fake.model_dump.return_value = {
            "overall_score":   score,
            "skill_score":     60.0,
            "experience_score": 80.0,
            "keyword_score":   70.0,
            "missing_required_skills": [],
        }
        return fake

    def _minimal_resume_dict(self) -> dict:
        return {
            "contact": {"name": "Jane"},
            "skills": [],
            "experience": [],
            "education": [],
            "projects": [],
            "certifications": [],
            "raw_text": "Jane Doe",
            "parse_confidence": 0.9,
        }

    def _minimal_jd_dict(self) -> dict:
        return {
            "title": "Engineer",
            "company": "Corp",
            "skills": [],
            "keywords": [],
            "raw_text": "Engineer wanted",
            "parse_confidence": 0.9,
        }

    def test_updates_state_with_match_result(self) -> None:
        """Node must populate state['match_result'] and set current_step."""
        fake_result = self._fake_match_result(score=72.0)
        fake_run = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.MatchAgent") as MockAgent:
            MockAgent.return_value.match.return_value = (fake_result, fake_run)

            state = _base_state(
                resume=self._minimal_resume_dict(),
                jd=self._minimal_jd_dict(),
            )
            result = match_node(state)

        assert result["current_step"] == "matching"
        assert result["match_result"]["overall_score"] == 72.0
        assert result["error"] is None

    def test_appends_agent_run_to_list(self) -> None:
        fake_result = self._fake_match_result()
        fake_run = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.MatchAgent") as MockAgent:
            MockAgent.return_value.match.return_value = (fake_result, fake_run)

            prior_run = _fake_agent_run("resume_agent")
            state = _base_state(
                resume=self._minimal_resume_dict(),
                jd=self._minimal_jd_dict(),
                agent_runs=[prior_run],
            )
            result = match_node(state)

        assert len(result["agent_runs"]) == 2
        assert result["agent_runs"][1] == fake_run

    def test_returns_error_when_resume_missing(self) -> None:
        state = _base_state(jd=self._minimal_jd_dict())
        result = match_node(state)

        assert result["current_step"] == "error"
        assert "resume" in result["error"].lower()

    def test_returns_error_when_jd_missing(self) -> None:
        state = _base_state(resume=self._minimal_resume_dict())
        result = match_node(state)

        assert result["current_step"] == "error"
        assert "jd" in result["error"].lower()

    def test_returns_error_on_agent_exception(self) -> None:
        with patch("app.graph.workflow.MatchAgent") as MockAgent:
            MockAgent.return_value.match.side_effect = RuntimeError("LLM timeout")

            state = _base_state(
                resume=self._minimal_resume_dict(),
                jd=self._minimal_jd_dict(),
            )
            result = match_node(state)

        assert result["current_step"] == "error"
        assert "LLM timeout" in result["error"]


# ---------------------------------------------------------------------------
# after_match_router
# ---------------------------------------------------------------------------

class TestAfterMatchRouter:
    def test_low_score_routes_to_rewrite(self) -> None:
        state = _base_state(match_result={"overall_score": 50})
        assert after_match_router(state) == "rewrite"

    def test_score_below_threshold_routes_to_rewrite(self) -> None:
        state = _base_state(match_result={"overall_score": 69.9})
        assert after_match_router(state) == "rewrite"

    def test_high_score_routes_to_interview(self) -> None:
        state = _base_state(match_result={"overall_score": 80})
        assert after_match_router(state) == "interview"

    def test_score_at_threshold_routes_to_interview(self) -> None:
        """Score of exactly 70 should go to interview, not rewrite."""
        state = _base_state(match_result={"overall_score": 70})
        assert after_match_router(state) == "interview"

    def test_error_state_routes_to_end(self) -> None:
        from langgraph.graph import END
        state = _base_state(current_step="error", match_result={"overall_score": 90})
        assert after_match_router(state) == END

    def test_missing_match_result_defaults_to_rewrite(self) -> None:
        """No match_result → score defaults to 0 → rewrite."""
        state = _base_state(match_result=None)
        assert after_match_router(state) == "rewrite"


# ---------------------------------------------------------------------------
# Integration helpers
# ---------------------------------------------------------------------------

def _unique_thread() -> str:
    """Return a unique thread_id so MemorySaver namespaces never collide."""
    return f"test-{uuid.uuid4().hex}"


def _fake_resume_model(score: float = 80.0) -> MagicMock:
    """Fake ParsedResume returned by a mocked ResumeAgent.parse()."""
    m = MagicMock()
    m.raw_text = "Jane Doe\njane@example.com\nPython FastAPI"
    m.model_dump.return_value = {
        "contact": {"name": "Jane Doe", "email": "jane@example.com"},
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "raw_text": "Jane Doe\njane@example.com\nPython FastAPI",
        "parse_confidence": 0.9,
    }
    return m


def _fake_jd_model() -> MagicMock:
    """Fake ParsedJobDescription returned by a mocked JDAgent.parse()."""
    m = MagicMock()
    m.model_dump.return_value = {
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "skills": [],
        "keywords": [],
        "raw_text": "Backend Engineer Python FastAPI",
        "parse_confidence": 0.9,
    }
    return m


def _fake_match_model(overall_score: float = 80.0) -> MagicMock:
    """Fake MatchResult returned by a mocked MatchAgent.match()."""
    m = MagicMock()
    m.model_dump.return_value = {
        "overall_score":          overall_score,
        "skill_score":            75.0,
        "experience_score":       80.0,
        "keyword_score":          85.0,
        "missing_required_skills": [],
        "missing_preferred_skills": [],
        "improvement_suggestions":  [],
        "interview_focus_areas":    [],
        "overall_assessment":       "Strong match.",
    }
    return m


# ---------------------------------------------------------------------------
# Integration tests — full compiled graph via run_workflow()
# ---------------------------------------------------------------------------

class TestWorkflowIntegration:
    """
    These tests invoke the full compiled LangGraph via run_workflow().
    Each test uses a unique thread_id so the shared MemorySaver does not
    bleed state between runs.
    """

    def test_full_workflow_happy_path(self) -> None:
        """
        All three agents succeed.  Expect the full graph to complete with
        resume, jd, and match_result populated and three agent_run entries.
        """
        resume_run  = _fake_agent_run("resume_agent")
        jd_run      = _fake_agent_run("jd_agent")
        match_run   = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MockResume, \
             patch("app.graph.workflow.JDAgent")    as MockJD,     \
             patch("app.graph.workflow.MatchAgent") as MockMatch:

            MockResume.return_value.parse.return_value  = (_fake_resume_model(), resume_run)
            MockJD.return_value.parse.return_value      = (_fake_jd_model(),    jd_run)
            MockMatch.return_value.match.return_value   = (_fake_match_model(80.0), match_run)

            final = run_workflow(
                user_id="test-user",
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a backend engineer.",
                thread_id=_unique_thread(),
            )

        # Core outputs
        assert final["resume"]       is not None, "resume must be populated"
        assert final["jd"]           is not None, "jd must be populated"
        assert final["match_result"] is not None, "match_result must be populated"

        # Three distinct agent_run entries (one per agent)
        assert len(final["agent_runs"]) == 3
        agent_names = [r["agent_name"] for r in final["agent_runs"]]
        assert "resume_agent" in agent_names
        assert "jd_agent"     in agent_names
        assert "match_agent"  in agent_names

        # Workflow progressed past matching
        assert final["current_step"] in {"matching", "rewriting", "interviewing", "reviewing"}
        assert final["error"] is None

    def test_workflow_resume_parse_error(self) -> None:
        """
        ResumeAgent raises an exception.  The error must propagate through
        parse_resume_node → error_handler_node → END without reaching JDAgent
        or MatchAgent.
        """
        with patch("app.graph.workflow.ResumeAgent") as MockResume, \
             patch("app.graph.workflow.JDAgent")    as MockJD,     \
             patch("app.graph.workflow.MatchAgent") as MockMatch:

            MockResume.return_value.parse.side_effect = RuntimeError("PDF is corrupted")

            final = run_workflow(
                user_id="test-user",
                resume_file_path="/fake/bad.pdf",
                jd_text="some jd text",
                thread_id=_unique_thread(),
            )

        assert final["current_step"] == "error"
        assert final["error"] is not None
        assert "PDF is corrupted" in final["error"]

        # Nodes after parse_resume must never have been reached
        assert final["resume"] is None
        assert final["jd"]     is None

        # JDAgent and MatchAgent must not have been invoked at all
        MockJD.return_value.parse.assert_not_called()
        MockMatch.return_value.match.assert_not_called()

        # A failed agent_run entry must still be logged
        assert len(final["agent_runs"]) >= 1
        assert final["agent_runs"][0]["status"] == "error"

    def test_workflow_jd_parse_error(self) -> None:
        """
        ResumeAgent succeeds but JDAgent raises.  The resume dict must be
        present in state while jd and match_result stay None.
        """
        resume_run = _fake_agent_run("resume_agent")

        with patch("app.graph.workflow.ResumeAgent") as MockResume, \
             patch("app.graph.workflow.JDAgent")    as MockJD,     \
             patch("app.graph.workflow.MatchAgent") as MockMatch:

            MockResume.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MockJD.return_value.parse.side_effect = ValueError("JD page returned 403")

            final = run_workflow(
                user_id="test-user",
                resume_file_path="/fake/resume.pdf",
                jd_text="https://jobs.example.com/123",
                thread_id=_unique_thread(),
            )

        assert final["current_step"] == "error"
        assert final["error"] is not None
        assert "403" in final["error"]

        # Resume was parsed before the failure
        assert final["resume"] is not None
        assert final["resume"]["contact"]["name"] == "Jane Doe"

        # JD and match must not be populated
        assert final["jd"]           is None
        assert final["match_result"] is None

        # MatchAgent must never have been reached
        MockMatch.return_value.match.assert_not_called()

    def test_workflow_checkpoint_resume(self) -> None:
        """
        After a successful run the checkpoint must be inspectable via
        get_workflow_state().  The snapshot must reflect the final state
        and indicate the workflow is complete (next == []).
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        thread_id = _unique_thread()

        with patch("app.graph.workflow.ResumeAgent") as MockResume, \
             patch("app.graph.workflow.JDAgent")    as MockJD,     \
             patch("app.graph.workflow.MatchAgent") as MockMatch:

            MockResume.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MockJD.return_value.parse.return_value     = (_fake_jd_model(),    jd_run)
            MockMatch.return_value.match.return_value  = (_fake_match_model(80.0), match_run)

            run_workflow(
                user_id="test-user",
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a backend engineer.",
                thread_id=thread_id,
            )

        snap = get_workflow_state(thread_id)

        # Snapshot must carry the final state values
        assert snap["values"] is not None
        assert snap["values"].get("match_result") is not None
        assert snap["values"].get("error") is None

        # next == [] means the workflow has fully completed
        assert snap["next"] == [], f"Expected no pending nodes, got: {snap['next']}"

        # Checkpoint metadata and timestamp must be present
        assert snap["created_at"] is not None
        assert snap["metadata"] is not None
        assert snap["metadata"].get("step") is not None


# ---------------------------------------------------------------------------
# run_parse_resume / run_parse_jd / run_full_pipeline
# ---------------------------------------------------------------------------

class TestRunHelpers:
    """Tests for the convenience wrapper functions added in Phase 3."""

    # ── run_parse_resume ─────────────────────────────────────────────────────

    def test_run_parse_resume_returns_dict(self) -> None:
        """Happy path: returns (dict, [agent_run]) where dict has resume fields."""
        fake_run = _fake_agent_run("resume_agent")

        with patch("app.graph.workflow.ResumeAgent") as MockResume:
            MockResume.return_value.parse.return_value = (_fake_resume_model(), fake_run)
            resume_dict, agent_runs = run_parse_resume("/fake/resume.pdf", user_id="u1")

        assert isinstance(resume_dict, dict)
        assert resume_dict["contact"]["name"] == "Jane Doe"
        assert isinstance(agent_runs, list)
        assert len(agent_runs) == 1
        assert agent_runs[0]["agent_name"] == "resume_agent"
        assert agent_runs[0]["status"] == "success"

    def test_run_parse_resume_returns_none_on_failure(self) -> None:
        """On agent exception: dict is None, agent_runs has a failed entry."""
        with patch("app.graph.workflow.ResumeAgent") as MockResume:
            MockResume.return_value.parse.side_effect = RuntimeError("PDF corrupt")
            resume_dict, agent_runs = run_parse_resume("/bad.pdf")

        assert resume_dict is None
        assert len(agent_runs) >= 1
        assert agent_runs[0]["status"] == "error"

    # ── run_parse_jd ─────────────────────────────────────────────────────────

    def test_run_parse_jd_returns_dict(self) -> None:
        """Happy path: returns (dict, [agent_run]) where dict has JD fields."""
        fake_run = _fake_agent_run("jd_agent")

        with patch("app.graph.workflow.JDAgent") as MockJD:
            MockJD.return_value.parse.return_value = (_fake_jd_model(), fake_run)
            jd_dict, agent_runs = run_parse_jd("We are hiring a backend engineer.", user_id="u1")

        assert isinstance(jd_dict, dict)
        assert jd_dict["title"] == "Backend Engineer"
        assert isinstance(agent_runs, list)
        assert len(agent_runs) == 1
        assert agent_runs[0]["agent_name"] == "jd_agent"
        assert agent_runs[0]["status"] == "success"

    def test_run_parse_jd_returns_none_on_failure(self) -> None:
        """On agent exception: dict is None, agent_runs has a failed entry."""
        with patch("app.graph.workflow.JDAgent") as MockJD:
            MockJD.return_value.parse.side_effect = ValueError("JD too short")
            jd_dict, agent_runs = run_parse_jd("x")

        assert jd_dict is None
        assert len(agent_runs) >= 1
        assert agent_runs[0]["status"] == "error"

    # ── run_full_pipeline ─────────────────────────────────────────────────────

    def test_run_full_pipeline_happy_path(self) -> None:
        """All agents succeed: resume, jd, and match_result all populated."""
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),    jd_run)
            MM.return_value.match.return_value = (_fake_match_model(80.0), match_run)

            state = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a backend engineer.",
                thread_id=_unique_thread(),
            )

        assert state["resume"]       is not None
        assert state["jd"]           is not None
        assert state["match_result"] is not None
        assert state["error"]        is None
        assert len(state["agent_runs"]) == 3

    def test_run_full_pipeline_with_error(self) -> None:
        """ResumeAgent failure: state carries error, jd and match_result are None."""
        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.side_effect = RuntimeError("disk read error")

            state = run_full_pipeline(
                resume_file_path="/bad/resume.pdf",
                jd_text="some JD",
                thread_id=_unique_thread(),
            )

        assert state["error"]        is not None
        assert "disk read error"     in state["error"]
        assert state["resume"]       is None
        assert state["jd"]           is None
        assert state["match_result"] is None
        MJ.return_value.parse.assert_not_called()
        MM.return_value.match.assert_not_called()

    def test_pipeline_routing_low_score(self) -> None:
        """
        Score = 40 → after_match_router sends to 'rewrite'.
        The placeholder rewrite_node runs and raises the score to 75,
        then match runs again → interview → review.
        current_step ends on "reviewing" (post-rewrite path).
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        # MatchAgent is called twice: first returns 40, second returns 75
        # (rewrite_node bumps match_result directly, so MatchAgent is only
        #  called once per graph invocation — the second pass uses the
        #  placeholder-bumped score).  We set side_effect to cover both calls.
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),    jd_run)
            # First match call → score 40 → triggers rewrite placeholder
            # rewrite_node bumps to 75 → second match call → score 75 → interview
            MM.return_value.match.side_effect = [
                (_fake_match_model(40.0), match_run),
                (_fake_match_model(75.0), match_run),
            ]

            state = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="some JD",
                thread_id=_unique_thread(),
            )

        assert state["error"] is None
        # After rewrite loop: score was bumped to ≥ 70, then interview → review
        assert state["current_step"] in {"rewriting", "interviewing", "reviewing"}
        # Match was called twice (first pass → rewrite → second pass)
        assert MM.return_value.match.call_count == 2

    def test_pipeline_routing_high_score(self) -> None:
        """
        Score = 85 → after_match_router sends directly to 'interview', skipping rewrite.
        current_step ends on "reviewing".
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),    jd_run)
            MM.return_value.match.return_value = (_fake_match_model(85.0), match_run)

            state = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="some JD",
                thread_id=_unique_thread(),
            )

        assert state["error"] is None
        assert state["current_step"] in {"interviewing", "reviewing"}
        # Match called exactly once — no rewrite loop
        assert MM.return_value.match.call_count == 1
        assert state["match_result"]["overall_score"] == 85.0
