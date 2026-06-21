"""
Model Comparison Script — Prompt Strategy Evaluation
=====================================================
Compares 3 prompt strategies on claude-haiku-4-5-20251001 across 3 eval pairs.

Strategies:
  A — Minimal   : bare-bones rewrite instruction, no constraints
  B — Current   : full DO NOT / YOU MAY system prompt with self-check (production)
  C — CoT       : current prompt + explicit chain-of-thought reasoning step

Pairs evaluated:
  Pair 1  (easy)   — Java Backend Dev → Senior Backend Engineer
  Pair 5  (medium) — QA Tester → Software Development Engineer
  Pair 10 (hard)   — Vague Dev → Specific Backend JD

Metrics per run:
  KW Before  — keyword coverage in original bullets
  KW After   — keyword coverage in rewritten bullets
  KW Δ       — coverage improvement
  Fidelity   — FidelityChecker score (0.0 → 1.0)
  H-Flags    — HIGH-severity fidelity violations (company/title/date fabrications)
  Tokens     — total tokens consumed (input + output)
  Duration   — wall-clock time (ms)

Usage (from agent-service/):
    python tests/run_model_comparison.py

Requires ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, ".")

import anthropic

from app.agents.fidelity_checker import FidelityChecker
# Import private helpers — read-only; we do NOT modify agent code
from app.agents.rewrite_agent import _SYSTEM_PROMPT, _build_user_prompt  # noqa: PLC2701
from app.models.job_description import JDSkillRequirement, ParsedJobDescription
from app.models.resume import (
    ParsedResume,
    ResumeContact,
    ResumeExperience,
    ResumeSkill,
)
from app.models.rewrite_result import (
    RewriteResult,
    RewrittenBullet,
    RewrittenExperience,
)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# Prompt templates for each strategy
# ---------------------------------------------------------------------------

_SYSTEM_A = """\
You are a resume writer. Rewrite the provided resume bullets to better match the job description.

Return ONLY a valid JSON object — no prose, no markdown fences:

{
  "rewritten_bullets": [
    {
      "original": "<exact original text>",
      "rewritten": "<improved text>",
      "changes_made": ["<change description>"]
    }
  ],
  "keywords_injected": ["<keyword1>", "<keyword2>"],
  "confidence": 0.0
}
"""

# Strategy B reuses the production _SYSTEM_PROMPT unchanged
_SYSTEM_B = _SYSTEM_PROMPT

_COT_SUFFIX = """\

━━━ CHAIN-OF-THOUGHT STEP (do this before writing JSON) ━━━━━━━━━━━━━━━━━━━━━
Before outputting the rewritten bullets, briefly reason through:
  1. Which JD keywords are currently missing from the original bullets?
  2. For each bullet: what is the weakest element and what specific change \
would most improve it?
  3. Which claims in the original can be reasonably reframed vs. which \
cannot be touched?

Write your reasoning as a short plain-text block, then output the JSON \
object described above.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

_SYSTEM_C = _SYSTEM_PROMPT + _COT_SUFFIX

STRATEGIES: list[tuple[str, str, str]] = [
    ("A-Minimal", "Minimal prompt — no constraints, just rewrite instruction", _SYSTEM_A),
    ("B-Current", "Current prompt — full DO NOT / YOU MAY + self-check (production)", _SYSTEM_B),
    ("C-CoT",     "Chain-of-thought — current prompt + explicit reasoning step", _SYSTEM_C),
]

# ---------------------------------------------------------------------------
# Eval pairs: Pair 1, 5, 10 (easy / medium / hard)
# ---------------------------------------------------------------------------

@dataclass
class EvalPair:
    label: str
    difficulty: str
    resume: ParsedResume
    jd: ParsedJobDescription
    match_result: dict


