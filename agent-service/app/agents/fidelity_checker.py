"""
FidelityChecker — prevents hallucination in rewritten resume bullets.

Two-layer entity extraction:
  1. Rule-based  — regex for dates, numbers/metrics, and a curated 50+ term
     technology vocabulary.  Always runs; no network needed.
  2. Claude-assisted — extracts company names and job titles that are hard to
     catch with regex.  Runs after rule-based; gracefully degrades if Claude
     is unavailable.

Comparison is case-insensitive and uses tech-synonym normalisation so that
"React", "ReactJS", and "React.js" are treated as the same entity.

Action verbs (Built, Developed, Led, …) are explicitly excluded from flagging
— changing a verb is stylistic, not a factual invention.

Severity:
  HIGH   — new company name, new job title, new degree/institution
  MEDIUM — new technology claim, new unverified metric
  LOW    — rephrased responsibility, reasonable contextual inference

Scoring:
  fidelity_score = 1.0 - (weighted_new / weighted_total_rw)
  Weights: high=3, medium=2, low=1.  Clamped to [0.0, 1.0].
  Passes when score >= threshold (default 0.85).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

import anthropic
from pydantic import BaseModel, Field

from app.models.fidelity_report import FidelityFlag, FidelityReport, _DEFAULT_THRESHOLD
from app.models.resume import ParsedResume
from app.models.rewrite_result import RewriteResult

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Severity weights (used for weighted fidelity scoring)
# ---------------------------------------------------------------------------

_SEVERITY: dict[str, str] = {
    "company":    "high",
    "title":      "high",
    "education":  "high",
    "date":       "high",
    "metric":     "medium",
    "technology": "medium",
    "context":    "low",
}

_SEVERITY_WEIGHT: dict[str, int] = {
    "high":   3,
    "medium": 2,
    "low":    1,
}

# ---------------------------------------------------------------------------
# Action verbs — changing these is ALLOWED (stylistic, not factual)
# ---------------------------------------------------------------------------

_ACTION_VERBS: frozenset[str] = frozenset({
    "accelerated", "achieved", "administered", "advanced", "architected",
    "automated", "built", "championed", "collaborated", "completed",
    "contributed", "coordinated", "created", "defined", "delivered",
    "demonstrated", "deployed", "designed", "developed", "devised",
    "directed", "drove", "enabled", "engineered", "established",
    "evaluated", "executed", "expanded", "facilitated", "founded",
    "generated", "guided", "implemented", "improved", "increased",
    "initiated", "integrated", "introduced", "launched", "led",
    "maintained", "managed", "mentored", "migrated", "modernised",
    "modernized", "monitored", "optimised", "optimized", "orchestrated",
    "oversaw", "owned", "partnered", "piloted", "planned", "produced",
    "proposed", "provided", "published", "reduced", "refactored",
    "replaced", "researched", "resolved", "reviewed", "scaled",
    "shipped", "simplified", "spearheaded", "standardised", "standardized",
    "streamlined", "supported", "transformed", "upgraded", "validated",
    "worked", "wrote",
})

# ---------------------------------------------------------------------------
# Technology vocabulary — canonical → set of known aliases (all lower-case)
# ---------------------------------------------------------------------------

_TECH_CANONICAL: dict[str, set[str]] = {
    "python":         {"python", "python3", "py"},
    "javascript":     {"javascript", "js", "es6", "es2015", "ecmascript"},
    "typescript":     {"typescript", "ts"},
    "java":           {"java"},
    "go":             {"go", "golang"},
    "rust":           {"rust"},
    "c++":            {"c++", "cpp", "c plus plus"},
    "c#":             {"c#", "csharp", "c sharp", "dotnet c#"},
    "ruby":           {"ruby"},
    "swift":          {"swift"},
    "kotlin":         {"kotlin"},
    "scala":          {"scala"},
    "r":              {"r language", "r programming"},
    "php":            {"php"},
    "react":          {"react", "reactjs", "react.js", "react js"},
    "angular":        {"angular", "angularjs", "angular.js"},
    "vue":            {"vue", "vuejs", "vue.js"},
    "next.js":        {"next.js", "nextjs", "next js"},
    "node.js":        {"node.js", "nodejs", "node js", "node"},
    "django":         {"django"},
    "flask":          {"flask"},
    "fastapi":        {"fastapi", "fast api"},
    "spring boot":    {"spring boot", "springboot", "spring framework", "spring"},
    "rails":          {"rails", "ruby on rails", "ror"},
    ".net":           {".net", "dotnet", "asp.net", "dot net"},
    "express":        {"express", "express.js", "expressjs"},
    "pytorch":        {"pytorch", "torch"},
    "tensorflow":     {"tensorflow", "tf"},
    "scikit-learn":   {"scikit-learn", "sklearn", "scikit learn"},
    "langchain":      {"langchain"},
    "langgraph":      {"langgraph"},
    "postgresql":     {"postgresql", "postgres", "pg", "psql"},
    "mysql":          {"mysql"},
    "mongodb":        {"mongodb", "mongo"},
    "redis":          {"redis"},
    "elasticsearch":  {"elasticsearch", "elastic search", "opensearch"},
    "dynamodb":       {"dynamodb", "dynamo", "dynamo db"},
    "sqlite":         {"sqlite", "sqlite3"},
    "cassandra":      {"cassandra", "apache cassandra"},
    "snowflake":      {"snowflake"},
    "bigquery":       {"bigquery", "google bigquery"},
    "redshift":       {"redshift", "amazon redshift"},
    "aws":            {"aws", "amazon web services"},
    "gcp":            {"gcp", "google cloud", "google cloud platform"},
    "azure":          {"azure", "microsoft azure"},
    "docker":         {"docker"},
    "kubernetes":     {"kubernetes", "k8s"},
    "terraform":      {"terraform"},
    "ansible":        {"ansible"},
    "helm":           {"helm"},
    "kafka":          {"kafka", "apache kafka"},
    "spark":          {"spark", "apache spark"},
    "airflow":        {"airflow", "apache airflow"},
    "dbt":            {"dbt"},
    "git":            {"git", "github", "gitlab", "bitbucket"},
    "graphql":        {"graphql", "gql"},
    "grpc":           {"grpc"},
    "rest":           {"rest", "rest api", "restful", "restful api"},
    "ci/cd":          {"ci/cd", "cicd", "continuous integration", "continuous deployment"},
    "linux":          {"linux", "unix", "ubuntu", "centos", "debian"},
    "bash":           {"bash", "shell", "shell scripting", "zsh"},
    "microservices":  {"microservices", "micro services", "micro-services"},
    "qdrant":         {"qdrant"},
    "pinecone":       {"pinecone"},
    "weaviate":       {"weaviate"},
    "openai":         {"openai"},
    "anthropic":      {"anthropic"},
    "hugging face":   {"hugging face", "huggingface"},
    "oauth":          {"oauth", "oauth2", "oidc"},
    "jwt":            {"jwt", "json web token"},
}

# Reverse map: alias → canonical (all lower-case)
_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in _TECH_CANONICAL.items()
    for alias in aliases
}


def normalize_tech(name: str) -> str:
    """Return canonical technology name, or the lowercased original if unknown."""
    key = name.strip().lower()
    return _ALIAS_TO_CANONICAL.get(key, key)


# ---------------------------------------------------------------------------
# Rule-based extraction
# ---------------------------------------------------------------------------

# Dates: 2020, 2020-01, 01/2020, Jan 2020, January 2020, Present, Current
_DATE_RE = re.compile(
    r"\b(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\.?\s+(?:19|20)\d{2}"      # Jan 2020, Feb. 2019
    r"|(?:19|20)\d{2}-\d{2}"     # 2020-01
    r"|\d{2}/(?:19|20)\d{2}"     # 01/2020
    r"|\b(?:19|20)\d{2}\b"       # 2020
    r"|Present|Current"           # open-ended roles
    r")",
    re.IGNORECASE,
)

# Metrics: 50%, $1.2M, $120K, 1M+, 10K users, 3x, 99.9%, #1, 1,000
_METRIC_RE = re.compile(
    r"(?:"
    r"\$\s*[\d,]+(?:\.\d+)?\s*[KkMmBb]?\+?"    # $1.2M, $120K, $500+
    r"|[\d,]+(?:\.\d+)?\s*[KkMmBb]\+?\b"        # 50K, 1.2M, 1M+
    r"|[\d,]+(?:\.\d+)?\s*%"                     # 20%, 99.9%
    r"|\d+(?:\.\d+)?\s*x\b"                      # 3x, 10x
    r"|#\s*\d+"                                   # #1, #3
    r"|\b\d{1,3}(?:,\d{3})+\b"                  # 1,000  10,000
    r")"
)

# Approximate quantifiers that should be treated as MEDIUM severity when new
# (they add a metric but hedge it, so less severe than a hard number)
_APPROX_QUALIFIER_RE = re.compile(
    r"\b(?:approximately|roughly|nearly|about|around|over|more than|up to|"
    r"at least|almost|~)\b",
    re.IGNORECASE,
)


def _extract_dates_rule(text: str) -> set[str]:
    return {m.group().strip().lower() for m in _DATE_RE.finditer(text)}


def _extract_metrics_rule(text: str) -> set[str]:
    return {m.group().strip() for m in _METRIC_RE.finditer(text)}


def _extract_technologies_rule(text: str) -> set[str]:
    """
    Scan text for known technology aliases from _ALIAS_TO_CANONICAL.
    Returns canonical names only, so synonyms are deduplicated.
    Uses word-boundary matching to avoid false positives (e.g. 'R' in 'React').
    """
    found: set[str] = set()
    text_lower = text.lower()

    for alias, canonical in _ALIAS_TO_CANONICAL.items():
        # Skip very short aliases (single char) without explicit word boundaries
        if len(alias) <= 1:
            continue
        # Use a word-boundary pattern; escape dots and special chars
        pattern = r"(?<![a-z0-9#.])" + re.escape(alias) + r"(?![a-z0-9#.])"
        if re.search(pattern, text_lower):
            found.add(canonical)
    return found


def _normalize_set(s: set[str]) -> set[str]:
    return {v.lower().strip() for v in s if v.strip()}


# ---------------------------------------------------------------------------
# ExtractedEntities model (public API)
# ---------------------------------------------------------------------------


class ExtractedEntities(BaseModel):
    companies:     set[str] = Field(default_factory=set)
    titles:        set[str] = Field(default_factory=set)
    dates:         set[str] = Field(default_factory=set)
    technologies:  set[str] = Field(default_factory=set)
    metrics:       set[str] = Field(default_factory=set)
    education:     set[str] = Field(default_factory=set)
    certifications: set[str] = Field(default_factory=set)

    model_config = {"arbitrary_types_allowed": True}

    def all_entities(self) -> set[str]:
        return (
            self.companies | self.titles | self.dates
            | self.technologies | self.metrics
            | self.education | self.certifications
        )


# ---------------------------------------------------------------------------
# Aggregate text helpers
# ---------------------------------------------------------------------------


def _resume_all_text(resume: ParsedResume) -> str:
    parts: list[str] = [resume.raw_text]
    for exp in resume.experience:
        parts.append(exp.company)
        parts.append(exp.title)
        parts.extend(exp.bullets)
        parts.extend(exp.technologies)
    for edu in resume.education:
        parts.append(edu.institution)
        parts.append(edu.degree)
        parts.append(edu.field_of_study)
    for cert in resume.certifications:
        parts.append(cert.name)
        parts.append(cert.issuer)
    for skill in resume.skills:
        parts.append(skill.name)
    for proj in resume.projects:
        parts.append(proj.name)
        parts.extend(proj.technologies)
    return " ".join(p for p in parts if p)


def _rewrite_all_bullets(rewrite_result: RewriteResult) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for exp in rewrite_result.experiences:
        for rb in exp.rewritten_bullets:
            out.append((rb.rewritten, f"{exp.company} / {exp.title}"))
    return out


# ---------------------------------------------------------------------------
# Claude-assisted extraction (companies and job titles only)
# ---------------------------------------------------------------------------

_ENTITY_SYSTEM_PROMPT = """\
You are an entity extraction engine. Extract named entities from the given text.

