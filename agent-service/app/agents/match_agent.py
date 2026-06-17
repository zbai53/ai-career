import json
import logging
import os
import time
from datetime import date

import anthropic
from pydantic import ValidationError

from app.models.job_description import ParsedJobDescription
from app.models.match_result import MatchResult
from app.models.resume import ParsedResume

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 2048

# Common synonyms for skill matching: each tuple is a group of equivalent terms.
# If a resume has any term in a group and the JD requires any term in the same
# group, it counts as a match.
_SKILL_SYNONYMS: list[frozenset[str]] = [
    frozenset({"javascript", "js"}),
    frozenset({"typescript", "ts"}),
    frozenset({"postgresql", "postgres", "psql"}),
    frozenset({"kubernetes", "k8s"}),
    frozenset({"amazon web services", "aws"}),
    frozenset({"google cloud platform", "gcp", "google cloud"}),
    frozenset({"microsoft azure", "azure"}),
    frozenset({"machine learning", "ml"}),
    frozenset({"artificial intelligence", "ai"}),
    frozenset({"continuous integration", "ci", "ci/cd", "continuous deployment", "cd"}),
    frozenset({"react", "reactjs", "react.js"}),
    frozenset({"vue", "vuejs", "vue.js"}),
    frozenset({"node", "nodejs", "node.js"}),
    frozenset({"spring", "spring boot", "spring framework"}),
    frozenset({"natural language processing", "nlp"}),
    frozenset({"large language model", "llm", "large language models", "llms"}),
]


def _canonical(name: str) -> str:
    """Lowercase and strip whitespace for comparison."""
    return name.strip().lower()


def _synonym_group(name: str) -> frozenset[str] | None:
    """Return the synonym group containing *name*, or None."""
    key = _canonical(name)
    for group in _SKILL_SYNONYMS:
        if key in group:
            return group
    return None


def _skills_match(resume_skill: str, jd_skill: str) -> bool:
    """True when two skill names are equivalent (exact or synonym)."""
    r, j = _canonical(resume_skill), _canonical(jd_skill)
    if r == j:
        return True
    r_group = _synonym_group(r)
    j_group = _synonym_group(j)
    if r_group is not None and j_group is not None and r_group == j_group:
        return True
    return False


def _compute_skill_score(
    resume: ParsedResume,
    jd: ParsedJobDescription,
) -> tuple[float, list[str], list[str], list[str]]:
    """
    Returns (skill_score, matched_skills, missing_required, missing_preferred).

    Scoring:
      required  contribution: matched_required / total_required * 70
      preferred contribution: matched_preferred / total_preferred * 30
    """
    resume_skill_names = [s.name for s in resume.skills]

    required_skills = [s for s in jd.skills if s.is_required]
    preferred_skills = [s for s in jd.skills if not s.is_required]

    matched: list[str] = []
    missing_required: list[str] = []
    missing_preferred: list[str] = []

    def _find_in_resume(jd_skill_name: str) -> bool:
        return any(_skills_match(r, jd_skill_name) for r in resume_skill_names)

    for skill in required_skills:
        if _find_in_resume(skill.name):
            matched.append(skill.name)
        else:
            missing_required.append(skill.name)

    for skill in preferred_skills:
        if _find_in_resume(skill.name):
            matched.append(skill.name)
        else:
            missing_preferred.append(skill.name)

    required_score = (
        (len(required_skills) - len(missing_required)) / len(required_skills) * 70
        if required_skills
        else 70.0  # no required skills → full required credit
    )
    preferred_score = (
        (len(preferred_skills) - len(missing_preferred)) / len(preferred_skills) * 30
        if preferred_skills
        else 30.0  # no preferred skills → full preferred credit
    )

    return required_score + preferred_score, matched, missing_required, missing_preferred


def _parse_date(date_str: str | None) -> date | None:
    """Parse YYYY-MM into a date object (day=1). Returns None on failure."""
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        return date(year, month, 1)
    except (ValueError, IndexError):
        return None


def _compute_years_experience(resume: ParsedResume) -> float:
    """Sum the calendar duration of all non-overlapping experience entries."""
    today = date.today()
    total_days = 0
    for exp in resume.experience:
        start = _parse_date(exp.start_date)
        if start is None:
            continue
        end = today if exp.is_current or exp.end_date is None else _parse_date(exp.end_date)
        if end is None:
            end = today
        delta = (end - start).days
        if delta > 0:
            total_days += delta
    return total_days / 365.25