def _build_selected_pairs() -> list[EvalPair]:

    # ------------------------------------------------------------------
    # Pair 1 — Java Backend Dev → Senior Backend Engineer  (EASY)
    # Lots of skill overlap; primarily needs microservices reframing.
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
            "Built REST API using Java\nMaintained PostgreSQL database\nWrote unit tests"
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
            ],
            "overall_assessment": (
                "Candidate has solid Java and PostgreSQL experience but "
                "needs to frame work in terms of microservices architecture."
            ),
        },
    }

    # ------------------------------------------------------------------
    # Pair 5 — QA Tester → Software Development Engineer  (MEDIUM)
    # Career transition; needs reframing of QA work as SDE deliverables.
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
            "Wrote test cases\nPerformed manual testing\nFiled bug reports in Jira"
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
        keywords=["Python", "unit testing", "debugging", "automation", "software development",
                  "code quality", "test-driven"],
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

    # ------------------------------------------------------------------
    # Pair 10 — Vague Dev → Specific Backend JD  (HARD)
    # Candidate has the right stack but every bullet is maximally vague.
    # Biggest improvement opportunity; also highest hallucination risk.
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
            "Worked on backend stuff\nDid some database things\nHelped with deployments"
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
        keywords=["Python", "PostgreSQL", "Docker", "REST API", "CI/CD",
                  "microservices", "backend", "API design"],
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
                "Specificity is the only barrier."
            ),
        },
    }

    return [
        EvalPair("Pair 1",  "easy",   resume_1,  jd_1,  match_1),
        EvalPair("Pair 5",  "medium", resume_5,  jd_5,  match_5),
        EvalPair("Pair 10", "hard",   resume_10, jd_10, match_10),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _keyword_coverage(bullets: list[str], keywords: list[str]) -> float:
    """Fraction of JD keywords present in the bullet text (substring match)."""
    if not keywords:
        return 0.0
    text = " ".join(bullets).lower()
    return sum(1 for kw in keywords if kw.lower() in text) / len(keywords)


def _extract_json(raw: str) -> dict:
    """
    Extract the outermost JSON object containing 'rewritten_bullets' from a
    response string.  Handles CoT prose before the JSON block and optional
    markdown fences.

    Strategy: try each '{' position in order, parse the balanced object it
    starts, and return the first one that is a dict with 'rewritten_bullets'.
    This correctly handles:
      - Pure JSON responses (Strategy A, B)
      - CoT text followed by JSON (Strategy C)
      - Optional markdown fences
    """
    # Strip markdown fences
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().replace("```", "")

    # Fast path: whole string is valid JSON
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "rewritten_bullets" in data:
            return data
    except json.JSONDecodeError:
        pass

    def _balanced_end(text: str) -> int:
        """Return index of the closing '}' that matches the opening '{' at text[0]."""
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"' and not escape:
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    # Scan forward: try each '{' as a potential root object
    for match in re.finditer(r"\{", raw):
        candidate = raw[match.start():]
        end = _balanced_end(candidate)
        if end == -1:
            continue
        try:
            data = json.loads(candidate[: end + 1])
            if isinstance(data, dict) and "rewritten_bullets" in data:
                return data
        except json.JSONDecodeError:
            continue

    raise ValueError("No JSON object with 'rewritten_bullets' found in response")


def _build_rewrite_result(
    pair: EvalPair, data: dict
) -> RewriteResult:
    """
    Construct a minimal RewriteResult from Claude's parsed JSON output.
    Used for FidelityChecker.check() input.
    """
    exp = pair.resume.experience[0]
    raw_bullets = data.get("rewritten_bullets", [])

    rewritten_bullets: list[RewrittenBullet] = []
    for i, item in enumerate(raw_bullets):
        original = item.get("original", exp.bullets[i] if i < len(exp.bullets) else "")
        rewritten = item.get("rewritten", original)
        changes = list(item.get("changes_made", []))
        rewritten_bullets.append(
            RewrittenBullet(original=original, rewritten=rewritten, changes_made=changes)
        )

    # Pad if Claude returned fewer bullets than originals
    while len(rewritten_bullets) < len(exp.bullets):
        b = exp.bullets[len(rewritten_bullets)]
        rewritten_bullets.append(RewrittenBullet(original=b, rewritten=b, changes_made=[]))

    return RewriteResult(
        experiences=[
            RewrittenExperience(
                company=exp.company,
                title=exp.title,
                original_bullets=exp.bullets,
                rewritten_bullets=rewritten_bullets,
            )
        ],
        keywords_injected=sorted(data.get("keywords_injected", [])),
        overall_improvement_summary="(strategy comparison run)",
        rewrite_confidence=float(data.get("confidence", 0.8)),
    )


# ---------------------------------------------------------------------------
# Per-strategy runner
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    strategy_name: str
    pair_label: str
    pair_difficulty: str
    kw_before: float
    kw_after: float
    fidelity: float
    flags_h: int
    flags_m: int
    flags_l: int
    tokens: int
    duration_ms: int
    rewritten_bullets: list[str]
    error: str | None = None


def _build_user_prompt_minimal(pair: EvalPair) -> str:
    """Minimal user prompt for Strategy A — just the facts, no guidance."""
    gap = pair.match_result.get("gap_analysis") or pair.match_result
    exp = pair.resume.experience[0]
    bullets_text = "\n".join(f"- {b}" for b in exp.bullets)
    keywords_text = ", ".join(pair.jd.keywords or [])
    missing_text = ", ".join(
        gap.get("missing_required_skills", []) + gap.get("missing_preferred_skills", [])
    ) or "none"

    return (
        f"RESUME EXPERIENCE:\n"
        f"  Company: {exp.company}\n"
        f"  Title: {exp.title}\n"
        f"\nBULLETS TO REWRITE:\n{bullets_text}\n"
        f"\nTARGET JOB: {pair.jd.title}\n"
        f"JD KEYWORDS: {keywords_text}\n"
        f"MISSING SKILLS: {missing_text}\n"
        f"\nRewrite the {len(exp.bullets)} bullets. "
        f"Return exactly {len(exp.bullets)} objects in rewritten_bullets."
    )


def _build_user_prompt_full(pair: EvalPair) -> str:
    """Full production user prompt for Strategies B and C."""
    gap = pair.match_result.get("gap_analysis") or pair.match_result
    exp = pair.resume.experience[0]
    return _build_user_prompt(
        company=exp.company,
        title=exp.title,
        bullets=exp.bullets,
        jd_title=pair.jd.title or "the target role",
        missing_skills=(
            gap.get("missing_required_skills", [])
            + gap.get("missing_preferred_skills", [])
        ),
        jd_keywords=list(pair.jd.keywords or []),
        improvement_suggestions=gap.get("improvement_suggestions", []),
        fidelity_flags=None,
    )


def _run_strategy(
    strategy_name: str,
    system_prompt: str,
    pair: EvalPair,
    client: anthropic.Anthropic,
    checker: FidelityChecker,
) -> RunResult:
    """Call Claude with the given system prompt, measure all metrics."""
    exp = pair.resume.experience[0]
    originals = exp.bullets
    keywords = list(pair.jd.keywords or [])
    kw_before = _keyword_coverage(originals, keywords)

    user_prompt = (
        _build_user_prompt_minimal(pair)
        if strategy_name == "A-Minimal"
        else _build_user_prompt_full(pair)
    )

    # For CoT, append explicit reasoning instruction to user prompt
    if strategy_name == "C-CoT":
        user_prompt += (
            "\n\nBefore writing the JSON: reason through which keywords are missing, "
            "what to change in each bullet, and which claims are safe to reframe. "
            "Then output the JSON object."
        )

    t0 = time.perf_counter()
    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        return RunResult(
            strategy_name=strategy_name,
            pair_label=pair.label,
            pair_difficulty=pair.difficulty,
            kw_before=kw_before,
            kw_after=0.0,
            fidelity=0.0,
            flags_h=0, flags_m=0, flags_l=0,
            tokens=0,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            rewritten_bullets=originals,
            error=str(exc),
        )

    duration_ms = int((time.perf_counter() - t0) * 1000)
    tokens = response.usage.input_tokens + response.usage.output_tokens
    raw_text = response.content[0].text

    try:
        data = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        return RunResult(
            strategy_name=strategy_name,
            pair_label=pair.label,
            pair_difficulty=pair.difficulty,
            kw_before=kw_before,
            kw_after=0.0,
            fidelity=0.0,
            flags_h=0, flags_m=0, flags_l=0,
            tokens=tokens,
            duration_ms=duration_ms,
            rewritten_bullets=originals,
            error=f"JSON parse failed: {exc}",
        )

    rw_result = _build_rewrite_result(pair, data)
    rewritten = [rb.rewritten for rb in rw_result.experiences[0].rewritten_bullets]
    kw_after = _keyword_coverage(rewritten, keywords)

    fidelity_report = checker.check(pair.resume, rw_result)
    flags_h = sum(1 for f in fidelity_report.flags if f.severity == "high")
    flags_m = sum(1 for f in fidelity_report.flags if f.severity == "medium")
    flags_l = sum(1 for f in fidelity_report.flags if f.severity == "low")

    return RunResult(
        strategy_name=strategy_name,
        pair_label=pair.label,
        pair_difficulty=pair.difficulty,
        kw_before=kw_before,
        kw_after=kw_after,
        fidelity=fidelity_report.fidelity_score,
        flags_h=flags_h,
        flags_m=flags_m,
        flags_l=flags_l,
        tokens=tokens,
        duration_ms=duration_ms,
        rewritten_bullets=rewritten,
    )


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

_SEP  = "─" * 90
_DSEP = "═" * 90


def _pct(f: float) -> str:
    return f"{f * 100:.0f}%"


def _delta(before: float, after: float) -> str:
    d = after - before
    sign = "+" if d >= 0 else ""
    return f"{sign}{d * 100:.0f}%"


def _flags_str(h: int, m: int, l: int) -> str:
    total = h + m + l
    if total == 0:
        return "0"
    parts = []
    if h: parts.append(f"{h}H")
    if m: parts.append(f"{m}M")
    if l: parts.append(f"{l}L")
    return "/".join(parts)


def _print_detail(results: list[RunResult], pairs: list[EvalPair]) -> None:
    """Print per-pair bullet comparison for all 3 strategies."""
    pair_labels = list(dict.fromkeys(r.pair_label for r in results))
    strategy_names = list(dict.fromkeys(r.strategy_name for r in results))

    result_map: dict[tuple[str, str], RunResult] = {
        (r.strategy_name, r.pair_label): r for r in results
    }

    pair_meta = {p.label: p for p in pairs}

    for pl in pair_labels:
        pair = pair_meta[pl]
        print()
        print(_SEP)
        difficulty_tag = f"[{pair.difficulty.upper()}]"
        print(f"  {pl} {difficulty_tag} — {pair.jd.title}  (JD: {pair.jd.company})")
        print(_SEP)
        print(f"  Original bullets:")
        for b in pair.resume.experience[0].bullets:
            print(f"    • {b}")
        print()

        for sname in strategy_names:
            r = result_map.get((sname, pl))
            if r is None:
                continue
            status = " [ERROR: " + r.error + "]" if r.error else ""
            print(f"  Strategy {sname}{status}:")
            for b in r.rewritten_bullets:
                print(f"    • {b}")
            print()


def _print_comparison_table(results: list[RunResult]) -> None:
    print()
    print(_DSEP)
    print("  COMPARISON TABLE — Strategy × Pair (9 combinations)")
    print(_DSEP)
    print()

    # Column widths
    header = (
        f"  {'Strategy':<12} {'Pair':<8} {'Diff':<7} "
        f"{'KW_Before':>9} {'KW_After':>9} {'KW_Δ':>7} "
        f"{'Fidelity':>9} {'H-Flags':>8} {'Tokens':>7} {'Duration':>9}"
    )
    sep_row = "  " + "─" * (len(header) - 2)
    print(header)
    print(sep_row)

    for r in results:
        err_marker = " *" if r.error else ""
        print(
            f"  {r.strategy_name + err_marker:<12} {r.pair_label:<8} {r.pair_difficulty:<7} "
            f"{_pct(r.kw_before):>9} {_pct(r.kw_after):>9} {_delta(r.kw_before, r.kw_after):>7} "
            f"{r.fidelity:>9.3f} {r.flags_h:>8} {r.tokens:>7} {r.duration_ms:>7} ms"
        )

    if any(r.error for r in results):
        print()
        print("  * = error during run (metrics may be 0)")

    print()


def _print_per_strategy_aggregate(results: list[RunResult]) -> None:
    print(_DSEP)
    print("  AGGREGATE BY STRATEGY")
    print(_DSEP)
    print()

    strategy_names = list(dict.fromkeys(r.strategy_name for r in results))

    header = (
        f"  {'Strategy':<12} {'Avg KW_Δ':>9} {'Avg Fidelity':>13} "
        f"{'Total H-Flags':>14} {'Avg Tokens':>11} {'Avg Duration':>13}"
    )
    print(header)
    print("  " + "─" * (len(header) - 2))

    strategy_data: dict[str, dict] = {}
    for sname in strategy_names:
        group = [r for r in results if r.strategy_name == sname and not r.error]
        if not group:
            strategy_data[sname] = {}
            continue
        n = len(group)
        strategy_data[sname] = {
            "avg_kw_delta":  sum(r.kw_after - r.kw_before for r in group) / n,
            "avg_fidelity":  sum(r.fidelity for r in group) / n,
            "total_h_flags": sum(r.flags_h for r in group),
            "avg_tokens":    sum(r.tokens for r in group) / n,
            "avg_duration":  sum(r.duration_ms for r in group) / n,
        }

    for sname in strategy_names:
        d = strategy_data.get(sname, {})
        if not d:
            print(f"  {sname:<12}  (no valid runs)")
            continue
        print(
            f"  {sname:<12} {_delta(0.0, d['avg_kw_delta']):>9} "
            f"{d['avg_fidelity']:>13.3f} "
            f"{d['total_h_flags']:>14} "
            f"{d['avg_tokens']:>11.0f} "
            f"{d['avg_duration']:>10.0f} ms"
        )

    print()
    return strategy_data


def _print_recommendations(strategy_data: dict[str, dict]) -> None:
    print(_DSEP)
    print("  RECOMMENDATIONS")
    print(_DSEP)
    print()

    if not all(strategy_data.get(s) for s in ("A-Minimal", "B-Current", "C-CoT")):
        print("  (Insufficient data to generate recommendations — check for errors above)")
        print()
        return

    a = strategy_data["A-Minimal"]
    b = strategy_data["B-Current"]
    c = strategy_data["C-CoT"]

    kw_winner = max(
        [("A-Minimal", a), ("B-Current", b), ("C-CoT", c)],
        key=lambda x: x[1]["avg_kw_delta"],
    )
    fidelity_winner = max(
        [("A-Minimal", a), ("B-Current", b), ("C-CoT", c)],
        key=lambda x: x[1]["avg_fidelity"],
    )
    cost_winner = min(
        [("A-Minimal", a), ("B-Current", b), ("C-CoT", c)],
        key=lambda x: x[1]["avg_tokens"],
    )

    # Quality score: keyword coverage weighted equally with fidelity,
    # then penalised for H-flags and token cost
    def quality_score(d: dict) -> float:
        kw_norm  = d["avg_kw_delta"]   # 0.0–1.0
        fid_norm = d["avg_fidelity"]   # 0.0–1.0
        h_penalty = d["total_h_flags"] * 0.05          # each H-flag costs 5pp
        tok_penalty = d["avg_tokens"] / 10_000         # 10k tokens costs ~1.0
        return (kw_norm + fid_norm) / 2 - h_penalty - tok_penalty * 0.1

    scores = {
        "A-Minimal": quality_score(a),
        "B-Current": quality_score(b),
        "C-CoT":     quality_score(c),
    }
    balanced_winner = max(scores, key=lambda s: scores[s])

    def fmt(d: dict) -> str:
        return (
            f"KW Δ={_delta(0.0, d['avg_kw_delta'])}, "
            f"Fidelity={d['avg_fidelity']:.3f}, "
            f"H-Flags={d['total_h_flags']}, "
            f"Tokens={d['avg_tokens']:.0f}"
        )

    print(f"  Best keyword coverage  : {kw_winner[0]}  ({fmt(kw_winner[1])})")
    print(f"  Best fidelity          : {fidelity_winner[0]}  ({fmt(fidelity_winner[1])})")
    print(f"  Lowest token cost      : {cost_winner[0]}  ({fmt(cost_winner[1])})")
    print(f"  Best quality/cost mix  : {balanced_winner}  (score={scores[balanced_winner]:.3f})")
    print()

    print("  Analysis:")
    print()

    # A-Minimal
    a_vs_b_kw  = (a["avg_kw_delta"]  - b["avg_kw_delta"])  * 100
    a_vs_b_fid = (a["avg_fidelity"]  - b["avg_fidelity"])
    print(f"  A-Minimal vs B-Current:")
    print(f"    KW coverage : {'A better by' if a_vs_b_kw > 0 else 'B better by'} "
          f"{abs(a_vs_b_kw):.0f}pp")
    print(f"    Fidelity    : {'A better by' if a_vs_b_fid > 0 else 'B better by'} "
          f"{abs(a_vs_b_fid):.3f}")
    print(f"    H-Flags     : A={a['total_h_flags']}  B={b['total_h_flags']}")
    print(f"    Tokens      : A={a['avg_tokens']:.0f}  B={b['avg_tokens']:.0f} "
          f"({'A cheaper' if a['avg_tokens'] < b['avg_tokens'] else 'B cheaper'})")
    print()

    # C-CoT vs B-Current
    c_vs_b_kw  = (c["avg_kw_delta"]  - b["avg_kw_delta"])  * 100
    c_vs_b_fid = (c["avg_fidelity"]  - b["avg_fidelity"])
    c_vs_b_tok = (c["avg_tokens"]    - b["avg_tokens"])
    print(f"  C-CoT vs B-Current:")
    print(f"    KW coverage : {'C better by' if c_vs_b_kw > 0 else 'B better by'} "
          f"{abs(c_vs_b_kw):.0f}pp")
    print(f"    Fidelity    : {'C better by' if c_vs_b_fid > 0 else 'B better by'} "
          f"{abs(c_vs_b_fid):.3f}")
    print(f"    H-Flags     : C={c['total_h_flags']}  B={b['total_h_flags']}")
    print(f"    Extra tokens from CoT: {c_vs_b_tok:+.0f} avg per run")
    print()

    print(f"  Recommendation:")
    if balanced_winner == "B-Current":
        print("  → Use B-Current (production prompt). It achieves the best balance of")
        print("    keyword coverage and fidelity without the token overhead of CoT.")
        if c["avg_fidelity"] >= b["avg_fidelity"]:
            print("  → C-CoT matches or improves fidelity but costs more tokens —")
            print("    worth evaluating for high-stakes rewrites where fidelity is critical.")
        if a["total_h_flags"] > b["total_h_flags"]:
            print(f"  → A-Minimal introduces {a['total_h_flags'] - b['total_h_flags']} more H-flags than B-Current;")
            print("    do not use in production without a fidelity guard.")
    elif balanced_winner == "C-CoT":
        print("  → Use C-CoT. The reasoning step improves quality enough to justify")
        print(f"    the extra {c_vs_b_tok:+.0f} tokens per run. Consider enabling for")
        print("    career-transition pairs where reframing is the primary challenge.")
        print("  → B-Current remains the cost-efficient fallback for straightforward rewrites.")
    else:
        print("  → A-Minimal yields the best keyword coverage but check H-flag count;")
        print("    it must be paired with a fidelity checker in production to be safe.")
    print()
    print(_DSEP)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_comparison() -> int:
    print(f"\n{_DSEP}")
    print("  MODEL COMPARISON — Prompt Strategy Evaluation")
    print(f"  Model: {_MODEL}")
    print(f"  Strategies: A-Minimal | B-Current | C-CoT")
    print(f"  Pairs: 1 (easy) | 5 (medium) | 10 (hard)")
    print(f"{_DSEP}\n")

    client  = anthropic.Anthropic()
    checker = FidelityChecker()
    pairs   = _build_selected_pairs()

    results: list[RunResult] = []

    total = len(STRATEGIES) * len(pairs)
    idx = 0
    for strategy_name, strategy_desc, system_prompt in STRATEGIES:
        print(f"\n  [{strategy_name}] {strategy_desc}")
        print(f"  {'─' * 70}")
        for pair in pairs:
            idx += 1
            print(f"  ({idx}/{total}) {pair.label} [{pair.difficulty}] — {pair.jd.title} …", end="", flush=True)
            r = _run_strategy(strategy_name, system_prompt, pair, client, checker)
            results.append(r)
            status = f" ERROR: {r.error}" if r.error else f" ✓  ({r.tokens} tok, {r.duration_ms} ms)"
            print(status)

    _print_detail(results, pairs)
    _print_comparison_table(results)
    strategy_data = _print_per_strategy_aggregate(results)
    _print_recommendations(strategy_data)

    return 0


if __name__ == "__main__":
    sys.exit(run_comparison())
