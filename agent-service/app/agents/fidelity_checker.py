"""
FidelityChecker — prevents hallucination in rewritten resume bullets.

Two-layer entity extraction:
  1. Rule-based  — regex for dates, numbers/metrics, known patterns. Always runs.
  2. Claude-assisted — extracts company names, job titles, and technology names
     that are hard to catch with regex. Runs after rule-based; gracefully
     degrades to rule-based-only if Claude is unavailable.

Scoring:
  fidelity_score = 1.0 - (new_entities / total_rewritten_entities)
  clamped to [0.0, 1.0].  Passes when score >= threshold (default 0.85).
"""

import json
import logging
import os
import re
import time

import anthropic

from app.models.fidelity_report import FidelityFlag, FidelityReport, _DEFAULT_THRESHOLD
from app.models.resume import ParsedResume
from app.models.rewrite_result import RewriteResult

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

_SEVERITY: dict[str, str] = {
    "company":    "high",
    "title":      "high",
    "date":       "high",
    "metric":     "medium",
    "technology": "low",
}

# ---------------------------------------------------------------------------
# Rule-based extraction helpers
# ---------------------------------------------------------------------------

# Dates: 2019, 2019-03, 03/2019, Jan 2019, January 2019
_DATE_RE = re.compile(
    r"\b(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{4}"
    r"|\d{4}-\d{2}"
    r"|\d{2}/\d{4}"
    r"|\b(?:19|20)\d{2}\b"
    r")",
    re.IGNORECASE,
)

# Numbers with business units: 20%, $1.2M, 50K, 3x, 99.9%, #1
_METRIC_RE = re.compile(
    r"(?:"
    r"\$\s*[\d,]+(?:\.\d+)?[KkMmBb]?"   # $1.2M, $500K
    r"|[\d,]+(?:\.\d+)?\s*[KkMmBb]\b"   # 50K, 1.2M
    r"|[\d,]+(?:\.\d+)?\s*%"             # 20%, 99.9%
    r"|\d+(?:\.\d+)?\s*x\b"             # 3x, 10x
    r"|#\s*\d+"                           # #1, #3
    r"|\b\d{1,3}(?:,\d{3})+\b"          # 1,000  10,000
    r")"
)


def _extract_dates_rule(text: str) -> set[str]:
    return {m.group().strip().lower() for m in _DATE_RE.finditer(text)}


def _extract_metrics_rule(text: str) -> set[str]:
    return {m.group().strip() for m in _METRIC_RE.finditer(text)}


def _normalize_set(s: set[str]) -> set[str]:
    return {v.lower().strip() for v in s if v.strip()}


# ---------------------------------------------------------------------------
# Aggregate text helpers
# ---------------------------------------------------------------------------

def _resume_all_text(resume: ParsedResume) -> str:
    """Concatenate all resume text fields for rule-based scanning."""
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
    """Return list of (bullet_text, source_label) for all rewritten bullets."""
    out: list[tuple[str, str]] = []
    for exp in rewrite_result.experiences:
        for rb in exp.rewritten_bullets:
            label = f"{exp.company} / {exp.title}"
            out.append((rb.rewritten, label))
    return out


# ---------------------------------------------------------------------------
# Claude-assisted extraction
# ---------------------------------------------------------------------------

_ENTITY_SYSTEM_PROMPT = """\
You are an entity extraction engine. Given a block of text, extract named entities \
in these categories: companies, job_titles, technologies.

Return ONLY a valid JSON object with exactly these keys — no prose, no markdown fences:
{
  "companies":    ["<name>", ...],
  "job_titles":   ["<title>", ...],
  "technologies": ["<tech>", ...]
}

Rules:
- companies: organization names (employers, schools, products if named after a company)
- job_titles: formal role names (Software Engineer, VP of Engineering, …)
- technologies: programming languages, frameworks, tools, platforms, databases, cloud services
- Do NOT include generic words (e.g., "team", "project", "system")
- If a category has nothing, return an empty list.\
"""


def _call_claude_entities(client: anthropic.Anthropic, text: str) -> dict[str, list[str]]:
    """
    Use Claude to extract company, title, and technology entities from text.
    Returns a dict with keys companies, job_titles, technologies.
    Falls back to empty lists on any error.
    """
    try:
        t0 = time.perf_counter()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_ENTITY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:8000]}],  # guard token limit
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
            "companies":    [str(x) for x in data.get("companies", [])],
            "job_titles":   [str(x) for x in data.get("job_titles", [])],
            "technologies": [str(x) for x in data.get("technologies", [])],
        }
    except Exception as exc:
        logger.warning("Claude entity extraction failed (degraded mode): %s", exc)
        return {"companies": [], "job_titles": [], "technologies": []}


# ---------------------------------------------------------------------------
# FidelityChecker
# ---------------------------------------------------------------------------


