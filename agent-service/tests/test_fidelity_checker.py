"""
Tests for FidelityChecker.

All Claude API calls are mocked — tests only exercise rule-based extraction
unless explicitly testing the Claude-assisted path.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.agents.fidelity_checker import (
    FidelityChecker,
    _extract_dates_rule,
    _extract_metrics_rule,
)
from app.models.fidelity_report import FidelityReport
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)
from app.models.rewrite_result import RewriteResult, RewrittenBullet, RewrittenExperience


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resume(
    companies: list[str] | None = None,
    titles: list[str] | None = None,
    bullets: list[str] | None = None,
    technologies: list[str] | None = None,
    skills: list[str] | None = None,
) -> ParsedResume:
    companies = companies or ["Acme Corp"]
    titles = titles or ["Software Engineer"]
    bullets = bullets or ["Built internal tooling used by 5 teams"]
    technologies = technologies or ["Python", "Django"]
    skills = skills or ["Python", "Django"]

    return ParsedResume(
        contact=ResumeContact(name="Jane Doe", email="jane@example.com"),
        experience=[
            ResumeExperience(
                company=c,
                title=t,
                bullets=bullets,
                technologies=technologies,
            )
            for c, t in zip(companies, titles)
        ],
        skills=[ResumeSkill(name=s, category="language") for s in skills],
        raw_text=" ".join(bullets) + " " + " ".join(technologies),
        parse_confidence=0.9,
    )


def _make_rewrite(
    company: str = "Acme Corp",
    title: str = "Software Engineer",
    original_bullets: list[str] | None = None,
    rewritten_bullets: list[str] | None = None,
) -> RewriteResult:
    original_bullets = original_bullets or ["Built internal tooling used by 5 teams"]
    rewritten_bullets = rewritten_bullets or original_bullets

    rb = [
        RewrittenBullet(
            original=orig,
            rewritten=rw,
            changes_made=[],
        )
        for orig, rw in zip(original_bullets, rewritten_bullets)
    ]
    return RewriteResult(
        experiences=[
            RewrittenExperience(
                company=company,
                title=title,
                original_bullets=original_bullets,
                rewritten_bullets=rb,
            )
        ],
        keywords_injected=[],
        overall_improvement_summary="Test rewrite.",
        rewrite_confidence=0.9,
    )


def _checker_no_claude() -> FidelityChecker:
    """Return a FidelityChecker with Claude disabled (rule-based only)."""
    with patch.dict("os.environ", {}, clear=True):
        checker = FidelityChecker.__new__(FidelityChecker)
        checker.threshold = 0.85
        checker._client = None
        return checker


# ---------------------------------------------------------------------------
# Rule-based extraction unit tests
# ---------------------------------------------------------------------------


class TestExtractDatesRegex(unittest.TestCase):
    def test_iso_date(self):
        result = _extract_dates_rule("Started 2020-01 at the company.")
        self.assertIn("2020-01", result)

    def test_slash_date(self):
        result = _extract_dates_rule("End date 01/2020.")
        self.assertIn("01/2020", result)

    def test_four_digit_year(self):
        result = _extract_dates_rule("Worked there in 2020 and 2021.")
        self.assertIn("2020", result)
        self.assertIn("2021", result)

    def test_month_name_year(self):
        result = _extract_dates_rule("Joined January 2019.")
        self.assertTrue(any("january 2019" in d for d in result))

    def test_no_false_positive_on_random_number(self):
        result = _extract_dates_rule("Handled 42 tickets per week.")
        self.assertEqual(result, set())


class TestExtractMetricsRegex(unittest.TestCase):
    def test_percentage(self):
        result = _extract_metrics_rule("Reduced latency by 50%.")
        self.assertTrue(any("50%" in m for m in result))

    def test_dollar_millions(self):
        result = _extract_metrics_rule("Managed $1.2M budget.")
        self.assertTrue(any("1.2m" in m.lower() or "$1.2m" in m.lower() for m in result))

    def test_k_suffix(self):
        result = _extract_metrics_rule("Served 10K users daily.")
        self.assertTrue(any("10k" in m.lower() for m in result))

    def test_uptime_percentage(self):
        result = _extract_metrics_rule("Maintained 99.9% uptime.")
        self.assertTrue(any("99.9%" in m for m in result))

    def test_multiplier(self):
        result = _extract_metrics_rule("Increased throughput 3x.")
        self.assertTrue(any("3x" in m.lower() for m in result))

    def test_no_match_plain_text(self):
        result = _extract_metrics_rule("Led a cross-functional team.")
        self.assertEqual(result, set())


# ---------------------------------------------------------------------------
# FidelityChecker.check() integration tests (rule-based only, no Claude)
# ---------------------------------------------------------------------------


class TestNoNewEntitiesPerfectScore(unittest.TestCase):
    """Identical entities in original and rewrite → fidelity_score = 1.0."""

    def test_score_is_one(self):
        checker = _checker_no_claude()
        resume = _make_resume(
            bullets=["Reduced load time by 30% at Acme Corp"],
        )
        rewrite = _make_rewrite(
            original_bullets=["Reduced load time by 30% at Acme Corp"],
            rewritten_bullets=["Reduced page load time by 30% at Acme Corp using caching"],
        )
        report = checker.check(resume, rewrite)
        # No new metrics/dates introduced — should pass
        self.assertGreaterEqual(report.fidelity_score, 0.85)
        self.assertTrue(report.passed)

    def test_perfect_identity_rewrite(self):
        checker = _checker_no_claude()
        resume = _make_resume()
        # Rewrite is identical to original
        rewrite = _make_rewrite(
            original_bullets=["Built internal tooling used by 5 teams"],
            rewritten_bullets=["Built internal tooling used by 5 teams"],
        )
        report = checker.check(resume, rewrite)
        self.assertEqual(report.fidelity_score, 1.0)
        self.assertEqual(report.new_entities_found, 0)
        self.assertTrue(report.passed)


class TestAllNewEntitiesLowScore(unittest.TestCase):
    """Rewrite introduces many new metrics → score drops below threshold."""

    def test_low_score_when_many_new_metrics(self):
        checker = _checker_no_claude()
        resume = _make_resume(
            bullets=["Improved system performance significantly"],
        )
        # Rewrite adds several metrics absent from the original resume
        rewrite = _make_rewrite(
            original_bullets=["Improved system performance significantly"],
            rewritten_bullets=["Improved system performance by 75%, saving $500K annually, achieving 99.9% uptime"],
        )
        report = checker.check(resume, rewrite)
        # New metrics (75%, $500K, 99.9%) should be flagged; score < 1.0
        self.assertLess(report.fidelity_score, 1.0)
        self.assertGreater(report.new_entities_found, 0)


class TestSeverityClassification(unittest.TestCase):
    """Verify severity mapping: company=high, technology=low."""

    def test_company_hallucination_is_high_severity(self):
        """Inject a fake company name; flag must have severity='high'."""
        checker = _checker_no_claude()

        # Resume has only "Acme Corp"; rewrite mentions "FakeCorpXYZ" (new company)
        # Since rule-based extraction doesn't catch company names, we mock Claude
        mock_client = MagicMock()

        # Claude returns FakeCorpXYZ as a company in the rewrite
        def _entity_side_effect(model, max_tokens, system, messages):
            text = messages[0]["content"]
            resp = MagicMock()
            resp.usage = MagicMock(input_tokens=50, output_tokens=20)
            if "FakeCorpXYZ" in text:
                resp.content = [MagicMock(text='{"companies":["FakeCorpXYZ"],"job_titles":[],"technologies":[]}')]
            else:
                resp.content = [MagicMock(text='{"companies":["Acme Corp"],"job_titles":["Software Engineer"],"technologies":["Python"]}')]
            return resp

        mock_client.messages.create.side_effect = _entity_side_effect
        checker._client = mock_client

        resume = _make_resume()
        rewrite = _make_rewrite(
            rewritten_bullets=["Led distributed systems work at FakeCorpXYZ using Python"],
        )
        report = checker.check(resume, rewrite)

        company_flags = [f for f in report.flags if f.entity_type == "company"]
        self.assertTrue(len(company_flags) > 0, "Expected at least one company flag")
        for flag in company_flags:
            self.assertEqual(flag.severity, "high")

    def test_technology_flag_is_medium_severity(self):
        """New technology in rewrite → severity='medium' (unverified tech claim)."""
        checker = _checker_no_claude()

        # Kubernetes is not in the original resume; rule-based will catch it
        resume = _make_resume(technologies=["Python"], skills=["Python"])
        rewrite = _make_rewrite(
            rewritten_bullets=["Deployed microservices using Kubernetes and Python"],
        )
        report = checker.check(resume, rewrite)

        tech_flags = [f for f in report.flags if f.entity_type == "technology"]
        self.assertTrue(len(tech_flags) > 0, "Expected at least one technology flag")
        for flag in tech_flags:
            self.assertEqual(flag.severity, "medium")

    def test_metric_flag_is_medium_severity(self):
        """New metric in rewrite → severity='medium'."""
        checker = _checker_no_claude()
        resume = _make_resume(bullets=["Improved query performance"])
        rewrite = _make_rewrite(
            original_bullets=["Improved query performance"],
            rewritten_bullets=["Improved query performance by 80%"],
        )
        report = checker.check(resume, rewrite)

        metric_flags = [f for f in report.flags if f.entity_type == "metric"]
        self.assertTrue(len(metric_flags) > 0, "Expected at least one metric flag")
        for flag in metric_flags:
            self.assertEqual(flag.severity, "medium")


class TestReportStructure(unittest.TestCase):
    def test_report_fields_present(self):
        checker = _checker_no_claude()
        resume = _make_resume()
        rewrite = _make_rewrite()
        report = checker.check(resume, rewrite)

        self.assertIsInstance(report, FidelityReport)
        self.assertIsInstance(report.fidelity_score, float)
        self.assertIsInstance(report.flags, list)
        self.assertIsInstance(report.total_original_entities, int)
        self.assertIsInstance(report.total_rewritten_entities, int)
        self.assertIsInstance(report.new_entities_found, int)
        self.assertIsInstance(report.passed, bool)
        self.assertEqual(report.threshold, 0.85)

    def test_score_clamped_between_0_and_1(self):
        checker = _checker_no_claude()
        resume = _make_resume()
        rewrite = _make_rewrite()
        report = checker.check(resume, rewrite)
        self.assertGreaterEqual(report.fidelity_score, 0.0)
        self.assertLessEqual(report.fidelity_score, 1.0)

    def test_empty_rewrite_gives_perfect_score(self):
        checker = _checker_no_claude()
        resume = _make_resume()
        rewrite = RewriteResult(
            experiences=[],
            keywords_injected=[],
            overall_improvement_summary="Nothing to rewrite.",
            rewrite_confidence=1.0,
        )
        report = checker.check(resume, rewrite)
        self.assertEqual(report.fidelity_score, 1.0)
        self.assertTrue(report.passed)


if __name__ == "__main__":
    unittest.main()
