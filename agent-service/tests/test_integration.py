"""
Integration tests for the AI Career agent-service.

These tests are organised in two tiers based on mocking depth:

Tier 1 — Claude API-level mocking (TestClaudeApiIntegration)
    The real agent code (ResumeAgent, JDAgent, MatchAgent) executes in full.
    Only two external dependencies are replaced:
      - pdfplumber.open          — PDF file reading
      - anthropic.Anthropic      — Anthropic client constructor

    This exercises JSON serialisation/deserialisation, Pydantic model validation,
    Python scoring logic inside MatchAgent, and the LangGraph routing logic —
    all without a real API key or resume file.

Tier 2 — Agent-level mocking (TestGraphRoutingIntegration, TestApiEndpoints)
    The agent classes themselves are replaced with MagicMocks (same technique as
    test_workflow.py).  These tests focus on graph routing behaviour and HTTP
    endpoint contracts rather than agent internals.

All tests hit the full compiled LangGraph (via run_full_pipeline or TestClient)
to confirm end-to-end wiring is intact.
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.graph.workflow import run_full_pipeline


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _unique_thread() -> str:
    return f"inttest-{uuid.uuid4().hex}"


def _fake_agent_run(agent_name: str, duration_ms: int = 150, token_count: int = 80) -> dict:
    return {
        "agent_name":    agent_name,
        "input_summary": "test input",
        "output_summary": "test output",
        "status":        "success",
        "duration_ms":   duration_ms,
        "token_count":   token_count,
        "model_name":    "claude-haiku-4-5-20251001",
        "error_message": None,
        "created_at":    "2026-06-18T00:00:00+00:00",
    }


def _fake_resume_model(name: str = "Jane Doe") -> MagicMock:
    m = MagicMock()
    m.raw_text = f"{name} Python FastAPI"
    m.model_dump.return_value = {
        "contact": {"name": name, "email": f"{name.lower().replace(' ', '.')}@example.com"},
        "summary": "Experienced Python/FastAPI engineer.",
        "skills": [
            {"name": "Python",   "category": "language",  "proficiency": "expert"},
            {"name": "FastAPI",  "category": "framework", "proficiency": "expert"},
        ],
        "experience": [{
            "company":      "Acme Corp",
            "title":        "Software Engineer",
            "location":     "Remote",
            "start_date":   "2022-01",
            "end_date":     None,
            "is_current":   True,
            "bullets":      ["Built backend APIs"],
            "technologies": ["Python", "FastAPI"],
        }],
        "education":      [],
        "projects":       [],
        "certifications": [],
        "raw_text":       f"{name} Python FastAPI",
        "parse_confidence": 0.9,
    }
    return m


def _fake_jd_model() -> MagicMock:
    m = MagicMock()
    m.model_dump.return_value = {
        "title":               "Backend Engineer",
        "company":             "TechCorp",
        "skills": [
            {"name": "Python",  "is_required": True,  "category": "language"},
            {"name": "FastAPI", "is_required": True,  "category": "framework"},
            {"name": "Docker",  "is_required": False, "category": "tool"},
        ],
        "keywords":            ["Python", "FastAPI", "microservices"],
        "min_years_experience": 2,
        "raw_text":            "Backend Engineer at TechCorp",
        "parse_confidence":    0.92,
    }
    return m


def _fake_match_model(overall_score: float = 80.0) -> MagicMock:
    m = MagicMock()
    m.model_dump.return_value = {
        "overall_score":           overall_score,
        "skill_score":             75.0,
        "experience_score":        80.0,
        "keyword_score":           85.0,
        "missing_required_skills": [],
        "missing_preferred_skills": ["Docker"],
        "improvement_suggestions": ["Quantify your impact."],
        "interview_focus_areas":   ["System design"],
        "overall_assessment":      "Good match.",
        "matched_skills":          ["Python", "FastAPI"],
        "matched_keywords":        ["Python", "FastAPI"],
    }
    return m


# ---------------------------------------------------------------------------
# Tier 1 helpers — Claude API-level mocking
# ---------------------------------------------------------------------------

def _make_claude_response(json_text: str) -> MagicMock:
    """Build a mock anthropic messages.create() return value."""
    response = MagicMock()
    response.content = [MagicMock(text=json_text)]
    response.usage   = MagicMock(input_tokens=120, output_tokens=240)
    return response


def _make_pdf_mock(text: str = "Jane Doe jane@example.com Python FastAPI") -> MagicMock:
    """Return a mock pdfplumber context manager that yields one page of text."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = text

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages    = [mock_page]
    return mock_pdf


