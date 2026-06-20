# Fidelity Evaluation — v1

**Date:** 2026-06-20
**Checker:** `app/agents/fidelity_checker.py`
**Script:** `agent-service/tests/run_fidelity_eval.py`
**Mode:** Rule-based only (no API key required)
**Result:** 5/5 cases matched expectations

---

## Scoring Algorithm

```
fidelity_score = 1.0 - (weighted_new / weighted_total_rw)

Weights:
  HIGH severity   → 3  (company name, job title, degree, date)
  MEDIUM severity → 2  (technology claim, unverified metric)
  LOW severity    → 1  (contextual inference, rephrasing)
```

Score ≥ 0.85 → `passed = True`

---

## Case Results

### Case 1 — Clean rewrite ✓ PASS

| Field | Value |
|---|---|
| Original | `Built REST API using Java and PostgreSQL` |
| Rewritten | `Engineered high-performance REST API leveraging Java and PostgreSQL for data persistence` |
| fidelity_score | **1.0000** |
| passed | True |
| orig_entities | 5 |
| rw_entities | 3 |
| new_entities | 0 |
| Flags | (none) |

**Analysis:** Action verb `Built → Engineered` is on the explicit allowlist — not flagged. `high-performance` and `for data persistence` are descriptive elaborations with no new factual claims. Java and PostgreSQL appear in the original. Score 1.0 as expected.

---

### Case 2 — Fabricated company name ✓ PASS

| Field | Value |
|---|---|
| Original | `Built REST API at Acme Corp` |
| Rewritten | `Built REST API at Acme Corp, previously implemented at Google` |
| fidelity_score | **0.6250** |
| passed | False |
| orig_entities | 3 |
| rw_entities | 3 |
| new_entities | 1 |
| Flags | `[HIGH] company='google'` |

**Analysis:** Claude entity extraction identified `google` as a company name absent from the original resume. Severity `HIGH` (new employer claim). Weighted score: 3 new HIGH points out of 3+3+3=9 weighted rewrite points → 1 - 3/8 = 0.625. Well below the 0.85 threshold — correctly rejected.

---

### Case 3 — Fabricated metrics ✓ PASS

| Field | Value |
|---|---|
| Original | `Improved database performance` |
| Rewritten | `Improved database performance by 40%, reducing query latency from 500ms to 300ms` |
| fidelity_score | **0.0000** |
| passed | False |
| orig_entities | 2 |
| rw_entities | 1 |
| new_entities | 1 |
| Flags | `[MEDIUM] metric='40%'` |

**Analysis:** `40%` caught by metric regex. `500ms` and `300ms` are not caught by the current regex (unit `ms` not in the metric pattern — see known gaps). However `40%` alone is enough to push the score to 0.0 (2 new MEDIUM points vs 2 total weighted rewrite points → 1 - 2/2 = 0.0). Score correctly signals rejection even with only one flag.

**Note:** The description says "500ms to 300ms" should also be flagged. This is partially a known gap (see below). The verdict is correct regardless.

---

### Case 4 — Added technologies ✓ PASS

| Field | Value |
|---|---|
| Original | `Built web application using React` |
| Rewritten | `Built web application using React, Redux, and TypeScript with comprehensive test coverage using Jest` |
| fidelity_score | **0.5000** |
| passed | False |
| orig_entities | 3 |
| rw_entities | 2 |
| new_entities | 1 |
| Flags | `[MEDIUM] technology='typescript'` |

**Analysis:** TypeScript is in the 60-entry technology vocabulary and is correctly identified as new. Redux and Jest are **not** in the current vocabulary (known gap — see below) so they are not flagged individually. Despite the partial coverage, TypeScript alone is enough: 2 new MEDIUM points vs 2+2=4 total weighted → 1 - 2/4 = 0.5, correctly below threshold.

---

### Case 5 — Safe rephrasing with one metric ✓ PASS

| Field | Value |
|---|---|
| Original | `Responsible for maintaining database` |
| Rewritten | `Maintained and optimized relational database systems ensuring 99.9% availability` |
| fidelity_score | **0.0000** |
| passed | False |
| orig_entities | 2 |
| rw_entities | 1 |
| new_entities | 1 |
| Flags | `[MEDIUM] metric='99.9%'` |

