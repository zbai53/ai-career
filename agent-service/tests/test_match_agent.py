"""
Tests for MatchAgent.

All Claude API calls are mocked — no real network calls are made.
Pure-Python scoring helpers are tested directly via the private functions;
the full match() flow is tested with a mocked Anthropic client.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agents.match_agent import (
    MatchAgent,
    _compute_experience_score_base,
    _compute_keyword_score,
    _compute_skill_score,
    _compute_years_experience,
)
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.match_result import MatchResult
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_resume(
    skills: list[str] | list[dict],
    raw_text: str = "",
    experience: list[dict] | None = None,
) -> ParsedResume:
    if skills and isinstance(skills[0], str):
        skill_objs = [ResumeSkill(name=s, category="language") for s in skills]
    else:
        skill_objs = [ResumeSkill(**s) for s in skills]  # type: ignore[arg-type]
    return ParsedResume(
        contact=ResumeContact(name="Test User"),
        skills=skill_objs,
        experience=[ResumeExperience(**e) for e in (experience or [])],
        raw_text=raw_text,
        parse_confidence=0.9,
    )


def _make_jd(
    required: list[str],
    preferred: list[str] | None = None,
    keywords: list[str] | None = None,
    min_years: int | None = None,
) -> ParsedJobDescription:
    skills = [
        JDSkillRequirement(name=s, is_required=True, category="language")
        for s in required
    ] + [
        JDSkillRequirement(name=s, is_required=False, category="language")
        for s in (preferred or [])
    ]
    return ParsedJobDescription(
        title="Software Engineer",
        skills=skills,
        keywords=keywords or [],
        min_years_experience=min_years,
        raw_text="test jd",
        parse_confidence=0.9,
    )


# Gap JSON that passes all validation in _call_gap_analysis
_MOCK_GAP = json.dumps({
    "missing_required_skills": [],
    "missing_preferred_skills": [],
    "improvement_suggestions": ["Add more details"],
    "interview_focus_areas": ["System design"],
    "overall_assessment": "Good fit.",
})

# Relevance score that CAN be parsed as float (unlike _MOCK_GAP)
_MOCK_RELEVANCE = "20"


def _mock_create_side_effects(relevance: str = _MOCK_RELEVANCE, gap: str = _MOCK_GAP):
    """Return a side_effect list: [relevance_response, gap_response]."""
    def _resp(text):
        r = MagicMock()
        r.content = [SimpleNamespace(text=text)]
        r.usage = SimpleNamespace(input_tokens=10, output_tokens=10)
        return r
    return [_resp(relevance), _resp(gap)]


# ---------------------------------------------------------------------------
# Skill score — pure Python
# ---------------------------------------------------------------------------

class TestSkillScore:
    def test_skill_score_all_match(self):
        """All required + preferred skills present → score ≈ 100."""
        resume = _make_resume(["Java", "Python", "Spring Boot"])
        jd = _make_jd(required=["Java", "Python"], preferred=["Spring Boot"])
        score, matched, missing_req, missing_pref = _compute_skill_score(resume, jd)

        assert score == pytest.approx(100.0)
        assert set(matched) == {"Java", "Python", "Spring Boot"}
        assert missing_req == []
        assert missing_pref == []

    def test_skill_score_partial_match(self):
        """2 of 4 required skills matched → required contribution = 2/4 * 70 = 35."""
        resume = _make_resume(["Python", "Docker"])
        jd = _make_jd(required=["Python", "Docker", "Kubernetes", "AWS"])
        score, matched, missing_req, _ = _compute_skill_score(resume, jd)

        # 2/4 required → 35; no preferred → full 30 credit
        assert score == pytest.approx(35.0 + 30.0)
        assert len(matched) == 2
        assert set(missing_req) == {"Kubernetes", "AWS"}

    def test_skill_score_no_match(self):
        """No required skills present → required contribution = 0."""
        resume = _make_resume(["Ruby", "Rails"])
        jd = _make_jd(required=["Java", "Python"], preferred=["Spring Boot"])
        score, _, missing_req, missing_pref = _compute_skill_score(resume, jd)

        # 0/2 required → 0; 0/1 preferred → 0
        assert score == pytest.approx(0.0)
        assert set(missing_req) == {"Java", "Python"}
        assert missing_pref == ["Spring Boot"]

    def test_synonym_counts_as_match(self):
        """k8s in resume should match 'Kubernetes' in JD."""
        resume = _make_resume(["k8s"])
        jd = _make_jd(required=["Kubernetes"])
        _, matched, missing_req, _ = _compute_skill_score(resume, jd)

        assert missing_req == []
        assert "Kubernetes" in matched

    def test_no_required_skills_gives_full_required_credit(self):
        """JD with only preferred skills → 70-point required credit is free."""
        resume = _make_resume(["Python"])
        jd = _make_jd(required=[], preferred=["Python", "Go"])
        score, _, _, missing_pref = _compute_skill_score(resume, jd)

        # 70 (free) + 1/2 * 30 = 85
        assert score == pytest.approx(85.0)
        assert "Go" in missing_pref


# ---------------------------------------------------------------------------
# Keyword score — pure Python
# ---------------------------------------------------------------------------

class TestKeywordScore:
    def test_keyword_score_three_of_five(self):
        """3 of 5 keywords found → score = 60."""
        resume = _make_resume([], raw_text="Java Spring Boot PostgreSQL experience")
        jd = _make_jd([], keywords=["Java", "Spring Boot", "PostgreSQL", "Kubernetes", "Docker"])
        score, matched_kw = _compute_keyword_score(resume, jd)

        assert score == pytest.approx(60.0)
        assert set(matched_kw) == {"Java", "Spring Boot", "PostgreSQL"}

    def test_keyword_score_case_insensitive(self):
        resume = _make_resume([], raw_text="kubernetes PYTHON terraform")
        jd = _make_jd([], keywords=["Kubernetes", "Python", "Terraform"])
        score, _ = _compute_keyword_score(resume, jd)

        assert score == pytest.approx(100.0)

    def test_keyword_score_no_keywords_in_jd(self):
        """No JD keywords → full score (nothing to miss)."""
        score, matched_kw = _compute_keyword_score(
            _make_resume([], raw_text="anything"),
            _make_jd([]),
        )
        assert score == pytest.approx(100.0)
        assert matched_kw == []


# ---------------------------------------------------------------------------
# Experience score — pure Python
# ---------------------------------------------------------------------------

class TestExperienceScore:
    def test_experience_score_meets_requirement(self):
        """5 years, JD wants 3 → base score 70."""
        assert _compute_experience_score_base(5.0, 3) == pytest.approx(70.0)

    def test_experience_score_within_one_year_short(self):
        """2.5 years, JD wants 3 → gap 0.5 → base score 50."""
        assert _compute_experience_score_base(2.5, 3) == pytest.approx(50.0)

    def test_experience_score_under_requirement(self):
        """1 year, JD wants 3 → gap 2 → base score 30."""
        assert _compute_experience_score_base(1.0, 3) == pytest.approx(30.0)

    def test_experience_score_no_jd_requirement(self):
        """No min_years_experience → neutral 60."""
        assert _compute_experience_score_base(2.0, None) == pytest.approx(60.0)

    def test_years_of_experience_calculation(self):
        """3-year job + ongoing job started 2+ years ago → total > 5 years."""
        experience = [
            {
                "company": "A", "title": "SWE",
                "start_date": "2018-01", "end_date": "2021-01",
                "is_current": False, "bullets": [], "technologies": [],
            },
            {
                "company": "B", "title": "Sr SWE",
                "start_date": "2021-01", "end_date": None,
                "is_current": True, "bullets": [], "technologies": [],
            },
        ]
        years = _compute_years_experience(_make_resume([], experience=experience))
        assert years > 5.0


# ---------------------------------------------------------------------------
# Overall score weighting — pure Python
# ---------------------------------------------------------------------------

class TestOverallScoreWeighted:
    def test_overall_score_weighted(self):
        """
        Compute the three component scores via the helpers, then verify that
        overall = skill*0.45 + experience*0.30 + keyword*0.25 holds.
        """
        resume = _make_resume(
            ["Java", "Python"],
            raw_text="Java Python",
            experience=[
                {
                    "company": "X", "title": "SWE",
                    "start_date": "2020-01", "end_date": None,
                    "is_current": True, "bullets": [], "technologies": [],
                }
            ],
        )
        jd = _make_jd(
            required=["Java", "Python"],
            preferred=[],
            keywords=["Java", "Python"],
            min_years=3,
        )

        skill_score, _, _, _ = _compute_skill_score(resume, jd)
        kw_score, _ = _compute_keyword_score(resume, jd)
        exp_base = _compute_experience_score_base(
            _compute_years_experience(resume), jd.min_years_experience
        )

        expected_overall = skill_score * 0.45 + exp_base * 0.30 + kw_score * 0.25

        assert skill_score == pytest.approx(100.0)
        assert kw_score == pytest.approx(100.0)
        assert exp_base == pytest.approx(70.0)
        assert expected_overall == pytest.approx(100 * 0.45 + 70 * 0.30 + 100 * 0.25)


# ---------------------------------------------------------------------------
# Full match() integration — with mocked Claude
# ---------------------------------------------------------------------------

@patch("app.agents.match_agent.anthropic.Anthropic")
class TestMatchAgent:

    def test_skill_score_all_match(self, mock_cls):
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Java", "Python", "Spring Boot"])
        jd = _make_jd(["Java", "Python"], ["Spring Boot"])
        result = agent.match(resume, jd)
        assert result.skill_score >= 90

    def test_skill_score_partial_match(self, mock_cls):
        """2 of 4 required skills → score should be 35 + 30 = 65."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Python", "Docker"])
        jd = _make_jd(["Python", "Docker", "Kubernetes", "AWS"])
        result = agent.match(resume, jd)
        assert result.skill_score == pytest.approx(65.0)

    def test_skill_score_no_match(self, mock_cls):
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Ruby", "Rails"])
        jd = _make_jd(["Java", "Python"], ["Spring Boot"])
        result = agent.match(resume, jd)
        assert result.skill_score <= 10

    def test_keyword_score(self, mock_cls):
        """3 of 5 JD keywords in resume text → keyword_score ≈ 60."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume([], raw_text="Java Spring Boot PostgreSQL experience")
        jd = _make_jd(
            [], [],
            keywords=["Java", "Spring Boot", "PostgreSQL", "Kubernetes", "Docker"],
        )
        result = agent.match(resume, jd)
        assert 55 <= result.keyword_score <= 65

    def test_experience_score_meets_requirement(self, mock_cls):
        """5+ years experience, JD wants 3 → experience_score ≥ 70 (base 70 + bonus)."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects(relevance="20")
        )
        agent = MatchAgent()
        resume = _make_resume(
            [],
            experience=[
                {
                    "company": "A", "title": "SWE",
                    "start_date": "2018-01", "end_date": None,
                    "is_current": True, "bullets": [], "technologies": [],
                }
            ],
        )
        jd = _make_jd([], min_years=3)
        result = agent.match(resume, jd)
        assert result.experience_score >= 70

    def test_experience_score_under_requirement(self, mock_cls):
        """~1 year experience, JD wants 3 → base 30, experience_score < 70."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects(relevance="0")
        )
        agent = MatchAgent()
        resume = _make_resume(
            [],
            experience=[
                {
                    "company": "A", "title": "SWE",
                    "start_date": "2024-01", "end_date": None,
                    "is_current": True, "bullets": [], "technologies": [],
                }
            ],
        )
        jd = _make_jd([], min_years=3)
        result = agent.match(resume, jd)
        assert result.experience_score < 70

    def test_overall_score_weighted(self, mock_cls):
        """overall_score must equal skill*0.45 + experience*0.30 + keyword*0.25."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Java", "Python"], raw_text="Java Python")
        jd = _make_jd(["Java", "Python"], [], keywords=["Java", "Python"])
        result = agent.match(resume, jd)

        expected = (
            result.skill_score * 0.45
            + result.experience_score * 0.30
            + result.keyword_score * 0.25
        )
        assert abs(result.overall_score - expected) < 0.1

    def test_gap_analysis_returns_valid_model(self, mock_cls):
        """match() must return a fully-populated MatchResult with all required fields."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Java"])
        jd = _make_jd(["Java", "Python"], ["AWS"])
        result = agent.match(resume, jd)

        assert isinstance(result, MatchResult)
        assert 0.0 <= result.overall_score <= 100.0
        assert 0.0 <= result.skill_score <= 100.0
        assert 0.0 <= result.experience_score <= 100.0
        assert 0.0 <= result.keyword_score <= 100.0
        assert isinstance(result.improvement_suggestions, list)
        assert isinstance(result.interview_focus_areas, list)
        assert isinstance(result.overall_assessment, str)
        assert isinstance(result.matched_skills, list)
        assert isinstance(result.matched_keywords, list)
        assert isinstance(result.missing_required_skills, list)
        assert isinstance(result.missing_preferred_skills, list)

    def test_gap_analysis_fallback_on_bad_json(self, mock_cls):
        """If Claude returns invalid JSON twice, match() still returns a MatchResult."""
        def _bad_resp():
            r = MagicMock()
            r.content = [SimpleNamespace(text="not json {{")]
            r.usage = SimpleNamespace(input_tokens=10, output_tokens=5)
            return r

        def _relevance_resp():
            r = MagicMock()
            r.content = [SimpleNamespace(text="15")]
            r.usage = SimpleNamespace(input_tokens=10, output_tokens=3)
            return r

        mock_cls.return_value.messages.create.side_effect = [
            _relevance_resp(),
            _bad_resp(),  # gap attempt 1
            _bad_resp(),  # gap attempt 2 (strict retry)
        ]
        agent = MatchAgent()
        resume = _make_resume(["Python"], raw_text="Python")
        jd = _make_jd(["Python"], keywords=["Python"])
        result = agent.match(resume, jd)

        assert isinstance(result, MatchResult)
        assert result.overall_assessment == "Gap analysis could not be completed."
        assert result.improvement_suggestions == []
