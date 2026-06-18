"""
Tests for the LangGraph workflow node functions and routing logic.

All agent calls are mocked — no real Anthropic API calls are made.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.graph.state import JobHelperState
from app.graph.workflow import (
    after_match_router,
    match_node,
    parse_jd_node,
    parse_resume_node,
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
