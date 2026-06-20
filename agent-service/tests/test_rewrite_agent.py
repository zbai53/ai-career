"""
Tests for RewriteAgent.

All Claude API calls are mocked. FidelityChecker is also mocked in
retry-specific tests to control fidelity outcomes precisely.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from app.agents.fidelity_checker import FidelityChecker
from app.agents.rewrite_agent import RewriteAgent
from app.models.fidelity_report import FidelityReport
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)
from app.models.rewrite_result import RewriteResult


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_resume() -> ParsedResume:
    return ParsedResume(
        contact=ResumeContact(name="Jane Doe", email="jane@example.com"),
        experience=[
            ResumeExperience(
                company="Acme Corp",
                title="Software Engineer",
                start_date="2021-01",
                end_date="2023-06",
                bullets=[
                    "Built internal tooling used by 5 teams",
                    "Reduced deployment time significantly",
                ],
                technologies=["Python", "Django", "PostgreSQL"],
            )
        ],
        skills=[
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="Django", category="framework"),
            ResumeSkill(name="PostgreSQL", category="database"),
        ],
        raw_text="Built internal tooling. Reduced deployment time. Python Django PostgreSQL.",
        parse_confidence=0.92,
    )


def _make_jd() -> ParsedJobDescription:
    return ParsedJobDescription(
        title="Backend Engineer",
        company="TechCo",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="FastAPI", is_required=True, category="framework"),
            JDSkillRequirement(name="Docker", is_required=False, category="tool"),
        ],
        keywords=["microservices", "REST API", "CI/CD"],
        responsibilities=["Build scalable backend services"],
        raw_text="Backend Engineer at TechCo. Python, FastAPI required.",
        parse_confidence=0.95,
    )


def _make_match_result(overall_score: float = 72.0) -> dict:
    return {
        "overall_score": overall_score,
        "skill_score": 60.0,
        "experience_score": 80.0,
        "keyword_score": 55.0,
        "gap_analysis": {
            "missing_required_skills": ["FastAPI"],
            "missing_preferred_skills": ["Docker"],
            "improvement_suggestions": [
                "Highlight REST API experience",
                "Mention CI/CD pipelines if applicable",
            ],
            "overall_assessment": "Good Python background; needs FastAPI framing.",
        },
    }


def _claude_rewrite_response(
    bullets: list[str],
    keywords: list[str] | None = None,
    confidence: float = 0.88,
) -> MagicMock:
    """Build a mock Claude response returning a well-formed rewrite JSON."""
    payload = {
        "rewritten_bullets": [
            {
                "original": b,
                "rewritten": f"[Rewritten] {b}",
                "changes_made": ["Strengthened action verb", "Added REST API keyword"],
            }
            for b in bullets
        ],
        "keywords_injected": keywords or ["microservices", "REST API"],
        "confidence": confidence,
    }
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(payload))]
    mock_resp.usage = MagicMock(input_tokens=200, output_tokens=150)
    return mock_resp


def _passing_fidelity_report() -> FidelityReport:
    return FidelityReport(
        fidelity_score=0.95,
        flags=[],
        total_original_entities=10,
        total_rewritten_entities=10,
        new_entities_found=0,
        passed=True,
        threshold=0.85,
    )


def _failing_fidelity_report(flagged_entity: str = "FakeCorpXYZ") -> FidelityReport:
    from app.models.fidelity_report import FidelityFlag
    return FidelityReport(
        fidelity_score=0.70,
        flags=[
            FidelityFlag(
                entity=flagged_entity,
                entity_type="company",
                found_in=f"Worked at {flagged_entity} on microservices",
                severity="high",
            )
        ],
        total_original_entities=10,
        total_rewritten_entities=11,
        new_entities_found=1,
        passed=False,
        threshold=0.85,
    )


def _make_agent_with_mock_claude(claude_responses: list) -> tuple[RewriteAgent, MagicMock]:
    """
    Return (agent, mock_fidelity_checker) with Claude patched to return
    claude_responses in sequence. FidelityChecker always passes by default.
    """
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = claude_responses

    mock_checker = MagicMock(spec=FidelityChecker)
    mock_checker.threshold = 0.85
    mock_checker.check.return_value = _passing_fidelity_report()

    with patch("anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        agent = RewriteAgent(fidelity_checker=mock_checker)
        agent._client = mock_client

    return agent, mock_checker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRewriteReturnsValidResult(unittest.TestCase):
    def test_rewrite_returns_valid_result(self):
        """Basic smoke test: returns a RewriteResult with rewritten bullets."""
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets)]
        )
        result, agent_run = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertIsInstance(result, RewriteResult)
        self.assertEqual(len(result.experiences), 1)
        exp = result.experiences[0]
        self.assertEqual(len(exp.rewritten_bullets), len(bullets))
        for rb in exp.rewritten_bullets:
            self.assertIsNotNone(rb.rewritten)
            self.assertGreater(len(rb.rewritten), 0)

    def test_agent_run_log_has_expected_keys(self):
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets)]
        )
        _, agent_run = agent.rewrite(resume, _make_jd(), _make_match_result())

        for key in ("agent_name", "status", "duration_ms", "token_count"):
            self.assertIn(key, agent_run)
        self.assertEqual(agent_run["agent_name"], "rewrite_agent")
        self.assertEqual(agent_run["status"], "success")

    def test_rewrite_attempts_defaults_to_one_on_pass(self):
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets)]
        )
        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())
        self.assertEqual(result.rewrite_attempts, 1)


class TestRewritePreservesCompanyNames(unittest.TestCase):
    def test_company_name_unchanged_in_experience(self):
        """The experience.company field must equal the original resume company."""
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets)]
        )
        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertEqual(result.experiences[0].company, "Acme Corp")

    def test_title_unchanged_in_experience(self):
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets)]
        )
        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertEqual(result.experiences[0].title, "Software Engineer")


class TestRewriteInjectsKeywords(unittest.TestCase):
    def test_keywords_returned_in_result(self):
        """keywords_injected should include what Claude reported."""
        resume = _make_resume()
        bullets = resume.experience[0].bullets
        expected_keywords = ["microservices", "REST API"]

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets, keywords=expected_keywords)]
        )
        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        for kw in expected_keywords:
            self.assertIn(kw, result.keywords_injected)

    def test_keywords_injected_is_sorted(self):
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, _ = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets, keywords=["z-keyword", "a-keyword"])]
        )
        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertEqual(result.keywords_injected, sorted(result.keywords_injected))


class TestFidelityCheckPassesCleanRewrite(unittest.TestCase):
    def test_fidelity_report_attached_and_passed(self):
        """A clean rewrite: fidelity_report.passed=True, score >= 0.85."""
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        agent, mock_checker = _make_agent_with_mock_claude(
            [_claude_rewrite_response(bullets)]
        )
        mock_checker.check.return_value = _passing_fidelity_report()

        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertIsNotNone(result.fidelity_report)
        self.assertTrue(result.fidelity_report.passed)
        self.assertGreaterEqual(result.fidelity_report.fidelity_score, 0.85)
        self.assertEqual(result.rewrite_attempts, 1)


class TestFidelityCheckFlagsHallucination(unittest.TestCase):
    def test_fake_company_is_flagged(self):
        """
        When the fidelity checker flags a new company, the report should
        contain that flag. (Two attempts: both fail — we just check the flags.)
        """
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _claude_rewrite_response(
            bullets,
            keywords=["microservices"],
        )

        mock_checker = MagicMock(spec=FidelityChecker)
        mock_checker.threshold = 0.85
        # Both attempts fail fidelity
        mock_checker.check.return_value = _failing_fidelity_report("FakeCorpXYZ")

        with patch("anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            agent = RewriteAgent(fidelity_checker=mock_checker)
            agent._client = mock_client

        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertIsNotNone(result.fidelity_report)
        self.assertFalse(result.fidelity_report.passed)
        flagged = [f.entity for f in result.fidelity_report.flags]
        self.assertIn("FakeCorpXYZ", flagged)


class TestRewriteRetryOnLowFidelity(unittest.TestCase):
    def test_retry_on_low_fidelity(self):
        """
        First rewrite fails fidelity; second passes.
        rewrite_attempts should equal 2.
        """
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _claude_rewrite_response(bullets)

        mock_checker = MagicMock(spec=FidelityChecker)
        mock_checker.threshold = 0.85
        mock_checker.check.side_effect = [
            _failing_fidelity_report("FakeCorpXYZ"),  # attempt 1 fails
            _passing_fidelity_report(),               # attempt 2 passes
        ]

        with patch("anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            agent = RewriteAgent(fidelity_checker=mock_checker)
            agent._client = mock_client

        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertEqual(result.rewrite_attempts, 2)
        self.assertTrue(result.fidelity_report.passed)
        self.assertEqual(mock_checker.check.call_count, 2)

    def test_retry_prompt_includes_flagged_entities(self):
        """
        On fidelity retry, the stricter prompt is sent to Claude.
        We verify Claude was called at least twice (one per attempt).
        """
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _claude_rewrite_response(bullets)

        mock_checker = MagicMock(spec=FidelityChecker)
        mock_checker.threshold = 0.85
        mock_checker.check.side_effect = [
            _failing_fidelity_report("FakeCorpXYZ"),
            _passing_fidelity_report(),
        ]

        with patch("anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            agent = RewriteAgent(fidelity_checker=mock_checker)
            agent._client = mock_client

        agent.rewrite(resume, _make_jd(), _make_match_result())

        # Claude must have been called at least twice (once per rewrite attempt)
        self.assertGreaterEqual(mock_client.messages.create.call_count, 2)

        # Second call's user message should mention the flagged entity
        second_call_args = mock_client.messages.create.call_args_list[1]
        messages = second_call_args.kwargs.get("messages") or second_call_args[1].get("messages", [])
        user_content = messages[0]["content"] if messages else ""
        self.assertIn("FakeCorpXYZ", user_content)

    def test_max_two_attempts(self):
        """Even if both attempts fail fidelity, we stop at 2 attempts."""
        resume = _make_resume()
        bullets = resume.experience[0].bullets

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _claude_rewrite_response(bullets)

        mock_checker = MagicMock(spec=FidelityChecker)
        mock_checker.threshold = 0.85
        mock_checker.check.return_value = _failing_fidelity_report("FakeCorpXYZ")

        with patch("anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            agent = RewriteAgent(fidelity_checker=mock_checker)
            agent._client = mock_client

        result, _ = agent.rewrite(resume, _make_jd(), _make_match_result())

        self.assertEqual(result.rewrite_attempts, 2)
        self.assertEqual(mock_checker.check.call_count, 2)


if __name__ == "__main__":
    unittest.main()
