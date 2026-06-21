"""
Rewrite Evaluation Script — v1
================================
Compares RewriteAgent output in two modes for 10 resume-JD pairs:

  Baseline  — fidelity checker is bypassed (no retry, no constraint)
  Checked   — fidelity checker runs normally (retry on score < 0.80)

Metrics reported per pair:
  • Keyword coverage before / after rewrite
  • Fidelity score (baseline vs checked)
  • Number of flagged entities, broken down by severity (HIGH / MEDIUM / LOW)
  • Number of rewrite attempts
  • Overall assessment: GOOD / OK / BAD

Final summary:
  • Average keyword coverage improvement
  • Average fidelity score
  • % of rewrites that passed on first attempt
  • % that triggered retry
  • % that still failed after retry

Usage (from agent-service/):
    python tests/run_rewrite_eval.py

Requires ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass, field

sys.path.insert(0, ".")

from app.agents.fidelity_checker import FidelityChecker
from app.agents.rewrite_agent import (
    FIDELITY_THRESHOLD_STRICT,
    FIDELITY_THRESHOLD_WARN,
    RewriteAgent,
    compare_versions,
)
from app.models.fidelity_report import FidelityReport
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)
from app.models.rewrite_result import RewriteResult

# ---------------------------------------------------------------------------
# Stub fidelity checker (baseline mode — always returns a perfect score)
# ---------------------------------------------------------------------------

class _AlwaysPassChecker(FidelityChecker):
    """
    Bypass fidelity checking for the baseline run.

    Returns a perfect FidelityReport for every call so RewriteAgent never
    retries — giving us the raw, unconstrained rewrite to compare against.
    The real FidelityChecker is run post-hoc to measure actual baseline fidelity.
    """

    def check(self, resume: ParsedResume, rewrite_result: RewriteResult) -> FidelityReport:  # type: ignore[override]
        return FidelityReport(
            fidelity_score=1.0,
            flags=[],
            total_original_entities=0,
            total_rewritten_entities=0,
            new_entities_found=0,
            passed=True,
            threshold=0.85,
        )


# ---------------------------------------------------------------------------
# Eval case definition
# ---------------------------------------------------------------------------

@dataclass
class EvalPair:
    name: str
    description: str
    resume: ParsedResume
    jd: ParsedJobDescription
    match_result: dict
    ideal_rewrite: list[str]   # ground-truth bullets (for reference only)


# ---------------------------------------------------------------------------
# Build all 10 resume-JD pairs
# ---------------------------------------------------------------------------

def _build_pairs() -> list[EvalPair]:

    # ------------------------------------------------------------------
    # Pair 1 — Java Backend Dev → Senior Backend Engineer
    # ------------------------------------------------------------------
    resume_1 = ParsedResume(
        contact=ResumeContact(name="Jordan Lee", email="jordan@example.com"),
        experience=[
            ResumeExperience(
                company="Initech",
                title="Backend Developer",
                start_date="2021-06",
                end_date="2024-01",
                bullets=[
                    "Built REST API using Java",
                    "Maintained PostgreSQL database",
                    "Wrote unit tests",
                ],
                technologies=["Java", "PostgreSQL", "JUnit"],
            )
        ],
        skills=[
            ResumeSkill(name="Java", category="language"),
            ResumeSkill(name="PostgreSQL", category="database"),
            ResumeSkill(name="JUnit", category="tool"),
        ],
        raw_text=(
            "Jordan Lee  jordan@example.com\n"
            "Initech — Backend Developer  2021-06 to 2024-01\n"
            "Built REST API using Java\n"
            "Maintained PostgreSQL database\n"
            "Wrote unit tests"
        ),
        parse_confidence=0.95,
    )
    jd_1 = ParsedJobDescription(
        title="Senior Backend Engineer",
        company="CloudScale",
        skills=[
            JDSkillRequirement(name="Java", is_required=True, category="language"),
            JDSkillRequirement(name="microservices", is_required=True, category="domain"),
            JDSkillRequirement(name="PostgreSQL", is_required=True, category="database"),
            JDSkillRequirement(name="CI/CD", is_required=False, category="tool"),
            JDSkillRequirement(name="Docker", is_required=False, category="tool"),
        ],
        keywords=["microservices", "REST", "PostgreSQL", "CI/CD", "Docker", "Java", "distributed"],
        responsibilities=[
            "Design and build microservices in Java",
            "Own the database layer and ensure high availability",
            "Participate in the full CI/CD pipeline",
        ],
        raw_text="Senior Backend Engineer — CloudScale\nJava, microservices, PostgreSQL, CI/CD",
        parse_confidence=0.92,
    )
    match_1 = {
        "overall_score": 58,
        "gap_analysis": {
            "missing_required_skills": ["microservices"],
            "missing_preferred_skills": ["CI/CD", "Docker"],
            "improvement_suggestions": [
                "Highlight any service decomposition or API design work",
                "Mention testing frameworks and test coverage targets",
                "Quantify API usage or database scale if possible",
            ],
            "overall_assessment": (
                "Candidate has solid Java and PostgreSQL experience but "
                "needs to frame work in terms of microservices architecture."
            ),
        },
    }
    ideal_1 = [
        "Architected Java-based REST API serving as the backbone of a microservices system, enabling independent service scaling",
        "Managed and optimized PostgreSQL database schema supporting production workloads with reliable backup and recovery",
        "Authored comprehensive JUnit test suites, maintaining high coverage and enabling confident CI/CD deployments",
    ]

    # ------------------------------------------------------------------
    # Pair 2 — React Frontend Dev → Full Stack Engineer
    # ------------------------------------------------------------------
    resume_2 = ParsedResume(
        contact=ResumeContact(name="Morgan Kim", email="morgan@example.com"),
        experience=[
            ResumeExperience(
                company="PixelWorks",
                title="Frontend Developer",
                start_date="2022-03",
                end_date="2024-05",
                bullets=[
                    "Created React components",
                    "Fixed CSS bugs",
                    "Deployed to production",
                ],
                technologies=["React", "CSS", "JavaScript"],
            )
        ],
        skills=[
            ResumeSkill(name="React", category="framework"),
            ResumeSkill(name="JavaScript", category="language"),
            ResumeSkill(name="CSS", category="tool"),
        ],
        raw_text=(
            "Morgan Kim  morgan@example.com\n"
            "PixelWorks — Frontend Developer  2022-03 to 2024-05\n"
            "Created React components\n"
            "Fixed CSS bugs\n"
            "Deployed to production"
        ),
        parse_confidence=0.93,
    )
    jd_2 = ParsedJobDescription(
        title="Full Stack Engineer",
        company="LaunchPad",
        skills=[
            JDSkillRequirement(name="React", is_required=True, category="framework"),
            JDSkillRequirement(name="TypeScript", is_required=True, category="language"),
            JDSkillRequirement(name="Node.js", is_required=True, category="framework"),
            JDSkillRequirement(name="CI/CD", is_required=True, category="tool"),
            JDSkillRequirement(name="REST API", is_required=False, category="domain"),
        ],
        keywords=["React", "TypeScript", "Node.js", "CI/CD", "full stack", "REST API", "pipeline"],
        responsibilities=[
            "Build and maintain full stack features in React and Node.js",
            "Write TypeScript across frontend and backend",
            "Own the CI/CD pipeline from build to deploy",
        ],
        raw_text="Full Stack Engineer — LaunchPad\nReact, TypeScript, Node.js, CI/CD",
        parse_confidence=0.91,
    )
    match_2 = {
        "overall_score": 45,
        "gap_analysis": {
            "missing_required_skills": ["TypeScript", "Node.js", "CI/CD"],
            "missing_preferred_skills": ["REST API"],
            "improvement_suggestions": [
                "Reframe React work to emphasize component architecture and reusability",
                "Mention any deployment pipelines or automation used",
                "Connect front-end skills to full-stack context",
            ],
            "overall_assessment": (
                "Candidate has React and deployment exposure but needs to "
                "surface CI/CD pipeline ownership and TypeScript context."
            ),
        },
    }
    ideal_2 = [
        "Engineered reusable React component library with strong separation of concerns, accelerating feature delivery",
        "Diagnosed and resolved cross-browser CSS regressions, improving UI consistency across desktop and mobile",
        "Automated CI/CD deployment pipeline to production, enabling reliable daily releases with zero-downtime",
    ]

    # ------------------------------------------------------------------
    # Pair 3 — Junior Dev → Mid-level Software Engineer (stretch)
    # ------------------------------------------------------------------
    resume_3 = ParsedResume(
        contact=ResumeContact(name="Alex Patel", email="alex.p@example.com"),
        experience=[
            ResumeExperience(
                company="DevShop",
                title="Junior Software Developer",
                start_date="2023-01",
                end_date="2024-06",
                bullets=[
                    "Helped with debugging",
                    "Attended code reviews",
                    "Learned Python",
                ],
                technologies=["Python", "Git"],
            )
        ],
        skills=[
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="Git", category="tool"),
        ],
        raw_text=(
            "Alex Patel  alex.p@example.com\n"
            "DevShop — Junior Software Developer  2023-01 to 2024-06\n"
            "Helped with debugging\n"
            "Attended code reviews\n"
            "Learned Python"
        ),
        parse_confidence=0.90,
    )
    jd_3 = ParsedJobDescription(
        title="Software Engineer",
        company="BuildRight",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="code review", is_required=True, category="soft_skill"),
            JDSkillRequirement(name="debugging", is_required=True, category="domain"),
            JDSkillRequirement(name="Git", is_required=False, category="tool"),
            JDSkillRequirement(name="unit testing", is_required=False, category="tool"),
        ],
        keywords=["Python", "debugging", "code review", "Git", "unit testing", "problem solving"],
        responsibilities=[
            "Write and maintain Python services",
            "Participate in and lead code reviews",
            "Debug and resolve production issues",
        ],
        raw_text="Software Engineer — BuildRight\nPython, debugging, code review, Git",
        parse_confidence=0.90,
    )
    match_3 = {
        "overall_score": 52,
        "gap_analysis": {
            "missing_required_skills": ["unit testing"],
            "missing_preferred_skills": [],
            "improvement_suggestions": [
                "Reframe 'helped with debugging' as active ownership of bug resolution",
                "Turn 'attended code reviews' into a contribution-focused statement",
                "Show Python learning outcomes with a concrete deliverable",
            ],
            "overall_assessment": (
                "Candidate's bullets are passive. Reframing them as active contributions "
                "with concrete outcomes will significantly improve the match score."
            ),
        },
    }
    ideal_3 = [
        "Investigated and resolved production bugs by tracing root causes through logs and reproducing failure conditions",
        "Contributed to code review process, identifying logic errors and surfacing improvements across the codebase",
        "Built Python scripts to automate repetitive team workflows, delivering measurable productivity gains",
    ]

    # ------------------------------------------------------------------
    # Pair 4 — Data Analyst → Data Engineer (skill gap: SQL → Spark/Airflow)
    # ------------------------------------------------------------------
    resume_4 = ParsedResume(
        contact=ResumeContact(name="Sam Chen", email="sam.chen@example.com"),
        experience=[
            ResumeExperience(
                company="AnalyticsCo",
                title="Data Analyst",
                start_date="2021-09",
                end_date="2024-03",
                bullets=[
                    "Wrote SQL queries for reports",
                    "Created Excel dashboards",
                    "Cleaned data using Python",
                ],
                technologies=["SQL", "Excel", "Python", "Tableau"],
            )
        ],
        skills=[
            ResumeSkill(name="SQL", category="language"),
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="Excel", category="tool"),
            ResumeSkill(name="Tableau", category="tool"),
        ],
        raw_text=(
            "Sam Chen  sam.chen@example.com\n"
            "AnalyticsCo — Data Analyst  2021-09 to 2024-03\n"
            "Wrote SQL queries for reports\n"
            "Created Excel dashboards\n"
            "Cleaned data using Python"
        ),
        parse_confidence=0.92,
    )
    jd_4 = ParsedJobDescription(
        title="Data Engineer",
        company="DataFlow Inc",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="SQL", is_required=True, category="language"),
            JDSkillRequirement(name="Apache Spark", is_required=True, category="framework"),
            JDSkillRequirement(name="Airflow", is_required=True, category="tool"),
            JDSkillRequirement(name="ETL", is_required=True, category="domain"),
            JDSkillRequirement(name="data warehouse", is_required=False, category="domain"),
        ],
        keywords=["Python", "SQL", "Spark", "Airflow", "ETL", "data pipeline", "data warehouse", "batch processing"],
        responsibilities=[
            "Build and maintain ETL data pipelines using Spark and Airflow",
            "Write optimized SQL for data warehouse transformations",
            "Collaborate with analysts to understand data needs",
        ],
        raw_text="Data Engineer — DataFlow Inc\nPython, SQL, Spark, Airflow, ETL pipelines",
        parse_confidence=0.93,
    )
    match_4 = {
        "overall_score": 48,
        "gap_analysis": {
            "missing_required_skills": ["Apache Spark", "Airflow", "ETL"],
            "missing_preferred_skills": ["data warehouse"],
            "improvement_suggestions": [
                "Frame SQL work as part of data pipeline or ETL context",
                "Highlight Python data processing experience as transferable to Spark",
                "Emphasize data quality and transformation over reporting",
            ],
            "overall_assessment": (
                "Analyst has strong SQL and Python foundations but needs to reframe "
                "work in engineering and pipeline terms to close the data engineer gap."
            ),
        },
    }
    ideal_4 = [
        "Engineered complex SQL queries powering automated reporting pipelines, transforming raw data into analytics-ready datasets",
        "Built Python-based data cleaning and transformation scripts processing large datasets for downstream dashboard consumption",
        "Developed Excel-based analytical dashboards tracking business KPIs, demonstrating end-to-end data pipeline ownership",
    ]

    # ------------------------------------------------------------------
    # Pair 5 — QA Tester → SDE (career transition)
    # ------------------------------------------------------------------
    resume_5 = ParsedResume(
        contact=ResumeContact(name="Riley Johnson", email="riley.j@example.com"),
        experience=[
            ResumeExperience(
                company="QualitySoft",
                title="QA Engineer",
                start_date="2022-02",
                end_date="2024-04",
                bullets=[
                    "Wrote test cases",
                    "Performed manual testing",
                    "Filed bug reports in Jira",
                ],
                technologies=["Jira", "Selenium", "Python"],
            )
        ],
        skills=[
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="Selenium", category="tool"),
            ResumeSkill(name="Jira", category="tool"),
        ],
        raw_text=(
            "Riley Johnson  riley.j@example.com\n"
            "QualitySoft — QA Engineer  2022-02 to 2024-04\n"
            "Wrote test cases\n"
            "Performed manual testing\n"
            "Filed bug reports in Jira"
        ),
        parse_confidence=0.91,
    )
    jd_5 = ParsedJobDescription(
        title="Software Development Engineer",
        company="DevCorp",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="unit testing", is_required=True, category="domain"),
            JDSkillRequirement(name="debugging", is_required=True, category="domain"),
            JDSkillRequirement(name="software development", is_required=True, category="domain"),
            JDSkillRequirement(name="automation", is_required=False, category="tool"),
        ],
        keywords=["Python", "unit testing", "debugging", "automation", "software development", "code quality", "test-driven"],
        responsibilities=[
            "Write production-quality Python code",
            "Develop and maintain automated test suites",
            "Debug and resolve software defects",
        ],
        raw_text="Software Development Engineer — DevCorp\nPython, unit testing, debugging, automation",
        parse_confidence=0.91,
    )
    match_5 = {
        "overall_score": 44,
        "gap_analysis": {
            "missing_required_skills": ["software development"],
            "missing_preferred_skills": ["automation"],
            "improvement_suggestions": [
                "Reframe test case writing as software engineering deliverables",
                "Highlight automation scripting experience with Python",
                "Emphasize debugging and defect analysis as engineering skills",
            ],
            "overall_assessment": (
                "QA background provides strong testing foundation; "
                "needs to reframe contributions as software engineering work, not just testing."
            ),
        },
    }
    ideal_5 = [
        "Designed and implemented comprehensive test case frameworks covering functional, regression, and edge case scenarios",
        "Developed Python automation scripts replacing manual testing workflows, reducing regression cycle time significantly",
        "Analyzed and documented defects in Jira with root-cause analysis and reproduction steps, enabling faster resolution",
    ]

    # ------------------------------------------------------------------
    # Pair 6 — Intern → Junior Dev (limited experience)
    # ------------------------------------------------------------------
    resume_6 = ParsedResume(
        contact=ResumeContact(name="Casey Wong", email="casey.w@example.com"),
        experience=[
            ResumeExperience(
                company="TechStartup",
                title="Software Engineering Intern",
                start_date="2023-06",
                end_date="2023-08",
                bullets=[
                    "Shadowed senior developers",
                    "Fixed minor bugs",
                    "Attended daily standups",
                ],
                technologies=["Python", "Git", "Slack"],
            )
        ],
        skills=[
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="Git", category="tool"),
        ],
        raw_text=(
            "Casey Wong  casey.w@example.com\n"
            "TechStartup — Software Engineering Intern  2023-06 to 2023-08\n"
            "Shadowed senior developers\n"
            "Fixed minor bugs\n"
            "Attended daily standups"
        ),
        parse_confidence=0.88,
    )
    jd_6 = ParsedJobDescription(
        title="Junior Software Developer",
        company="GrowthTech",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="Git", is_required=True, category="tool"),
            JDSkillRequirement(name="debugging", is_required=True, category="domain"),
            JDSkillRequirement(name="Agile", is_required=False, category="domain"),
            JDSkillRequirement(name="collaboration", is_required=False, category="soft_skill"),
        ],
        keywords=["Python", "Git", "debugging", "Agile", "collaboration", "version control", "software development"],
        responsibilities=[
            "Write and debug Python code under guidance of senior engineers",
            "Use Git for version control and code collaboration",
            "Participate in Agile ceremonies",
        ],
        raw_text="Junior Software Developer — GrowthTech\nPython, Git, debugging, Agile",
        parse_confidence=0.90,
    )
    match_6 = {
        "overall_score": 50,
        "gap_analysis": {
            "missing_required_skills": [],
            "missing_preferred_skills": ["Agile", "collaboration"],
            "improvement_suggestions": [
                "Reframe 'shadowed' as active learning and collaboration with senior engineers",
                "Describe bug fixes with more technical context",
                "Frame standup attendance as Agile process participation",
            ],
            "overall_assessment": (
                "Intern has the right foundational skills; "
                "key challenge is making limited experience sound substantial and proactive."
            ),
        },
    }
    ideal_6 = [
        "Collaborated with senior engineers on feature development, contributing code fixes and building understanding of production systems",
        "Diagnosed and resolved software defects by debugging code, improving system stability across the intern project",
        "Participated in Agile daily standups and sprint ceremonies, gaining hands-on experience with engineering delivery workflows",
    ]

    # ------------------------------------------------------------------
    # Pair 7 — DevOps → Cloud Architect (promotion path)
    # ------------------------------------------------------------------
    resume_7 = ParsedResume(
        contact=ResumeContact(name="Dana Park", email="dana.park@example.com"),
        experience=[
            ResumeExperience(
                company="OpsTeam",
                title="DevOps Engineer",
                start_date="2020-04",
                end_date="2024-02",
                bullets=[
                    "Managed Jenkins CI/CD pipelines",
                    "Deployed apps to AWS EC2",
                    "Wrote Terraform scripts",
                ],
                technologies=["Jenkins", "AWS", "Terraform", "Docker", "Kubernetes"],
            )
        ],
        skills=[
            ResumeSkill(name="Jenkins", category="tool"),
            ResumeSkill(name="AWS", category="cloud"),
            ResumeSkill(name="Terraform", category="tool"),
            ResumeSkill(name="Docker", category="tool"),
            ResumeSkill(name="Kubernetes", category="tool"),
        ],
        raw_text=(
            "Dana Park  dana.park@example.com\n"
            "OpsTeam — DevOps Engineer  2020-04 to 2024-02\n"
            "Managed Jenkins CI/CD pipelines\n"
            "Deployed apps to AWS EC2\n"
            "Wrote Terraform scripts"
        ),
        parse_confidence=0.94,
    )
    jd_7 = ParsedJobDescription(
        title="Cloud Architect",
        company="ScaleSystems",
        skills=[
            JDSkillRequirement(name="AWS", is_required=True, category="cloud"),
            JDSkillRequirement(name="Terraform", is_required=True, category="tool"),
            JDSkillRequirement(name="cloud architecture", is_required=True, category="domain"),
            JDSkillRequirement(name="Kubernetes", is_required=True, category="tool"),
            JDSkillRequirement(name="CI/CD", is_required=False, category="tool"),
            JDSkillRequirement(name="multi-region", is_required=False, category="domain"),
        ],
        keywords=["AWS", "Terraform", "cloud architecture", "Kubernetes", "CI/CD", "infrastructure", "scalability", "multi-region"],
        responsibilities=[
            "Design scalable cloud architecture on AWS",
            "Own infrastructure-as-code strategy using Terraform",
            "Lead Kubernetes-based container orchestration",
        ],
        raw_text="Cloud Architect — ScaleSystems\nAWS, Terraform, cloud architecture, Kubernetes",
        parse_confidence=0.93,
    )
    match_7 = {
        "overall_score": 65,
        "gap_analysis": {
            "missing_required_skills": ["cloud architecture"],
            "missing_preferred_skills": ["multi-region"],
            "improvement_suggestions": [
                "Frame Jenkins and CI/CD work in terms of architectural decisions",
                "Describe Terraform as infrastructure design, not just scripting",
                "Elevate EC2 deployments to cloud architecture patterns",
            ],
            "overall_assessment": (
                "Strong DevOps foundation; needs to reframe operational tasks "
                "as architectural decisions to target the Cloud Architect level."
            ),
        },
    }
    ideal_7 = [
        "Architected Jenkins-based CI/CD platform enabling automated delivery pipelines for multiple engineering teams at scale",
        "Designed and executed cloud-native deployment architecture on AWS EC2, implementing auto-scaling and high-availability patterns",
        "Developed reusable Terraform infrastructure modules enabling consistent, repeatable cloud environment provisioning",
    ]

    # ------------------------------------------------------------------
    # Pair 8 — Mobile Dev → Backend Dev (pivot)
    # ------------------------------------------------------------------
    resume_8 = ParsedResume(
        contact=ResumeContact(name="Jamie Torres", email="jamie.t@example.com"),
        experience=[
            ResumeExperience(
                company="MobileFirst",
                title="iOS Developer",
                start_date="2021-08",
                end_date="2024-01",
                bullets=[
                    "Built iOS app using Swift",
                    "Integrated REST APIs",
                    "Published app to App Store",
                ],
                technologies=["Swift", "iOS", "REST", "Xcode"],
            )
        ],
        skills=[
            ResumeSkill(name="Swift", category="language"),
            ResumeSkill(name="iOS", category="domain"),
            ResumeSkill(name="REST API", category="domain"),
            ResumeSkill(name="Xcode", category="tool"),
        ],
        raw_text=(
            "Jamie Torres  jamie.t@example.com\n"
            "MobileFirst — iOS Developer  2021-08 to 2024-01\n"
            "Built iOS app using Swift\n"
            "Integrated REST APIs\n"
            "Published app to App Store"
        ),
        parse_confidence=0.92,
    )
    jd_8 = ParsedJobDescription(
        title="Backend Software Engineer",
        company="APIWorks",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="REST API", is_required=True, category="domain"),
            JDSkillRequirement(name="databases", is_required=True, category="domain"),
            JDSkillRequirement(name="microservices", is_required=False, category="domain"),
            JDSkillRequirement(name="server-side", is_required=False, category="domain"),
        ],
        keywords=["Python", "REST API", "databases", "microservices", "server-side", "backend", "API design"],
        responsibilities=[
            "Design and build REST API backends in Python",
            "Manage database schemas and query optimization",
            "Build and operate microservices",
        ],
        raw_text="Backend Software Engineer — APIWorks\nPython, REST API, databases, microservices",
        parse_confidence=0.91,
    )
    match_8 = {
        "overall_score": 40,
        "gap_analysis": {
            "missing_required_skills": ["Python", "databases"],
            "missing_preferred_skills": ["microservices", "server-side"],
            "improvement_suggestions": [
                "Reframe API integration experience as API design and consumption expertise",
                "Highlight any backend data handling done through the REST API layer",
                "Connect app publishing lifecycle to software delivery practices",
            ],
            "overall_assessment": (
                "Mobile background with solid REST API integration experience; "
                "key gap is server-side and database ownership — needs reframing to backend context."
            ),
        },
    }
    ideal_8 = [
        "Engineered iOS application using Swift, managing complex business logic and REST API integration for seamless data exchange",
        "Designed and implemented REST API client layer with authentication, error handling, and retry logic for reliable backend communication",
        "Managed end-to-end application release lifecycle on App Store, including version management, QA, and production monitoring",
    ]

    # ------------------------------------------------------------------
    # Pair 9 — Strong metrics resume → JD wanting metrics (preserve numbers)
    # ------------------------------------------------------------------
    resume_9 = ParsedResume(
        contact=ResumeContact(name="Blake Rivera", email="blake.r@example.com"),
        experience=[
            ResumeExperience(
                company="ScaleUp",
                title="Staff Engineer",
                start_date="2019-03",
                end_date="2024-05",
                bullets=[
                    "Reduced API latency by 40%",
                    "Served 1M daily requests",
                    "Led team of 5 engineers",
                ],
                technologies=["Python", "Go", "PostgreSQL", "Redis", "Kubernetes"],
            )
        ],
        skills=[
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="Go", category="language"),
            ResumeSkill(name="PostgreSQL", category="database"),
            ResumeSkill(name="Redis", category="database"),
            ResumeSkill(name="Kubernetes", category="tool"),
        ],
        raw_text=(
            "Blake Rivera  blake.r@example.com\n"
            "ScaleUp — Staff Engineer  2019-03 to 2024-05\n"
            "Reduced API latency by 40%\n"
            "Served 1M daily requests\n"
            "Led team of 5 engineers"
        ),
        parse_confidence=0.97,
    )
    jd_9 = ParsedJobDescription(
        title="Principal Engineer",
        company="HyperScale",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="distributed systems", is_required=True, category="domain"),
            JDSkillRequirement(name="Kubernetes", is_required=True, category="tool"),
            JDSkillRequirement(name="performance optimization", is_required=True, category="domain"),
            JDSkillRequirement(name="leadership", is_required=True, category="soft_skill"),
            JDSkillRequirement(name="Go", is_required=False, category="language"),
        ],
        keywords=["Python", "Go", "Kubernetes", "distributed systems", "performance", "leadership", "scalability", "reliability"],
        responsibilities=[
            "Architect distributed systems handling millions of requests per day",
            "Drive performance optimization across the stack",
            "Lead and mentor engineering teams",
        ],
        raw_text="Principal Engineer — HyperScale\nPython, Go, Kubernetes, distributed systems, performance, leadership",
        parse_confidence=0.95,
    )
    match_9 = {
        "overall_score": 72,
        "gap_analysis": {
            "missing_required_skills": ["distributed systems"],
            "missing_preferred_skills": [],
            "improvement_suggestions": [
                "Frame 1M daily requests as distributed system scale",
                "Connect 40% latency reduction to performance optimization narrative",
                "Highlight team leadership as engineering management capability",
            ],
            "overall_assessment": (
                "Strong existing metrics; primary task is reframing to match "
                "distributed systems and principal engineer scope — not inventing new claims."
            ),
        },
    }
    ideal_9 = [
        "Optimized distributed systems performance, reducing API latency by 40% through targeted caching and algorithmic improvements",
        "Architected scalable backend serving 1M daily requests with high reliability across distributed infrastructure",
        "Led engineering team of 5, driving technical excellence through mentorship, code reviews, and architectural decision-making",
    ]

    # ------------------------------------------------------------------
    # Pair 10 — Vague resume → Specific JD (biggest improvement opportunity)
    # ------------------------------------------------------------------
    resume_10 = ParsedResume(
        contact=ResumeContact(name="Robin Hayes", email="robin.h@example.com"),
        experience=[
            ResumeExperience(
                company="GenericCorp",
                title="Software Developer",
                start_date="2022-01",
                end_date="2024-06",
                bullets=[
                    "Worked on backend stuff",
                    "Did some database things",
                    "Helped with deployments",
                ],
                technologies=["Python", "PostgreSQL", "Docker"],
            )
        ],
        skills=[
            ResumeSkill(name="Python", category="language"),
            ResumeSkill(name="PostgreSQL", category="database"),
            ResumeSkill(name="Docker", category="tool"),
        ],
        raw_text=(
            "Robin Hayes  robin.h@example.com\n"
            "GenericCorp — Software Developer  2022-01 to 2024-06\n"
            "Worked on backend stuff\n"
            "Did some database things\n"
            "Helped with deployments"
        ),
        parse_confidence=0.85,
    )
    jd_10 = ParsedJobDescription(
        title="Backend Software Engineer",
        company="Clarity Tech",
        skills=[
            JDSkillRequirement(name="Python", is_required=True, category="language"),
            JDSkillRequirement(name="PostgreSQL", is_required=True, category="database"),
            JDSkillRequirement(name="Docker", is_required=True, category="tool"),
            JDSkillRequirement(name="REST API", is_required=True, category="domain"),
            JDSkillRequirement(name="CI/CD", is_required=False, category="tool"),
            JDSkillRequirement(name="microservices", is_required=False, category="domain"),
        ],
        keywords=["Python", "PostgreSQL", "Docker", "REST API", "CI/CD", "microservices", "backend", "API design"],
        responsibilities=[
            "Build and maintain Python backend services and REST APIs",
            "Manage PostgreSQL schemas and write complex queries",
            "Containerize and deploy services using Docker",
        ],
        raw_text="Backend Software Engineer — Clarity Tech\nPython, PostgreSQL, Docker, REST API, CI/CD",
        parse_confidence=0.93,
    )
    match_10 = {
        "overall_score": 55,
        "gap_analysis": {
            "missing_required_skills": ["REST API"],
            "missing_preferred_skills": ["CI/CD", "microservices"],
            "improvement_suggestions": [
                "Replace vague language with specific technical contributions",
                "Describe backend work with concrete technologies and outcomes",
                "Frame deployment help as Docker containerization or CI/CD participation",
            ],
            "overall_assessment": (
                "Candidate has the right technology stack but the bullet language is too vague. "
                "This is the highest-value rewrite opportunity — specificity is the only barrier."
            ),
        },
    }
    ideal_10 = [
        "Developed and maintained Python backend services and REST APIs, improving system reliability and response times for end users",
        "Designed and optimized PostgreSQL database schemas, writing complex queries and managing data integrity for production workloads",
        "Containerized and deployed services using Docker, participating in CI/CD workflows to ensure consistent production releases",
    ]

    return [
        EvalPair(
            name="Pair 1 — Java Backend Dev → Senior Backend Engineer",
            description="Mid-level Java dev → senior role. Key gaps: microservices, CI/CD, quantified impact.",
            resume=resume_1, jd=jd_1, match_result=match_1, ideal_rewrite=ideal_1,
        ),
        EvalPair(
            name="Pair 2 — React Frontend Dev → Full Stack Engineer",
            description="Frontend dev → full-stack. Key gaps: TypeScript, Node.js, CI/CD ownership.",
            resume=resume_2, jd=jd_2, match_result=match_2, ideal_rewrite=ideal_2,
        ),
        EvalPair(
            name="Pair 3 — Junior Dev → Mid-level (stretch)",
            description="Junior dev with passive bullets → mid-level. Transform 'helped / attended / learned' into active contributions.",
            resume=resume_3, jd=jd_3, match_result=match_3, ideal_rewrite=ideal_3,
        ),
        EvalPair(
            name="Pair 4 — Data Analyst → Data Engineer",
            description="Analyst → engineer. Key gaps: Spark, Airflow, ETL pipeline framing.",
            resume=resume_4, jd=jd_4, match_result=match_4, ideal_rewrite=ideal_4,
        ),
        EvalPair(
            name="Pair 5 — QA Tester → Software Development Engineer",
            description="QA → SDE career transition. Reframe testing deliverables as software engineering work.",
            resume=resume_5, jd=jd_5, match_result=match_5, ideal_rewrite=ideal_5,
        ),
        EvalPair(
            name="Pair 6 — Intern → Junior Developer",
            description="3-month intern → full-time junior dev. Limited experience needs maximum positive framing.",
            resume=resume_6, jd=jd_6, match_result=match_6, ideal_rewrite=ideal_6,
        ),
        EvalPair(
            name="Pair 7 — DevOps Engineer → Cloud Architect",
            description="DevOps → architect (promotion). Reframe operational work as architectural decisions.",
            resume=resume_7, jd=jd_7, match_result=match_7, ideal_rewrite=ideal_7,
        ),
        EvalPair(
            name="Pair 8 — iOS Developer → Backend Engineer",
            description="Mobile → backend pivot. Transferable: REST API integration, app lifecycle, client-side data handling.",
            resume=resume_8, jd=jd_8, match_result=match_8, ideal_rewrite=ideal_8,
        ),
        EvalPair(
            name="Pair 9 — Strong Metrics → Principal Engineer",
            description="Metrics-rich resume → senior JD. Key test: existing numbers (40%, 1M, 5) must be preserved.",
            resume=resume_9, jd=jd_9, match_result=match_9, ideal_rewrite=ideal_9,
        ),
        EvalPair(
            name="Pair 10 — Vague Dev → Specific Backend JD",
            description="Vague language with correct tech stack → specific JD. Highest improvement opportunity.",
            resume=resume_10, jd=jd_10, match_result=match_10, ideal_rewrite=ideal_10,
        ),
    ]


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _keyword_coverage(bullets: list[str], keywords: list[str]) -> float:
    """Fraction of JD keywords that appear in the bullet text (substring match)."""
    if not keywords:
        return 0.0
    text = " ".join(bullets).lower()
    return sum(1 for kw in keywords if kw.lower() in text) / len(keywords)


def _collect_bullets(result: RewriteResult) -> list[str]:
    return [rb.rewritten for exp in result.experiences for rb in exp.rewritten_bullets]


def _collect_originals(resume: ParsedResume) -> list[str]:
    return [b for exp in resume.experience for b in exp.bullets]


def _flag_counts(report: FidelityReport | None) -> tuple[int, int, int]:
    """Return (high, medium, low) flag counts."""
    if not report:
        return 0, 0, 0
    high   = sum(1 for f in report.flags if f.severity == "high")
    medium = sum(1 for f in report.flags if f.severity == "medium")
    low    = sum(1 for f in report.flags if f.severity == "low")
    return high, medium, low


def _assess(fidelity: float, kw_improvement: float) -> str:
    """
    GOOD  — fidelity >= STRICT (0.90) and keyword coverage improved
    OK    — fidelity >= WARN (0.80)
    BAD   — fidelity < WARN
    """
    if fidelity >= FIDELITY_THRESHOLD_STRICT and kw_improvement > 0:
        return "GOOD"
    if fidelity >= FIDELITY_THRESHOLD_STRICT:
        return "OK"   # clean fidelity but no kw gain
    if fidelity >= FIDELITY_THRESHOLD_WARN:
        return "OK"
    return "BAD"


# ---------------------------------------------------------------------------
# Per-pair result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PairResult:
    pair_name: str
    original_bullets: list[str]
    ideal_rewrite: list[str]
    jd_keywords: list[str]
    # Baseline
    baseline_bullets: list[str]
    baseline_fidelity: float
    baseline_flags_h: int
    baseline_flags_m: int
    baseline_flags_l: int
    baseline_attempts: int
    baseline_kw_before: float
    baseline_kw_after: float
    baseline_verbs_improved: int
    # Checked
    checked_bullets: list[str]
    checked_fidelity: float
    checked_flags_h: int
    checked_flags_m: int
    checked_flags_l: int
    checked_attempts: int
    checked_kw_before: float
    checked_kw_after: float
    checked_verbs_improved: int
    # Derived
    assessment: str = field(init=False)

    def __post_init__(self) -> None:
        kw_delta = self.checked_kw_after - self.checked_kw_before
        self.assessment = _assess(self.checked_fidelity, kw_delta)


# ---------------------------------------------------------------------------
# Run a single pair
# ---------------------------------------------------------------------------

def _run_pair(pair: EvalPair, verbose: bool = True) -> PairResult:
    keywords  = list(pair.jd.keywords or [])
    originals = _collect_originals(pair.resume)

    # ---- baseline (stub checker — no fidelity constraint) ----
    if verbose:
        print(f"  [baseline] calling RewriteAgent …")
    baseline_agent  = RewriteAgent(fidelity_checker=_AlwaysPassChecker())
    baseline_result, _ = baseline_agent.rewrite(pair.resume, pair.jd, pair.match_result)
    baseline_bullets   = _collect_bullets(baseline_result)

    # Measure real fidelity of unconstrained output
    real_checker     = FidelityChecker()
    baseline_report  = real_checker.check(pair.resume, baseline_result)
    bh, bm, bl       = _flag_counts(baseline_report)
    baseline_metrics  = compare_versions(originals, baseline_bullets, keywords)

    # ---- checked (normal agent with fidelity loop) ----
    if verbose:
        print(f"  [checked]  calling RewriteAgent …")
    checked_agent  = RewriteAgent()
    checked_result, _ = checked_agent.rewrite(pair.resume, pair.jd, pair.match_result)
    checked_bullets   = _collect_bullets(checked_result)
    checked_report    = checked_result.fidelity_report
    ch, cm, cl        = _flag_counts(checked_report)
    checked_metrics   = compare_versions(originals, checked_bullets, keywords)

    return PairResult(
        pair_name=pair.name,
        original_bullets=originals,
        ideal_rewrite=pair.ideal_rewrite,
        jd_keywords=keywords,
        # baseline
        baseline_bullets=baseline_bullets,
        baseline_fidelity=baseline_report.fidelity_score,
        baseline_flags_h=bh,
        baseline_flags_m=bm,
        baseline_flags_l=bl,
        baseline_attempts=baseline_result.rewrite_attempts,
        baseline_kw_before=_keyword_coverage(originals, keywords),
        baseline_kw_after=_keyword_coverage(baseline_bullets, keywords),
        baseline_verbs_improved=baseline_metrics.action_verbs_improved,
        # checked
        checked_bullets=checked_bullets,
        checked_fidelity=checked_report.fidelity_score if checked_report else 1.0,
        checked_flags_h=ch,
        checked_flags_m=cm,
        checked_flags_l=cl,
        checked_attempts=checked_result.rewrite_attempts,
        checked_kw_before=_keyword_coverage(originals, keywords),
        checked_kw_after=_keyword_coverage(checked_bullets, keywords),
        checked_verbs_improved=checked_metrics.action_verbs_improved,
    )


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

_SEP  = "─" * 82
_DSEP = "═" * 82


def _pct(f: float) -> str:
    return f"{f * 100:.0f}%"


def _flags_str(h: int, m: int, l: int) -> str:
    total = h + m + l
    if total == 0:
        return "0"
    parts = []
    if h: parts.append(f"{h}H")
    if m: parts.append(f"{m}M")
    if l: parts.append(f"{l}L")
    return f"{total} ({'/'.join(parts)})"


def _bullet_block(label: str, bullets: list[str]) -> None:
    print(f"  {label}:")
    for b in bullets:
        wrapped = textwrap.fill(b, width=74, initial_indent="    • ", subsequent_indent="      ")
        print(wrapped)


def _print_pair(pr: PairResult, idx: int, total: int) -> None:
    print(_SEP)
    print(f"  [{idx}/{total}] {pr.pair_name}")
    print(f"  Assessment: {pr.assessment}")
    print(_SEP)

    _bullet_block("Original bullets", pr.original_bullets)
    print()
    _bullet_block("Ideal rewrite (ground truth)", pr.ideal_rewrite)
    print()
    _bullet_block("Baseline (no fidelity constraint)", pr.baseline_bullets)
    print()
    _bullet_block("Checked  (with fidelity constraint)", pr.checked_bullets)
    print()

    kw_before = _pct(pr.baseline_kw_before)  # same for both modes
    W1, W2, W3 = 40, 11, 11

    def row(label: str, b: str, c: str) -> None:
        print(f"  {label:<{W1}} {b:>{W2}} {c:>{W3}}")

    print(f"  {'Metric':<{W1}} {'Baseline':>{W2}} {'Checked':>{W3}}")
    print(f"  {'─'*W1} {'─'*W2} {'─'*W3}")
    row("KW coverage before rewrite",     kw_before,                          kw_before)
    row("KW coverage after rewrite",      _pct(pr.baseline_kw_after),         _pct(pr.checked_kw_after))
    row("Coverage improvement",           _pct(pr.baseline_kw_after - pr.baseline_kw_before),
                                          _pct(pr.checked_kw_after  - pr.checked_kw_before))
    row("Fidelity score",                 f"{pr.baseline_fidelity:.3f}",      f"{pr.checked_fidelity:.3f}")
    row("Flagged entities (H/M/L)",       _flags_str(pr.baseline_flags_h, pr.baseline_flags_m, pr.baseline_flags_l),
                                          _flags_str(pr.checked_flags_h,  pr.checked_flags_m,  pr.checked_flags_l))
    row("Rewrite attempts",               str(pr.baseline_attempts),          str(pr.checked_attempts))
    row("Action verbs improved",          str(pr.baseline_verbs_improved),    str(pr.checked_verbs_improved))
    print()


def _print_summary(results: list[PairResult]) -> None:
    n = len(results)

    avg_b_kw   = sum(r.baseline_kw_after - r.baseline_kw_before for r in results) / n
    avg_c_kw   = sum(r.checked_kw_after  - r.checked_kw_before  for r in results) / n
    avg_b_fid  = sum(r.baseline_fidelity for r in results) / n
    avg_c_fid  = sum(r.checked_fidelity  for r in results) / n
    tot_b_flags = sum(r.baseline_flags_h + r.baseline_flags_m + r.baseline_flags_l for r in results)
    tot_c_flags = sum(r.checked_flags_h  + r.checked_flags_m  + r.checked_flags_l  for r in results)
    avg_b_att  = sum(r.baseline_attempts for r in results) / n
    avg_c_att  = sum(r.checked_attempts  for r in results) / n

    first_try  = sum(1 for r in results if r.checked_attempts == 1)
    retried    = sum(1 for r in results if r.checked_attempts >= 2)
    failed_all = sum(1 for r in results if r.checked_fidelity < FIDELITY_THRESHOLD_WARN)

    flags_reduced = (
        (tot_b_flags - tot_c_flags) / tot_b_flags * 100
        if tot_b_flags > 0 else 0.0
    )
    kw_retained = (
        avg_c_kw / avg_b_kw * 100
        if avg_b_kw > 0 else 100.0
    )

    assessments = {"GOOD": 0, "OK": 0, "BAD": 0}
    for r in results:
        assessments[r.assessment] += 1

    print(_DSEP)
    print("  SUMMARY — 10-Pair Evaluation")
    print(_DSEP)
    print()

    # Per-pair assessment table
    print(f"  {'#':<4} {'Pair':<42} {'Fidelity':>9} {'KW +Δ':>7} {'Flags':>7} {'Att':>4} {'Grade':>6}")
    print(f"  {'─'*4} {'─'*42} {'─'*9} {'─'*7} {'─'*7} {'─'*4} {'─'*6}")
    for i, r in enumerate(results, 1):
        kw_delta = r.checked_kw_after - r.checked_kw_before
        tot_flags = r.checked_flags_h + r.checked_flags_m + r.checked_flags_l
        # Truncate pair name for table
        short = r.pair_name.replace("Pair ", "P").split("—")[1].strip() if "—" in r.pair_name else r.pair_name
        if len(short) > 42:
            short = short[:39] + "…"
        print(f"  {i:<4} {short:<42} {r.checked_fidelity:>9.3f} {_pct(kw_delta):>7} {tot_flags:>7} {r.checked_attempts:>4} {r.assessment:>6}")
    print()

    # Aggregate metrics
    W1, W2, W3 = 44, 11, 11
    def row(label: str, b: str, c: str) -> None:
        print(f"  {label:<{W1}} {b:>{W2}} {c:>{W3}}")

    print(f"  {'Aggregate Metric':<{W1}} {'Baseline':>{W2}} {'Checked':>{W3}}")
    print(f"  {'─'*W1} {'─'*W2} {'─'*W3}")
    row("Avg keyword coverage improvement",   _pct(avg_b_kw),           _pct(avg_c_kw))
    row("Avg fidelity score",                  f"{avg_b_fid:.3f}",       f"{avg_c_fid:.3f}")
    row("Total flagged entities",              str(tot_b_flags),          str(tot_c_flags))
    row("Avg rewrite attempts",                f"{avg_b_att:.1f}",       f"{avg_c_att:.1f}")
    print()

    # Checked-mode breakdown
    print(f"  Checked-mode pass/retry breakdown ({n} pairs):")
    print(f"    Passed on first attempt : {first_try:2d} / {n}  ({first_try/n*100:.0f}%)")
    print(f"    Triggered retry         : {retried:2d} / {n}  ({retried/n*100:.0f}%)")
    print(f"    Failed after retry      : {failed_all:2d} / {n}  ({failed_all/n*100:.0f}%)")
    print()

    # Assessment breakdown
    print(f"  Assessment breakdown (checked mode):")
    print(f"    GOOD (fidelity ≥ {FIDELITY_THRESHOLD_STRICT:.0%}, KW improved) : {assessments['GOOD']:2d} / {n}")
    print(f"    OK   (fidelity ≥ {FIDELITY_THRESHOLD_WARN:.0%})                 : {assessments['OK']:2d} / {n}")
    print(f"    BAD  (fidelity < {FIDELITY_THRESHOLD_WARN:.0%})                 : {assessments['BAD']:2d} / {n}")
    print()

    print(f"  Key findings:")
    print(f"    • Fidelity checker reduced flagged entities by {flags_reduced:.0f}%")
    print(f"      ({tot_b_flags} baseline flags → {tot_c_flags} checked flags across {n} pairs)")
    print(f"    • Keyword coverage improvement retained at {kw_retained:.0f}% of baseline")
    print(f"      ({_pct(avg_b_kw)} baseline avg → {_pct(avg_c_kw)} checked avg)")
    print(f"    • Avg fidelity: {avg_b_fid:.3f} (baseline) → {avg_c_fid:.3f} (checked)")
    print()
    print(_DSEP)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_eval() -> int:
    print(f"\n{_DSEP}")
    print(" REWRITE EVALUATION — v1  (10 pairs)")
    print(f" Baseline (no constraint) vs Fidelity-Checked")
    print(f"{_DSEP}\n")

    pairs   = _build_pairs()
    results: list[PairResult] = []

    for i, pair in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] {pair.name}")
        print(f"  {pair.description}")
        print()
        try:
            pr = _run_pair(pair, verbose=True)
            results.append(pr)
            _print_pair(pr, i, len(pairs))
        except Exception as exc:
            print(f"  ERROR running pair: {exc}")
            import traceback
            traceback.print_exc()
            return 1

    _print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(run_eval())
