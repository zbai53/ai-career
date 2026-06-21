import json
import logging
import os
import re
import time

import anthropic

from app.agents.fidelity_checker import FidelityChecker
from app.models.fidelity_report import FidelityFlag, FidelityReport
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume
from app.models.rewrite_result import (
    ImprovementMetrics,
    RewriteResult,
    RewrittenBullet,
    RewrittenExperience,
)
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 4096
_MAX_REWRITE_ATTEMPTS = 2

# ---------------------------------------------------------------------------
# Configurable fidelity thresholds
# ---------------------------------------------------------------------------

FIDELITY_THRESHOLD_STRICT = 0.90   # clean pass — no warnings
FIDELITY_THRESHOLD_WARN   = 0.80   # pass with warnings — borderline
# score < FIDELITY_THRESHOLD_WARN  → failed, must retry

# ---------------------------------------------------------------------------
# Weak action verbs — replacing any of these with a stronger verb is tracked
# as an improvement by compare_versions()
# ---------------------------------------------------------------------------

_WEAK_VERBS: frozenset[str] = frozenset({
    "did", "done", "does",
    "had", "has", "have",
    "made", "make", "makes",
    "got", "get", "gets",
    "helped", "help", "helps",
    "involved", "involve", "involves",
    "worked", "work", "works",
    "assisted", "assist", "assists",
    "used", "use", "uses",
    "handled", "handle", "handles",
    "responsible", "tasked",
    "participated", "participate",
    "supported", "support",
    "contributed", "contribute",
    "provided", "provide",
    "performed", "perform",
    "completed", "complete",
    "conducted", "conduct",
})

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert resume writer and career coach. Your task is to rewrite resume \
bullet points to better match a specific job description.

━━━ DO NOT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• DO NOT add technologies the candidate hasn't used. Only mention tools, \
languages, or frameworks that appear in the original bullet or the experience \
entry's technology list.
• DO NOT fabricate metrics (percentages, dollar amounts, user counts, time \
savings). If a number isn't in the original, do not invent one.
• DO NOT change company names, job titles, or dates. Copy them exactly.
• DO NOT claim leadership roles (led, managed, directed, oversaw) unless the \
original bullet explicitly mentions leadership or management responsibility.
• DO NOT add certifications, degrees, or awards that are not stated in the \
original resume.

━━━ YOU MAY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• YOU MAY rephrase passive language into active voice \
("was responsible for" → "owned and delivered").
• YOU MAY reorder the emphasis within a bullet to lead with the strongest claim.
• YOU MAY add context that is reasonably implied by the original \
(e.g. "Wrote SQL queries" → "Authored complex SQL queries for business \
intelligence reporting").
• YOU MAY swap weak action verbs for stronger equivalents \
(Built → Engineered, Made → Developed, Helped → Contributed).
• YOU MAY highlight transferable skills that genuinely connect the \
candidate's background to the target JD.

━━━ SELF-CHECK (before returning) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each rewritten bullet, ask: can every factual claim — company name, \
technology, metric, job title — be found in the original resume? \
If any claim cannot be traced, remove it before responding.

━━━ ADDITIONAL RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Inject relevant JD keywords naturally — the bullet must still read as \
authentic human writing, not keyword stuffing.
• Keep each bullet to one sentence, ideally under 25 words.

━━━ OUTPUT FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object — no prose, no markdown fences:

{
  "rewritten_bullets": [
    {
      "original": "<exact original text>",
      "rewritten": "<improved text>",
      "changes_made": ["<change 1 and why>", "<change 2 and why>"],
      "fidelity_note": "<'all claims traceable to original' OR 'added reasonable inference: {what}'>"
    }
  ],
  "keywords_injected": ["<keyword1>", "<keyword2>"],
  "confidence": 0.0
}

