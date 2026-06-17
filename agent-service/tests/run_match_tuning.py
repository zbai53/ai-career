"""
Manual scoring tuner — not a pytest file.

Run from the agent-service directory:

    ANTHROPIC_API_KEY=<key> python -m tests.run_match_tuning

Evaluates a realistic full-stack developer resume against five JDs spanning
different domains and seniority levels, then prints per-dimension scores and
a summary table.

Expected score ranges (based on algorithm analysis):
  Pair 1 — Backend Java Engineer (60-80)
  Pair 2 — Frontend React Engineer (50-70)
  Pair 3 — Data Scientist       (20-40)
  Pair 4 — DevOps Engineer      (30-50)
  Pair 5 — Junior Full Stack    (70-90)
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
# Shared candidate — Jordan Lee, full-stack dev, ~2 years experience
# ---------------------------------------------------------------------------
# Skill set spans both backend (Java/Spring/Postgres) and frontend (React/TS),
# with basic DevOps tooling (Docker, CI/CD, Git).  ~2 years total experience
# gives a single current role started 2024-06, so gaps against senior JDs
# will be visible in the experience dimension.
# ---------------------------------------------------------------------------

CANDIDATE = ParsedResume(
    contact=ResumeContact(name="Jordan Lee", email="jordan@example.com"),
    summary=(
        "Full-stack software engineer with ~2 years of experience building "
        "web applications using Java, Spring Boot, React, and PostgreSQL. "
        "Comfortable across the stack; currently focused on backend services."
    ),
    skills=[
        ResumeSkill(name="Java",        category="language"),
        ResumeSkill(name="Python",      category="language"),
        ResumeSkill(name="JavaScript",  category="language"),
        ResumeSkill(name="TypeScript",  category="language"),
        ResumeSkill(name="React",       category="framework"),
        ResumeSkill(name="Spring Boot", category="framework"),
        ResumeSkill(name="PostgreSQL",  category="database"),
        ResumeSkill(name="SQL",         category="database"),
        ResumeSkill(name="Docker",      category="tool"),
        ResumeSkill(name="Git",         category="tool"),
        ResumeSkill(name="REST API",    category="skill"),
        ResumeSkill(name="CI/CD",       category="skill"),
        ResumeSkill(name="HTML/CSS",    category="skill"),
    ],
    experience=[
        ResumeExperience(
            company="Acme Corp",
            title="Software Engineer",
            start_date="2024-06",
            end_date=None,
            is_current=True,
            bullets=[
                "Built REST APIs with Spring Boot serving 50k daily requests",
                "Migrated legacy monolith to three microservices, cutting deploy time by 40%",
                "Developed React dashboards consumed by internal ops team of 30",
                "Containerised services with Docker; set up GitHub Actions CI/CD pipeline",
            ],
            technologies=[
                "Java", "Spring Boot", "PostgreSQL", "React",
                "JavaScript", "TypeScript", "REST API", "Git", "SQL", "Docker",
            ],
        ),
    ],
    # Keyword-rich raw text for keyword-score dimension
    raw_text=(
        "Java Python JavaScript TypeScript React Spring Boot PostgreSQL SQL "
        "Docker Git REST API CI/CD microservices backend development "
        "HTML CSS agile scrum"
    ),
    parse_confidence=0.93,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(name: str, category: str = "language") -> JDSkillRequirement:
    return JDSkillRequirement(name=name, is_required=True, category=category)


def _pref(name: str, category: str = "language") -> JDSkillRequirement:
    return JDSkillRequirement(name=name, is_required=False, category=category)


# ---------------------------------------------------------------------------
# JD 1 — Backend Java Engineer  (expected overall: 60-80)
# Strong skill overlap; experience gap of 1 year (JD wants 3, candidate has ~2)
# Missing Kafka drags skill score slightly.
# ---------------------------------------------------------------------------

JD_BACKEND_JAVA = ParsedJobDescription(
    title="Backend Java Engineer",
    company="FinCo",
    industry="fintech",
    skills=[
        _req("Java"),
        _req("Spring Boot", "framework"),
        _req("PostgreSQL", "database"),
        _req("REST API",   "skill"),
        _req("Kafka",      "tool"),
        _pref("Docker",    "tool"),
        _pref("AWS",       "cloud"),
        _pref("Kubernetes","tool"),
    ],
    keywords=[
        "Java", "Spring Boot", "PostgreSQL", "REST API", "Kafka",
        "microservices", "Docker", "CI/CD",
    ],
    min_years_experience=3,
    raw_text="Backend Java Engineer fintech Spring Boot PostgreSQL Kafka microservices REST API",
    parse_confidence=0.92,
)

# ---------------------------------------------------------------------------
# JD 2 — Frontend React Engineer  (expected overall: 50-70)
# Resume has React/TS/JS but lacks pure-frontend skills (CSS, HTML, Jest, etc.).
# Experience years meet the bar but tech relevance is partial.
# ---------------------------------------------------------------------------

JD_FRONTEND_REACT = ParsedJobDescription(
    title="Frontend React Engineer",
    company="UX Startup",
    industry="saas",
    skills=[
        _req("React",      "framework"),
        _req("TypeScript"),
        _req("JavaScript"),
        _req("CSS",        "skill"),
        _req("HTML",       "skill"),
        _pref("Vue",       "framework"),
        _pref("Angular",   "framework"),
        _pref("GraphQL",   "skill"),
        _pref("Jest",      "tool"),
        _pref("Storybook", "tool"),
    ],
    keywords=[
        "React", "TypeScript", "JavaScript", "CSS", "HTML",
        "responsive", "accessibility", "Jest", "Next.js", "Tailwind",
    ],
    min_years_experience=2,
    raw_text="Frontend React Engineer TypeScript JavaScript CSS HTML responsive design accessibility",
    parse_confidence=0.91,
)

# ---------------------------------------------------------------------------
# JD 3 — Data Scientist  (expected overall: 20-40)
# Domain mismatch — candidate has Python but no ML/stats background.
# Low skill, keyword, and tech-relevance scores all drag overall down.
# ---------------------------------------------------------------------------

JD_DATA_SCIENTIST = ParsedJobDescription(
    title="Data Scientist",
    company="Analytics Inc",
    industry="data",
    skills=[
        _req("Python"),
        _req("Machine Learning", "skill"),
        _req("PyTorch",          "framework"),
        _req("scikit-learn",     "framework"),
        _req("Statistics",       "skill"),
        _pref("SQL"),
        _pref("AWS",    "cloud"),
        _pref("Spark",  "tool"),
        _pref("Pandas", "tool"),
        _pref("NLP",    "skill"),
    ],
    keywords=[
        "Python", "machine learning", "deep learning", "neural networks",
        "PyTorch", "scikit-learn", "data science", "statistics", "pandas", "Jupyter",
    ],
    min_years_experience=3,
    raw_text="Data Scientist Python machine learning PyTorch scikit-learn statistics deep learning NLP",
    parse_confidence=0.90,
)

# ---------------------------------------------------------------------------
# JD 4 — DevOps Engineer  (expected overall: 30-50)
# Candidate has Docker and CI/CD but misses Kubernetes, Terraform, Linux depth.
# Experience gap (JD wants 3 years, candidate has ~2) adds further penalty.
# ---------------------------------------------------------------------------

JD_DEVOPS = ParsedJobDescription(
    title="DevOps Engineer",
    company="InfraOps",
    industry="cloud infrastructure",
    skills=[
        _req("Docker",     "tool"),
        _req("Kubernetes", "tool"),
        _req("Terraform",  "tool"),
        _req("Linux",      "tool"),
        _req("CI/CD",      "skill"),
        _pref("AWS",       "cloud"),
        _pref("Jenkins",   "tool"),
        _pref("Ansible",   "tool"),
        _pref("Helm",      "tool"),
        _pref("Prometheus","tool"),
    ],
    keywords=[
        "Docker", "Kubernetes", "Terraform", "Linux", "CI/CD",
        "AWS", "Jenkins", "Ansible", "Helm", "Prometheus", "GitOps", "SRE",
    ],
    min_years_experience=3,
    raw_text="DevOps Engineer Docker Kubernetes Terraform Linux CI/CD AWS Jenkins Ansible Helm Prometheus",
    parse_confidence=0.91,
)

# ---------------------------------------------------------------------------
# JD 5 — Junior Full Stack  (expected overall: 70-90)
# Close skill match; experience exceeds requirement; strong keyword overlap.
# Missing Node.js and some preferred tools are the only gaps.
# ---------------------------------------------------------------------------

JD_JUNIOR_FULLSTACK = ParsedJobDescription(
    title="Junior Full Stack Developer",
    company="GrowthApp",
    industry="saas",
    skills=[
        _req("JavaScript"),
        _req("React",    "framework"),
        _req("REST API", "skill"),
        _req("SQL",      "database"),
        _pref("TypeScript"),
        _pref("Git",     "tool"),
        _pref("CSS",     "skill"),
        _pref("Node.js", "framework"),
    ],
    keywords=[
        "JavaScript", "React", "REST API", "SQL", "full-stack",
        "TypeScript", "Git", "CSS", "HTML", "Node.js", "agile",
    ],
    min_years_experience=1,
    raw_text="Junior Full Stack Developer JavaScript React REST API SQL TypeScript Git CSS HTML agile",
    parse_confidence=0.93,
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

PAIRS = [
    ("Pair 1 — Backend Java Engineer  (expect 60-80)", JD_BACKEND_JAVA),
    ("Pair 2 — Frontend React Engineer (expect 50-70)", JD_FRONTEND_REACT),
    ("Pair 3 — Data Scientist          (expect 20-40)", JD_DATA_SCIENTIST),
    ("Pair 4 — DevOps Engineer         (expect 30-50)", JD_DEVOPS),
    ("Pair 5 — Junior Full Stack       (expect 70-90)", JD_JUNIOR_FULLSTACK),
]


def _print_detail(label: str, result) -> None:
    missing_top3 = result.missing_required_skills[:3]
    assessment_preview = (
        result.overall_assessment[:100] + "…"
        if len(result.overall_assessment) > 100
        else result.overall_assessment
    )
    print(f"\n{'=' * 65}")
    print(f"  {label}")
    print(f"{'=' * 65}")
    print(f"  skill_score      : {result.skill_score:6.1f} / 100")
    print(f"  experience_score : {result.experience_score:6.1f} / 100")
    print(f"  keyword_score    : {result.keyword_score:6.1f} / 100")
    print(f"  overall_score    : {result.overall_score:6.1f} / 100")
    print(f"  top missing req  : {missing_top3 or '(none)'}")
    print(f"  assessment       : {assessment_preview or '(none)'}")


def _print_summary(rows: list[tuple[str, object]]) -> None:
    print(f"\n\n{'=' * 75}")
    print("  SUMMARY TABLE")
    print(f"{'=' * 75}")
    header = f"  {'Pair':<40} {'Skill':>6}  {'Exp':>6}  {'KW':>6}  {'Overall':>7}"
    print(header)
    print(f"  {'-' * 40} {'-' * 6}  {'-' * 6}  {'-' * 6}  {'-' * 7}")
    for label, result in rows:
        short = label.split("—")[1].strip() if "—" in label else label
        print(
            f"  {short:<40} "
            f"{result.skill_score:>6.1f}  "
            f"{result.experience_score:>6.1f}  "
            f"{result.keyword_score:>6.1f}  "
            f"{result.overall_score:>7.1f}"
        )
    print(f"{'=' * 75}")


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        return

    agent = MatchAgent()
    summary_rows: list[tuple[str, object]] = []

    for label, jd in PAIRS:
        print(f"\nRunning: {label} …", flush=True)
        try:
            result, _agent_run = agent.match(CANDIDATE, jd)
            _print_detail(label, result)
            summary_rows.append((label, result))
        except Exception as exc:
            print(f"  ERROR: {exc}")

    if summary_rows:
        _print_summary(summary_rows)

    print("\nDone.")


if __name__ == "__main__":
    main()
