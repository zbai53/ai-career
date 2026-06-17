import json
import logging
import os
import re
import time
from datetime import date

import anthropic
from pydantic import ValidationError

from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.match_result import MatchResult
from app.models.resume import ParsedResume, ResumeExperience
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 2048

# ---------------------------------------------------------------------------
# Skill normalisation
# ---------------------------------------------------------------------------
# Maps every known variant (lowercased) to its canonical form.
# Canonical forms are themselves included so the dict is self-contained.

SKILL_SYNONYMS: dict[str, str] = {
    # JavaScript / TypeScript
    "js": "javascript",
    "javascript": "javascript",
    "es6": "javascript",
    "es2015": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    # Python
    "py": "python",
    "python": "python",
    "python3": "python",
    "python 3": "python",
    # Spring
    "spring": "spring boot",
    "spring boot": "spring boot",
    "springboot": "spring boot",
    "spring framework": "spring boot",
    # Kubernetes
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    # PostgreSQL
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "pg": "postgresql",
    "psql": "postgresql",
    # Node.js
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    # React
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    # MongoDB
    "mongo": "mongodb",
    "mongodb": "mongodb",
    # AWS
    "aws": "aws",
    "amazon web services": "aws",
    "amazon aws": "aws",
    # GCP
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    # Docker
    "docker": "docker",
    "containerization": "docker",
    "container": "docker",
    # CI/CD
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "continuous integration": "ci/cd",
    "continuous deployment": "ci/cd",
    "continuous delivery": "ci/cd",
    # Machine / Deep learning
    "ml": "machine learning",
    "machine learning": "machine learning",
    "dl": "deep learning",
    "deep learning": "deep learning",
    # Azure
    "azure": "azure",
    "microsoft azure": "azure",
    # Terraform
    "terraform": "terraform",
    "infrastructure as code": "terraform",
    "iac": "terraform",
    # Vue
    "vue": "vue",
    "vuejs": "vue",
    "vue.js": "vue",
    # Angular
    "angular": "angular",
    "angularjs": "angular",
    "angular.js": "angular",
    # Artificial intelligence
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    # NLP
    "nlp": "nlp",
    "natural language processing": "nlp",
    # LLM
    "llm": "llm",
    "llms": "llm",
    "large language model": "llm",
    "large language models": "llm",
    # Go
    "go": "go",
    "golang": "go",
    # Ruby on Rails
    "rails": "rails",
    "ror": "rails",
    "ruby on rails": "rails",
    # .NET
    ".net": ".net",
    "dotnet": ".net",
    "asp.net": ".net",
    "dot net": ".net",
    # C#
    "c#": "c#",
    "csharp": "c#",
    "c sharp": "c#",
    # Elasticsearch
    "elasticsearch": "elasticsearch",
    "elastic search": "elasticsearch",
    "opensearch": "elasticsearch",
    # DynamoDB
    "dynamodb": "dynamodb",
    "dynamo": "dynamodb",
    "dynamo db": "dynamodb",
    # GraphQL
    "graphql": "graphql",
    "gql": "graphql",
    # REST
    "rest": "rest api",
    "rest api": "rest api",
    "restful": "rest api",
    "restful api": "rest api",
    "rest apis": "rest api",
    # gRPC
    "grpc": "grpc",
    # Apache Spark
    "spark": "apache spark",
    "apache spark": "apache spark",
    # TensorFlow
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    # PyTorch
    "pytorch": "pytorch",
    "torch": "pytorch",
    # scikit-learn
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    # Redis
    "redis": "redis",
    # Kafka
    "kafka": "kafka",
    "apache kafka": "kafka",
    # Helm
    "helm": "helm",
    # Ansible
    "ansible": "ansible",
    # Git
    "git": "git",
    "github": "git",
    "gitlab": "git",
    "bitbucket": "git",
    # Linux / Bash
    "linux": "linux",
    "unix": "linux",
    "bash": "bash",
    "shell scripting": "bash",
    "shell": "bash",
    # OAuth / Auth
    "oauth": "oauth",
    "oauth2": "oauth",
    "oidc": "oauth",
    # Microservices
    "microservices": "microservices",
    "micro services": "microservices",
    "micro-services": "microservices",
    # Distributed systems
    "distributed systems": "distributed systems",
    "distributed computing": "distributed systems",
    # Agile / Scrum
    "agile": "agile",
    "scrum": "agile",
    "kanban": "agile",
    # React Native
    "react native": "react native",
    "rn": "react native",
    # Hugging Face
    "hugging face": "hugging face",
    "huggingface": "hugging face",
    # Data engineering
    "apache airflow": "apache airflow",
    "airflow": "apache airflow",
    "dbt": "dbt",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "google bigquery": "bigquery",
    "redshift": "redshift",
    "amazon redshift": "redshift",
}