class FidelityChecker:
    def __init__(self, threshold: float = _DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self._client: anthropic.Anthropic | None = anthropic.Anthropic(api_key=api_key)
        else:
            logger.warning(
                "ANTHROPIC_API_KEY not set — FidelityChecker running in rule-based-only mode"
            )
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, original: ParsedResume, rewrite_result: RewriteResult) -> FidelityReport:
        """
        Compare the original resume against all rewritten bullets and return a
        FidelityReport describing any newly introduced (potentially hallucinated)
        entities.
        """
        # ------------------------------------------------------------------
        # Step 1 — Extract entities from the original resume
        # ------------------------------------------------------------------
        orig_text = _resume_all_text(original)

        orig_dates  = _normalize_set(_extract_dates_rule(orig_text))
        orig_metrics = _normalize_set(_extract_metrics_rule(orig_text))

        # Seed structured entities from the resume model fields (always available)
        orig_companies: set[str] = _normalize_set(
            {exp.company for exp in original.experience}
            | {edu.institution for edu in original.education}
            | {cert.issuer for cert in original.certifications}
        )
        orig_titles: set[str] = _normalize_set(
            {exp.title for exp in original.experience}
        )
        orig_technologies: set[str] = _normalize_set(
            {s.name for s in original.skills}
            | {tech for exp in original.experience for tech in exp.technologies}
            | {tech for proj in original.projects for tech in proj.technologies}
        )

        # Refine with Claude entity extraction on the full resume text
        if self._client:
            orig_claude = _call_claude_entities(self._client, orig_text)
            orig_companies    |= _normalize_set(set(orig_claude["companies"]))
            orig_titles       |= _normalize_set(set(orig_claude["job_titles"]))
            orig_technologies |= _normalize_set(set(orig_claude["technologies"]))

        # Combined original entity universe
        all_orig_entities: set[str] = (
            orig_companies | orig_titles | orig_dates | orig_metrics | orig_technologies
        )

        # ------------------------------------------------------------------
        # Step 2 — Extract entities from all rewritten bullets
        # ------------------------------------------------------------------
        bullet_pairs = _rewrite_all_bullets(rewrite_result)
        rewrite_full_text = " ".join(b for b, _ in bullet_pairs)

        rw_dates   = _normalize_set(_extract_dates_rule(rewrite_full_text))
        rw_metrics = _normalize_set(_extract_metrics_rule(rewrite_full_text))
        rw_companies: set[str] = set()
        rw_titles: set[str] = set()
        rw_technologies: set[str] = set()

        if self._client and bullet_pairs:
            rw_claude = _call_claude_entities(self._client, rewrite_full_text)
            rw_companies    = _normalize_set(set(rw_claude["companies"]))
            rw_titles       = _normalize_set(set(rw_claude["job_titles"]))
            rw_technologies = _normalize_set(set(rw_claude["technologies"]))

        all_rw_entities: set[str] = (
            rw_companies | rw_titles | rw_dates | rw_metrics | rw_technologies
        )

        # ------------------------------------------------------------------
        # Step 3 — Compare: flag entities new in rewrite vs original
        # ------------------------------------------------------------------
        new_companies    = rw_companies    - orig_companies
        new_titles       = rw_titles       - orig_titles
        new_technologies = rw_technologies - orig_technologies
        new_metrics      = rw_metrics      - orig_metrics
        new_dates        = rw_dates        - orig_dates

        flags: list[FidelityFlag] = []

        def _make_flags(new_entities: set[str], entity_type: str) -> None:
            for entity in sorted(new_entities):
                # Find which bullet it appears in
                found_in = next(
                    (bullet for bullet, _ in bullet_pairs if entity in bullet.lower()),
                    "unknown bullet",
                )
                flags.append(
                    FidelityFlag(
                        entity=entity,
                        entity_type=entity_type,
                        found_in=found_in,
                        severity=_SEVERITY[entity_type],
                    )
                )

        _make_flags(new_companies,    "company")
        _make_flags(new_titles,       "title")
        _make_flags(new_dates,        "date")
        _make_flags(new_metrics,      "metric")
        _make_flags(new_technologies, "technology")

        # ------------------------------------------------------------------
        # Step 4 — Score
        # ------------------------------------------------------------------
        total_orig = len(all_orig_entities)
        total_rw   = len(all_rw_entities)
        total_new  = len(new_companies | new_titles | new_technologies | new_metrics | new_dates)

        if total_rw == 0:
            fidelity_score = 1.0
        else:
            fidelity_score = max(0.0, min(1.0, 1.0 - total_new / total_rw))

        logger.info(
            "Fidelity check: score=%.3f | orig_entities=%d | rw_entities=%d | flagged=%d | passed=%s",
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
