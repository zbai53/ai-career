"""
Unit + integration tests for CoachAgent.

All Anthropic API calls are mocked — no external services required.
The TestClient test directly injects pre-built sessions into app.main._sessions
to avoid the full HTTP start/answer flow while still exercising the real
/end-with-review endpoint.

Patching target for Claude: app.agents.coach_agent.anthropic.Anthropic
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.coach_agent import CoachAgent
from app.models.coach_review import (
    BehavioralReview,
    CoachReview,
    CommunicationReview,
    STARScore,
    TechnicalReview,
)
from app.models.interview import AnswerEvaluation, InterviewQuestion, InterviewSessionData
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.resume import ParsedResume, ResumeContact


# ---------------------------------------------------------------------------
# Shared fixtures & factories
# ---------------------------------------------------------------------------

def _minimal_jd(title: str = "Senior Backend Engineer") -> ParsedJobDescription:
    return ParsedJobDescription(
        title=title,
        skills=[
            JDSkillRequirement(name="Python",     is_required=True,  category="language"),
            JDSkillRequirement(name="PostgreSQL",  is_required=True,  category="database"),
            JDSkillRequirement(name="Docker",      is_required=False, category="tool"),
        ],
        responsibilities=["Design backend services", "Mentor junior engineers"],
        keywords=["Python", "REST", "microservices"],
        raw_text=f"{title} — backend systems",
        parse_confidence=0.9,
    )


def _minimal_resume() -> ParsedResume:
    return ParsedResume(
        contact=ResumeContact(name="Alex Tester", email="alex@example.com"),
        raw_text="Python PostgreSQL Docker FastAPI microservices",
        parse_confidence=0.9,
    )


def _make_question(text: str, qtype: str = "technical", difficulty: str = "medium") -> InterviewQuestion:
    return InterviewQuestion(
        text=text,
        type=qtype,
        category="databases" if qtype == "technical" else "teamwork",
        difficulty=difficulty,
        topics=["databases" if qtype == "technical" else "teamwork"],
    )


def _make_answer(
    question: str,
    answer: str,
    relevance: float = 7.0,
    depth: float = 7.0,
    communication: float = 8.0,
    overall: float = 7.3,
    strengths: list[str] | None = None,
    improvements: list[str] | None = None,
) -> AnswerEvaluation:
    return AnswerEvaluation(
        question=question,
        answer=answer,
        relevance_score=relevance,
        depth_score=depth,
        communication_score=communication,
        overall_score=overall,
        strengths=strengths or ["Clear and direct", "Good structure"],
        improvements=improvements or ["Add more detail", "Quantify outcomes"],
        follow_up=None,
    )


def _make_session(
    questions: list[InterviewQuestion],
    answers: list[AnswerEvaluation],
    session_id: str = "test-session",
    jd_title: str = "Senior Backend Engineer",
) -> InterviewSessionData:
    now = datetime.now(timezone.utc).isoformat()
    return InterviewSessionData(
        session_id=session_id,
        jd_title=jd_title,
        questions=questions,
        answers=answers,
        current_question_index=len(questions),
        status="completed",
        started_at=now,
        ended_at=now,
    )


def _mock_claude(response_text: str) -> MagicMock:
    """Return an anthropic.Anthropic class mock that yields response_text."""
    content_block = MagicMock()
    content_block.text = response_text

    message = MagicMock()
    message.content = [content_block]
    message.usage.input_tokens = 200
    message.usage.output_tokens = 300

    client = MagicMock()
    client.messages.create.return_value = message

    cls = MagicMock(return_value=client)
    return cls


def _coach_review_json(
    overall_score: float = 72.0,
    readiness: str = "almost",
    strengths: list[str] | None = None,
    improvements: list[str] | None = None,
    behavioral_questions: list[str] | None = None,
    technical_questions: list[str] | None = None,
) -> str:
    behavioral_reviews = [
        {
            "question": q,
            "star_score": {"situation": 7.0, "task": 6.0, "action": 8.0, "result": 5.0},
            "feedback": f"Good action description for '{q[:30]}...', but result lacked quantification.",
        }
        for q in (behavioral_questions or [])
    ]
    technical_reviews = [
        {
            "question": q,
            "accuracy":  8.0,
            "depth":     7.0,
            "practical": 6.0,
            "feedback": f"Technically accurate for '{q[:30]}...'; more real-world examples would help.",
        }
        for q in (technical_questions or [])
    ]
    return json.dumps({
        "overall_score": overall_score,
        "behavioral_reviews": behavioral_reviews,
        "technical_reviews": technical_reviews,
        "communication": {
            "clarity":     8.0,
            "conciseness": 7.5,
            "confidence":  7.0,
            "feedback": "Answers were clear and well-paced; occasional hedging language noted.",
        },
        "top_strengths": (strengths or [
            "Demonstrated strong Python expertise in the REST API design question",
            "Used a concrete STAR story when discussing the deadline question",
            "Showed clear understanding of PostgreSQL indexing trade-offs",
        ])[:3],
        "areas_for_improvement": (improvements or [
            "Quantify outcomes — e.g. add latency numbers to the API caching answer",
            "Expand STAR Results — the conflict resolution story ended without a clear outcome",
            "Broaden distributed systems knowledge beyond current project scope",
        ])[:3],
        "recommended_topics": [
            "Database query optimization and indexing strategies",
            "Distributed systems: CAP theorem, eventual consistency",
            "STAR method — quantifying results with metrics",
        ],
        "readiness": readiness,
        "summary": (
            "Alex demonstrated solid Python and database skills throughout the interview. "
            "Technical answers were accurate but could benefit from deeper trade-off analysis. "
            "Behavioral answers followed STAR structure but lacked quantified outcomes. "
            "With focused preparation on results quantification, Alex should be interview-ready."
        ),
    })


# ---------------------------------------------------------------------------
# 1. test_review_returns_valid_coach_review
# ---------------------------------------------------------------------------

def test_review_returns_valid_coach_review():
    """
    Mock Claude to return a complete review JSON; verify CoachReview has
    all expected top-level fields with correct types.
    """
    bq = "Tell me about a time you had to meet a tight deadline."
    tq = "How would you design a rate limiter for an API?"

    questions = [_make_question(bq, "behavioral"), _make_question(tq, "technical")]
    answers   = [
        _make_answer(bq, "At my previous job, we had a sprint with a Friday launch..."),
        _make_answer(tq, "I would use a token bucket algorithm backed by Redis..."),
    ]
    session = _make_session(questions, answers)

    review_json = _coach_review_json(
        behavioral_questions=[bq],
        technical_questions=[tq],
    )

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        agent = CoachAgent()
        review, agent_run = agent.review(session, _minimal_jd(), _minimal_resume())

    assert isinstance(review, CoachReview)

    # Top-level fields
    assert isinstance(review.overall_score,          float)
    assert isinstance(review.behavioral_reviews,     list)
    assert isinstance(review.technical_reviews,      list)
    assert isinstance(review.communication,          CommunicationReview)
    assert isinstance(review.top_strengths,          list)
    assert isinstance(review.areas_for_improvement,  list)
    assert isinstance(review.recommended_topics,     list)
    assert review.readiness in ("yes", "almost", "needs_more_practice")
    assert isinstance(review.summary, str) and len(review.summary) > 0

    # agent_run logging
    assert agent_run["agent_name"] == "coach_agent"
    assert agent_run["status"]     == "success"
    assert agent_run["token_count"] > 0


# ---------------------------------------------------------------------------
# 2. test_review_scores_within_range
# ---------------------------------------------------------------------------

def test_review_scores_within_range():
    """All numeric scores must be within their declared ranges."""
    bq = "Describe a conflict you resolved with a teammate."
    tq = "What is the difference between SQL and NoSQL?"

    questions = [_make_question(bq, "behavioral"), _make_question(tq, "technical")]
    answers   = [
        _make_answer(bq, "I once had a disagreement about database schema choices..."),
        _make_answer(tq, "SQL is relational with ACID guarantees; NoSQL trades consistency..."),
    ]
    session = _make_session(questions, answers)

    review_json = _coach_review_json(
        overall_score=65.0,
        behavioral_questions=[bq],
        technical_questions=[tq],
    )

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    # overall_score: 0–100
    assert 0.0 <= review.overall_score <= 100.0, f"overall_score={review.overall_score}"

    # behavioral STAR scores: 0–10
    for br in review.behavioral_reviews:
        for field in ("situation", "task", "action", "result"):
            v = getattr(br.star_score, field)
            assert 0.0 <= v <= 10.0, f"STAR.{field}={v}"

    # technical scores: 0–10
    for tr in review.technical_reviews:
        for field in ("accuracy", "depth", "practical"):
            v = getattr(tr, field)
            assert 0.0 <= v <= 10.0, f"TechnicalReview.{field}={v}"

    # communication scores: 0–10
    for field in ("clarity", "conciseness", "confidence"):
        v = getattr(review.communication, field)
        assert 0.0 <= v <= 10.0, f"communication.{field}={v}"


# ---------------------------------------------------------------------------
# 3. test_review_has_star_analysis_for_behavioral
# ---------------------------------------------------------------------------

def test_review_has_star_analysis_for_behavioral():
    """
    A session with 2 behavioral answers must produce 2 BehavioralReview entries,
    each containing a valid STARScore.
    """
    bq1 = "Tell me about a time you failed and what you learned."
    bq2 = "Describe how you handle disagreements with your manager."

    questions = [_make_question(bq1, "behavioral"), _make_question(bq2, "behavioral")]
    answers   = [
        _make_answer(
            bq1,
            "During a product launch I underestimated infrastructure load. "
            "The site went down for 20 minutes. I learned to always run load tests.",
        ),
        _make_answer(
            bq2,
            "I once disagreed about a DB migration strategy. I prepared a written "
            "comparison of both approaches and we aligned on mine after discussion.",
        ),
    ]
    session = _make_session(questions, answers)

    review_json = _coach_review_json(
        behavioral_questions=[bq1, bq2],
        technical_questions=[],
    )

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    assert len(review.behavioral_reviews) == 2, (
        f"Expected 2 behavioral reviews, got {len(review.behavioral_reviews)}"
    )

    for i, br in enumerate(review.behavioral_reviews):
        assert isinstance(br, BehavioralReview), f"Entry {i} is not a BehavioralReview"
        assert isinstance(br.star_score, STARScore), f"Entry {i} has no STARScore"
        assert isinstance(br.question, str) and br.question, f"Entry {i} has no question text"
        assert isinstance(br.feedback, str) and br.feedback, f"Entry {i} has no feedback"
        # Each STAR component must be a float
        for attr in ("situation", "task", "action", "result"):
            assert isinstance(getattr(br.star_score, attr), float), (
                f"STAR.{attr} is not a float for entry {i}"
            )


# ---------------------------------------------------------------------------
# 4. test_review_has_technical_analysis
# ---------------------------------------------------------------------------

def test_review_has_technical_analysis():
    """
    A session with 2 technical answers must produce 2 TechnicalReview entries,
    each with accuracy, depth, and practical scores.
    """
    tq1 = "How does database indexing work and when should you use it?"
    tq2 = "Explain REST vs GraphQL trade-offs for a high-traffic API."

    questions = [_make_question(tq1, "technical"), _make_question(tq2, "technical")]
    answers   = [
        _make_answer(
            tq1,
            "An index is a B-tree (or hash for equality) data structure that lets "
            "the engine skip full table scans. Use it on high-cardinality columns "
            "that appear in WHERE clauses. Avoid over-indexing — writes get slower.",
            depth=9.0,
        ),
        _make_answer(
            tq2,
            "REST is simpler and cacheable; GraphQL reduces over-fetching but adds "
            "complexity. For read-heavy traffic I'd use REST with HTTP caching.",
            depth=7.0,
        ),
    ]
    session = _make_session(questions, answers)

    review_json = _coach_review_json(
        technical_questions=[tq1, tq2],
        behavioral_questions=[],
    )

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    assert len(review.technical_reviews) == 2, (
        f"Expected 2 technical reviews, got {len(review.technical_reviews)}"
    )

    for i, tr in enumerate(review.technical_reviews):
        assert isinstance(tr, TechnicalReview), f"Entry {i} is not a TechnicalReview"
        assert isinstance(tr.question, str) and tr.question
        assert isinstance(tr.feedback, str) and tr.feedback
        for field in ("accuracy", "depth", "practical"):
            v = getattr(tr, field)
            assert isinstance(v, float), f"{field} is not a float for entry {i}"
            assert 0.0 <= v <= 10.0, f"{field}={v} out of range for entry {i}"


# ---------------------------------------------------------------------------
# 5. test_review_readiness_categories
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("overall_score,expected_readiness", [
    (82.0, "yes"),
    (63.0, "almost"),
    (44.0, "needs_more_practice"),
])
def test_review_readiness_categories(overall_score: float, expected_readiness: str):
    """
    Readiness must reflect the score level returned by Claude
    (or derived from overall_score if Claude returns an invalid value).
    """
    q = "Tell me about yourself."
    questions = [_make_question(q, "behavioral")]
    answers   = [_make_answer(q, "I am a backend engineer with 4 years of Python experience.")]
    session   = _make_session(questions, answers)

    review_json = _coach_review_json(
        overall_score=overall_score,
        readiness=expected_readiness,
        behavioral_questions=[q],
        technical_questions=[],
    )

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    assert review.readiness == expected_readiness, (
        f"overall_score={overall_score}: expected '{expected_readiness}', got '{review.readiness}'"
    )


def test_readiness_derived_from_score_when_claude_returns_invalid():
    """
    If Claude returns an unrecognised readiness string, it must be derived
    from overall_score using the fallback thresholds (≥75 → yes, ≥50 → almost).
    """
    q = "Tell me about a project you are proud of."
    questions = [_make_question(q, "behavioral")]
    answers   = [_make_answer(q, "I built a distributed caching layer that cut p99 by 40%.")]
    session   = _make_session(questions, answers)

    # Inject an invalid readiness value; overall_score=80 should map to "yes"
    bad_json = json.loads(_coach_review_json(overall_score=80.0, behavioral_questions=[q]))
    bad_json["readiness"] = "strong_yes"   # not a valid Literal
    review_json = json.dumps(bad_json)

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    assert review.readiness == "yes", (
        f"Expected 'yes' (score=80 fallback), got '{review.readiness}'"
    )


# ---------------------------------------------------------------------------
# 6. test_review_includes_specific_examples
# ---------------------------------------------------------------------------

def test_review_includes_specific_examples():
    """
    top_strengths and areas_for_improvement must reference specific content
    from the candidate's answers, not just generic advice.
    """
    tq = "Describe how you optimised a slow SQL query."
    bq = "Tell me about a time you had to learn a new technology fast."

    questions = [_make_question(tq, "technical"), _make_question(bq, "behavioral")]
    answers   = [
        _make_answer(
            tq,
            "I profiled the query with EXPLAIN ANALYZE, added a composite index on "
            "(user_id, created_at), and reduced response time from 800ms to 12ms.",
        ),
        _make_answer(
            bq,
            "When we migrated to Kubernetes I had two weeks to learn it. "
            "I worked through the official docs and deployed our first service.",
        ),
    ]
    session = _make_session(questions, answers)

    # Craft mock strengths and improvements that reference the actual answer content
    specific_strengths = [
        "In the SQL optimisation answer, cited concrete metrics (800ms → 12ms) showing impact",
        "Used EXPLAIN ANALYZE in the answer — demonstrates hands-on profiling knowledge",
        "STAR structure was clear in the Kubernetes answer with a specific two-week timeline",
    ]
    specific_improvements = [
        "In the Kubernetes answer, state the outcome more explicitly — did the migration succeed?",
        "Expand on why a composite index on (user_id, created_at) was the right choice",
        "Mention what you would do differently to scale Kubernetes learning for the team",
    ]

    review_json = _coach_review_json(
        strengths=specific_strengths,
        improvements=specific_improvements,
        technical_questions=[tq],
        behavioral_questions=[bq],
    )

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    assert len(review.top_strengths) == 3
    assert len(review.areas_for_improvement) == 3

    # Each strength must reference something specific from an answer
    for strength in review.top_strengths:
        assert len(strength) > 20, f"Strength too generic: '{strength}'"

    # Each improvement must be actionable (contains a verb phrase)
    action_verbs = {"state", "expand", "mention", "quantify", "add", "describe", "show", "clarify"}
    for improvement in review.areas_for_improvement:
        has_action = any(v in improvement.lower() for v in action_verbs)
        assert has_action, f"Improvement lacks actionable language: '{improvement}'"

    # Strengths must reference content from the answers
    combined_strength_text = " ".join(review.top_strengths).lower()
    assert any(kw in combined_strength_text for kw in ("sql", "800ms", "kubernetes", "index", "star")), (
        f"top_strengths don't reference answer content: {review.top_strengths}"
    )


# ---------------------------------------------------------------------------
# 7. test_end_session_includes_coach_review (TestClient integration)
# ---------------------------------------------------------------------------

def test_end_session_includes_coach_review():
    """
    POST /api/interview/{session_id}/end-with-review must return a response that
    includes a 'coach_review' key with a full CoachReview payload.

    Strategy: inject a pre-built session directly into app.main._sessions to
    bypass the start/answer flow, then call /end-with-review with mock JD/resume
    and a mocked CoachAgent.
    """
    from app.main import app as fastapi_app
    import app.main as main_module

    bq = "Tell me about a time you handled competing priorities."
    tq = "Explain how you would design a caching strategy."

    questions = [_make_question(bq, "behavioral"), _make_question(tq, "technical")]
    answers   = [
        _make_answer(
            bq,
            "In Q3 I had three concurrent deadlines. I mapped dependencies, "
            "negotiated a two-day extension on one, and shipped on time.",
            relevance=8.0, depth=7.0, communication=8.5, overall=7.8,
        ),
        _make_answer(
            tq,
            "I use a read-through cache with Redis. TTL is set per object type — "
            "user profiles at 5 min, product data at 60 min.",
            relevance=9.0, depth=8.0, communication=8.0, overall=8.3,
        ),
    ]

    injected_session = _make_session(
        questions, answers,
        session_id="end-review-test-session",
        jd_title="Backend Engineer",
    )

    # Minimal valid JD and resume dicts for the request body
    jd_dict = {
        "title": "Backend Engineer",
        "skills": [],
        "responsibilities": [],
        "keywords": ["Python", "Redis"],
        "raw_text": "Backend Engineer — Python Redis",
        "parse_confidence": 0.9,
    }
    resume_dict = {
        "contact": {"name": "Test Candidate", "email": "test@example.com"},
        "raw_text": "Python Redis backend engineer",
        "parse_confidence": 0.9,
    }

    review_json = _coach_review_json(
        overall_score=76.0,
        readiness="yes",
        behavioral_questions=[bq],
        technical_questions=[tq],
        strengths=[
            "Strong Redis caching knowledge shown in technical answer",
            "Concrete timeline (Q3) cited in priority management story",
            "Clear communication throughout both answers",
        ],
        improvements=[
            "Quantify the outcome of the caching strategy (latency improvement)",
            "Specify the final result of the competing-priorities situation",
            "Discuss trade-offs of TTL settings under high write load",
        ],
    )

    with (
        patch.dict(main_module._sessions, {"end-review-test-session": injected_session}),
        patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(review_json)),
    ):
        client = TestClient(fastapi_app)
        response = client.post(
            "/api/interview/end-review-test-session/end-with-review",
            json={
                "session": injected_session.model_dump(),
                "jd":      jd_dict,
                "resume":  resume_dict,
            },
        )

    assert response.status_code == 200, f"Unexpected status: {response.status_code} — {response.text}"
    body = response.json()

    # Session summary fields
    assert body["session_id"]         == "end-review-test-session"
    assert body["status"]             == "completed"
    assert body["questions_answered"] == 2

    # Aggregate scores
    avg = body["average_scores"]
    assert avg["overall"] == round((7.8 + 8.3) / 2, 1)

    # Coach review must be present and non-null
    assert "coach_review" in body, f"'coach_review' key missing from response: {list(body.keys())}"
    cr = body["coach_review"]
    assert cr is not None, "coach_review is null"

    # Spot-check coach review structure
    assert 0.0 <= cr["overall_score"] <= 100.0
    assert cr["readiness"] in ("yes", "almost", "needs_more_practice")
    assert isinstance(cr["top_strengths"], list) and len(cr["top_strengths"]) > 0
    assert isinstance(cr["areas_for_improvement"], list) and len(cr["areas_for_improvement"]) > 0
    assert isinstance(cr["summary"], str) and cr["summary"]
    assert "communication" in cr


# ---------------------------------------------------------------------------
# Edge-case: tolerates markdown-fenced JSON from Claude
# ---------------------------------------------------------------------------

def test_review_tolerates_markdown_fences():
    """CoachAgent must parse Claude's response even when wrapped in ```json fences."""
    q = "What is your greatest technical achievement?"
    questions = [_make_question(q, "technical")]
    answers   = [_make_answer(q, "I built a distributed job queue that handled 1M tasks/day.")]
    session   = _make_session(questions, answers)

    fenced = "```json\n" + _coach_review_json(overall_score=70.0, technical_questions=[q]) + "\n```"

    with patch("app.agents.coach_agent.anthropic.Anthropic", _mock_claude(fenced)):
        review, _ = CoachAgent().review(session, _minimal_jd(), _minimal_resume())

    assert 0.0 <= review.overall_score <= 100.0
    assert review.readiness in ("yes", "almost", "needs_more_practice")