Return ONLY a valid JSON object with exactly these keys — no prose, no markdown fences:
{
  "companies":  ["<name>", ...],
  "job_titles": ["<title>", ...]
}

Rules:
- companies: employer and organisation names (including universities, schools)
- job_titles: formal role names (Software Engineer, VP of Engineering, …)
- Do NOT include generic words like "team", "project", "system", "platform"
- Do NOT include technology names (those are handled separately)
- Return empty lists when nothing applies.\
"""


def _call_claude_entities(client: anthropic.Anthropic, text: str) -> dict[str, list[str]]:
    try:
        t0 = time.perf_counter()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_ENTITY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:8000]}],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Claude entity extraction: %.0f ms | in=%d out=%d",
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
        return {
            "companies":  [str(x) for x in data.get("companies", [])],
            "job_titles": [str(x) for x in data.get("job_titles", [])],
        }
    except Exception as exc:
        logger.warning("Claude entity extraction failed (degraded mode): %s", exc)
        return {"companies": [], "job_titles": []}


# ---------------------------------------------------------------------------
# FidelityChecker
# ---------------------------------------------------------------------------


class FidelityChecker:
    def __init__(self, threshold: float = _DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self._client: Optional[anthropic.Anthropic] = anthropic.Anthropic(api_key=api_key)
        else:
            logger.warning(
                "ANTHROPIC_API_KEY not set — FidelityChecker running in rule-based-only mode"
            )
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_entities(self, text: str) -> ExtractedEntities:
        """
        Extract all entity types from a block of text using rule-based extraction
        only (no Claude call).  Use this for inspecting what the checker sees.
        """
        return ExtractedEntities(
            companies=set(),       # requires structured resume or Claude
            titles=set(),          # requires structured resume or Claude
            dates=_normalize_set(_extract_dates_rule(text)),
            technologies=_extract_technologies_rule(text),
            metrics=_normalize_set(_extract_metrics_rule(text)),
            education=set(),
            certifications=set(),
        )

    def check(self, original: ParsedResume, rewrite_result: RewriteResult) -> FidelityReport:
        """
        Compare the original resume against all rewritten bullets.
        Returns a FidelityReport describing any newly introduced entities.
        """
        # ------------------------------------------------------------------
        # Step 1 — Extract entities from the original resume
        # ------------------------------------------------------------------
        orig_text = _resume_all_text(original)

        orig_dates       = _normalize_set(_extract_dates_rule(orig_text))
        orig_metrics     = _normalize_set(_extract_metrics_rule(orig_text))
        orig_technologies = _extract_technologies_rule(orig_text)

        # Structured fields — always available, never wrong
        orig_companies: set[str] = _normalize_set(
            {exp.company for exp in original.experience}
            | {edu.institution for edu in original.education}
            | {cert.issuer for cert in original.certifications}
        )
        orig_titles: set[str] = _normalize_set(
            {exp.title for exp in original.experience}
        )
        orig_education: set[str] = _normalize_set(
            {edu.institution for edu in original.education}
            | {edu.degree for edu in original.education}
            | {edu.field_of_study for edu in original.education}
        )
        orig_certifications: set[str] = _normalize_set(
            {cert.name for cert in original.certifications}
        )
        # Skill names are authoritative technology evidence
        orig_technologies |= _normalize_set({s.name for s in original.skills})
        orig_technologies = {normalize_tech(t) for t in orig_technologies}

        # Claude refinement for companies and titles
        if self._client:
            orig_claude = _call_claude_entities(self._client, orig_text)
            orig_companies |= _normalize_set(set(orig_claude["companies"]))
            orig_titles    |= _normalize_set(set(orig_claude["job_titles"]))

        all_orig_entities: set[str] = (
            orig_companies | orig_titles | orig_dates | orig_metrics
            | orig_technologies | orig_education | orig_certifications
        )

        # ------------------------------------------------------------------
        # Step 2 — Extract entities from all rewritten bullets
        # ------------------------------------------------------------------
        bullet_pairs = _rewrite_all_bullets(rewrite_result)
        rewrite_full_text = " ".join(b for b, _ in bullet_pairs)

        rw_dates        = _normalize_set(_extract_dates_rule(rewrite_full_text))
        rw_metrics      = _normalize_set(_extract_metrics_rule(rewrite_full_text))
        rw_technologies = {normalize_tech(t) for t in _extract_technologies_rule(rewrite_full_text)}
        rw_companies: set[str] = set()
        rw_titles: set[str] = set()

        if self._client and bullet_pairs:
            rw_claude    = _call_claude_entities(self._client, rewrite_full_text)
            rw_companies = _normalize_set(set(rw_claude["companies"]))
            rw_titles    = _normalize_set(set(rw_claude["job_titles"]))

        all_rw_entities: set[str] = (
            rw_companies | rw_titles | rw_dates | rw_metrics | rw_technologies
        )

        # ------------------------------------------------------------------
        # Step 3 — Compare: flag new entities, apply fuzzy tech matching
        # ------------------------------------------------------------------
        new_companies    = rw_companies    - orig_companies
        new_titles       = rw_titles       - orig_titles
        new_technologies = rw_technologies - orig_technologies
        new_dates        = rw_dates        - orig_dates

        # Metrics: flag as medium; downgrade to low if hedged with approximator
        new_metrics_raw = rw_metrics - orig_metrics
        new_metrics: set[str] = set()
        new_metrics_approx: set[str] = set()  # "approximately 20%" — still medium
        for m in new_metrics_raw:
            # Find which bullet contains this metric
            source = next(
                (bullet for bullet, _ in bullet_pairs if m in bullet.lower()),
                "",
            )
            if _APPROX_QUALIFIER_RE.search(source):
                new_metrics_approx.add(m)
            else:
                new_metrics.add(m)

        flags: list[FidelityFlag] = []

        def _make_flags(new_entities: set[str], entity_type: str, severity: str | None = None) -> None:
            etype_severity = severity or _SEVERITY.get(entity_type, "low")
            for entity in sorted(new_entities):
                found_in = next(
                    (bullet for bullet, _ in bullet_pairs if entity in bullet.lower()),
                    "unknown bullet",
                )
                flags.append(
                    FidelityFlag(
                        entity=entity,
                        entity_type=entity_type,
                        found_in=found_in,
                        severity=etype_severity,
                    )
                )

        _make_flags(new_companies,    "company",    "high")
        _make_flags(new_titles,       "title",      "high")
        _make_flags(new_dates,        "date",       "high")
        _make_flags(new_technologies, "technology", "medium")
        _make_flags(new_metrics,      "metric",     "medium")
        _make_flags(new_metrics_approx, "metric",   "medium")  # hedged but still unverified

        # ------------------------------------------------------------------
        # Step 4 — Weighted fidelity score
        # ------------------------------------------------------------------
        total_orig = len(all_orig_entities)
        total_rw   = len(all_rw_entities)

        all_new = (
            new_companies | new_titles | new_dates
            | new_technologies | new_metrics | new_metrics_approx
        )
        total_new = len(all_new)

        def _weighted_sum(entity_set: set[str], severity: str) -> int:
            return len(entity_set) * _SEVERITY_WEIGHT[severity]

        rw_weight = (
            _weighted_sum(rw_companies,    "high")
            + _weighted_sum(rw_titles,     "high")
            + _weighted_sum(rw_dates,      "high")
            + _weighted_sum(rw_technologies, "medium")
            + _weighted_sum(rw_metrics,    "medium")
        )
        new_weight = (
            _weighted_sum(new_companies,    "high")
            + _weighted_sum(new_titles,     "high")
            + _weighted_sum(new_dates,      "high")
            + _weighted_sum(new_technologies, "medium")
            + _weighted_sum(new_metrics | new_metrics_approx, "medium")
        )

        if rw_weight == 0:
            fidelity_score = 1.0
        else:
            fidelity_score = max(0.0, min(1.0, 1.0 - new_weight / rw_weight))

        logger.info(
            "Fidelity check: score=%.3f | orig=%d | rw=%d | flagged=%d | passed=%s",
            fidelity_score, total_orig, total_rw, total_new, fidelity_score >= self.threshold,
        )

        return FidelityReport(
            fidelity_score=round(fidelity_score, 4),
            flags=flags,
            total_original_entities=total_orig,
            total_rewritten_entities=total_rw,
            new_entities_found=total_new,
            passed=fidelity_score >= self.threshold,
            threshold=self.threshold,
        )