# Canonical JSON strings returned by the mocked Claude client.
# They must pass Pydantic validation for ParsedResume / ParsedJobDescription
# and the gap-analysis key-check inside MatchAgent._call_gap_analysis().

_PDF_TEXT = "Jane Doe  jane@example.com  Python FastAPI PostgreSQL microservices"

_RESUME_JSON = json.dumps({
    "contact": {
        "name":          "Jane Doe",
        "email":         "jane@example.com",
        "phone":         None,
        "address":       "San Francisco, CA",
        "linkedin_url":  None,
        "github_url":    None,
        "portfolio_url": None,
    },
    "summary": "Backend engineer with Python and FastAPI expertise.",
    "skills": [
        {"name": "Python",     "category": "language",  "proficiency": "expert"},
        {"name": "FastAPI",    "category": "framework", "proficiency": "expert"},
        {"name": "PostgreSQL", "category": "database",  "proficiency": "proficient"},
    ],
    "experience": [{
        "company":      "Acme Corp",
        "title":        "Software Engineer",
        "location":     "Remote",
        "start_date":   "2022-01",
        "end_date":     None,
        "is_current":   True,
        "bullets":      ["Built REST APIs in Python/FastAPI serving 500k req/day"],
        "technologies": ["Python", "FastAPI", "PostgreSQL"],
    }],
    "education":      [],
    "projects":       [],
    "certifications": [],
    "raw_text":       "...[truncated by agent]",   # overwritten by agent
    "parse_confidence": 0.9,
})

_JD_JSON = json.dumps({
    "title":   "Backend Engineer",
    "company": "TechCorp",
    "location": "Remote",
    "remote_type": "remote",
    "employment_type": "full-time",
    "min_years_experience": 2,
    "max_years_experience": None,
    "salary_min":      None,
    "salary_max":      None,
    "salary_currency": None,
    "responsibilities": ["Design and build scalable APIs"],
    "skills": [
        {"name": "Python",  "is_required": True,  "category": "language"},
        {"name": "FastAPI", "is_required": True,  "category": "framework"},
        {"name": "Docker",  "is_required": False, "category": "tool"},
    ],
    "qualifications": [],
    "keywords": ["Python", "FastAPI", "microservices"],
    "industry": "fintech",
    "raw_text": "...[truncated by agent]",   # overwritten by agent
    "source_url": None,
    "parse_confidence": 0.92,
})

_GAP_JSON = json.dumps({
    "missing_required_skills":  [],
    "missing_preferred_skills": ["Docker"],
    "improvement_suggestions":  [
        "Quantify your API performance improvements with specific metrics.",
        "Add Docker to your skills section if you have any container experience.",
    ],
    "interview_focus_areas": [
        "System design for high-throughput APIs",
        "Python async patterns and concurrency",
    ],
    "overall_assessment": (
        "Strong match. Python and FastAPI align well with core requirements. "
        "Docker experience would be a bonus but is not blocking."
    ),
})


# ---------------------------------------------------------------------------
# Tier 1: Claude API-level integration tests
# ---------------------------------------------------------------------------

