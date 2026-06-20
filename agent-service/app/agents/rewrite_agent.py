import json
import logging
import os
import time

import anthropic

from app.agents.fidelity_checker import FidelityChecker
from app.models.fidelity_report import FidelityReport
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume
from app.models.rewrite_result import RewriteResult, RewrittenBullet, RewrittenExperience
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 4096
_MAX_REWRITE_ATTEMPTS = 2

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert resume writer and career coach. Your task is to rewrite resume \
bullet points to better match a specific job description.

RULES — read carefully before responding:
1. Do NOT invent new experiences, technologies, companies, titles, dates, or metrics \
   that are not in the original. You may rephrase, reorganize, and emphasize \
   differently, but all factual claims must be traceable to the original bullet.
2. Inject relevant JD keywords naturally — the bullet must still read as authentic \
   human writing, not keyword stuffing.
3. Quantify achievements where possible using numbers/percentages already present \
   in the original or reasonably implied (e.g. "several" → keep as is; do not add \
   "50%" if no number was given).
4. Use strong, specific action verbs (Led, Architected, Reduced, Deployed, …).
5. Highlight transferable skills that connect the candidate's background to the JD.
6. Keep each bullet to one sentence, ideally under 25 words.

Return ONLY a valid JSON object with this schema — no prose, no markdown fences:

{
  "rewritten_bullets": [
    {
      "original": "<exact original text>",
      "rewritten": "<improved text>",
      "changes_made": ["<change 1 and why>", "<change 2 and why>"]
    }
  ],
  "keywords_injected": ["<keyword1>", "<keyword2>"],
  "confidence": 0.0
}

"confidence" is a float 0.0–1.0 rating how well the rewrite improves the match \
without fabricating anything.\
"""


def _build_user_prompt(
    company: str,
    title: str,
    bullets: list[str],
    jd_title: str,
    missing_skills: list[str],
    jd_keywords: list[str],
    improvement_suggestions: list[str],
    flagged_entities: list[str] | None = None,
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

    if flagged_entities:
        entities_text = ", ".join(f'"{e}"' for e in flagged_entities)
        prompt += (
            f"\n\nFIDELITY VIOLATION — REMOVE THESE FABRICATED CLAIMS:\n"
            f"The previous rewrite introduced the following entities that do NOT appear "
            f"in the original resume: {entities_text}.\n"
            f"Remove these fabricated claims entirely. Every fact in the rewrite must "
            f"be directly traceable to the original bullets above.\n"
        )

    prompt += (
        f"\nRewrite the {len(bullets)} bullets above. Return exactly {len(bullets)} "
        f"objects in rewritten_bullets, in the same order."
    )
    return prompt


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
        Rewrite resume bullets to better match the JD, then fidelity-check the
        result. If fidelity_score < threshold, retry once with a stricter prompt
        that names every flagged entity. Maximum _MAX_REWRITE_ATTEMPTS attempts.

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
        attempts = 0
        flagged_entities: list[str] | None = None

        for attempt in range(1, _MAX_REWRITE_ATTEMPTS + 1):
            attempts = attempt
            rewrite_result = self._do_rewrite(
                resume=resume,
                jd=jd,
                gap=gap,
                missing_skills=missing_skills,
                improvement_suggestions=improvement_suggestions,
                jd_keywords=jd_keywords,
                flagged_entities=flagged_entities,
            )

            fidelity_report = self._fidelity_checker.check(resume, rewrite_result)
            logger.info(
                "Fidelity check (attempt %d/%d): score=%.3f passed=%s",
                attempt, _MAX_REWRITE_ATTEMPTS,
                fidelity_report.fidelity_score, fidelity_report.passed,
            )

            if fidelity_report.passed:
                break

            if attempt < _MAX_REWRITE_ATTEMPTS:
                flagged_entities = [f.entity for f in fidelity_report.flags]
                logger.warning(
                    "Fidelity failed (score=%.3f) — retrying with %d flagged entities removed",
                    fidelity_report.fidelity_score, len(flagged_entities),
                )

        # Attach fidelity report and attempt count to the final result
        rewrite_result = RewriteResult(
            experiences=rewrite_result.experiences,
            keywords_injected=rewrite_result.keywords_injected,
            overall_improvement_summary=rewrite_result.overall_improvement_summary,
            rewrite_confidence=rewrite_result.rewrite_confidence,
            fidelity_report=fidelity_report,
            rewrite_attempts=attempts,
        )

        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "Rewrite completed in %d ms — %d experiences, %d keywords, attempts=%d, "
            "fidelity=%.3f",
            duration_ms,
            len(rewrite_result.experiences),
            len(rewrite_result.keywords_injected),
            attempts,
            fidelity_report.fidelity_score if fidelity_report else 0.0,
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
                f"fidelity={(fidelity_report.fidelity_score if fidelity_report else 0.0):.3f}, "
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
        flagged_entities: list[str] | None,
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
                flagged_entities=flagged_entities,
            )

            rewritten_bullets = [
                RewrittenBullet(
                    original=item.get("original", orig),
                    rewritten=item.get("rewritten", orig),
                    changes_made=item.get("changes_made", []),
                )
                for item, orig in zip(result["rewritten_bullets"], exp.bullets)
            ]

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
        flagged_entities: list[str] | None = None,
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
            flagged_entities=flagged_entities,
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