def _compute_experience_score_base(years: float, min_required: int | None) -> float:
    """
    Base experience score (0-70) based on years vs JD minimum.

    ≥ min_required        → 70
    within 1 year short   → 50
    > 1 year short        → 30
    no JD requirement     → 60 (neutral)
    """
    if min_required is None:
        return 60.0
    gap = min_required - years
    if gap <= 0:
        return 70.0
    if gap <= 1.0:
        return 50.0
    return 30.0


def _compute_keyword_score(
    resume: ParsedResume,
    jd: ParsedJobDescription,
) -> tuple[float, list[str]]:
    """
    Returns (keyword_score 0-100, list_of_matched_keywords).
    Case-insensitive substring search in resume.raw_text.
    """
    if not jd.keywords:
        return 100.0, []

    raw_lower = resume.raw_text.lower()
    matched = [kw for kw in jd.keywords if kw.lower() in raw_lower]
    score = len(matched) / len(jd.keywords) * 100
    return score, matched


_GAP_ANALYSIS_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "missing_required_skills": {"type": "array", "items": {"type": "string"}},
            "missing_preferred_skills": {"type": "array", "items": {"type": "string"}},
            "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
            "interview_focus_areas": {"type": "array", "items": {"type": "string"}},
            "overall_assessment": {"type": "string"},
        },
        "required": [
            "missing_required_skills",
            "missing_preferred_skills",
            "improvement_suggestions",
            "interview_focus_areas",
            "overall_assessment",
        ],
    },
    indent=2,
)

_GAP_SYSTEM_PROMPT = f"""\
You are a senior technical recruiter and career coach. You will be given:
1. A candidate's parsed resume (JSON)
2. A parsed job description (JSON)
3. Pre-computed match scores

Your task: return ONLY a single valid JSON object matching the schema below.
No prose, no markdown fences, no extra keys.

SCHEMA:
{_GAP_ANALYSIS_SCHEMA}

RULES:
- missing_required_skills / missing_preferred_skills: list only skills that are
  genuinely absent from the resume, using the exact skill names from the JD.
- improvement_suggestions: 3-5 specific, actionable suggestions for how the
  candidate can rewrite or augment their resume bullets to better target this JD.
  Focus on language, keyword injection, and quantification — not fabrication.
- interview_focus_areas: 3-5 topics the candidate should study or practise given
  the gap between their background and this role.
- overall_assessment: 2-3 sentences summarising the match quality, the strongest
  alignment, and the most critical gap.\
"""


class MatchParseError(Exception):
    pass