class TestClaudeApiIntegration:
    """
    Real agent code executes; only pdfplumber and the Anthropic client are mocked.

    Score derivation for the canonical test data (computed by MatchAgent Python logic):
      - skill_score:       70.0  (Python+FastAPI required → 70pts, Docker missed → 0pt preferred)
      - experience_score: 100.0  (4.4 yrs vs 2 min, plus tech relevance bonus)
      - keyword_score:     66.7  (Python ✓ FastAPI ✓ microservices ✗ in PDF text)
      - overall_score:     78.2  (≥70 → routes to interview → review → completed)
    """

    def _run_full(self, thread_id: str | None = None) -> dict:
        """
        Invoke the full pipeline with all external I/O mocked at the lowest level.
        Returns the final workflow state dict.
        """
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_claude_response(_RESUME_JSON),   # ResumeAgent._call_claude
            _make_claude_response(_JD_JSON),        # JDAgent._call_claude
            _make_claude_response(_GAP_JSON),       # MatchAgent._call_gap_analysis
        ]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-fake-key"}), \
             patch("anthropic.Anthropic", return_value=mock_client),           \
             patch("pdfplumber.open", return_value=_make_pdf_mock(_PDF_TEXT)):

            return run_full_pipeline(
                resume_file_path="/fake/jane_doe.pdf",
                jd_text=(
                    "Backend Engineer at TechCorp. Required: Python, FastAPI. "
                    "Preferred: Docker. Minimum 2 years of experience."
                ),
                thread_id=thread_id or _unique_thread(),
            )

    def test_full_pipeline_resume_to_match(self) -> None:
        """
        All three agents succeed with real code + mocked Claude responses.

        Verifies that the output state has fully-populated resume, jd, and
        match_result dicts with the expected score dimensions, three agent_run
        entries, workflow_status 'completed', and no error.
        """
        final = self._run_full()

        # ── Core outputs ────────────────────────────────────────────────────
        assert final["resume"]       is not None, "resume must be populated"
        assert final["jd"]           is not None, "jd must be populated"
        assert final["match_result"] is not None, "match_result must be populated"
        assert final["error"]        is None,     "no error expected"

        # ── Resume content (real Pydantic parse) ────────────────────────────
        assert final["resume"]["contact"]["name"] == "Jane Doe"
        assert any(s["name"] == "Python" for s in final["resume"]["skills"])

        # ── JD content ──────────────────────────────────────────────────────
        assert final["jd"]["title"] == "Backend Engineer"

        # ── match_result has all four score dimensions ───────────────────────
        mr = final["match_result"]
        for key in ("overall_score", "skill_score", "experience_score", "keyword_score"):
            assert key in mr, f"match_result missing '{key}'"
            assert isinstance(mr[key], (int, float)), f"'{key}' must be numeric"
            assert 0 <= mr[key] <= 100, f"'{key}' must be in [0, 100], got {mr[key]}"

        # High-score path: resume strongly matches JD
        assert mr["overall_score"] >= 70, (
            f"Expected overall_score ≥ 70, got {mr['overall_score']}"
        )

        # ── agent_runs: one per agent, all successful ───────────────────────
        runs       = final["agent_runs"]
        names      = [r["agent_name"] for r in runs]
        assert "resume_agent" in names
        assert "jd_agent"     in names
        assert "match_agent"  in names
        assert len(runs) == 3, f"expected 3 agent_runs, got {len(runs)}"

        # ── workflow_status: 'completed' (review_node sets this) ────────────
        assert final.get("workflow_status") == "completed", (
            f"expected 'completed', got '{final.get('workflow_status')}'"
        )


# ---------------------------------------------------------------------------
# Tier 2: Agent-level routing tests
# ---------------------------------------------------------------------------

class TestGraphRoutingIntegration:
    """
    Full pipeline runs via run_full_pipeline() with agent classes mocked.
    Focuses on routing behaviour rather than agent internals.
    """

    def test_pipeline_low_score_routes_to_rewrite(self) -> None:
        """
        When the first match returns overall_score=40, the graph must route
        to the 'rewrite' node before eventually completing via interview/review.

        After rewrite, MatchAgent is called a second time (returning 75 in the
        side_effect list) so the workflow continues to interview → review.

        Assertions:
          - current_step indicates the rewrite path was taken
          - 'match' step appears in agent_runs (match ran at least once)
          - MatchAgent.match was called exactly twice (one loop iteration)
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),     jd_run)
            # First pass → 40 (rewrite), second pass → 75 (interview)
            MM.return_value.match.side_effect = [
                (_fake_match_model(40.0), match_run),
                (_fake_match_model(75.0), match_run),
            ]

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We need a backend engineer.",
                thread_id=_unique_thread(),
            )

        assert final["error"] is None

        # Rewrite path → interview → review
        assert final["current_step"] in {"rewriting", "interviewing", "reviewing"}, (
            f"expected a post-rewrite step, got '{final['current_step']}'"
        )

        # Match agent ran twice — once per loop iteration
        assert MM.return_value.match.call_count == 2, (
            f"expected 2 match calls (rewrite loop), got {MM.return_value.match.call_count}"
        )

        # 'match' step appears in agent_runs (either directly or as match_agent)
        match_runs = [r for r in final["agent_runs"] if r["agent_name"] == "match_agent"]
        assert len(match_runs) >= 1, "match_agent must appear in agent_runs"

    def test_pipeline_high_score_routes_to_interview(self) -> None:
        """
        When the match returns overall_score=85, the graph must route directly
        to the interview path (skipping rewrite), with MatchAgent called once.

        Assertions:
          - current_step indicates the interview path was taken
          - MatchAgent.match called exactly once (no rewrite loop)
          - match_result overall_score equals 85.0
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),     jd_run)
            MM.return_value.match.return_value = (_fake_match_model(85.0), match_run)

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We need a backend engineer.",
                thread_id=_unique_thread(),
            )

        assert final["error"] is None

        # Interview path (no rewrite)
        assert final["current_step"] in {"interviewing", "reviewing"}, (
            f"expected interview/review step, got '{final['current_step']}'"
        )

        # Match called exactly once — rewrite never triggered
        assert MM.return_value.match.call_count == 1

        assert final["match_result"]["overall_score"] == 85.0


