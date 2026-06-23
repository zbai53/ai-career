#!/usr/bin/env python3
"""
End-to-end smoke test for the AI Career agent-service.

Tests the full user journey through the system with all external I/O mocked:
  1. Parse resume   — POST /api/resume/parse
  2. Parse JD       — POST /api/jd/parse
  3. Match          — POST /api/match          (score < 70 → triggers rewrite)
  4. ATS check      — find_missing_keywords()  (in-process, no HTTP)
  5. Rewrite        — POST /api/rewrite        (fidelity-checked)
  6. Interview x2   — start + answer × 2 + end-with-review
  7. Summary        — all scores, total time, total tokens

Mocking strategy
----------------
• Resume / JD:  workflow-level (app.graph.workflow.ResumeAgent / JDAgent)
• Match:        main-module-level (app.main.MatchAgent) → deterministic score=48
• Rewrite:      main-module-level (app.main.RewriteAgent)
• Interview:    Qdrant mocked; app.agents.interview_agent.anthropic.Anthropic mocked
• Coach review: app.agents.coach_agent.anthropic.Anthropic mocked

Run with:
    PYTHONPATH=. python tests/test_end_to_end.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.rag.ats_keywords import find_missing_keywords

# ---------------------------------------------------------------------------
# Candidate / JD profile
# ---------------------------------------------------------------------------

CANDIDATE_NAME = "Jordan Lee"
JD_TITLE       = "Senior Backend Engineer"
JD_COMPANY     = "CloudScale Systems"
NUM_QUESTIONS  = 2   # keep the test fast

RESUME_SKILLS_PRESENT = ["Python", "Docker", "Git", "REST API", "PostgreSQL"]
RESUME_RAW_TEXT = (
    "Jordan Lee  jordan.lee@example.com  "
    "Python Docker Git REST API PostgreSQL microservices unit testing"
)

# ---------------------------------------------------------------------------
# Fake Pydantic model dumps
# ---------------------------------------------------------------------------

_RESUME_DUMP = {
    "contact": {
        "name":          CANDIDATE_NAME,
        "email":         "jordan.lee@example.com",
        "phone":         None,
        "address":       "Toronto, ON",
        "linkedin_url":  None,
        "github_url":    None,
        "portfolio_url": None,
    },
    "summary": "Backend developer with 3 years of Python and REST API experience.",
    "skills": [
        {"name": "Python",     "category": "language",  "proficiency": "expert"},
        {"name": "Docker",     "category": "tool",       "proficiency": "proficient"},
        {"name": "Git",        "category": "tool",       "proficiency": "expert"},
        {"name": "REST API",   "category": "concept",    "proficiency": "expert"},
        {"name": "PostgreSQL", "category": "database",   "proficiency": "proficient"},
    ],
    "experience": [{
        "company":      "ByteFlow Inc",
        "title":        "Backend Developer",
        "location":     "Remote",
        "start_date":   "2022-01",
        "end_date":     None,
        "is_current":   True,
        "bullets":      [
            "Built REST APIs in Python/FastAPI serving 200K requests/day",
            "Containerised services with Docker; maintained PostgreSQL schemas",
        ],
        "technologies": ["Python", "Docker", "PostgreSQL", "Git"],
    }],
    "education":       [],
    "projects":        [],
    "certifications":  [],
    "raw_text":        RESUME_RAW_TEXT,
    "parse_confidence": 0.91,
}

_JD_DUMP = {
    "title":   JD_TITLE,
    "company": JD_COMPANY,
    "location": "Remote",
    "remote_type": "remote",
    "employment_type": "full-time",
    "min_years_experience": 5,
    "max_years_experience": None,
    "salary_min":      None,
    "salary_max":      None,
    "salary_currency": None,
    "responsibilities": [
        "Design and own distributed backend systems",
        "Mentor junior engineers and lead technical design reviews",
    ],
    "skills": [
        {"name": "Java",        "is_required": True,  "category": "language"},
        {"name": "Python",      "is_required": True,  "category": "language"},
        {"name": "Spring Boot", "is_required": True,  "category": "framework"},
        {"name": "PostgreSQL",  "is_required": True,  "category": "database"},
        {"name": "Kubernetes",  "is_required": True,  "category": "tool"},
        {"name": "Redis",       "is_required": False, "category": "tool"},
        {"name": "Kafka",       "is_required": False, "category": "tool"},
    ],
    "qualifications": ["Bachelor's in Computer Science or equivalent"],
    "keywords":  ["Java", "Spring Boot", "microservices", "Kubernetes", "CI/CD"],
    "industry":  "technology",
    "raw_text":  f"Senior Backend Engineer at {JD_COMPANY} — Java Spring Boot Kubernetes",
    "source_url": None,
    "parse_confidence": 0.93,
}

_MATCH_DUMP = {
    "overall_score":            48.0,
    "skill_score":              40.0,
    "experience_score":         36.0,
    "keyword_score":            40.0,
    "missing_required_skills":  ["Java", "Spring Boot", "Kubernetes"],
    "missing_preferred_skills": ["Redis", "Kafka"],
    "improvement_suggestions": [
        "Highlight any Java experience or cross-language patterns.",
        "Add Kubernetes exposure — even local Minikube usage counts.",
        "Quantify throughput and latency gains in bullet points.",
    ],
    "interview_focus_areas":   ["System design", "Distributed systems", "Java/JVM ecosystem"],
    "overall_assessment": (
        f"Jordan has solid Python and Docker fundamentals but is missing core "
        f"Java-stack skills required for the {JD_TITLE} role. "
        "A rewrite focusing on transferable patterns is recommended."
    ),
    "matched_skills":   ["Python", "PostgreSQL"],
    "matched_keywords": ["microservices"],
}

_REWRITE_DUMP = {
    "experiences": [{
        "company": "ByteFlow Inc",
        "title":   "Backend Developer",
        "original_bullets": [
            "Built REST APIs in Python/FastAPI serving 200K requests/day",
            "Containerised services with Docker; maintained PostgreSQL schemas",
        ],
        "rewritten_bullets": [
            {
                "original":   "Built REST APIs in Python/FastAPI serving 200K requests/day",
                "rewritten":  "Engineered high-throughput microservice APIs (200K req/day) applying RESTful design patterns transferable to Java/Spring Boot environments.",
                "changes_made": ["Added microservices framing", "Highlighted cross-language transferability"],
            },
            {
                "original":   "Containerised services with Docker; maintained PostgreSQL schemas",
                "rewritten":  "Containerised and orchestrated services using Docker, applying Kubernetes-compatible deployment patterns; optimised PostgreSQL schemas for sub-10ms query latency.",
                "changes_made": ["Added Kubernetes-compatible framing", "Quantified PostgreSQL latency"],
            },
        ],
    }],
    "keywords_injected":          ["microservices", "Kubernetes-compatible"],
    "overall_improvement_summary": (
        "Reframed two bullets to highlight transferable architecture patterns "
        "and quantified performance metrics. Fidelity check passed on first attempt."
    ),
    "rewrite_confidence": 0.87,
    "fidelity_report": {
        "fidelity_score": 0.94,
        "passed":         True,
        "flags":          [],
    },
    "rewrite_attempts":   1,
    "improvement_metrics": {
        "keywords_added":            ["microservices", "Kubernetes-compatible"],
        "keywords_removed":          [],
        "avg_bullet_length_change":  0.38,
        "action_verbs_improved":     2,
    },
    "fidelity_status": "passed",
}

_INTERVIEW_Q_TECH = {
    "id":         "e2e-t001",
    "text":       "What is the difference between SQL and NoSQL databases? When would you choose each?",
    "type":       "technical",
    "role":       "backend",
    "difficulty": "easy",
    "topic":      "databases",
    "score":      0.88,
}

_INTERVIEW_Q_BEH = {
    "id":         "e2e-b001",
    "text":       "Tell me about a time you had to meet a tight deadline under significant pressure.",
    "type":       "behavioral",
    "role":       "general",
    "difficulty": "medium",
    "topic":      "time_management",
    "score":      0.82,
}

_EVAL_JSON = json.dumps({
    "relevance":          8.0,
    "depth":              7.5,
    "communication":      8.5,
    "overall":            8.0,
    "strengths":          ["Clear and structured answer", "Good technical depth", "Concrete examples cited"],
    "improvements":       ["Quantify the business impact", "Mention trade-offs more explicitly"],
    "follow_up_question": "Can you walk me through how you would scale that solution?",
})

_COACH_REVIEW_JSON = json.dumps({
    "overall_score": 74.5,
    "behavioral_reviews": [{
        "question":   _INTERVIEW_Q_BEH["text"],
        "star_score": {"situation": 7.5, "task": 7.0, "action": 8.5, "result": 6.5},
        "feedback":   (
            "Good situational framing and clear action steps. "
            "The result section would benefit from quantified outcomes."
        ),
    }],
    "technical_reviews": [{
        "question":  _INTERVIEW_Q_TECH["text"],
        "accuracy":  8.5,
        "depth":     7.0,
        "practical": 7.5,
        "feedback":  (
            "Accurate distinction between SQL/NoSQL. "
            "Stronger answer would include real use-case examples (e.g. Redis for sessions)."
        ),
    }],
    "communication": {
        "clarity":     8.0,
        "conciseness": 7.5,
        "confidence":  8.0,
        "feedback":    "Well-paced responses with clear vocabulary. Minor hedging on the SQL answer.",
    },
    "top_strengths": [
        "Strong command of database fundamentals demonstrated in the SQL/NoSQL question",
        "STAR structure was clear in the deadline story — situation and action were vivid",
        "Communication was confident and easy to follow throughout",
    ],
    "areas_for_improvement": [
        "Quantify the result in the deadline story — how much was delivered and by when?",
        "Expand NoSQL use-case depth — mention specific engines (Mongo, Redis, Cassandra)",
        "Address trade-offs proactively rather than waiting for follow-up prompts",
    ],
    "recommended_topics": [
        "NoSQL engine trade-offs: MongoDB vs Cassandra vs Redis",
        "STAR method — quantifying results with metrics",
        "Distributed systems fundamentals: CAP theorem, consistency models",
    ],
    "readiness": "almost",
    "summary": (
        f"{CANDIDATE_NAME} demonstrated solid foundational knowledge across both "
        "technical and behavioural questions. Technical accuracy was good; depth "
        "of trade-off analysis could be stronger. Behavioural answers followed STAR "
        "structure but lacked quantified results. Targeted preparation on distributed "
        "systems and result quantification should bring readiness to 'yes' within "
        "1-2 weeks."
    ),
})

# ---------------------------------------------------------------------------
# Mock factory helpers
# ---------------------------------------------------------------------------

def _fake_agent_run(agent_name: str, duration_ms: int = 180, token_count: int = 120) -> dict:
    return {
        "agent_name":    agent_name,
        "input_summary": "e2e test input",
        "output_summary": "e2e test output",
        "status":        "success",
        "duration_ms":   duration_ms,
        "token_count":   token_count,
        "model_name":    "claude-haiku-4-5-20251001",
        "error_message": None,
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }


def _fake_model(dump: dict) -> MagicMock:
    """Return a MagicMock that behaves like a Pydantic model."""
    m = MagicMock()
    m.model_dump.return_value = dump
    return m


def _make_claude_single(response_text: str) -> MagicMock:
    """Anthropic class mock that always returns the same response."""
    cb = MagicMock()
    cb.text = response_text

    msg = MagicMock()
    msg.content = [cb]
    msg.usage.input_tokens  = 200
    msg.usage.output_tokens = 280

    client = MagicMock()
    client.messages.create.return_value = msg
    return MagicMock(return_value=client)


def _make_claude_sequence(responses: list[str]) -> MagicMock:
    """Anthropic class mock that returns responses in order across all instantiations."""
    def _msg(text: str) -> MagicMock:
        cb = MagicMock()
        cb.text = text
        msg = MagicMock()
        msg.content = [cb]
        msg.usage.input_tokens  = 150
        msg.usage.output_tokens = 120
        return msg

    client = MagicMock()
    client.messages.create.side_effect = [_msg(r) for r in responses]
    return MagicMock(return_value=client)


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def step1_parse_resume(client: TestClient) -> tuple[dict, int]:
    """POST /api/resume/parse — returns (resume_dict, tokens)."""
    resume_model  = _fake_model(_RESUME_DUMP)
    agent_run     = _fake_agent_run("resume_agent", duration_ms=820, token_count=340)

    with patch("app.graph.workflow.ResumeAgent") as MockRA:
        MockRA.return_value.parse.return_value = (resume_model, agent_run)
        resp = client.post(
            "/api/resume/parse",
            files={"file": ("jordan_lee_resume.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )

    assert resp.status_code == 200, f"Step 1 failed [{resp.status_code}]: {resp.text}"
    data = resp.json()

    contact = data.get("contact", {})
    skills  = data.get("skills", [])
    exp     = data.get("experience", [])
    tokens  = agent_run["token_count"]

    print(
        f"  ✓ Resume parsed: {contact.get('name', '?')}, "
        f"{len(skills)} skills, "
        f"{len(exp)} experience(s)"
    )
    return data, tokens


def step2_parse_jd(client: TestClient) -> tuple[dict, int]:
    """POST /api/jd/parse — returns (jd_dict, tokens)."""
    jd_model  = _fake_model(_JD_DUMP)
    agent_run = _fake_agent_run("jd_agent", duration_ms=650, token_count=290)

    with patch("app.graph.workflow.JDAgent") as MockJD:
        MockJD.return_value.parse.return_value = (jd_model, agent_run)
        resp = client.post(
            "/api/jd/parse",
            json={"text": _JD_DUMP["raw_text"]},
        )

    assert resp.status_code == 200, f"Step 2 failed [{resp.status_code}]: {resp.text}"
    data = resp.json()

    required = [s for s in data.get("skills", []) if s.get("is_required")]
    tokens   = agent_run["token_count"]

    print(
        f"  ✓ JD parsed: {data.get('title', '?')} at {data.get('company', '?')}, "
        f"{len(required)} required skill(s)"
    )
    return data, tokens


def step3_match(client: TestClient, resume_data: dict, jd_data: dict) -> tuple[dict, int]:
    """POST /api/match — returns (match_dict, tokens)."""
    match_model = _fake_model(_MATCH_DUMP)
    agent_run   = _fake_agent_run("match_agent", duration_ms=1240, token_count=850)

    with patch("app.main.MatchAgent") as MockMA:
        MockMA.return_value.match.return_value = (match_model, agent_run)
        resp = client.post(
            "/api/match",
            json={"resume": resume_data, "jd": jd_data},
        )

    assert resp.status_code == 200, f"Step 3 failed [{resp.status_code}]: {resp.text}"
    data   = resp.json()
    tokens = agent_run["token_count"]

    print(
        f"  ✓ Match scored: "
        f"overall={data.get('overall_score', '?')}, "
        f"skill={data.get('skill_score', '?')}, "
        f"experience={data.get('experience_score', '?')}, "
        f"keyword={data.get('keyword_score', '?')}"
    )
    return data, tokens


def step4_ats_check(resume_raw_text: str) -> dict:
    """find_missing_keywords — in-process, no HTTP call."""
    result = find_missing_keywords(resume_raw_text, "technology", "backend_engineer")
    pct    = result["coverage_percent"]
    miss5  = result["missing"][:5]

    print(
        f"  ✓ ATS check (technology/backend_engineer): "
        f"{pct}% coverage, "
        f"missing: {miss5}"
        + (" …" if len(result["missing"]) > 5 else "")
    )
    return result


def step5_rewrite(
    client:      TestClient,
    resume_data: dict,
    jd_data:     dict,
    match_data:  dict,
) -> tuple[dict, int]:
    """POST /api/rewrite — returns (rewrite_dict, tokens)."""
    rewrite_model = _fake_model(_REWRITE_DUMP)
    agent_run     = _fake_agent_run("rewrite_agent", duration_ms=2350, token_count=1120)

    with patch("app.main.RewriteAgent") as MockRW:
        MockRW.return_value.rewrite.return_value = (rewrite_model, agent_run)
        resp = client.post(
            "/api/rewrite",
            json={
                "resume":       resume_data,
                "jd":           jd_data,
                "match_result": match_data,
            },
        )

    assert resp.status_code == 200, f"Step 5 failed [{resp.status_code}]: {resp.text}"
    data   = resp.json()
    tokens = agent_run["token_count"]

    fidelity = data.get("fidelity_report", {}).get("fidelity_score", "?")
    attempts = data.get("rewrite_attempts", "?")

    print(f"  ✓ Rewrite done: fidelity={fidelity}, attempts={attempts}")
    return data, tokens


def step6_interview(
    client:      TestClient,
    resume_data: dict,
    jd_data:     dict,
) -> tuple[dict, int]:
    """
    Full interview flow:
      POST /api/interview/start
      POST /api/interview/{id}/answer × 2
      POST /api/interview/{id}/end-with-review

    Returns (end_body, total_tokens).
    """
    # search_questions is called 4 times per start_session (one per slot):
    #   slot 1 — technical/easy   → 1 result
    #   slot 2 — technical/medium → 0 results (n=0 for 2-Q session)
    #   slot 3 — behavioral/medium → 1 result
    #   slot 4 — behavioral/hard  → 0 results (n=0 for 2-Q session)
    search_side_effects = [
        [_INTERVIEW_Q_TECH],  # slot 1
        [],                   # slot 2
        [_INTERVIEW_Q_BEH],   # slot 3
        [],                   # slot 4
    ]

    # Two evaluation calls (Q1 + Q2), both high-scoring → next_question / done
    mock_interview_claude = _make_claude_sequence([_EVAL_JSON, _EVAL_JSON])
    # One coach review call
    mock_coach_claude = _make_claude_single(_COACH_REVIEW_JSON)

    total_tokens = 0
    body_end     = {}

    with (
        patch("app.rag.question_index.index_questions"),
        patch("app.rag.question_index.search_questions",
              side_effect=search_side_effects),
        patch("app.agents.interview_agent.anthropic.Anthropic",
              mock_interview_claude),
        patch("app.agents.coach_agent.anthropic.Anthropic",
              mock_coach_claude),
    ):
        # ── 6a. Start ────────────────────────────────────────────────────────
        resp_start = client.post(
            "/api/interview/start",
            json={
                "jd":           jd_data,
                "resume":       resume_data,
                "num_questions": NUM_QUESTIONS,
            },
        )
        assert resp_start.status_code == 200, (
            f"Step 6 start failed [{resp_start.status_code}]: {resp_start.text}"
        )
        start_body = resp_start.json()
        session_id = start_body["session_id"]

        # ── 6b. Answer Q1 ────────────────────────────────────────────────────
        resp_a1 = client.post(
            f"/api/interview/{session_id}/answer",
            json={
                "answer": (
                    "SQL is a relational database with ACID guarantees and a fixed schema. "
                    "NoSQL databases trade strict consistency for horizontal scalability. "
                    "I would choose PostgreSQL for structured transactional data "
                    "and Redis or MongoDB when I need flexible schemas or caching at scale."
                )
            },
        )
        assert resp_a1.status_code == 200, (
            f"Step 6 answer 1 failed [{resp_a1.status_code}]: {resp_a1.text}"
        )
        a1_body = resp_a1.json()
        # Accumulate interview eval tokens (mocked: 150 + 120 per call)
        total_tokens += 270

        # ── 6c. Answer Q2 ────────────────────────────────────────────────────
        resp_a2 = client.post(
            f"/api/interview/{session_id}/answer",
            json={
                "answer": (
                    "In my last role we had a hard launch deadline for a payment integration. "
                    "I broke the feature into three parallel tracks, held daily stand-ups "
                    "to surface blockers early, and delivered all three tracks 6 hours before "
                    "the deadline with full test coverage."
                )
            },
        )
        assert resp_a2.status_code == 200, (
            f"Step 6 answer 2 failed [{resp_a2.status_code}]: {resp_a2.text}"
        )
        a2_body = resp_a2.json()
        total_tokens += 270

        # ── 6d. End with review ──────────────────────────────────────────────
        # Build minimal valid JD and resume dicts for the end-with-review body
        minimal_jd = {
            "title":           jd_data.get("title", JD_TITLE),
            "skills":          jd_data.get("skills", []),
            "responsibilities": jd_data.get("responsibilities", []),
            "keywords":         jd_data.get("keywords", []),
            "raw_text":         jd_data.get("raw_text", ""),
            "parse_confidence": jd_data.get("parse_confidence", 0.9),
        }
        minimal_resume = {
            "contact":          resume_data.get("contact", {"name": CANDIDATE_NAME}),
            "raw_text":         resume_data.get("raw_text", RESUME_RAW_TEXT),
            "parse_confidence": resume_data.get("parse_confidence", 0.9),
        }

        # Retrieve the live session state to build the request body
        from app.main import _sessions
        live_session = _sessions.get(session_id)
        assert live_session is not None, f"Session {session_id!r} not found in _sessions"

        resp_end = client.post(
            f"/api/interview/{session_id}/end-with-review",
            json={
                "session": live_session.model_dump(),
                "jd":      minimal_jd,
                "resume":  minimal_resume,
            },
        )
        assert resp_end.status_code == 200, (
            f"Step 6 end failed [{resp_end.status_code}]: {resp_end.text}"
        )
        body_end = resp_end.json()
        # Coach review token count (mocked: 200 + 280)
        total_tokens += 480

    coach = body_end.get("coach_review") or {}
    avg   = body_end.get("average_scores", {})

    print(
        f"  ✓ Interview complete ({NUM_QUESTIONS} questions): "
        f"avg_overall={avg.get('overall', '?')}, "
        f"readiness={coach.get('readiness', '?')}"
    )
    return body_end, total_tokens


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    from app.main import app as fastapi_app

    client     = TestClient(fastapi_app)
    t_pipeline = time.perf_counter()
    all_tokens = 0

    print("=" * 62)
    print("  AI Career — End-to-End Pipeline Smoke Test")
    print("=" * 62)

    # ── Step 1: Parse resume ─────────────────────────────────────────────────
    print("\nStep 1 — Parse Resume")
    resume_data, tok1 = step1_parse_resume(client)
    all_tokens += tok1

    # ── Step 2: Parse JD ─────────────────────────────────────────────────────
    print("\nStep 2 — Parse Job Description")
    jd_data, tok2 = step2_parse_jd(client)
    all_tokens += tok2

    # ── Step 3: Match ─────────────────────────────────────────────────────────
    print("\nStep 3 — Match Resume ↔ JD")
    match_data, tok3 = step3_match(client, resume_data, jd_data)
    all_tokens += tok3
    overall_score = match_data.get("overall_score", 0)

    # ── Step 4: ATS keyword check ─────────────────────────────────────────────
    print("\nStep 4 — ATS Keyword Coverage Check")
    raw_text = resume_data.get("raw_text") or RESUME_RAW_TEXT
    ats_result = step4_ats_check(raw_text)

    # ── Step 5: Rewrite (conditional) ────────────────────────────────────────
    rewrite_data: dict = {}
    if overall_score < 70:
        print(f"\nStep 5 — Rewrite Resume (score={overall_score} < 70 → triggered)")
        rewrite_data, tok5 = step5_rewrite(client, resume_data, jd_data, match_data)
        all_tokens += tok5
    else:
        print(f"\nStep 5 — Rewrite skipped (score={overall_score} ≥ 70)")

    # ── Step 6: Interview ─────────────────────────────────────────────────────
    print(f"\nStep 6 — Mock Interview ({NUM_QUESTIONS} questions)")
    end_body, tok6 = step6_interview(client, resume_data, jd_data)
    all_tokens += tok6

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed_s = time.perf_counter() - t_pipeline
    avg_scores = end_body.get("average_scores", {})
    coach      = end_body.get("coach_review") or {}

    print("\n" + "=" * 62)
    print("  PIPELINE SUMMARY")
    print("=" * 62)
    print(f"  Candidate       : {CANDIDATE_NAME}")
    print(f"  Target role     : {JD_TITLE} @ {JD_COMPANY}")
    print(f"  Total time      : {elapsed_s:.2f}s")
    print(f"  Total tokens    : {all_tokens:,}")
    print()
    print("  ── Match scores ──────────────────────────────────────")
    print(f"  Overall         : {match_data.get('overall_score', '?')}/100")
    print(f"  Skill           : {match_data.get('skill_score', '?')}/100")
    print(f"  Experience      : {match_data.get('experience_score', '?')}/100")
    print(f"  Keyword         : {match_data.get('keyword_score', '?')}/100")
    print(f"  Rewrite         : {'✓ done' if rewrite_data else 'skipped'}", end="")
    if rewrite_data:
        fid = rewrite_data.get("fidelity_report", {}).get("fidelity_score", "?")
        att = rewrite_data.get("rewrite_attempts", "?")
        print(f" (fidelity={fid}, attempts={att})", end="")
    print()
    print()
    print("  ── ATS coverage ──────────────────────────────────────")
    print(f"  Coverage        : {ats_result['coverage_percent']}%")
    print(f"  Present         : {ats_result['present']}")
    print(f"  Missing         : {ats_result['missing'][:6]}"
          + (" …" if len(ats_result["missing"]) > 6 else ""))
    print()
    print("  ── Interview scores ──────────────────────────────────")
    print(f"  Avg relevance   : {avg_scores.get('relevance', '?')}/10")
    print(f"  Avg depth       : {avg_scores.get('depth', '?')}/10")
    print(f"  Avg comm.       : {avg_scores.get('communication', '?')}/10")
    print(f"  Avg overall     : {avg_scores.get('overall', '?')}/10")
    print()
    print("  ── Coach review ──────────────────────────────────────")
    print(f"  Coach score     : {coach.get('overall_score', '?')}/100")
    print(f"  Readiness       : {coach.get('readiness', '?')}")
    for s in (coach.get("top_strengths") or []):
        print(f"    ★ {s}")
    for i in (coach.get("areas_for_improvement") or []):
        print(f"    ↑ {i}")
    print()
    print("  All steps completed successfully. ✓")
    print("=" * 62)


if __name__ == "__main__":
    main()
