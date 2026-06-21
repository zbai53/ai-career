"""
Rewrite Evaluation Script — v1
================================
Compares RewriteAgent output in two modes for 3 resume-JD pairs:

  Baseline  — fidelity checker is bypassed (no retry, no constraint)
  Checked   — fidelity checker runs normally (retry on score < 0.80)

Metrics reported per pair:
  • Keyword coverage before / after rewrite
  • Fidelity score
  • Number of flagged entities
  • Number of rewrite attempts

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
from app.agents.rewrite_agent import RewriteAgent, compare_versions
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
# Build the 3 resume-JD pairs
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
        "Architected and deployed Java-based microservices REST API, enabling independent scaling across 3 service domains",
        "Managed and optimized PostgreSQL database schema supporting production workloads with automated backup and recovery",
        "Authored comprehensive unit and integration test suites using JUnit, maintaining 85%+ coverage across core services",
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
        "Engineered reusable React component library using TypeScript, reducing feature delivery time across 4 product teams",
        "Diagnosed and resolved cross-browser CSS and layout regressions, improving UI consistency across desktop and mobile",
        "Automated CI/CD deployment pipeline to production, cutting release cycle from weekly to daily with zero-downtime deploys",
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
        "Investigated and resolved production bugs by reproducing failure conditions and tracing root cause through application logs",
        "Contributed to code review process by identifying logic errors and flagging security anti-patterns across 20+ PRs",
        "Developed Python automation scripts to streamline team workflows, demonstrating applied language proficiency",
    ]

    return [
        EvalPair(
            name="Pair 1 — Java Backend Dev → Senior Backend Engineer",
            description=(
                "Mid-level Java developer targeting a senior role. "
                "Key gaps: 'microservices', 'CI/CD', quantified impact."
            ),
            resume=resume_1,
            jd=jd_1,
            match_result=match_1,
            ideal_rewrite=ideal_1,
        ),
        EvalPair(
            name="Pair 2 — React Frontend Dev → Full Stack Engineer",
            description=(
                "Frontend dev targeting a full-stack role. "
                "Key gaps: TypeScript, Node.js, CI/CD pipeline ownership."
            ),
            resume=resume_2,
            jd=jd_2,
            match_result=match_2,
            ideal_rewrite=ideal_2,
        ),
        EvalPair(
            name="Pair 3 — Junior Dev → Mid-level (stretch)",
            description=(
                "Junior dev with passive bullet language targeting a mid-level role. "
                "Key transformation: reframe passive 'helped / attended / learned' into active contributions."
            ),
            resume=resume_3,
            jd=jd_3,
            match_result=match_3,
            ideal_rewrite=ideal_3,
        ),
    ]


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _keyword_coverage(bullets: list[str], keywords: list[str]) -> float:
    """Fraction of JD keywords that appear in the bullet text."""
    if not keywords:
        return 0.0
    text = " ".join(bullets).lower()
    found = sum(1 for kw in keywords if kw.lower() in text)
    return found / len(keywords)


def _collect_bullets(result: RewriteResult) -> list[str]:
    return [rb.rewritten for exp in result.experiences for rb in exp.rewritten_bullets]


def _collect_originals(resume: ParsedResume) -> list[str]:
    return [b for exp in resume.experience for b in exp.bullets]


# ---------------------------------------------------------------------------
# Per-pair runner
# ---------------------------------------------------------------------------

@dataclass
class PairResult:
    pair_name: str
    original_bullets: list[str]
    # Baseline
    baseline_bullets: list[str]
    baseline_fidelity: float
    baseline_flags: int
    baseline_attempts: int
    baseline_kw_coverage_before: float
    baseline_kw_coverage_after: float
    # Checked
    checked_bullets: list[str]
    checked_fidelity: float
    checked_flags: int
    checked_attempts: int
    checked_kw_coverage_before: float
    checked_kw_coverage_after: float
    # Shared
    jd_keywords: list[str]
    ideal_rewrite: list[str]
    # Action verb improvement
    baseline_verbs_improved: int = 0
    checked_verbs_improved: int = 0


def _run_pair(pair: EvalPair, verbose: bool = True) -> PairResult:
    keywords = list(pair.jd.keywords or [])
    originals = _collect_originals(pair.resume)

    # ---- baseline (stub checker → no retry) ----
    if verbose:
        print(f"  [baseline] calling RewriteAgent …")
    baseline_agent = RewriteAgent(fidelity_checker=_AlwaysPassChecker())
    baseline_result, _ = baseline_agent.rewrite(pair.resume, pair.jd, pair.match_result)
    baseline_bullets = _collect_bullets(baseline_result)

    # Run the real checker on baseline result to measure actual fidelity
    real_checker = FidelityChecker()
    baseline_report = real_checker.check(pair.resume, baseline_result)

    baseline_metrics = compare_versions(originals, baseline_bullets, keywords)

    # ---- checked (normal agent) ----
    if verbose:
        print(f"  [checked]  calling RewriteAgent …")
    checked_agent = RewriteAgent()
    checked_result, _ = checked_agent.rewrite(pair.resume, pair.jd, pair.match_result)
    checked_bullets = _collect_bullets(checked_result)
    checked_report = checked_result.fidelity_report

    checked_metrics = compare_versions(originals, checked_bullets, keywords)

    return PairResult(
        pair_name=pair.name,
        original_bullets=originals,
        # baseline
        baseline_bullets=baseline_bullets,
        baseline_fidelity=baseline_report.fidelity_score,
        baseline_flags=len(baseline_report.flags),
        baseline_attempts=baseline_result.rewrite_attempts,
        baseline_kw_coverage_before=_keyword_coverage(originals, keywords),
        baseline_kw_coverage_after=_keyword_coverage(baseline_bullets, keywords),
        baseline_verbs_improved=baseline_metrics.action_verbs_improved,
        # checked
        checked_bullets=checked_bullets,
        checked_fidelity=checked_report.fidelity_score if checked_report else 1.0,
        checked_flags=len(checked_report.flags) if checked_report else 0,
        checked_attempts=checked_result.rewrite_attempts,
        checked_kw_coverage_before=_keyword_coverage(originals, keywords),
        checked_kw_coverage_after=_keyword_coverage(checked_bullets, keywords),
        checked_verbs_improved=checked_metrics.action_verbs_improved,
        # shared
        jd_keywords=keywords,
        ideal_rewrite=pair.ideal_rewrite,
    )


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

_SEP  = "─" * 78
_DSEP = "═" * 78
_W    = 78


def _pct(f: float) -> str:
    return f"{f * 100:.0f}%"


def _bullet_block(label: str, bullets: list[str]) -> None:
    print(f"  {label}:")
    for b in bullets:
        wrapped = textwrap.fill(b, width=72, initial_indent="    • ", subsequent_indent="      ")
        print(wrapped)


def _print_pair(pr: PairResult) -> None:
    print(_SEP)
    print(f"  {pr.pair_name}")
    print(_SEP)

    _bullet_block("Original bullets", pr.original_bullets)
    print()
    _bullet_block("Ideal rewrite (ground truth)", pr.ideal_rewrite)
    print()
    _bullet_block("Baseline rewrite  (no fidelity constraint)", pr.baseline_bullets)
    print()
    _bullet_block("Checked rewrite   (with fidelity constraint)", pr.checked_bullets)
    print()

    # Metrics table
    kw_cov_before = _pct(pr.baseline_kw_coverage_before)   # same for both
    print(f"  {'Metric':<38} {'Baseline':>10} {'Checked':>10}")
    print(f"  {'─'*38} {'─'*10} {'─'*10}")
    print(f"  {'JD keyword coverage (before rewrite)':<38} {kw_cov_before:>10} {kw_cov_before:>10}")
    print(f"  {'JD keyword coverage (after rewrite)':<38} {_pct(pr.baseline_kw_coverage_after):>10} {_pct(pr.checked_kw_coverage_after):>10}")
    print(f"  {'Coverage improvement':<38} {_pct(pr.baseline_kw_coverage_after - pr.baseline_kw_coverage_before):>10} {_pct(pr.checked_kw_coverage_after - pr.checked_kw_coverage_before):>10}")
    print(f"  {'Fidelity score':<38} {pr.baseline_fidelity:>10.3f} {pr.checked_fidelity:>10.3f}")
    print(f"  {'Flagged entities':<38} {pr.baseline_flags:>10} {pr.checked_flags:>10}")
    print(f"  {'Rewrite attempts':<38} {pr.baseline_attempts:>10} {pr.checked_attempts:>10}")
    print(f"  {'Action verbs improved':<38} {pr.baseline_verbs_improved:>10} {pr.checked_verbs_improved:>10}")
    print()


def _print_summary(results: list[PairResult]) -> None:
    print(_DSEP)
    print("  SUMMARY — Baseline vs Fidelity-Checked Rewrites")
    print(_DSEP)

    # Aggregate stats
    avg_baseline_kw = sum(r.baseline_kw_coverage_after - r.baseline_kw_coverage_before for r in results) / len(results)
    avg_checked_kw  = sum(r.checked_kw_coverage_after  - r.checked_kw_coverage_before  for r in results) / len(results)
    avg_baseline_fid = sum(r.baseline_fidelity for r in results) / len(results)
    avg_checked_fid  = sum(r.checked_fidelity  for r in results) / len(results)
    total_baseline_flags = sum(r.baseline_flags for r in results)
    total_checked_flags  = sum(r.checked_flags  for r in results)
    avg_baseline_attempts = sum(r.baseline_attempts for r in results) / len(results)
    avg_checked_attempts  = sum(r.checked_attempts  for r in results) / len(results)

    flags_reduced_pct = (
        (total_baseline_flags - total_checked_flags) / total_baseline_flags * 100
        if total_baseline_flags > 0
        else 0.0
    )
    kw_retention_pct = (
        avg_checked_kw / avg_baseline_kw * 100
        if avg_baseline_kw > 0
        else 100.0
    )

    print()
    print(f"  {'Metric':<44} {'Baseline':>10} {'Checked':>10}")
    print(f"  {'─'*44} {'─'*10} {'─'*10}")
    print(f"  {'Avg keyword coverage improvement':<44} {_pct(avg_baseline_kw):>10} {_pct(avg_checked_kw):>10}")
    print(f"  {'Avg fidelity score':<44} {avg_baseline_fid:>10.3f} {avg_checked_fid:>10.3f}")
    print(f"  {'Total flagged entities':<44} {total_baseline_flags:>10} {total_checked_flags:>10}")
    print(f"  {'Avg rewrite attempts':<44} {avg_baseline_attempts:>10.1f} {avg_checked_attempts:>10.1f}")
    print()

    print(f"  Key findings:")
    print(f"    • Fidelity checker reduced flagged entities by {flags_reduced_pct:.0f}%")
    print(f"      ({total_baseline_flags} baseline flags → {total_checked_flags} checked flags)")
    print(f"    • Keyword coverage improvement retained at {kw_retention_pct:.0f}% of baseline")
    print(f"      ({_pct(avg_baseline_kw)} baseline → {_pct(avg_checked_kw)} checked)")
    print(f"    • Avg fidelity score improved from {avg_baseline_fid:.3f} → {avg_checked_fid:.3f}")
    print()
    print(_DSEP)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_eval() -> int:
    print(f"\n{_DSEP}")
    print(" REWRITE EVALUATION — v1")
    print(" Baseline (no fidelity constraint) vs Fidelity-Checked Rewrites")
    print(f"{_DSEP}\n")

    pairs = _build_pairs()
    results: list[PairResult] = []

    for i, pair in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] {pair.name}")
        print(f"  {pair.description}")
        print()
        try:
            pr = _run_pair(pair, verbose=True)
            results.append(pr)
            _print_pair(pr)
        except Exception as exc:
            print(f"  ERROR running pair: {exc}")
            import traceback
            traceback.print_exc()
            return 1

    _print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(run_eval())