# ---------------------------------------------------------------------------
# Tier 2: HTTP endpoint tests (TestClient)
# ---------------------------------------------------------------------------

class TestApiEndpoints:
    """
    Tests for the FastAPI HTTP layer.  Uses TestClient to exercise the full
    request/response cycle (routing, file-upload handling, JSON serialisation)
    with agent classes mocked.
    """

    @pytest.fixture(autouse=True)
    def _client(self):
        from app.main import app
        self.client = TestClient(app)

    # ── POST /api/pipeline/run ───────────────────────────────────────────────

    def test_pipeline_api_endpoint(self) -> None:
        """
        POST /api/pipeline/run with a multipart upload must return 200 with
        resume, jd, and match_result populated in the response body.
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),     jd_run)
            MM.return_value.match.return_value = (_fake_match_model(80.0), match_run)

            response = self.client.post(
                "/api/pipeline/run",
                data={"jd_text": "We need a backend engineer.", "user_id": "inttest-user"},
                files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")},
            )

        # ── Status ──────────────────────────────────────────────────────────
        assert response.status_code == 200, (
            f"expected 200, got {response.status_code}: {response.text}"
        )

        body = response.json()

        # ── Core output fields ───────────────────────────────────────────────
        assert body.get("resume")       is not None, "resume must be in response"
        assert body.get("jd")           is not None, "jd must be in response"
        assert body.get("match_result") is not None, "match_result must be in response"
        assert body.get("error")        is None

        # ── Summary fields added by the endpoint ────────────────────────────
        assert "workflow_status"   in body
        assert "steps_completed"   in body
        assert "total_duration_ms" in body
        assert "total_tokens"      in body

        # All three agents succeeded → three entries in steps_completed
        assert len(body["steps_completed"]) == 3

    # ── Individual parse/match endpoints ─────────────────────────────────────

    def test_individual_endpoints_still_work(self) -> None:
        """
        Smoke-test for the three standalone endpoints to confirm they still
        return 200 after the pipeline refactor:
          POST /api/resume/parse   (file upload)
          POST /api/jd/parse       (JSON body)
          POST /api/match          (JSON body)
        """
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent") as MR, \
             patch("app.graph.workflow.JDAgent")    as MJ, \
             patch("app.graph.workflow.MatchAgent") as MM:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),     jd_run)
            MM.return_value.match.return_value = (_fake_match_model(78.0), match_run)

            # ── /api/resume/parse ────────────────────────────────────────────
            r_resume = self.client.post(
                "/api/resume/parse",
                files={"file": ("resume.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            )
            assert r_resume.status_code == 200, (
                f"/api/resume/parse returned {r_resume.status_code}: {r_resume.text}"
            )
            resume_body = r_resume.json()
            assert "contact" in resume_body, "resume/parse response missing 'contact'"

            # ── /api/jd/parse ────────────────────────────────────────────────
            r_jd = self.client.post(
                "/api/jd/parse",
                json={"text": "We are hiring a backend engineer who knows Python and FastAPI."},
            )
            assert r_jd.status_code == 200, (
                f"/api/jd/parse returned {r_jd.status_code}: {r_jd.text}"
            )
            jd_body = r_jd.json()
            assert "title" in jd_body, "jd/parse response missing 'title'"

            # ── /api/match ───────────────────────────────────────────────────
            r_match = self.client.post(
                "/api/match",
                json={
                    "resume": {
                        "contact":          {"name": "Jane Doe"},
                        "skills":           [{"name": "Python", "category": "language"}],
                        "experience":       [],
                        "education":        [],
                        "projects":         [],
                        "certifications":   [],
                        "raw_text":         "Jane Doe Python",
                        "parse_confidence": 0.9,
                    },
                    "jd": {
                        "title":            "Backend Engineer",
                        "skills":           [{"name": "Python", "is_required": True, "category": "language"}],
                        "keywords":         ["Python"],
                        "raw_text":         "Backend engineer Python",
                        "parse_confidence": 0.9,
                    },
                },
            )
            assert r_match.status_code == 200, (
                f"/api/match returned {r_match.status_code}: {r_match.text}"
            )
            match_body = r_match.json()
            assert "overall_score" in match_body, "match response missing 'overall_score'"