def normalize_skill(name: str) -> str:
    """
    Return the canonical form of a skill name.

    Steps:
    1. Lowercase and strip whitespace.
    2. Look up in SKILL_SYNONYMS; return canonical if found.
    3. Otherwise return the lowercased name as-is.
    """
    key = name.strip().lower()
    return SKILL_SYNONYMS.get(key, key)


def _word_contained(shorter: str, longer: str) -> bool:
    """
    True when *shorter* appears as a complete token inside *longer*.
    Uses a word-boundary regex so "java" does NOT match inside "javascript",
    but "react" DOES match inside "react native".
    """
    pattern = r"(?<![a-z0-9])" + re.escape(shorter) + r"(?![a-z0-9])"
    return bool(re.search(pattern, longer))


def _skill_match_weight(resume_skill: str, jd_skill: str) -> float:
    """
    Return a match weight between a resume skill and a JD skill:

    1.0  — exact match after normalisation (includes synonym resolution)
    0.5  — one normalised name is a whole-word token within the other
           (partial / specialisation match, e.g. "React Native" contains "React")
    0.0  — no relationship

    Examples:
      "k8s" vs "Kubernetes"      → 1.0  (both normalise to "kubernetes")
      "React Native" vs "React"  → 0.5  (whole token "react" in "react native")
      "Java" vs "JavaScript"     → 0.0  ("java" is NOT a whole token in "javascript")
    """
    r = normalize_skill(resume_skill)
    j = normalize_skill(jd_skill)

    if r == j:
        return 1.0

    # Partial / containment match — require whole-word boundary and len ≥ 3
    # to avoid spurious matches (e.g. "go" matching "django").
    if len(r) >= 3 and len(j) >= 3 and (
        _word_contained(r, j) or _word_contained(j, r)
    ):
        return 0.5

    return 0.0


def _compute_skill_score(
    resume: ParsedResume,
    jd: ParsedJobDescription,
) -> tuple[float, list[str], list[str], list[str]]:
    """
    Returns (skill_score, matched_skills, missing_required, missing_preferred).

    Scoring uses weighted match values:
      exact match   → weight 1.0
      partial match → weight 0.5
      no match      → weight 0.0

    required  contribution: sum(weights) / total_required * 70
    preferred contribution: sum(weights) / total_preferred * 30

    Skills with weight > 0 appear in *matched_skills*.
    Skills with weight == 0 appear in the corresponding missing list.
    """
    resume_skill_names = [s.name for s in resume.skills]

    required_skills = [s for s in jd.skills if s.is_required]
    preferred_skills = [s for s in jd.skills if not s.is_required]

    matched: list[str] = []
    missing_required: list[str] = []
    missing_preferred: list[str] = []

    def _best_weight(jd_skill_name: str) -> float:
        """Highest match weight across all resume skills for this JD skill."""
        return max(
            (_skill_match_weight(r, jd_skill_name) for r in resume_skill_names),
            default=0.0,
        )

    required_weight_sum = 0.0
    for skill in required_skills:
        w = _best_weight(skill.name)
        required_weight_sum += w
        if w > 0:
            matched.append(skill.name)
        else:
            missing_required.append(skill.name)

    preferred_weight_sum = 0.0
    for skill in preferred_skills:
        w = _best_weight(skill.name)
        preferred_weight_sum += w
        if w > 0:
            matched.append(skill.name)
        else:
            missing_preferred.append(skill.name)

    required_score = (
        required_weight_sum / len(required_skills) * 70
        if required_skills
        else 70.0  # no required skills → full required credit
    )
    preferred_score = (
        preferred_weight_sum / len(preferred_skills) * 30
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


def calculate_years_of_experience(experience: list[ResumeExperience]) -> float:
    """
    Total years of non-overlapping work experience.

    Parses YYYY-MM start/end dates, substitutes today for is_current=True or
    missing end_date, then merges overlapping intervals before summing durations.
    Returns total years as a float (e.g. 2.5).
    """
    today = date.today()
    intervals: list[tuple[date, date]] = []

    for exp in experience:
        start = _parse_date(exp.start_date)
        if start is None:
            continue
        if exp.is_current or exp.end_date is None:
            end = today
        else:
            end = _parse_date(exp.end_date)
            if end is None:
                end = today
        if end > start:
            intervals.append((start, end))

    if not intervals:
        return 0.0

    # Sort by start date then merge overlapping intervals
    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[date, date]] = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:          # overlapping or adjacent
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days for start, end in merged)
    return total_days / 365.25


