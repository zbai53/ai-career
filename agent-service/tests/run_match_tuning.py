"""
Manual scoring tuner — not a pytest file.

Run from the agent-service directory:

    ANTHROPIC_API_KEY=<key> python -m tests.run_match_tuning

Prints per-dimension scores for three candidate/JD pairs so you can sanity-check
that the scoring feels correct before running the full test suite.
"""

import os

from app.agents.match_agent import MatchAgent
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)

# ---------------------------------------------------------------------------
# Shared candidate — a solid senior backend engineer
# ---------------------------------------------------------------------------

CANDIDATE = ParsedResume(
    contact=ResumeContact(name="Alex Chen", email="alex@example.com"),
    summary="Senior backend engineer with 6 years of experience in Python, Java, and cloud-native systems.",
    skills=[
        ResumeSkill(name="Python", category="language"),
        ResumeSkill(name="Java", category="language"),
        ResumeSkill(name="Spring Boot", category="framework"),
        ResumeSkill(name="FastAPI", category="framework"),
        ResumeSkill(name="PostgreSQL", category="database"),
        ResumeSkill(name="Redis", category="database"),
        ResumeSkill(name="Docker", category="tool"),
        ResumeSkill(name="Kubernetes", category="tool"),
        ResumeSkill(name="AWS", category="cloud"),
        ResumeSkill(name="REST API", category="skill"),
        ResumeSkill(name="CI/CD", category="skill"),
    ],
    experience=[
        ResumeExperience(
            company="Stripe",
            title="Senior Software Engineer",
            start_date="2021-06",
            end_date=None,
            is_current=True,
            bullets=[
                "Led design of payment retry system reducing failure rate by 18%",
                "Mentored 3 junior engineers; drove adoption of internal RPC framework",
            ],
            technologies=["Python", "Java", "Kafka", "PostgreSQL", "Kubernetes", "gRPC"],
        ),
        ResumeExperience(
            company="Lyft",
            title="Software Engineer",
            start_date="2019-01",
            end_date="2021-05",
            is_current=False,
            bullets=[
                "Built real-time ETA pipeline serving 2M requests/day",
                "Reduced p99 API latency from 320ms to 95ms",
            ],
            technologies=["Python", "Spark", "Redis", "MySQL", "Airflow"],
        ),
    ],
    raw_text=(
        "Python Java Spring Boot FastAPI PostgreSQL Redis Docker Kubernetes AWS "
        "REST API CI/CD Kafka Spark microservices distributed systems agile"
    ),
    parse_confidence=0.95,
)


def _req(name: str, category: str = "language") -> JDSkillRequirement:
    return JDSkillRequirement(name=name, is_required=True, category=category)


def _pref(name: str, category: str = "language") -> JDSkillRequirement:
    return JDSkillRequirement(name=name, is_required=False, category=category)


# ---------------------------------------------------------------------------
# JD 1 — Great match: Python/Java backend engineer in fintech
# ---------------------------------------------------------------------------

JD_GREAT = ParsedJobDescription(
    title="Senior Backend Engineer",
    company="Fintech Startup",
    industry="fintech",
    skills=[
        _req("Python"),
        _req("Java"),
        _req("PostgreSQL", "database"),
        _req("Kubernetes", "tool"),
        _req("REST API", "skill"),
        _pref("Spring Boot", "framework"),
        _pref("AWS", "cloud"),
        _pref("Kafka", "tool"),
    ],
    keywords=[
        "Python", "Java", "PostgreSQL", "Kubernetes", "REST API",
        "microservices", "distributed systems", "CI/CD", "agile",
    ],
    min_years_experience=5,
    raw_text="Senior Backend Engineer fintech Python Java PostgreSQL Kubernetes REST API microservices",
    parse_confidence=0.92,
)

# ---------------------------------------------------------------------------
# JD 2 — Partial match: ML engineer role — some overlap, different specialty
# ---------------------------------------------------------------------------

JD_PARTIAL = ParsedJobDescription(
    title="Machine Learning Engineer",
    company="AI Lab",
    industry="artificial intelligence",
    skills=[
        _req("Python"),
        _req("PyTorch", "framework"),
        _req("TensorFlow", "framework"),
        _req("Machine Learning", "skill"),
        _pref("AWS", "cloud"),
        _pref("Docker", "tool"),
        _pref("Kubernetes", "tool"),
    ],
    keywords=[
        "Python", "PyTorch", "TensorFlow", "machine learning", "deep learning",
        "model training", "GPU", "MLOps", "AWS", "Docker",
    ],
    min_years_experience=3,
    raw_text="Machine Learning Engineer AI Python PyTorch TensorFlow deep learning MLOps",
    parse_confidence=0.90,
)

# ---------------------------------------------------------------------------
# JD 3 — Poor match: iOS mobile developer — completely different domain
# ---------------------------------------------------------------------------

JD_POOR = ParsedJobDescription(
    title="Senior iOS Engineer",
    company="Mobile Co",
    industry="mobile",
    skills=[
        _req("Swift", "language"),
        _req("Objective-C", "language"),
        _req("SwiftUI", "framework"),
        _req("Xcode", "tool"),
        _pref("React Native", "framework"),
        _pref("Core Data", "database"),
    ],
    keywords=[
        "Swift", "iOS", "SwiftUI", "Xcode", "Objective-C",
        "UIKit", "App Store", "mobile", "Core Data", "ARKit",
    ],
    min_years_experience=4,
    raw_text="Senior iOS Engineer Swift SwiftUI Xcode UIKit mobile App Store",
    parse_confidence=0.91,
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _print_result(label: str, result) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  overall_score    : {result.overall_score:6.1f} / 100")
    print(f"  skill_score      : {result.skill_score:6.1f} / 100")
    print(f"  experience_score : {result.experience_score:6.1f} / 100")
    print(f"  keyword_score    : {result.keyword_score:6.1f} / 100")
    print(f"  matched_skills   : {result.matched_skills}")
    print(f"  missing_required : {result.missing_required_skills}")
    print(f"  overall_assessment: {result.overall_assessment}")


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        return

    agent = MatchAgent()

    cases = [
        ("GREAT MATCH  — Senior Backend Eng (fintech)", JD_GREAT),
        ("PARTIAL MATCH — ML Engineer (AI lab)",        JD_PARTIAL),
        ("POOR MATCH   — Senior iOS Engineer",          JD_POOR),
    ]

    for label, jd in cases:
        print(f"\nRunning: {label} …", flush=True)
        try:
            result = agent.match(CANDIDATE, jd)
            _print_result(label, result)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main()
