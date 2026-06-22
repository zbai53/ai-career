"""
CoachAgent — post-interview performance review powered by Claude.

Takes the full InterviewSessionData (all Q&A pairs + per-answer evaluations)
and the target JD, sends it to Claude, and returns a structured CoachReview.
"""
import json
import logging
import os
import re
import time
from typing import Optional

import anthropic

from app.agents.prompt_templates import (
    COACH_REVIEW_SYSTEM_PROMPT,
    COACH_REVIEW_USER_PROMPT,
)
from app.models.coach_review import (
    BehavioralReview,
    CoachReview,
    CommunicationReview,
    STARScore,
    TechnicalReview,
)
from app.models.interview import AnswerEvaluation, InterviewSessionData
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 4096


class CoachAgent:
    """
    Reviews a completed interview session and produces a CoachReview.

    Usage::

        agent = CoachAgent()
        review, agent_run = agent.review(session, jd, resume)
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(
        self,
        session: InterviewSessionData,
        jd: ParsedJobDescription,
        resume: ParsedResume,
    ) -> tuple[CoachReview, dict]:
        """
        Analyze the full interview and return a CoachReview + agent_run log.

        Args:
            session: Completed InterviewSessionData with Q&A and evaluations.
            jd:      The target job description.
            resume:  The candidate's parsed resume (used for context).

        Returns:
            (CoachReview, agent_run_dict)
        """
        t0 = time.perf_counter()

        transcript = self._build_transcript(session)
        user_content = COACH_REVIEW_USER_PROMPT.format(
            jd_title=jd.title,
            num_questions=len(session.questions),
            transcript=transcript,
        )

        client = anthropic.Anthropic(api_key=self._api_key)
        try:
            message = client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=COACH_REVIEW_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw_text = message.content[0].text.strip()
            token_count = message.usage.input_tokens + message.usage.output_tokens
        except Exception as exc:
            logger.error("Claude coach review call failed: %s", exc)
            raise

        data = self._parse_response(raw_text)
        review = self._build_review(data, session)

        duration_ms = int((time.perf_counter() - t0) * 1000)
        agent_run = log_agent_run(
            agent_name="coach_agent",
            input_summary=f"{len(session.answers)} answers for {jd.title}"[:100],
            output_summary=f"overall={review.overall_score:.1f} readiness={review.readiness}",
            status="success",
            duration_ms=duration_ms,
            token_count=token_count,
            model_name=_MODEL,
        )

        return review, agent_run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_transcript(self, session: InterviewSessionData) -> str:
        """
        Format all Q&A pairs plus their automated evaluation scores into a
        plain-text transcript for Claude.
        """
        lines: list[str] = []
        questions = session.questions

        for i, evaluation in enumerate(session.answers):
            q = questions[i] if i < len(questions) else None
            q_type       = q.type       if q else "unknown"
            q_difficulty = q.difficulty if q else "unknown"

            lines.append(f"--- Question {i + 1} [{q_type} / {q_difficulty}] ---")
            lines.append(f"Q: {evaluation.question}")
            lines.append(f"A: {evaluation.answer}")
            lines.append(
                f"Automated scores — relevance: {evaluation.relevance_score}, "
                f"depth: {evaluation.depth_score}, "
                f"communication: {evaluation.communication_score}, "
                f"overall: {evaluation.overall_score}"
            )
            if evaluation.strengths:
                lines.append(f"Strengths noted: {', '.join(evaluation.strengths)}")
            if evaluation.improvements:
                lines.append(f"Improvements noted: {', '.join(evaluation.improvements)}")
            lines.append("")

        return "\n".join(lines).strip()

    def _parse_response(self, raw_text: str) -> dict:
        """Extract and validate the JSON payload from Claude's response."""
        text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
            logger.error("Could not parse coach review JSON: %s", raw_text[:300])
            return {}

    def _build_review(self, data: dict, session: InterviewSessionData) -> CoachReview:
        """
        Construct a validated CoachReview from the parsed JSON dict.

        Falls back gracefully for any missing or malformed fields so a partial
        Claude response still produces a usable review.
        """
        # --- behavioral_reviews ---
        behavioral_reviews: list[BehavioralReview] = []
        for br in data.get("behavioral_reviews") or []:
            try:
                star_raw = br.get("star_score") or {}
                behavioral_reviews.append(
                    BehavioralReview(
                        question=str(br.get("question", "")),
                        star_score=STARScore(
                            situation=_clamp(star_raw.get("situation", 5.0)),
                            task=_clamp(star_raw.get("task", 5.0)),
                            action=_clamp(star_raw.get("action", 5.0)),
                            result=_clamp(star_raw.get("result", 5.0)),
                        ),
                        feedback=str(br.get("feedback", "")),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping malformed behavioral review entry: %s", exc)

        # --- technical_reviews ---
        technical_reviews: list[TechnicalReview] = []
        for tr in data.get("technical_reviews") or []:
            try:
                technical_reviews.append(
                    TechnicalReview(
                        question=str(tr.get("question", "")),
                        accuracy=_clamp(tr.get("accuracy", 5.0)),
                        depth=_clamp(tr.get("depth", 5.0)),
                        practical=_clamp(tr.get("practical", 5.0)),
                        feedback=str(tr.get("feedback", "")),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping malformed technical review entry: %s", exc)

        # --- communication ---
        comm_raw = data.get("communication") or {}
        communication = CommunicationReview(
            clarity=_clamp(comm_raw.get("clarity", 5.0)),
            conciseness=_clamp(comm_raw.get("conciseness", 5.0)),
            confidence=_clamp(comm_raw.get("confidence", 5.0)),
            feedback=str(comm_raw.get("feedback", "")),
        )

        # --- overall_score ---
        overall_score = _clamp_100(data.get("overall_score", 50.0))

        # --- readiness ---
        readiness_raw = str(data.get("readiness", "")).strip().lower()
        if readiness_raw not in ("yes", "almost", "needs_more_practice"):
            # Derive from overall_score as fallback
            if overall_score >= 75:
                readiness_raw = "yes"
            elif overall_score >= 50:
                readiness_raw = "almost"
            else:
                readiness_raw = "needs_more_practice"

        # --- lists ---
        top_strengths        = _ensure_list(data.get("top_strengths"))[:3]
        areas_for_improvement = _ensure_list(data.get("areas_for_improvement"))[:3]
        recommended_topics   = _ensure_list(data.get("recommended_topics"))[:5]

        return CoachReview(
            overall_score=overall_score,
            behavioral_reviews=behavioral_reviews,
            technical_reviews=technical_reviews,
            communication=communication,
            top_strengths=top_strengths,
            areas_for_improvement=areas_for_improvement,
            recommended_topics=recommended_topics,
            readiness=readiness_raw,
            summary=str(data.get("summary", "")),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _clamp(value, lo: float = 0.0, hi: float = 10.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return 5.0


def _clamp_100(value) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 50.0


def _ensure_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []
