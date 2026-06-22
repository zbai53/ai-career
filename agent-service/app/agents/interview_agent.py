"""
InterviewAgent — multi-turn mock interview powered by RAG + Claude.

Flow:
    1. start_session()    — fetch questions from Qdrant, build session
    2. ask_next()         — return next question in order
    3. evaluate_answer()  — score the candidate's answer via Claude
    4. generate_follow_up() — optionally generate a contextual follow-up
"""
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import anthropic

from app.agents.prompt_templates import (
    INTERVIEW_EVALUATE_SYSTEM_PROMPT,
    INTERVIEW_EVALUATE_USER_PROMPT,
    INTERVIEW_FOLLOW_UP_PROMPT,
)
from app.models.interview import AnswerEvaluation, InterviewQuestion, InterviewSessionData
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Keyword sets for role detection
# ---------------------------------------------------------------------------

_FRONTEND_KEYWORDS = {
    "frontend", "front-end", "front end", "ui", "ux", "react", "vue", "angular",
    "javascript", "typescript", "css", "html", "web developer",
}
_BACKEND_KEYWORDS = {
    "backend", "back-end", "back end", "server", "api", "java", "python",
    "go", "rust", "node", "spring", "django", "fastapi", "microservices",
    "distributed", "data engineer", "platform engineer",
}


def _detect_role(jd: ParsedJobDescription) -> str:
    """Infer a Qdrant role filter value from the JD title and skills."""
    title_lower = jd.title.lower()
    skill_names = {s.name.lower() for s in jd.skills}
    combined = title_lower + " " + " ".join(skill_names)

    if any(kw in combined for kw in _FRONTEND_KEYWORDS):
        return "frontend"
    if any(kw in combined for kw in _BACKEND_KEYWORDS):
        return "backend"
    return "general"


def _build_query(jd: ParsedJobDescription) -> str:
    """Construct a RAG query string from JD skill names and responsibilities."""
    skill_names = [s.name for s in jd.skills[:8]]
    resp_snippet = jd.responsibilities[0] if jd.responsibilities else ""
    parts = skill_names + ([resp_snippet] if resp_snippet else [])
    return " ".join(parts) or jd.title


def _dedup(questions: list[dict], seen_ids: set) -> list[dict]:
    """Return questions whose IDs have not been seen yet, updating seen_ids."""
    result = []
    for q in questions:
        qid = str(q.get("id", ""))
        if qid not in seen_ids:
            seen_ids.add(qid)
            result.append(q)
    return result


def _to_interview_question(raw: dict) -> InterviewQuestion:
    topic = raw.get("topic") or "general"
    return InterviewQuestion(
        text=raw.get("text", ""),
        type=raw.get("type", "technical"),
        category=topic,
        difficulty=raw.get("difficulty", "medium"),
        topics=[topic],
    )