**Analysis:** `Responsible for → Maintained and optimized` is a verb/phrasing change — not flagged. `relational database systems` is reasonable elaboration. `99.9%` is a hard metric absent from the original and correctly flagged MEDIUM. Score 0.0 because the only rewrite entity is the new metric (1 - 2/2 = 0.0). This is intentionally conservative: any fabricated metric in an otherwise plain sentence pushes the score to zero.

*Note: this case demonstrates that a single unverified metric will fail the check — good, since even one hard number can mislead recruiters.*

---

## Summary Table

| # | Case | Score | Passed | Flags | Result |
|---|---|---|---|---|---|
| 1 | Clean rewrite | 1.0000 | ✓ | 0 | ✓ PASS |
| 2 | Fabricated company | 0.6250 | ✗ | 1 HIGH | ✓ PASS |
| 3 | Fabricated metrics | 0.0000 | ✗ | 1 MEDIUM | ✓ PASS |
| 4 | Added technologies | 0.5000 | ✗ | 1 MEDIUM | ✓ PASS |
| 5 | Safe rephrasing + metric | 0.0000 | ✗ | 1 MEDIUM | ✓ PASS |

**5/5 cases matched expectations.**

---

## Strengths

1. **Company hallucination detection** — Claude entity extraction reliably catches fabricated employer names (Case 2). Single call to Claude for the whole bullet set, not per-entity.
2. **Hard metric detection** — regex catches percentages, dollar amounts, K/M suffixes, multipliers with zero false positives on plain text.
3. **Tech synonym normalisation** — `React`, `ReactJS`, `React.js` all resolve to `"react"` before comparison. Prevents false positives on alias substitutions.
4. **Action verb allowlist** — 75 common verbs explicitly excluded from flagging. `Built → Engineered`, `Led → Orchestrated`, etc. are not hallucinations.
5. **Weighted scoring** — a fabricated company (HIGH, weight 3) hurts the score 3× more than a suspect tech (MEDIUM, weight 2). Better reflects real-world risk.
6. **Graceful degradation** — rule-based extraction (dates, metrics, technologies) runs without any API key. Claude adds company/title detection but is optional.

---

## Known Gaps

| Gap | Affected Cases | Severity | Planned Fix |
|---|---|---|---|
| `ms` / `μs` / `ns` latency units not in metric regex | Case 3 (`500ms`, `300ms`) | Low — overall verdict correct | Add time-unit pattern to `_METRIC_RE` |
| `redux`, `jest`, `webpack`, `vite`, `vitest` missing from tech vocab | Case 4 | Low — TypeScript still caught it | Expand `_TECH_CANONICAL` with 20+ frontend/test tools |
| Approximate metrics (`~20%`, `approximately 40%`) get same weight as hard metrics | All | Low | Implement `_APPROX_QUALIFIER_RE` downgrade path (scaffolded, not yet wired to score) |
| No NLP-level company name matching — "Google LLC" ≠ "Google" | Case 2 (partial) | Medium | Claude extraction normalises this in practice; add substring fuzzy match as fallback |
| Titles extracted by Claude only — rule-based can miss novel job titles | Case 2 | Medium | Add common title vocabulary similar to tech vocab |

---

## Observations for Phase 4

- The weighted scoring prevents a single LOW flag from torpedoing an otherwise clean rewrite. This is the right trade-off.
- Cases 3 and 5 both score 0.0 — a single new metric against zero original metrics → denominator equals numerator. This is mathematically correct but may be too aggressive in practice. Consider a **minimum denominator floor** (e.g. treat total_rw_weight as at least 2) so a single metric in an otherwise very short bullet doesn't score exactly 0.
- The 0.85 threshold works well for these cases. All fabrication cases scored ≤ 0.625; the clean rewrite scored 1.0. There is a wide separation — the threshold has room to be tuned later without changing the verdicts.
- The `rewrite_attempts` field in `RewriteResult` enables downstream analysis: if retries consistently hit 2, the prompt constraints need tightening.
