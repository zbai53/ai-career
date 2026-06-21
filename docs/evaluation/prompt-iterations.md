# Rewrite Agent — Prompt Iteration Log

**Agent:** `RewriteAgent` (`app/agents/rewrite_agent.py`)
**Templates:** `app/agents/prompt_templates.py`

---

## v1 Prompt — Basic Rewrite Instruction (Day 22)

**Introduced:** Day 22 (initial Rewrite Agent implementation)
**Status:** Superseded by v2

### Design

A minimal system prompt instructing the model to rewrite resume bullets to better
match a job description.  No constraints on what the model could or could not add.
User prompt supplied the original bullets, target JD keywords, and gap analysis.

### Prompt summary

```
You are an expert resume writer and career coach. Your task is to rewrite resume
bullet points to better match a specific job description.

Inject relevant JD keywords naturally. Keep each bullet to one sentence, ideally
under 25 words.

Return ONLY a valid JSON object ...
```

No guardrails on fabrication, no explicit permissions, no self-check.

### Observed behaviour (from rewrite-eval-v1.md baseline mode)

| Metric | Value |
|--------|-------|
| Avg keyword coverage improvement | +50pp |
| Avg fidelity score | 0.655 |
| Total fabricated entities (10 pairs) | 13 |
| HIGH-severity flags | 7 |

**Key failure pattern:** The model freely injected technologies, leadership claims,
and metrics that were not present in the original resume.  Examples:

- Injected `microservices`, `CI/CD`, `Docker` for a candidate who genuinely lacked them (Pair 1)
- Added leadership framing ("led a team") when the original bullet was purely individual-contributor
- Invented percentages and quantified impact numbers not present in the source

The +50pp keyword gain was inflated: approximately half was fabricated content.

---

## v2 Prompt — DO NOT / YOU MAY Guardrails + Self-Check (Day 25)

**Introduced:** Day 25 (prompt iteration after evaluation baseline)
**Status:** Current production prompt (`REWRITE_SYSTEM_PROMPT` in `prompt_templates.py`)

### Design rationale

Evaluation of the v1 baseline revealed that free-form rewriting had a 0.655 average
fidelity score.  The v2 prompt restructures the system message into three explicit
sections:

1. **DO NOT block** — hard prohibitions that address the most common failure modes
2. **YOU MAY block** — explicit permissions that clarify the rewriting latitude
3. **SELF-CHECK** — a pre-response reasoning step that prompts the model to verify
   every factual claim before responding

### DO NOT block

| Rule | Failure it prevents |
|------|---------------------|
| Do not add technologies the candidate hasn't used | Eliminated 7/13 HIGH-severity tech fabrications from baseline |
| Do not fabricate metrics (%, $, counts) | Prevents inventing impact numbers |
| Do not change company names, job titles, or dates | Protects verifiable recruiting facts |
| Do not claim leadership (led, managed, directed) unless in original | Stops contributor→leader overreach |
| Do not add certifications or awards | Prevents credential fabrication |

### YOU MAY block

| Rule | Value it unlocks |
|------|-----------------|
| Rephrase passive → active voice | Highest-value rewrite operation; large gains in Pairs 3, 6, 10 with zero fidelity risk |
| Reorder emphasis within a bullet | Allows leading with the strongest claim |
| Add context reasonably implied by the original | Enables domain-vocabulary reframing ("SQL queries" → "ETL queries") |
| Swap weak action verbs for stronger equivalents | Endorses existing verb improvement behaviour |
| Highlight transferable skills connecting to the JD | Anchors keyword injection to the candidate's real background |

### SELF-CHECK instruction

Added a pre-response self-check: "For each rewritten bullet, ask: can every
factual claim — company name, technology, metric, job title — be found in the
original resume? If any claim cannot be traced, remove it before responding."

