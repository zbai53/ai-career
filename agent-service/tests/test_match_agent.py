"""
Tests for MatchAgent.

All Claude API calls are mocked — no real network calls are made.
Pure-Python scoring helpers are tested directly via the private functions;
the full match() flow is tested with a mocked Anthropic client.
"""

import json
import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agents.match_agent import (
    MatchAgent,
    _compute_experience_score_base,
    _compute_keyword_score,
    _compute_skill_score,
    _compute_years_experience,
    calculate_technology_relevance,
    calculate_years_of_experience,
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


def _mock_create_side_effects(gap: str = _MOCK_GAP):
    """Return a side_effect list: [gap_response].

    Experience relevance is now pure Python; Claude is called only for gap analysis.
    """
    def _resp(text):
        r = MagicMock()
        r.content = [SimpleNamespace(text=text)]
        r.usage = SimpleNamespace(input_tokens=10, output_tokens=10)
        return r
    return [_resp(gap)]


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

    def test_skill_synonym_match(self):
        """Resume has 'JS', JD requires 'JavaScript' — synonym resolves to full match."""
        resume = _make_resume(["JS"])
        jd = _make_jd(required=["JavaScript"])
        _, matched, missing_req, _ = _compute_skill_score(resume, jd)

        assert missing_req == []
        assert "JavaScript" in matched

    def test_skill_partial_match(self):
        """'React Native' on resume gives partial credit for JD skill 'React'."""
        resume = _make_resume(["React Native"])
        jd = _make_jd(required=["React"])
        score, matched, missing_req, _ = _compute_skill_score(resume, jd)

        # weight 0.5 → required_score = 0.5/1 * 70 = 35; no preferred → full 30
        assert score == pytest.approx(65.0)
        assert "React" in matched   # weight > 0, counted as matched
        assert missing_req == []    # not completely missing


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
        """2.5 years, JD wants 3 → gap 0.5 → within 1yr short → base score 45."""
        assert _compute_experience_score_base(2.5, 3) == pytest.approx(45.0)

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

    def test_years_calculation(self):
        """2020-01 to 2023-06 is approximately 3.4 years."""
        experience = [ResumeExperience(
            company="A", title="SWE",
            start_date="2020-01", end_date="2023-06",
            is_current=False, bullets=[], technologies=[],
        )]
        years = calculate_years_of_experience(experience)
        assert 3.3 <= years <= 3.6

    def test_years_calculation_current(self):
        """A current role from 2022-01 should calculate up to today."""
        experience = [ResumeExperience(
            company="B", title="SWE",
            start_date="2022-01", end_date=None,
            is_current=True, bullets=[], technologies=[],
        )]
        years = calculate_years_of_experience(experience)
        expected = (date.today() - date(2022, 1, 1)).days / 365.25
        assert abs(years - expected) < 0.05

    def test_technology_relevance(self):
        """2 of 3 required JD skills present in experience technologies → ~0.67."""
        experience = [ResumeExperience(
            company="A", title="SWE",
            start_date="2020-01", end_date="2023-01",
            is_current=False, bullets=[],
            technologies=["Java", "Spring Boot"],
        )]
        jd_skills = [
            JDSkillRequirement(name="Java", is_required=True, category="language"),
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="Spring Boot", is_required=True, category="framework"),
        ]
        relevance = calculate_technology_relevance(experience, jd_skills)
        assert abs(relevance - 2 / 3) < 0.01


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
        result, agent_run = agent.match(resume, jd)
        assert result.skill_score >= 90

    def test_skill_score_partial_match(self, mock_cls):
        """2 of 4 required skills → score should be 35 + 30 = 65."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Python", "Docker"])
        jd = _make_jd(["Python", "Docker", "Kubernetes", "AWS"])
        result, agent_run = agent.match(resume, jd)
        assert result.skill_score == pytest.approx(65.0)

    def test_skill_score_no_match(self, mock_cls):
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Ruby", "Rails"])
        jd = _make_jd(["Java", "Python"], ["Spring Boot"])
        result, agent_run = agent.match(resume, jd)
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
        result, agent_run = agent.match(resume, jd)
        assert 55 <= result.keyword_score <= 65

    def test_experience_score_meets_requirement(self, mock_cls):
        """8+ years experience, JD wants 3 → exceeds by 2+ → years_score 70 → experience_score ≥ 70."""
        mock_cls.return_value.messages.create.side_effect = _mock_create_side_effects()
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
        result, agent_run = agent.match(resume, jd)
        assert result.experience_score >= 70

    def test_experience_score_under_requirement(self, mock_cls):
        """~2.4 years experience, JD wants 3 → within 1yr short → years_score 45, experience_score < 70."""
        mock_cls.return_value.messages.create.side_effect = _mock_create_side_effects()
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
        result, agent_run = agent.match(resume, jd)
        assert result.experience_score < 70

    def test_overall_score_weighted(self, mock_cls):
        """overall_score must equal skill*0.45 + experience*0.30 + keyword*0.25."""
        mock_cls.return_value.messages.create.side_effect = (
            _mock_create_side_effects()
        )
        agent = MatchAgent()
        resume = _make_resume(["Java", "Python"], raw_text="Java Python")
        jd = _make_jd(["Java", "Python"], [], keywords=["Java", "Python"])
        result, agent_run = agent.match(resume, jd)

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
        result, agent_run = agent.match(resume, jd)

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
        assert agent_run["agent_name"] == "match_agent"
        assert agent_run["status"] == "success"
        assert isinstance(agent_run["duration_ms"], int)
        assert isinstance(agent_run["token_count"], int)
        assert "created_at" in agent_run

    def test_ats_keywords_included_in_result(self, mock_cls):
        """
        match() must populate ats_present, ats_missing, and ats_coverage_percent.

        Uses a backend_engineer JD so _infer_ats_role maps to technology/backend_engineer
        (25 keywords in the library).  The resume raw_text contains "Python" and "Docker",
        which are both in that ATS list, so ats_present must contain them and
        ats_coverage_percent must be > 0.  ats_missing must contain keywords absent from
        the resume text.

        find_missing_keywords is pure Python (no Qdrant) — no extra mocking needed.
        """
        mock_cls.return_value.messages.create.side_effect = _mock_create_side_effects()
        agent = MatchAgent()
        resume = _make_resume(
            ["Python", "Docker"],
            raw_text="Python Docker microservices unit testing experience",
        )
        jd = _make_jd(["Python", "Docker"], keywords=["Python"])
        # Override the JD title so _infer_ats_role picks backend_engineer
        jd.title = "Backend Engineer"

        result, _ = agent.match(resume, jd)

        assert isinstance(result.ats_present, list)
        assert isinstance(result.ats_missing, list)
        assert isinstance(result.ats_coverage_percent, float)
        # "Python" and "Docker" are in the technology/backend_engineer keyword list
        assert "Python" in result.ats_present
        assert "Docker" in result.ats_present
        # There should be missing keywords (we only have a few skills in the resume)
        assert len(result.ats_missing) > 0
        # Coverage is > 0 (we matched some keywords) and < 100 (we missed most)
        assert 0.0 < result.ats_coverage_percent < 100.0
        # present + missing = total ATS keyword count for this role
        assert len(result.ats_present) + len(result.ats_missing) == 25

    def test_gap_analysis_fallback_on_bad_json(self, mock_cls):
        """If Claude returns invalid JSON twice, match() still returns a MatchResult."""
        def _bad_resp():
            r = MagicMock()
            r.content = [SimpleNamespace(text="not json {{")]
            r.usage = SimpleNamespace(input_tokens=10, output_tokens=5)
            return r

        mock_cls.return_value.messages.create.side_effect = [
            _bad_resp(),  # gap attempt 1
            _bad_resp(),  # gap attempt 2 (strict retry)
        ]
        agent = MatchAgent()
        resume = _make_resume(["Python"], raw_text="Python")
        jd = _make_jd(["Python"], keywords=["Python"])
        result, agent_run = agent.match(resume, jd)

        assert isinstance(result, MatchResult)
        assert result.overall_assessment == "Gap analysis could not be completed."
        assert result.improvement_suggestions == []