class InterviewAgent:
    """
    Orchestrates a mock interview session.

    All Qdrant and Claude calls are encapsulated here.  The session object
    (`InterviewSessionData`) is mutable — callers hold a reference and observe
    state changes (index advancement, status updates) directly.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY")

    # ------------------------------------------------------------------
    # 1. Start session
    # ------------------------------------------------------------------

    def start_session(
        self,
        jd: ParsedJobDescription,
        resume: ParsedResume,
        num_questions: int = 5,
    ) -> InterviewSessionData:
        """
        Build an interview session by retrieving questions from Qdrant.

        Distribution (for num_questions=5):
            3 technical  (60 %): 1 easy + 2 medium
            2 behavioral (40 %): 1 medium + 1 hard
        Scales proportionally for other counts.
        """
        from app.rag.question_index import search_questions

        # Ensure the question bank is indexed (idempotent)
        try:
            from app.rag.question_index import index_questions
            index_questions()
        except Exception as exc:
            logger.warning("Could not index questions (Qdrant may be unavailable): %s", exc)
            # Fall back to direct-from-bank selection if Qdrant is unavailable
            return self._fallback_session(jd, num_questions)

        role = _detect_role(jd)
        query = _build_query(jd)

        n_technical = round(num_questions * 0.6)
        n_behavioral = num_questions - n_technical

        # Split technical: 1 easy + rest medium
        n_tech_easy   = 1
        n_tech_medium = n_technical - n_tech_easy

        # Split behavioral: all medium except 1 hard
        n_beh_hard   = 1 if n_behavioral >= 2 else 0
        n_beh_medium = n_behavioral - n_beh_hard

        seen_ids: set[str] = set()
        selected: list[dict] = []

        def _fetch(q_role, q_type, q_diff, n, extra_limit=8):
            try:
                results = search_questions(
                    query=query,
                    role=q_role if q_role else None,
                    type=q_type,
                    difficulty=q_diff,
                    limit=extra_limit,
                )
                return _dedup(results, seen_ids)[:n]
            except Exception as exc:
                logger.warning(
                    "RAG search failed (role=%s type=%s diff=%s): %s", q_role, q_type, q_diff, exc
                )
                return []

        selected += _fetch(role,    "technical",  "easy",   n_tech_easy)
        selected += _fetch(role,    "technical",  "medium", n_tech_medium)
        selected += _fetch(None,    "behavioral", "medium", n_beh_medium)
        selected += _fetch(None,    "behavioral", "hard",   n_beh_hard)

        # If we still don't have enough, fill with any available question
        if len(selected) < num_questions:
            extra = search_questions(query=query, limit=num_questions + 10)
            selected += _dedup(extra, seen_ids)[: num_questions - len(selected)]

        questions = [_to_interview_question(q) for q in selected[:num_questions]]

        return InterviewSessionData(
            session_id=str(uuid.uuid4()),
            jd_title=jd.title,
            questions=questions,
            answers=[],
            current_question_index=0,
            status="active",
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=None,
        )

    # ------------------------------------------------------------------
    # 2. Ask next question
    # ------------------------------------------------------------------

    def ask_next(self, session: InterviewSessionData) -> dict:
        """
        Return the next unasked question from the session.

        Advances `session.current_question_index` in-place.

        Returns:
            Question dict with keys: question, question_number, total_questions,
            type, difficulty.
            Or {"done": True, "message": "Interview complete"} when exhausted.
        """
        idx = session.current_question_index
        total = len(session.questions)

        if idx >= total:
            if session.status == "active":
                session.status = "completed"
                session.ended_at = datetime.now(timezone.utc).isoformat()
            return {"done": True, "message": "Interview complete"}

        q = session.questions[idx]
        session.current_question_index += 1

        return {
            "question":         q.text,
            "question_number":  idx + 1,
            "total_questions":  total,
            "type":             q.type,
            "difficulty":       q.difficulty,
        }

    # ------------------------------------------------------------------
    # 3. Evaluate answer
    # ------------------------------------------------------------------

    def evaluate_answer(
        self,
        session: InterviewSessionData,
        question: str,
        answer: str,
    ) -> dict:
        """
        Send the question + answer to Claude for structured evaluation.

        Appends an `AnswerEvaluation` to `session.answers`.

        Returns:
            dict with keys: relevance_score, depth_score, communication_score,
            overall_score, strengths, improvements, follow_up.
        """
        t0 = time.perf_counter()
        client = anthropic.Anthropic(api_key=self._api_key)

        user_content = INTERVIEW_EVALUATE_USER_PROMPT.format(
            question=question,
            answer=answer,
        )

        try:
            message = client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=INTERVIEW_EVALUATE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw_text = message.content[0].text.strip()
            token_count = message.usage.input_tokens + message.usage.output_tokens
        except Exception as exc:
            logger.error("Claude evaluation call failed: %s", exc)
            raise

        evaluation = self._parse_evaluation(raw_text)

        duration_ms = int((time.perf_counter() - t0) * 1000)
        log_agent_run(
            agent_name="interview_agent",
            input_summary=question[:100],
            output_summary=f"overall={evaluation.get('overall', '?')}",
            status="success",
            duration_ms=duration_ms,
            token_count=token_count,
            model_name=_MODEL,
        )

        # Record in session
        record = AnswerEvaluation(
            question=question,
            answer=answer,
            relevance_score=float(evaluation.get("relevance", 5)),
            depth_score=float(evaluation.get("depth", 5)),
            communication_score=float(evaluation.get("communication", 5)),
            overall_score=float(evaluation.get("overall", 5.0)),
            strengths=evaluation.get("strengths", []),
            improvements=evaluation.get("improvements", []),
            follow_up=evaluation.get("follow_up_question"),
        )
        session.answers.append(record)

        return {
            "relevance_score":     record.relevance_score,
            "depth_score":         record.depth_score,
            "communication_score": record.communication_score,
            "overall_score":       record.overall_score,
            "strengths":           record.strengths,
            "improvements":        record.improvements,
            "follow_up":           record.follow_up,
        }

    # ------------------------------------------------------------------
    # 4. Generate follow-up
    # ------------------------------------------------------------------

    def generate_follow_up(
        self,
        session: InterviewSessionData,
        question: str,
        answer: str,
        evaluation: dict,
    ) -> Optional[str]:
        """
        Generate a contextual follow-up question using Claude.

        Uses the `follow_up` hint from the evaluation dict as a seed.  Returns
        None when no follow-up is appropriate (hint is absent or empty).
        """
        hint = evaluation.get("follow_up")
        if not hint:
            return None

        client = anthropic.Anthropic(api_key=self._api_key)
        prompt = INTERVIEW_FOLLOW_UP_PROMPT.format(
            question=question,
            answer=answer,
            follow_up_hint=hint,
        )

        try:
            message = client.messages.create(
                model=_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            follow_up_text = message.content[0].text.strip()
            return follow_up_text if follow_up_text else None
        except Exception as exc:
            logger.warning("Follow-up generation failed, returning raw hint: %s", exc)
            return hint

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_evaluation(self, raw_text: str) -> dict:
        """Extract JSON from Claude's response, tolerating markdown fences."""
        # Strip optional markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Attempt to locate first {...} block
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                data = json.loads(m.group())
            else:
                logger.error("Could not parse evaluation JSON: %s", raw_text[:200])
                data = {}

        # Coerce numeric fields to float
        for key in ("relevance", "depth", "communication", "overall"):
            if key in data:
                try:
                    data[key] = float(data[key])
                except (TypeError, ValueError):
                    data[key] = 5.0

        # Ensure list fields are lists
        for key in ("strengths", "improvements"):
            if not isinstance(data.get(key), list):
                data[key] = []

        return data

    def _fallback_session(
        self, jd: ParsedJobDescription, num_questions: int
    ) -> InterviewSessionData:
        """Build a session from the in-memory question bank when Qdrant is unavailable."""
        from app.rag.question_index import _QUESTIONS

        n_technical = round(num_questions * 0.6)
        n_behavioral = num_questions - n_technical

        technical  = [q for q in _QUESTIONS if q["type"] == "technical"]
        behavioral = [q for q in _QUESTIONS if q["type"] == "behavioral"]

        selected_raw = technical[:n_technical] + behavioral[:n_behavioral]
        questions = [_to_interview_question(q) for q in selected_raw[:num_questions]]

        return InterviewSessionData(
            session_id=str(uuid.uuid4()),
            jd_title=jd.title,
            questions=questions,
            answers=[],
            current_question_index=0,
            status="active",
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=None,
        )