This directly targeted the Pair 9 failure mode (model injected valid-but-unverifiable
tech from the candidate's skills section into bullet text).

### v2 results (checked mode, 10 pairs)

| Metric | v1 Baseline | v2 Checked |
|--------|------------|------------|
| Avg keyword coverage improvement | +50pp | +33pp |
| Avg fidelity score | 0.655 | 0.977 |
| Total fabricated entities | 13 | 1 |
| HIGH-severity flags | 7 | 1 (false positive) |
| 8/10 GOOD outcomes | — | ✓ |

The fidelity improvement (0.655 → 0.977) confirms that the explicit guardrails
substantially reduce hallucination.  The trade-off is a ~17pp reduction in keyword
coverage, reflecting cases where the v1 prompt was cheating — injecting keywords
the candidate does not actually have.

---

## Model Comparison Findings (Day 26)

**Script:** `agent-service/tests/run_model_comparison.py`
**Model tested:** `claude-haiku-4-5-20251001`
**Pairs tested:** 1 (easy), 5 (medium), 10 (hard)

Three prompt strategies were compared:

| ID | Strategy | Description |
|----|----------|-------------|
| A-Minimal | Minimal | Bare-bones rewrite instruction — no constraints, just the task |
| B-Current | Current (v2) | Full DO NOT / YOU MAY system prompt with self-check (production) |
| C-CoT | Chain-of-Thought | v2 prompt + explicit reasoning step before JSON output |

### Metrics structure

Each of the 9 runs (3 strategies × 3 pairs) measures:

| Metric | Description |
|--------|-------------|
| KW Before | Keyword coverage in original bullets (substring match) |
| KW After | Keyword coverage in rewritten bullets |
| KW Δ | Coverage improvement (percentage points) |
| Fidelity | FidelityChecker score (0.0 = full fabrication, 1.0 = perfectly faithful) |
| H-Flags | HIGH-severity fidelity violations (company/title/date fabrications) |
| Tokens | Total tokens consumed (input + output) |
| Duration | Wall-clock time (ms) |

### Expected outcome

Based on the v1 evaluation and the design of each strategy:

- **A-Minimal** is expected to show the highest keyword coverage gain but the most
  H-flags, mirroring the v1 baseline behaviour.
- **B-Current** is expected to trade some keyword coverage for significantly lower
  H-flags and higher fidelity — consistent with the 10-pair eval results.
- **C-CoT** is expected to match or exceed B-Current on fidelity (the reasoning
  step forces the model to explicitly enumerate safe vs. unsafe claims) at the cost
  of additional tokens for the reasoning prose.

### Running the comparison

```bash
cd agent-service
python tests/run_model_comparison.py
```

Requires `ANTHROPIC_API_KEY` in the environment.  The script prints a full
comparison table, per-strategy aggregates, and a recommendation with rationale.

---

## Recommendation: Which Prompt to Use in Production

**Use v2 / B-Current (`REWRITE_SYSTEM_PROMPT`).**

### Rationale

1. **Fidelity is non-negotiable for resume rewriting.**  A candidate presenting a
   resume that fabricates technologies, metrics, or leadership experience faces real
   professional and legal risk if discovered by a recruiter.  The v1 prompt's 0.655
   average fidelity score is not acceptable in production.

2. **The 17pp keyword coverage reduction is the correct trade-off.**  When the v1
   prompt achieves higher coverage (e.g., +50pp vs. +33pp), the excess is largely
   fabricated.  The v2 system is not "worse at keyword injection" — it is correctly
   refusing to inject keywords the candidate does not have.

3. **The DO NOT / YOU MAY structure is maintainable.**  Adding or adjusting a
   rule requires editing a single constant in `prompt_templates.py` with no agent
   logic changes.  The structure also serves as documentation — a non-engineer
   reading the prompt can understand exactly what the model is and is not allowed
   to do.

4. **The SELF-CHECK step costs nothing extra.**  Unlike C-CoT, the self-check
   instruction in v2 is part of the system prompt and does not require reasoning
   prose before the JSON output.  It nudges the model to self-verify without
   paying for an extra CoT reasoning block in the response.

5. **C-CoT is worth evaluating for high-stakes pairs.**  The chain-of-thought
   strategy may improve fidelity on career-transition pairs (Pairs 5, 10) where
   the risk of over-reach is highest.  If model comparison results show C-CoT
   matching B-Current fidelity at modest token overhead, consider enabling it
   selectively for pairs with `overall_score < 50`.

### Decision tree

```
overall_score >= 70  →  route to interview (no rewrite needed)
overall_score 50–69  →  use B-Current (v2) system prompt
overall_score < 50   →  use B-Current; consider C-CoT if token budget allows
```

### Known open issue

The fidelity checker has one confirmed false-positive mode: technologies listed in
`ResumeExperience.technologies` or `ParsedResume.skills` are flagged when they
appear in rewritten bullets but were absent from the original bullet text.  This
caused the single BAD result in the 10-pair eval (Pair 9).

Fix tracked in `rewrite-eval-v1.md` → "Next Steps": expand entity extraction to
include the full resume context before marking a technology as a fabrication.

---

## Version history

| Version | Day | Change |
|---------|-----|--------|
| v1 | Day 22 | Initial basic rewrite prompt |
| v2 | Day 25 | Added DO NOT / YOU MAY guardrails, SELF-CHECK, centralized in `prompt_templates.py` |