"confidence" is a float 0.0–1.0 rating how well the rewrite improves the \
match without fabricating anything.\
"""


def _format_flags_for_retry(flags: list[FidelityFlag]) -> str:
    """
    Build a structured fidelity-violation block for the retry prompt.
    Groups flags by severity, includes entity type and exact text.
    """
    high   = [f for f in flags if f.severity == "high"]
    medium = [f for f in flags if f.severity == "medium"]
    low    = [f for f in flags if f.severity == "low"]

    lines: list[str] = [
        "FIDELITY VIOLATIONS DETECTED — the previous rewrite introduced claims that",
        "cannot be traced to the original resume. Correct these before responding.",
        "",
    ]

    if high:
        lines.append("HIGH SEVERITY — MUST be removed (company names, job titles, dates):")
        for f in high:
            lines.append(f'  • [{f.entity_type}] "{f.entity}" — not in original resume')
        lines.append("")

    if medium:
        lines.append(
            "MEDIUM SEVERITY — remove or verify (technology claims, unverified metrics):"
        )
        for f in medium:
            lines.append(
                f'  • [{f.entity_type}] "{f.entity}" — cannot be confirmed from original'
            )
        lines.append("")

    if low:
        lines.append("LOW SEVERITY — review for accuracy (contextual additions):")
        for f in low:
            lines.append(f'  • [{f.entity_type}] "{f.entity}"')
        lines.append("")

    lines += [
        "Return the corrected version.",
        "Do not add any new information not present in the original resume.",
    ]
    return "\n".join(lines)


def _build_user_prompt(
    company: str,
    title: str,
    bullets: list[str],
    jd_title: str,
    missing_skills: list[str],
    jd_keywords: list[str],
    improvement_suggestions: list[str],
    fidelity_flags: list[FidelityFlag] | None = None,
) -> str:
    bullets_text = "\n".join(f"- {b}" for b in bullets)
    missing_text = ", ".join(missing_skills) if missing_skills else "none identified"
    keywords_text = ", ".join(jd_keywords) if jd_keywords else "none"
    suggestions_text = (
        "\n".join(f"- {s}" for s in improvement_suggestions)
        if improvement_suggestions
        else "- Focus on relevant keywords and strong action verbs."
    )

    prompt = (
        f"EXPERIENCE ENTRY TO REWRITE:\n"
        f"  Company: {company}\n"
        f"  Title: {title}\n"
        f"\nORIGINAL BULLETS:\n{bullets_text}\n"
        f"\nTARGET JOB: {jd_title}\n"
        f"\nMISSING SKILLS TO ADDRESS (if present in this role): {missing_text}\n"
        f"\nJD KEYWORDS TO INJECT NATURALLY: {keywords_text}\n"
        f"\nIMPROVEMENT SUGGESTIONS FROM MATCH ANALYSIS:\n{suggestions_text}\n"
    )

    if fidelity_flags:
        prompt += "\n\n" + _format_flags_for_retry(fidelity_flags)

    prompt += (
        f"\nRewrite the {len(bullets)} bullets above. Return exactly {len(bullets)} "
        f"objects in rewritten_bullets, in the same order."
    )
    return prompt


def _fidelity_status(score: float) -> str:
    """Map a fidelity score to a status string."""
    if score >= FIDELITY_THRESHOLD_STRICT:
        return "passed"
    if score >= FIDELITY_THRESHOLD_WARN:
        return "warning"
    return "failed"


def _should_retry(score: float) -> bool:
    """Return True when fidelity is poor enough to warrant a retry."""
    return score < FIDELITY_THRESHOLD_WARN


# ---------------------------------------------------------------------------
# compare_versions — quality metrics (no Claude call)
# ---------------------------------------------------------------------------

def _first_word(text: str) -> str:
    """Return the first alphabetic word of a bullet, lower-cased."""
    m = re.match(r"[^a-zA-Z]*([a-zA-Z]+)", text)
    return m.group(1).lower() if m else ""


def compare_versions(
    original_bullets: list[str],
    rewritten_bullets: list[str],
    jd_keywords: list[str] | None = None,
) -> ImprovementMetrics:
    """
    Compare original and rewritten bullet lists and return quality metrics.

    Args:
        original_bullets:  Flat list of original bullet strings.
        rewritten_bullets: Flat list of rewritten bullet strings (same length).
        jd_keywords:       Optional list of JD keywords to track injection.

    Returns:
        ImprovementMetrics with:
          keywords_added            — JD keywords new in the rewrite
          keywords_removed          — words that vanished from the bullets
          avg_bullet_length_change  — fractional change in mean character count
          action_verbs_improved     — count of weak→strong verb swaps
    """
    jd_kw_lower = {k.lower() for k in (jd_keywords or [])}

    orig_text_lower = " ".join(original_bullets).lower()
    rw_text_lower   = " ".join(rewritten_bullets).lower()

    # Keywords added: JD keywords absent from originals but present in rewrites
    keywords_added = [
        kw for kw in sorted(jd_kw_lower)
        if kw not in orig_text_lower and kw in rw_text_lower
    ]

    # Keywords removed: words in originals that disappeared from rewrites
    orig_words  = {w for w in re.findall(r"\b[a-z]{4,}\b", orig_text_lower)}
    rw_words    = {w for w in re.findall(r"\b[a-z]{4,}\b", rw_text_lower)}
    # Only flag words that were in the originals but not in rewrites AND
    # are not stop-words (filter by length >= 5 to keep it meaningful)
    removed = sorted(
        w for w in (orig_words - rw_words)
        if len(w) >= 5
        and w not in _WEAK_VERBS
        and w not in {"which", "where", "their", "there", "these", "those",
                       "about", "above", "after", "again", "being", "between",
                       "could", "every", "other", "since", "still", "under",
                       "until", "while", "would"}
    )
    keywords_removed = removed[:20]  # cap to avoid noise

    # Avg bullet length change
    pairs = list(zip(original_bullets, rewritten_bullets))
    if pairs:
        orig_avg = sum(len(o) for o, _ in pairs) / len(pairs)
        rw_avg   = sum(len(r) for _, r in pairs) / len(pairs)
        length_change = (rw_avg - orig_avg) / orig_avg if orig_avg > 0 else 0.0
    else:
        length_change = 0.0

    # Action verb improvements: count pairs where original started with a weak verb
    # and the rewrite starts with a different (non-weak) verb
    verbs_improved = sum(
        1
        for orig, rw in pairs
        if _first_word(orig) in _WEAK_VERBS
        and _first_word(rw) not in _WEAK_VERBS
        and _first_word(rw) != ""
    )

    return ImprovementMetrics(
        keywords_added=keywords_added,
        keywords_removed=keywords_removed,
        avg_bullet_length_change=round(length_change, 4),
        action_verbs_improved=verbs_improved,
    )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class RewriteParseError(Exception):
    pass


class RewriteAgent:
    def __init__(self, fidelity_checker: FidelityChecker | None = None) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._token_count: int = 0
        self._fidelity_checker = fidelity_checker or FidelityChecker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rewrite(
        self,
        resume: ParsedResume,
        jd: ParsedJobDescription,
        match_result: dict,
    ) -> tuple[RewriteResult, dict]:
        """
        Rewrite resume bullets to better match the JD, fidelity-check the result,
        and compute quality improvement metrics.

        Retry policy (up to _MAX_REWRITE_ATTEMPTS):
          score < FIDELITY_THRESHOLD_WARN (0.80)   → retry with flag details in prompt
          WARN <= score < STRICT (0.90)             → pass with "warning" status
          score >= STRICT                           → pass clean

        Returns:
            (RewriteResult, agent_run_log)
        """
        self._token_count = 0
        t0 = time.perf_counter()

        gap = match_result.get("gap_analysis") or match_result
        missing_skills: list[str] = (
            gap.get("missing_required_skills", [])
            + gap.get("missing_preferred_skills", [])
        )
        improvement_suggestions: list[str] = gap.get("improvement_suggestions", [])
        jd_keywords: list[str] = list(jd.keywords or [])

        rewrite_result: RewriteResult | None = None
        fidelity_report: FidelityReport | None = None
        retry_flags: list[FidelityFlag] | None = None
        attempts = 0

        for attempt in range(1, _MAX_REWRITE_ATTEMPTS + 1):
            attempts = attempt
            rewrite_result = self._do_rewrite(
                resume=resume,
                jd=jd,
                gap=gap,
                missing_skills=missing_skills,
                improvement_suggestions=improvement_suggestions,
                jd_keywords=jd_keywords,
                fidelity_flags=retry_flags,
            )

            fidelity_report = self._fidelity_checker.check(resume, rewrite_result)
            status = _fidelity_status(fidelity_report.fidelity_score)
            logger.info(
                "Fidelity check (attempt %d/%d): score=%.3f status=%s",
                attempt, _MAX_REWRITE_ATTEMPTS,
                fidelity_report.fidelity_score, status,
            )

            if not _should_retry(fidelity_report.fidelity_score):
                break   # passed or warning — stop here

            if attempt < _MAX_REWRITE_ATTEMPTS:
                retry_flags = fidelity_report.flags
                logger.warning(
                    "Fidelity failed (score=%.3f < warn=%.2f) — "
                    "retrying with %d flagged entities",
                    fidelity_report.fidelity_score,
                    FIDELITY_THRESHOLD_WARN,
                    len(retry_flags),
                )

        # Compute improvement metrics across all experience bullets
        orig_all  = [
            b
            for exp in resume.experience
            for b in exp.bullets
        ]
        rw_all = [
            rb.rewritten
            for exp in rewrite_result.experiences
            for rb in exp.rewritten_bullets
        ]
        improvement_metrics = compare_versions(orig_all, rw_all, jd_keywords)

        # Assemble final result
        final_status = _fidelity_status(
            fidelity_report.fidelity_score if fidelity_report else 0.0
        )
        rewrite_result = RewriteResult(
            experiences=rewrite_result.experiences,
            keywords_injected=rewrite_result.keywords_injected,
            overall_improvement_summary=rewrite_result.overall_improvement_summary,
            rewrite_confidence=rewrite_result.rewrite_confidence,
            fidelity_report=fidelity_report,
            rewrite_attempts=attempts,
            improvement_metrics=improvement_metrics,
            fidelity_status=final_status,
        )

        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "Rewrite completed in %d ms — %d experiences, %d keywords, "
            "attempts=%d, fidelity=%.3f (%s), verbs_improved=%d",
            duration_ms,
            len(rewrite_result.experiences),
            len(rewrite_result.keywords_injected),
            attempts,
            fidelity_report.fidelity_score if fidelity_report else 0.0,
            final_status,
            improvement_metrics.action_verbs_improved,
        )

        agent_run = log_agent_run(
            agent_name="rewrite_agent",
            input_summary=(
                f"resume experiences={len(resume.experience)}, "
                f"jd={jd.title}, missing_skills={len(missing_skills)}"
            ),
            output_summary=(
                f"experiences_rewritten={len(rewrite_result.experiences)}, "
                f"keywords_injected={len(rewrite_result.keywords_injected)}, "
                f"fidelity={(fidelity_report.fidelity_score if fidelity_report else 0.0):.3f}"
                f"({final_status}), "
                f"attempts={attempts}"
            ),
            status="success",
            duration_ms=duration_ms,
            token_count=self._token_count,
            model_name=_MODEL,
        )
        return rewrite_result, agent_run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_rewrite(
        self,
        resume: ParsedResume,
        jd: ParsedJobDescription,
        gap: dict,
        missing_skills: list[str],
        improvement_suggestions: list[str],
        jd_keywords: list[str],
        fidelity_flags: list[FidelityFlag] | None,
    ) -> RewriteResult:
        """Execute one full rewrite pass over all experience entries."""
        rewritten_experiences: list[RewrittenExperience] = []
        all_keywords_injected: set[str] = set()
        confidence_scores: list[float] = []

        for exp in resume.experience:
            if not exp.bullets:
                rewritten_experiences.append(
                    RewrittenExperience(
                        company=exp.company,
                        title=exp.title,
                        original_bullets=[],
                        rewritten_bullets=[],
                    )
                )
                continue

            result = self._rewrite_experience(
                company=exp.company,
                title=exp.title,
                bullets=exp.bullets,
                jd_title=jd.title or "the target role",
                missing_skills=missing_skills,
                jd_keywords=jd_keywords,
                improvement_suggestions=improvement_suggestions,
                fidelity_flags=fidelity_flags,
            )

            rewritten_bullets = []
            for item, orig in zip(result["rewritten_bullets"], exp.bullets):
                changes = list(item.get("changes_made", []))
                fidelity_note = item.get("fidelity_note", "")
                if fidelity_note:
                    changes.append(f"[fidelity] {fidelity_note}")
                rewritten_bullets.append(
                    RewrittenBullet(
                        original=item.get("original", orig),
                        rewritten=item.get("rewritten", orig),
                        changes_made=changes,
                    )
                )

            rewritten_experiences.append(
                RewrittenExperience(
                    company=exp.company,
                    title=exp.title,
                    original_bullets=exp.bullets,
                    rewritten_bullets=rewritten_bullets,
                )
            )
            all_keywords_injected.update(result.get("keywords_injected", []))
            confidence_scores.append(float(result.get("confidence", 0.8)))

        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.8
        )
        overall_summary = (
            gap.get("overall_assessment")
            or f"Resume bullets updated to target {jd.title or 'the role'}, "
               f"injecting {len(all_keywords_injected)} JD keywords and "
               f"strengthening action language across {len(rewritten_experiences)} experience entries."
        )

        return RewriteResult(
            experiences=rewritten_experiences,
            keywords_injected=sorted(all_keywords_injected),
            overall_improvement_summary=overall_summary,
            rewrite_confidence=round(avg_confidence, 3),
        )

    def _rewrite_experience(
        self,
        company: str,
        title: str,
        bullets: list[str],
        jd_title: str,
        missing_skills: list[str],
        jd_keywords: list[str],
        improvement_suggestions: list[str],
        fidelity_flags: list[FidelityFlag] | None = None,
    ) -> dict:
        """
        Call Claude to rewrite bullets for a single experience entry.
        Retries once with a stricter prompt on JSON parse failure.
        """
        user_content = _build_user_prompt(
            company=company,
            title=title,
            bullets=bullets,
            jd_title=jd_title,
            missing_skills=missing_skills,
            jd_keywords=jd_keywords,
            improvement_suggestions=improvement_suggestions,
            fidelity_flags=fidelity_flags,
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
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content}],
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                self._token_count += (
                    response.usage.input_tokens + response.usage.output_tokens
                )
                logger.info(
                    "Rewrite call %d (%s / %s): %.0f ms | in=%d out=%d",
                    attempt + 1,
                    company,
                    title,
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
                if "rewritten_bullets" not in data:
                    raise ValueError("Missing key: rewritten_bullets")

                rewritten = data["rewritten_bullets"]
                if len(rewritten) != len(bullets):
                    logger.warning(
                        "Rewrite returned %d bullets for %d originals — adjusting",
                        len(rewritten), len(bullets),
                    )
                    while len(rewritten) < len(bullets):
                        rewritten.append(
                            {"original": bullets[len(rewritten)],
                             "rewritten": bullets[len(rewritten)],
                             "changes_made": []}
                        )
                    rewritten = rewritten[: len(bullets)]
                    data["rewritten_bullets"] = rewritten

                return data

            except (json.JSONDecodeError, ValueError) as exc:
                if strict:
                    logger.error(
                        "Rewrite parse failed for %s / %s after retry: %s",
                        company, title, exc,
                    )
                    break
                logger.warning(
                    "Rewrite attempt 1 failed for %s / %s (%s), retrying",
                    company, title, exc,
                )

        # Fallback — return original bullets unchanged
        return {
            "rewritten_bullets": [
                {"original": b, "rewritten": b,
                 "changes_made": ["Rewrite failed — original preserved."]}
                for b in bullets
            ],
            "keywords_injected": [],
            "confidence": 0.0,
        }