def _compute_years_experience(resume: ParsedResume) -> float:
    """Backward-compatible wrapper around calculate_years_of_experience."""
    return calculate_years_of_experience(resume.experience)


def calculate_technology_relevance(
    resume_experience: list[ResumeExperience],
    jd_skills: list[JDSkillRequirement],
) -> float:
    """
    Fraction of JD required skills that appear in any experience's technologies.

    Returns 0.0 when there are no required skills (no relevance bonus applies).
    Returns a value in [0.0, 1.0] otherwise.
    """
    required_skills = [s for s in jd_skills if s.is_required]
    if not required_skills:
        return 0.0

    # Collect all normalised technology names across all experience entries
    known_techs: set[str] = set()
    for exp in resume_experience:
        for tech in exp.technologies:
            known_techs.add(normalize_skill(tech))

    matched = sum(
        1 for skill in required_skills
        if normalize_skill(skill.name) in known_techs
    )
    return matched / len(required_skills)


def _compute_experience_score_base(years: float, min_required: int | None) -> float:
    """
    Years-based experience score (0-70) against the JD minimum.

    gap = min_required - years:
      gap ≤ -2          (exceeds by 2+ years)  → 70
      -2 < gap ≤  0     (meets requirement)     → 60
       0 < gap ≤  1     (≤1 year short)         → 45
       1 < gap ≤  2     (1-2 years short)       → 30
       gap >  2         (>2 years short)         → 15
      no JD requirement                          → 60 (neutral)
    """
    if min_required is None:
        return 60.0
    gap = min_required - years
    if gap <= -2.0:
        return 70.0
    if gap <= 0.0:
        return 60.0
    if gap <= 1.0:
        return 45.0
    if gap <= 2.0:
        return 30.0
    return 15.0


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
        self._token_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, resume: ParsedResume, jd: ParsedJobDescription) -> tuple[MatchResult, dict]:
        """
        Score a resume against a job description.

        Returns:
            (MatchResult, agent_run_log)
        """
        self._token_count = 0
        t0 = time.perf_counter()

        # --- Dimension 1: skill score (pure Python) ---
        skill_score, matched_skills, missing_required, missing_preferred = (
            _compute_skill_score(resume, jd)
        )

        # --- Dimension 2: experience score (pure Python) ---
        years = calculate_years_of_experience(resume.experience)
        years_score = _compute_experience_score_base(years, jd.min_years_experience)
        relevance = calculate_technology_relevance(resume.experience, jd.skills)
        experience_score = min(100.0, years_score + relevance * 30.0)

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

        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "Match completed in %d ms — overall=%.1f skill=%.1f exp=%.1f kw=%.1f",
            duration_ms, overall_score, skill_score, experience_score, keyword_score,
        )

        result = MatchResult(
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

        agent_run = log_agent_run(
            agent_name="match_agent",
            input_summary=f"resume skills={len(resume.skills)}, jd={jd.title}",
            output_summary=f"overall={result.overall_score}, skill={result.skill_score}",
            status="success",
            duration_ms=duration_ms,
            token_count=self._token_count,
            model_name=_MODEL,
        )
        return result, agent_run

    # ------------------------------------------------------------------
    # Claude helpers
    # ------------------------------------------------------------------

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
                self._token_count += response.usage.input_tokens + response.usage.output_tokens
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
