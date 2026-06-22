"""
Unit tests for InterviewAgent.

All Qdrant (RAG) and Anthropic API calls are mocked — no external services
are required.

Patching strategy:
  - RAG:    app.rag.question_index.index_questions
            app.rag.question_index.search_questions
            (imported inside start_session via a local 'from ... import')
  - Claude: app.agents.interview_agent.anthropic.Anthropic
            (imported at the top of interview_agent.py)
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from app.agents.interview_agent import InterviewAgent
from app.models.interview import AnswerEvaluation, InterviewQuestion, InterviewSessionData
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.resume import ParsedResume


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _minimal_jd(
    title: str = "Senior Backend Engineer",
    skills: list[str] | None = None,
) -> ParsedJobDescription:
    """Build the smallest valid ParsedJobDescription for testing."""
    skill_objects = [
        JDSkillRequirement(name=s, is_required=True, category="language")
        for s in (skills or ["Python", "PostgreSQL", "Docker"])
    ]
    return ParsedJobDescription(
        title=title,
        skills=skill_objects,
        responsibilities=["Build backend services"],
        keywords=["Python", "API"],
        raw_text=f"{title} job description",
        parse_confidence=0.9,
    )


def _minimal_resume() -> ParsedResume:
    """Build the smallest valid ParsedResume for testing."""
    from app.models.resume import ResumeContact
    return ParsedResume(
        contact=ResumeContact(name="Test Candidate", email="test@example.com"),
        raw_text="Test resume",
        parse_confidence=0.9,
    )


def _fake_question(
    qid: str,
    qtype: str = "technical",
    difficulty: str = "medium",
    text: str | None = None,
    topic: str = "databases",
    role: str = "backend",
) -> dict:
    """Return a raw question dict as search_questions would return it."""
    return {
        "id":         qid,
        "text":       text or f"[{qtype}/{difficulty}] Question {qid}",
        "type":       qtype,
        "role":       role,
        "difficulty": difficulty,
        "topic":      topic,
        "score":      0.85,
    }


def _fake_eval_json(
    relevance: float = 8.0,
    depth: float = 7.0,
    communication: float = 9.0,
    overall: float = 7.9,
    strengths: list[str] | None = None,
    improvements: list[str] | None = None,
    follow_up: str | None = "Can you elaborate on that?",
) -> str:
    return json.dumps({
        "relevance":           relevance,
        "depth":               depth,
        "communication":       communication,
        "overall":             overall,
        "strengths":           strengths or ["Clear explanation", "Good examples"],
        "improvements":        improvements or ["Add more detail", "Mention trade-offs"],
        "follow_up_question":  follow_up,
    })


def _mock_claude(response_text: str) -> MagicMock:
    """Return an anthropic.Anthropic mock that yields response_text."""
    content_block = MagicMock()
    content_block.text = response_text

    message = MagicMock()
    message.content = [content_block]
    message.usage.input_tokens = 100
    message.usage.output_tokens = 80

    client = MagicMock()
    client.messages.create.return_value = message

    anthropic_cls = MagicMock(return_value=client)
    return anthropic_cls


def _session_with_questions(n: int = 3) -> InterviewSessionData:
    """Build an InterviewSessionData directly (bypass RAG)."""
    questions = [
        InterviewQuestion(
            text=f"Question {i + 1}",
            type="technical" if i % 2 == 0 else "behavioral",
            category="general",
            difficulty="medium",
            topics=["general"],
        )
        for i in range(n)
    ]
    return InterviewSessionData(
        session_id="test-session",
        jd_title="Software Engineer",
        questions=questions,
        answers=[],
        current_question_index=0,
        status="active",
        started_at=datetime.now(timezone.utc).isoformat(),
        ended_at=None,
    )


# ---------------------------------------------------------------------------
# 1. start_session returns correct number of questions
# ---------------------------------------------------------------------------

class TestStartSession:

    def test_start_session_returns_questions(self):
        """
        Mock RAG to return 5 questions (3 technical + 2 behavioral); verify
        session has exactly 5 questions with the expected type mix.
        """
        # search_questions is called 4 times (tech-easy, tech-medium, beh-medium, beh-hard)
        # Return a unique question per slot so dedup doesn't swallow any.
        search_side_effects = [
            [_fake_question("t1", "technical", "easy")],          # call 1
            [_fake_question("t2", "technical", "medium"),
             _fake_question("t3", "technical", "medium")],        # call 2
            [_fake_question("b1", "behavioral", "medium")],       # call 3
            [_fake_question("b2", "behavioral", "hard")],         # call 4
        ]

        with (
            patch("app.rag.question_index.index_questions"),
            patch("app.rag.question_index.search_questions", side_effect=search_side_effects),
        ):
            agent = InterviewAgent()
            session = agent.start_session(_minimal_jd(), _minimal_resume(), num_questions=5)

        assert len(session.questions) == 5
        assert session.status == "active"
        assert session.current_question_index == 0
        assert session.session_id  # non-empty UUID string

        types = [q.type for q in session.questions]
        assert "technical" in types
        assert "behavioral" in types

    def test_question_mix_types(self):
        """
        start_session must return approximately 60 % technical and 40 % behavioral
        (3 technical + 2 behavioral for 5 questions).
        """
        search_side_effects = [
            [_fake_question("t1", "technical", "easy")],
            [_fake_question("t2", "technical", "medium"),
             _fake_question("t3", "technical", "medium")],
            [_fake_question("b1", "behavioral", "medium")],
            [_fake_question("b2", "behavioral", "hard")],
        ]

        with (
            patch("app.rag.question_index.index_questions"),
            patch("app.rag.question_index.search_questions", side_effect=search_side_effects),
        ):
            agent = InterviewAgent()
            session = agent.start_session(_minimal_jd(), _minimal_resume(), num_questions=5)

        types = [q.type for q in session.questions]
        n_technical  = types.count("technical")
        n_behavioral = types.count("behavioral")

        assert n_technical  == 3, f"Expected 3 technical, got {n_technical}"
        assert n_behavioral == 2, f"Expected 2 behavioral, got {n_behavioral}"

    def test_rag_retrieves_relevant_questions(self):
        """
        When the JD mentions Java, search_questions must be called with a query
        that contains 'Java', and the returned questions must contain that text.
        """
        java_question = _fake_question(
            "j1", "technical", "medium",
            text="Explain the difference between Java interfaces and abstract classes.",
            topic="api_design",
        )

        def _search_side(query, role=None, type=None, difficulty=None, limit=5, **kw):
            # Only return the Java question; other calls return empty
            if type == "technical" and difficulty == "medium":
                return [java_question]
            return []

        with (
            patch("app.rag.question_index.index_questions"),
            patch("app.rag.question_index.search_questions", side_effect=_search_side) as mock_search,
        ):
            jd = _minimal_jd(title="Java Backend Engineer", skills=["Java", "Spring Boot"])
            agent = InterviewAgent()
            session = agent.start_session(jd, _minimal_resume(), num_questions=5)

        # Verify query contained 'Java'
        all_calls = mock_search.call_args_list
        queries = [c.kwargs.get("query", c.args[0] if c.args else "") for c in all_calls]
        assert any("Java" in q for q in queries), (
            f"Expected 'Java' in at least one RAG query, got: {queries}"
        )

        # The Java question must appear in the session
        texts = [q.text for q in session.questions]
        assert any("Java" in t for t in texts), (
            f"Java question not found in session: {texts}"
        )

    def test_start_session_falls_back_when_qdrant_unavailable(self):
        """
        If index_questions() raises, start_session must silently fall back to
        the in-memory question bank and still return a valid session.
        """
        with patch("app.rag.question_index.index_questions", side_effect=ConnectionError("Qdrant down")):
            agent = InterviewAgent()
            session = agent.start_session(_minimal_jd(), _minimal_resume(), num_questions=5)

        assert len(session.questions) == 5
        assert session.status == "active"


# ---------------------------------------------------------------------------
# 2. ask_next tracks progress
# ---------------------------------------------------------------------------

class TestAskNext:

    def test_ask_next_tracks_progress(self):
        """
        Calling ask_next 3 times on a 3-question session must increment
        question_number each time; the 4th call must return done=True.
        """
        agent   = InterviewAgent()
        session = _session_with_questions(3)

        results = [agent.ask_next(session) for _ in range(3)]

        for i, result in enumerate(results):
            assert result.get("done") is None, f"Call {i + 1} returned done unexpectedly"
            assert result["question_number"] == i + 1
            assert result["total_questions"] == 3
            assert result["question"] == f"Question {i + 1}"

        # 4th call — exhausted
        final = agent.ask_next(session)
        assert final.get("done") is True
        assert "complete" in final.get("message", "").lower()

    def test_ask_next_marks_session_completed(self):
        """After all questions are exhausted, session.status must be 'completed'."""
        agent   = InterviewAgent()
        session = _session_with_questions(2)

        agent.ask_next(session)
        agent.ask_next(session)
        agent.ask_next(session)  # exhausts and marks completed

        assert session.status == "completed"
        assert session.ended_at is not None

    def test_ask_next_does_not_repeat_questions(self):
        """Each ask_next call must return a different question text."""
        agent   = InterviewAgent()
        session = _session_with_questions(3)

        texts = [agent.ask_next(session)["question"] for _ in range(3)]
        assert len(set(texts)) == 3, f"Duplicate questions returned: {texts}"


# ---------------------------------------------------------------------------
# 3 & 4. evaluate_answer — scores and content
# ---------------------------------------------------------------------------

class TestEvaluateAnswer:

    def test_evaluate_answer_returns_scores(self):
        """
        Mock Claude to return valid evaluation JSON; verify all score fields
        are present and within the [0, 10] range.
        """
        eval_json = _fake_eval_json(relevance=8.0, depth=7.0, communication=9.0, overall=7.9)

        with patch("app.agents.interview_agent.anthropic.Anthropic", _mock_claude(eval_json)):
            agent   = InterviewAgent()
            session = _session_with_questions(1)
            result  = agent.evaluate_answer(session, "What is Python?", "Python is a language.")

        for field in ("relevance_score", "depth_score", "communication_score", "overall_score"):
            assert field in result, f"Missing field: {field}"
            assert 0.0 <= result[field] <= 10.0, f"{field} = {result[field]} is out of [0, 10]"

        assert result["relevance_score"]     == 8.0
        assert result["depth_score"]         == 7.0
        assert result["communication_score"] == 9.0
        assert result["overall_score"]       == 7.9

    def test_evaluate_answer_has_strengths_and_improvements(self):
        """Evaluation must include non-empty strengths and improvements lists."""
        eval_json = _fake_eval_json(
            strengths=["Clear answer", "Good structure"],
            improvements=["Add more depth", "Mention trade-offs"],
        )

        with patch("app.agents.interview_agent.anthropic.Anthropic", _mock_claude(eval_json)):
            agent   = InterviewAgent()
            session = _session_with_questions(1)
            result  = agent.evaluate_answer(session, "Describe REST APIs.", "REST uses HTTP...")

        assert isinstance(result["strengths"], list)
        assert len(result["strengths"]) > 0, "strengths must not be empty"

        assert isinstance(result["improvements"], list)
        assert len(result["improvements"]) > 0, "improvements must not be empty"

    def test_evaluate_answer_appends_to_session(self):
        """evaluate_answer must append an AnswerEvaluation to session.answers."""
        eval_json = _fake_eval_json()

        with patch("app.agents.interview_agent.anthropic.Anthropic", _mock_claude(eval_json)):
            agent   = InterviewAgent()
            session = _session_with_questions(1)
            agent.evaluate_answer(session, "Q1", "A1")

        assert len(session.answers) == 1
        record = session.answers[0]
        assert isinstance(record, AnswerEvaluation)
        assert record.question == "Q1"
        assert record.answer   == "A1"

    def test_evaluate_answer_tolerates_markdown_fences(self):
        """evaluate_answer must parse JSON even if Claude wraps it in ```json fences."""
        fenced = "```json\n" + _fake_eval_json() + "\n```"

        with patch("app.agents.interview_agent.anthropic.Anthropic", _mock_claude(fenced)):
            agent   = InterviewAgent()
            session = _session_with_questions(1)
            result  = agent.evaluate_answer(session, "Q", "A")

        assert 0.0 <= result["overall_score"] <= 10.0


# ---------------------------------------------------------------------------
# 5. Session end — full lifecycle with summary
# ---------------------------------------------------------------------------

class TestSessionEndSummary:

    def test_session_end_returns_summary(self):
        """
        Start a session, answer all questions with mocked evaluations, then
        verify the session holds all Q&A pairs and that manually-computed
        average scores match the recorded evaluations.
        """
        eval_responses = [
            _fake_eval_json(relevance=8.0, depth=6.0, communication=9.0, overall=7.5),
            _fake_eval_json(relevance=7.0, depth=8.0, communication=7.0, overall=7.4),
        ]
        call_count = [0]

        def _claude_factory(*args, **kwargs):
            idx   = call_count[0] % len(eval_responses)
            call_count[0] += 1
            mock  = _mock_claude(eval_responses[idx])
            return mock(*args, **kwargs)

        with patch("app.agents.interview_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = _claude_factory

            agent   = InterviewAgent()
            session = _session_with_questions(2)

            # Work through both questions
            for _ in range(2):
                q_dict = agent.ask_next(session)
                agent.evaluate_answer(session, q_dict["question"], f"My answer to: {q_dict['question']}")

            # Exhaust the session
            done = agent.ask_next(session)

        assert done.get("done") is True
        assert session.status    == "completed"
        assert len(session.answers) == 2

        # Verify Q&A pairing
        assert session.answers[0].question == "Question 1"
        assert session.answers[1].question == "Question 2"

        # Verify average scores match the two evaluations
        expected_avg_overall = round((7.5 + 7.4) / 2, 1)
        computed_avg = round(
            sum(a.overall_score for a in session.answers) / len(session.answers), 1
        )
        assert computed_avg == expected_avg_overall, (
            f"Expected avg overall {expected_avg_overall}, got {computed_avg}"
        )

    def test_session_accumulates_all_evaluations(self):
        """session.answers must contain one AnswerEvaluation per answered question."""
        eval_json = _fake_eval_json()

        with patch("app.agents.interview_agent.anthropic.Anthropic", _mock_claude(eval_json)):
            agent   = InterviewAgent()
            session = _session_with_questions(3)

            for i in range(3):
                q_dict = agent.ask_next(session)
                agent.evaluate_answer(session, q_dict["question"], f"Answer {i + 1}")

        assert len(session.answers) == 3
        for i, record in enumerate(session.answers):
            assert record.question == f"Question {i + 1}"
            assert record.answer   == f"Answer {i + 1}"
