"""
Fidelity Evaluation Script — v1
================================
Runs FidelityChecker against 5 hand-crafted test cases with known expected
outcomes and prints a human-readable report.

Usage (from agent-service/):
    python tests/run_fidelity_eval.py

No API key required — FidelityChecker runs in rule-based-only mode.
Claude is only used for company/title extraction; all five cases are designed
so the verdict does not depend on Claude availability.
"""

from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass, field

# Ensure project root is on the path when run directly
sys.path.insert(0, ".")

from app.agents.fidelity_checker import FidelityChecker
from app.models.fidelity_report import FidelityFlag, FidelityReport
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)
from app.models.rewrite_result import RewriteResult, RewrittenBullet, RewrittenExperience

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEP = "─" * 72


def _make_resume(
    company: str,
    title: str,
    original_bullet: str,
    technologies: list[str] | None = None,
    skills: list[str] | None = None,
    extra_text: str = "",
) -> ParsedResume:
    return ParsedResume(
        contact=ResumeContact(name="Test Candidate", email="test@example.com"),
        experience=[
            ResumeExperience(
                company=company,
                title=title,
                bullets=[original_bullet],
                technologies=technologies or [],
            )
        ],
        skills=[ResumeSkill(name=s, category="tool") for s in (skills or [])],
        raw_text=f"{original_bullet} {extra_text}".strip(),
        parse_confidence=0.95,
    )


def _make_rewrite(
    company: str,
    title: str,
    original_bullet: str,
    rewritten_bullet: str,
) -> RewriteResult:
    return RewriteResult(
        experiences=[
            RewrittenExperience(
                company=company,
                title=title,
                original_bullets=[original_bullet],
                rewritten_bullets=[
                    RewrittenBullet(
                        original=original_bullet,
                        rewritten=rewritten_bullet,
                        changes_made=[],
                    )
                ],
            )
        ],
        keywords_injected=[],
        overall_improvement_summary="Eval rewrite.",
        rewrite_confidence=0.9,
    )


# ---------------------------------------------------------------------------
# Test case definition
# ---------------------------------------------------------------------------

@dataclass
class Expectation:
    min_score: float | None = None          # fidelity_score must be >= this
    max_score: float | None = None          # fidelity_score must be < this
    passed: bool | None = None              # report.passed must equal this
    flagged_entities: list[str] = field(default_factory=list)   # must appear in flags
    flagged_severities: dict[str, str] = field(default_factory=dict)  # entity → severity
    no_high_flags: bool = False             # no high-severity flags allowed


@dataclass
class EvalCase:
    name: str
    description: str
    original_bullet: str
    rewritten_bullet: str
    company: str
    title: str
    technologies: list[str]
    skills: list[str]
    extra_resume_text: str
    expectation: Expectation


CASES: list[EvalCase] = [
    # -------------------------------------------------------------------------
    EvalCase(
        name="Case 1 — Clean rewrite",
        description=(
            "Action verb change + light keyword injection. "
            "No new facts introduced. Should pass with score >= 0.9."
        ),
        company="TechStartup",
        title="Backend Engineer",
        original_bullet="Built REST API using Java and PostgreSQL",
        rewritten_bullet=(
            "Engineered high-performance REST API leveraging Java and PostgreSQL "
            "for data persistence"
        ),
        technologies=["Java", "PostgreSQL"],
        skills=["Java", "PostgreSQL"],
        extra_resume_text="",
        expectation=Expectation(
            min_score=0.9,
            passed=True,
            no_high_flags=True,
        ),
    ),
    # -------------------------------------------------------------------------
    EvalCase(
        name="Case 2 — Fabricated company name",
        description=(
            "Rewrite invents a previous employer (Google). "
            "Should fail with 'google' flagged HIGH severity."
        ),
        company="Acme Corp",
        title="Software Engineer",
        original_bullet="Built REST API at Acme Corp",
        rewritten_bullet=(
            "Built REST API at Acme Corp, previously implemented at Google"
        ),
        technologies=[],
        skills=[],
        extra_resume_text="Acme Corp",
        expectation=Expectation(
            max_score=0.85,
            passed=False,
            flagged_entities=["google"],
            flagged_severities={"google": "high"},
        ),
    ),
    # -------------------------------------------------------------------------
    EvalCase(
        name="Case 3 — Fabricated metrics",
        description=(
            "Rewrite adds hard numbers (40%, 500ms, 300ms) not in original. "
            "Should flag as MEDIUM severity unverified metrics."
        ),
        company="DataCo",
        title="Database Engineer",
        original_bullet="Improved database performance",
        rewritten_bullet=(
            "Improved database performance by 40%, reducing query latency "
            "from 500ms to 300ms"
        ),
        technologies=[],
        skills=[],
        extra_resume_text="",
        expectation=Expectation(
            flagged_entities=["40%"],
            flagged_severities={"40%": "medium"},
            no_high_flags=True,
        ),
    ),
    # -------------------------------------------------------------------------
    EvalCase(
        name="Case 4 — Added technologies",
        description=(
            "Original mentions React only; rewrite adds Redux, TypeScript, Jest. "
            "Rule-based vocabulary catches TypeScript (in vocab) and flags it MEDIUM. "
            "Redux/Jest are not yet in the vocab — documented as a known gap."
        ),
        company="WebAgency",
        title="Frontend Developer",
        original_bullet="Built web application using React",
        rewritten_bullet=(
            "Built web application using React, Redux, and TypeScript "
            "with comprehensive test coverage using Jest"
        ),
        technologies=["React"],
        skills=["React"],
        extra_resume_text="React",
        expectation=Expectation(
            flagged_entities=["typescript"],
            flagged_severities={"typescript": "medium"},
            no_high_flags=True,
        ),
    ),
    # -------------------------------------------------------------------------
    EvalCase(
        name="Case 5 — Safe rephrasing with one metric",
        description=(
            "Action verb swap + contextual elaboration. Adds '99.9%' availability "
            "metric not in original. Should flag that metric MEDIUM; overall score "
            "close to passing threshold."
        ),
        company="InfraTeam",
        title="SRE",
        original_bullet="Responsible for maintaining database",
        rewritten_bullet=(
            "Maintained and optimized relational database systems ensuring "
            "99.9% availability"
        ),
        technologies=[],
        skills=[],
        extra_resume_text="",
        expectation=Expectation(
            flagged_entities=["99.9%"],
            flagged_severities={"99.9%": "medium"},
            no_high_flags=True,
        ),
    ),
]

# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

def _check_expectation(report: FidelityReport, exp: Expectation) -> tuple[bool, list[str]]:
    """Return (met, list_of_failures)."""
    failures: list[str] = []
    flag_entities = {f.entity.lower(): f for f in report.flags}

    if exp.min_score is not None and report.fidelity_score < exp.min_score:
        failures.append(
            f"score {report.fidelity_score:.4f} < expected min {exp.min_score}"
        )
    if exp.max_score is not None and report.fidelity_score >= exp.max_score:
        failures.append(
            f"score {report.fidelity_score:.4f} >= expected max {exp.max_score}"
        )
    if exp.passed is not None and report.passed != exp.passed:
        failures.append(
            f"passed={report.passed}, expected {exp.passed}"
        )
    if exp.no_high_flags:
        high_flags = [f for f in report.flags if f.severity == "high"]
        if high_flags:
            entities = [f.entity for f in high_flags]
            failures.append(f"unexpected HIGH-severity flags: {entities}")
    for entity in exp.flagged_entities:
        if entity.lower() not in flag_entities:
            failures.append(f"expected entity '{entity}' not flagged")
    for entity, expected_sev in exp.flagged_severities.items():
        flag = flag_entities.get(entity.lower())
        if flag and flag.severity != expected_sev:
            failures.append(
                f"entity '{entity}' severity={flag.severity}, expected {expected_sev}"
            )

    return len(failures) == 0, failures


def _print_flags(flags: list[FidelityFlag]) -> None:
    if not flags:
        print("  Flags     : (none)")
        return
    for f in flags:
        print(f"  Flag      : [{f.severity.upper():6s}] {f.entity_type}={f.entity!r}")
        snippet = f.found_in[:80] + ("…" if len(f.found_in) > 80 else "")
        print(f"             found in: {snippet!r}")


def run_eval() -> int:
    checker = FidelityChecker()
    matched = 0

    print(f"\n{'═' * 72}")
    print(" FIDELITY EVALUATION — v1")
    print(f"{'═' * 72}\n")

    for i, case in enumerate(CASES, 1):
        resume = _make_resume(
            company=case.company,
            title=case.title,
            original_bullet=case.original_bullet,
            technologies=case.technologies,
            skills=case.skills,
            extra_text=case.extra_resume_text,
        )
        rewrite = _make_rewrite(
            company=case.company,
            title=case.title,
            original_bullet=case.original_bullet,
            rewritten_bullet=case.rewritten_bullet,
        )

        report = checker.check(resume, rewrite)
        met, failures = _check_expectation(report, case.expectation)

        verdict = "✓ PASS" if met else "✗ FAIL"
        matched += int(met)

        print(f"{_SEP}")
        print(f"[{i}/5] {case.name}")
        print(textwrap.fill(case.description, width=70, initial_indent="  "))
        print()
        print(f"  Original  : {case.original_bullet}")
        print(f"  Rewritten : {case.rewritten_bullet}")
        print()
        print(f"  Score     : {report.fidelity_score:.4f}  |  "
              f"passed={report.passed}  |  "
              f"orig_entities={report.total_original_entities}  |  "
              f"rw_entities={report.total_rewritten_entities}  |  "
              f"new={report.new_entities_found}")
        _print_flags(report.flags)
        print()
        print(f"  Result    : {verdict}")
        if failures:
            for f in failures:
                print(f"              ↳ {f}")
        print()

    print(f"{'═' * 72}")
    print(f" SUMMARY: {matched}/{len(CASES)} cases matched expectations")
    print(f"{'═' * 72}\n")

    return 0 if matched == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(run_eval())