class MatchAgent:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, resume: ParsedResume, jd: ParsedJobDescription) -> MatchResult:
        t0 = time.perf_counter()

        # --- Dimension 1: skill score (pure Python) ---
        skill_score, matched_skills, missing_required, missing_preferred = (
            _compute_skill_score(resume, jd)
        )

        # --- Dimension 2: experience score (base in Python, bonus via Claude) ---
        years = _compute_years_experience(resume)
        base_exp_score = _compute_experience_score_base(years, jd.min_years_experience)

        # Relevance bonus (0-30): Claude evaluates industry/technology alignment.
        relevance_bonus = self._call_experience_relevance(resume, jd, years)
        experience_score = min(100.0, base_exp_score + relevance_bonus)

        # --- Dimension 3: keyword score (pure Python) ---
        keyword_score, matched_kw = _compute_keyword_score(resume, jd)

        # --- Weighted overall ---
        overall_score = (
            skill_score * 0.45
            + experience_score * 0.30
            + keyword_score * 0.25
        )

        # --- Gap analysis via Claude ---
        gap = self._call_gap_analysis(
            resume, jd, skill_score, experience_score, keyword_score,
            missing_required, missing_preferred,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Match completed in %.0f ms — overall=%.1f skill=%.1f exp=%.1f kw=%.1f",
            elapsed_ms, overall_score, skill_score, experience_score, keyword_score,
        )

        return MatchResult(
            overall_score=round(overall_score, 2),
            skill_score=round(skill_score, 2),
            experience_score=round(experience_score, 2),
            keyword_score=round(keyword_score, 2),
            missing_required_skills=gap.get("missing_required_skills", missing_required),
            missing_preferred_skills=gap.get("missing_preferred_skills", missing_preferred),
            improvement_suggestions=gap.get("improvement_suggestions", []),
            interview_focus_areas=gap.get("interview_focus_areas", []),
            overall_assessment=gap.get("overall_assessment", ""),
            matched_skills=matched_skills,
            matched_keywords=matched_kw,
        )

    # ------------------------------------------------------------------
    # Claude helpers
    # ------------------------------------------------------------------

    def _call_experience_relevance(
        self,
        resume: ParsedResume,
        jd: ParsedJobDescription,
        actual_years: float,
    ) -> float:
        """
        Ask Claude to rate how relevant the candidate's experience is to this
        specific JD (industry, technology stack, domain). Returns 0-30.
        """
        prompt = (
            f"A candidate has {actual_years:.1f} years of experience.\n\n"
            f"Their experience roles:\n"
            + "\n".join(
                f"- {e.title} at {e.company} ({', '.join(e.technologies[:5])})"
                for e in resume.experience
            )
            + f"\n\nJob description industry: {jd.industry or 'not specified'}\n"
            f"JD required skills: {', '.join(s.name for s in jd.skills if s.is_required)}\n\n"
            "Rate the RELEVANCE of the candidate's experience to this specific role on a scale "
            "of 0-30 (0 = completely unrelated field, 30 = perfect domain and tech-stack match). "
            "Return ONLY a single integer between 0 and 30, nothing else."
        )

        try:
            t0 = time.perf_counter()
            response = self._client.messages.create(
                model=_MODEL,
                max_tokens=16,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.debug("Relevance call: %.0f ms", elapsed_ms)
            raw = response.content[0].text.strip()
            bonus = float(raw)
            return max(0.0, min(30.0, bonus))
        except Exception as exc:
            logger.warning("Experience relevance call failed (%s); defaulting to 15", exc)
            return 15.0

    def _call_gap_analysis(
        self,
        resume: ParsedResume,
        jd: ParsedJobDescription,
        skill_score: float,
        experience_score: float,
        keyword_score: float,
        missing_required: list[str],
        missing_preferred: list[str],
    ) -> dict:
        """
        Send resume + JD + pre-computed scores to Claude and return the gap
        analysis dict. Falls back to a minimal dict on failure.
        """
        user_content = (
            "RESUME (JSON):\n"
            + resume.model_dump_json(indent=2)
            + "\n\nJOB DESCRIPTION (JSON):\n"
            + jd.model_dump_json(indent=2)
            + f"\n\nPRE-COMPUTED SCORES:\n"
            f"  skill_score={skill_score:.1f}/100\n"
            f"  experience_score={experience_score:.1f}/100\n"
            f"  keyword_score={keyword_score:.1f}/100\n"
            f"  missing_required_skills={missing_required}\n"
            f"  missing_preferred_skills={missing_preferred}\n"
        )

        for attempt, strict in enumerate([False, True]):
            if strict:
                user_content += (
                    "\n\nIMPORTANT: Your previous response could not be parsed. "
                    "Return ONLY the raw JSON object — no prose, no markdown fences."
                )
            try:
                t0 = time.perf_counter()
                response = self._client.messages.create(
                    model=_MODEL,
                    max_tokens=_MAX_TOKENS,
                    system=_GAP_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content}],
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    "Gap analysis call %d: %.0f ms | in=%d out=%d",
                    attempt + 1,
                    elapsed_ms,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )

                raw = response.content[0].text.strip()
                if raw.startswith("```"):
                    raw = "\n".join(
                        line for line in raw.splitlines() if not line.startswith("```")
                    ).strip()

                data = json.loads(raw)
                # Validate required keys are present
                for key in ("improvement_suggestions", "interview_focus_areas", "overall_assessment"):
                    if key not in data:
                        raise ValueError(f"Missing key: {key}")
                return data

            except (json.JSONDecodeError, ValueError) as exc:
                if strict:
                    logger.error("Gap analysis failed after retry: %s", exc)
                    break
                logger.warning("Gap analysis attempt 1 failed (%s), retrying", exc)

        # Fallback — return minimal structure so match() always succeeds
        return {
            "missing_required_skills": missing_required,
            "missing_preferred_skills": missing_preferred,
            "improvement_suggestions": [],
            "interview_focus_areas": [],
            "overall_assessment": "Gap analysis could not be completed.",
        }
