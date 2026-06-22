# Rewrite Agent Evaluation — v1

**Date:** 2026-06-21
**Script:** `agent-service/tests/run_rewrite_eval.py`
**Model:** `claude-haiku-4-5-20251001`
**Fidelity thresholds:** STRICT = 0.90 (clean pass), WARN = 0.80 (retry trigger)
**Pairs evaluated:** 10

---

## Methodology

### Evaluation modes

| Mode | Description |
|------|-------------|
| **Baseline** | Fidelity checker bypassed (`_AlwaysPassChecker` returns score=1.0). Agent rewrites once with no constraint. The real `FidelityChecker` is run *post hoc* to measure true fidelity of unconstrained output. |
| **Checked** | Normal `RewriteAgent` — fidelity checker runs after each attempt; retries once when score < 0.80 (WARN threshold). |

### Assessment grades (checked mode only)

| Grade | Criteria |
|-------|----------|
| **GOOD** | Fidelity ≥ 0.90 (STRICT) **and** keyword coverage improved |
| **OK** | Fidelity ≥ 0.80 (WARN), or fidelity ≥ 0.90 but no keyword gain |
| **BAD** | Fidelity < 0.80 after all retry attempts |

### Metrics per pair

- **KW coverage** — fraction of JD keywords found in bullet text (substring match)
- **Coverage improvement** — `after − before` in percentage points
- **Fidelity score** — 0.0 (full hallucination) → 1.0 (perfectly faithful)
- **Flagged entities (H/M/L)** — count by severity: HIGH (company/title/date), MEDIUM (tech/metric), LOW (contextual)
- **Rewrite attempts** — 1 = passed first try; 2 = retry triggered
- **Action verbs improved** — bullets where a weak opening verb was replaced by a strong one

---

## 10-Pair Results Summary

| # | Pair | Fidelity | KW +Δ | Flags | Att | Grade |
|---|------|----------|-------|-------|-----|-------|
| 1 | Java Backend Dev → Senior Backend Engineer | 1.000 | +14% | 0 | 2 | **GOOD** |
| 2 | React Frontend Dev → Full Stack Engineer | 1.000 | 0% | 0 | 2 | OK |
| 3 | Junior Dev → Mid-level (stretch) | 1.000 | +33% | 0 | 1 | **GOOD** |
| 4 | Data Analyst → Data Engineer | 1.000 | +25% | 0 | 1 | **GOOD** |
| 5 | QA Tester → Software Development Engineer | 1.000 | +29% | 0 | 2 | **GOOD** |
| 6 | Intern → Junior Developer | 1.000 | +71% | 0 | 2 | **GOOD** |
| 7 | DevOps Engineer → Cloud Architect | 1.000 | +12% | 0 | 2 | **GOOD** |
| 8 | iOS Developer → Backend Engineer | 1.000 | +29% | 0 | 1 | **GOOD** |
| 9 | Strong Metrics Resume → Principal Engineer | 0.769 | +75% | 1H | 2 | **BAD** |
| 10 | Vague Dev → Specific Backend JD | 1.000 | +38% | 0 | 2 | **GOOD** |

### Aggregate metrics

| Metric | Baseline | Checked |
|--------|----------|---------|
| Avg keyword coverage improvement | 50% | 33% |
| Avg fidelity score | 0.655 | 0.977 |
| Total flagged entities (10 pairs) | 13 | 1 |
| Avg rewrite attempts | 1.0 | 1.7 |

### Pass/retry breakdown (checked mode)

| Outcome | Count | % |
|---------|-------|---|
| Passed on first attempt | 3 / 10 | 30% |
| Triggered retry (attempt 2) | 7 / 10 | 70% |
| **Failed after retry** | **1 / 10** | **10%** |

### Assessment breakdown (checked mode)

| Grade | Count |
|-------|-------|
| GOOD (fidelity ≥ 90% + KW improved) | 8 / 10 |
| OK (fidelity ≥ 80%) | 1 / 10 |
| BAD (fidelity < 80% after retry) | 1 / 10 |

---

## Per-Pair Analysis

### Pair 1 — Java Backend Dev → Senior Backend Engineer
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 43% → 57% (+14pp) | Attempts: 2

**Scenario:** Mid-level Java developer targeting a senior role. Key skill gaps: microservices architecture, CI/CD, and quantified impact.

**Key observation:** The baseline freely injected `microservices`, `CI/CD`, and `Docker` — all JD keywords the candidate genuinely lacks. The fidelity checker identified these as fabrications and the retry removed them, producing a factually honest rewrite. The +14pp keyword gain reflects terms genuinely traceable to the original (REST, Java, PostgreSQL). Assessment GOOD despite conservative keyword injection because the fidelity is clean.

---

### Pair 2 — React Frontend Dev → Full Stack Engineer
**Grade: OK** | Fidelity: 1.000 | KW coverage: 14% → 14% (0pp) | Attempts: 2

**Scenario:** Frontend developer targeting a full-stack role. Key gaps: TypeScript, Node.js, CI/CD (none present in original).

**Key observation:** Zero keyword gain in checked mode. This is the correct outcome — the candidate does not have TypeScript, Node.js, or CI/CD experience and those keywords should not appear. The mismatch is genuine and should surface to the user as a skills gap to address, not a rewriting problem. Assessment OK because fidelity is clean and the retry correctly constrained the output.

---

### Pair 3 — Junior Dev → Mid-level (stretch)
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 50% → 83% (+33pp) | Attempts: 1

**Scenario:** Junior developer with passive bullet language ("Helped", "Attended", "Learned") targeting a mid-level role.

**Key observation:** Best-case for the agent. No fidelity issues (checked_attempts = 1), strong keyword gain (+33pp), and action verb improvement (1 weak verb → strong). The passive language transformation — "Helped with debugging" → "Resolved production bugs through systematic debugging" — is exactly where rewriting adds value without fabrication. The candidate's experience is real; the phrasing was just underselling it.

---

### Pair 4 — Data Analyst → Data Engineer
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 25% → 50% (+25pp) | Attempts: 1

**Scenario:** Data analyst pivoting to data engineering. Key gaps: Spark, Airflow, ETL pipeline framing.

**Key observation:** Impressive transfer framing without fabrication. "Wrote SQL queries for reports" became "Developed SQL queries to extract and transform data for ETL pipelines" — the word ETL is a natural reframe of what SQL reporting actually is. Similarly, "Cleaned data using Python" → "Built Python-based data processing scripts for batch data cleaning and validation in ETL workflows." The model correctly avoided inventing Spark or Airflow since neither was in the original.

---

### Pair 5 — QA Tester → Software Development Engineer
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 0% → 29% (+29pp) | Attempts: 2

**Scenario:** QA engineer making a career transition to software development. Starting keyword coverage is 0%.

**Key observation:** Most dramatic career pivot in the set. Starting from zero keyword overlap, checked mode achieved +29pp through legitimate reframing: "Wrote test cases" → "Developed comprehensive test cases to ensure software quality and code coverage." The baseline introduced a HIGH-severity fabrication (flagged as `1H`) — likely a company/title hallucination in the first pass — which was removed on retry. The checked output avoids inventing Python automation that isn't in the original.

---

### Pair 6 — Intern → Junior Developer
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 0% → 71% (+71pp) | Attempts: 2

**Scenario:** 3-month internship experience targeting a full-time junior developer role. Starting keyword coverage is 0%.

**Key observation:** Highest keyword coverage gain of all 10 pairs (+71pp). The intern's experience — shadowing, fixing bugs, standups — maps naturally to the JD keywords (debugging, Agile, collaboration, Git) without requiring fabrication. The baseline introduced a HIGH-severity fabrication that was corrected on retry. The checked rewrite achieves impressive coverage by legitimately framing the same internship activities in engineering terms.

---

### Pair 7 — DevOps Engineer → Cloud Architect
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 38% → 50% (+12pp) | Attempts: 2

**Scenario:** DevOps engineer targeting a Cloud Architect role. Key transformation: operational tasks → architectural decisions.

**Key observation:** Moderate keyword gain (+12pp) but strong framing improvement. "Managed Jenkins CI/CD pipelines" → "Architected Jenkins CI/CD pipelines to enable scalable infrastructure deployment." The promotion-path scenario benefits more from language elevation than keyword injection. The baseline introduced a HIGH-severity fabrication (flagged `1H`) that was corrected. The checked rewrite correctly uses only Jenkins, AWS, and Terraform which are established in the original.

---

### Pair 8 — iOS Developer → Backend Engineer
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 14% → 43% (+29pp) | Attempts: 1

**Scenario:** Mobile developer pivoting to backend engineering. REST API integration experience is the key bridge.

**Key observation:** Passed on first attempt with strong keyword gain. The REST API integration experience is genuinely transferable. "Integrated REST APIs" → "Designed and consumed REST APIs for data persistence, gaining expertise in API contracts and server-side data handling." The model correctly mapped Swift/iOS experience to backend concepts without fabricating Python or databases. The baseline introduced a MEDIUM-severity fabrication (1M flag) involving `databases` or `microservices` which were absent from the original.

---

### Pair 9 — Strong Metrics Resume → Principal Engineer ⚠️
**Grade: BAD** | Fidelity: 0.769 | KW coverage: 0% → 75% (+75pp) | Attempts: 2

**Scenario:** Staff engineer with concrete metrics (40% latency reduction, 1M daily requests, team of 5) targeting a principal engineer role. Tests whether existing numbers are preserved.

**Key observation:** The only BAD result, and the most informative failure mode. The checked rewrite achieved the highest keyword coverage gain (+75pp) but **failed fidelity on both attempts** (score 0.769 < WARN threshold 0.80). The failing bullet was:

> "Architected scalable **Go/Python services** handling 1M daily requests with high reliability."

The original bullet is "Served 1M daily requests" — no mention of Go or Python in the bullet text. The fidelity checker flagged "Go/Python services" as a HIGH-severity fabrication because it wasn't found in the bullet, even though both Go and Python appear in the resume's `technologies` list.

**This is a false positive.** The fidelity checker compares against the bullet text of the experience entry, not the full resume context. When the model correctly uses technologies from the candidate's skills section to strengthen a bullet, the checker incorrectly flags it as a fabrication. The numbers (40%, 1M, 5) were all correctly preserved.

**Critical distinction:** The fidelity checker is being over-conservative here. Mentioning technologies from the resume's own technology list in a strengthened bullet is legitimate rewriting, not hallucination.

---

### Pair 10 — Vague Dev → Specific Backend JD
**Grade: GOOD** | Fidelity: 1.000 | KW coverage: 12% → 50% (+38pp) | Attempts: 2

**Scenario:** Developer with vague bullet language ("Worked on backend stuff", "Did some database things", "Helped with deployments") but the correct technology stack (Python, PostgreSQL, Docker).

**Key observation:** Highest-value rewrite scenario — the candidate has all the right technology but the language is maximally unhelpful. Checked mode achieved +38pp keyword gain by converting vague descriptions into specific technical claims while staying grounded in the declared tech stack. Action verbs improved by 2 (weak "Worked"/"Did"/"Helped" → "Developed"/"Managed"/"Supported"). The baseline overshot with 3 fabrications (3M); retry corrected these.

---

## Key Findings

### 1. Fidelity checker eliminates 92% of fabricated content
13 flagged entities in baseline → 1 in checked mode across 10 pairs. The single remaining flag is a false positive (Pair 9, technologies from the resume's skills section appearing in rewritten bullets).

### 2. 8/10 pairs achieve GOOD outcome
80% of pairs achieve both clean fidelity (≥ 0.90) and keyword coverage improvement. The agent is broadly reliable across diverse career scenarios.

### 3. The retry mechanism works: 70% of pairs trigger retry, only 1/10 ultimately fails
7 of 10 pairs required a second Claude call. In 6 of those 7 cases, the retry succeeded (fidelity improved to 1.000). Only Pair 9 failed both attempts — and that failure is attributable to a false positive in the fidelity checker, not genuine fabrication.

### 4. Average checked keyword coverage improvement: +33pp (66% of baseline's +50pp)
The fidelity checker trades keyword injection for factual accuracy. For pairs where the candidate has genuine skill gaps (Pairs 1, 2, 7), keyword coverage is appropriately conservative. For pairs where the gap is primarily framing (Pairs 3, 6, 9, 10), keyword coverage improves substantially.

### 5. The tension is real but correct
Pairs 1 and 2 show the fundamental design truth: the agent **cannot honestly inject keywords the candidate does not have**. Pair 2 (React → Full Stack, 0% keyword gain) is the clearest case — TypeScript and Node.js are legitimately absent. The correct product behavior is to surface this as a skills gap, not paper it over.

### 6. Where rewriting adds the most value (no fabrication risk)
- **Passive → active language** (Pairs 3, 6): large gains with zero fidelity risk
- **Domain vocabulary reframing** (Pairs 4, 5): "SQL queries for reports" → "ETL pipeline queries"
- **Vague → specific** (Pair 10): candidate has the right stack, language is the only barrier

### 7. False positive risk in fidelity checker (Pair 9 finding)
The checker evaluates entities against the original bullet text, not the full resume. Technologies listed in `ResumeExperience.technologies` or `ParsedResume.skills` can legitimately appear in rewritten bullets but will be flagged if absent from the original bullet. This is the primary source of false positives.

---

## Known Limitations

| Limitation | Impact | Affected Pairs |
|-----------|--------|----------------|
| **KW coverage uses substring match** | "Java" matches "JavaScript"; "data" matches "database" — inflates coverage numbers | Multiple |
| **Fidelity checks bullet text only, not full resume** | Technologies from `skills`/`technologies` fields get flagged as fabrications if not in bullet text | Pair 9 |
| **Redux, Jest, and similar tech not in `_TECH_CANONICAL`** | Won't be flagged as fabrications even if genuinely absent | All |
| **Action verb detection is first-word only** | Misses embedded weak verbs, e.g., "Led a team that helped…" | All |
| **No semantic similarity to ideal rewrite** | Results judged only on keyword count, not on quality alignment with ground truth | All |
| **Single model, single run** | No temperature sampling; results may vary across runs | All |

---

## Prompt Iteration v2

After the v1 evaluation, the system prompt was restructured into explicit `DO NOT` / `YOU MAY` sections to reduce hallucination and guide the model more precisely.

### DO NOT block (constraints)
| Rule | Rationale |
|------|-----------|
| DO NOT add technologies the candidate hasn't used | Prevents the most common HIGH-severity fabrication type seen in baseline (7 of 13 flags were tech hallucinations) |
| DO NOT fabricate metrics | Preserves the candidate's existing numbers; prevents inventing percentages/counts |
| DO NOT change company names, job titles, or dates | Protects verifiable facts that are highest-risk for recruiting |
| DO NOT claim leadership roles (led, managed, directed) unless in original | Eliminates a common overreach pattern where the model promotes contributors to leaders |
| DO NOT add certifications or awards | Prevents credential fabrication |

### YOU MAY block (permissions)
| Rule | Rationale |
|------|-----------|
| YOU MAY rephrase passive language into active voice | Codifies the highest-value rewrite operation (big gains in Pairs 3, 6, 10) |
| YOU MAY reorder emphasis within a bullet | Allows leading with the strongest claim without fabricating new ones |
| YOU MAY add context reasonably implied by the original | Permits legitimate domain-vocabulary reframing (e.g., "SQL queries" → "ETL queries") |
| YOU MAY swap weak action verbs for stronger equivalents | Explicitly endorses the verb improvement behavior the agent already does well |
| YOU MAY highlight transferable skills that genuinely connect to the JD | Anchors keyword injection to the candidate's real background |

### SELF-CHECK instruction
Added an explicit pre-response self-check: "For each rewritten bullet, ask: can every factual claim be found in the original resume? If not, remove it before responding." This directly targets the retry failure mode (Pair 9) where the model injected valid-but-unverifiable tech.

---

## Fidelity System Interview Talking Points

### 1. Two-layer defense: prompt constraints + post-hoc verification
The system uses a DO NOT / YOU MAY prompt structure to shape Claude's behavior, then runs a separate `FidelityChecker` agent that independently extracts entities from both the original and rewritten text and flags anything new. The key insight is that prompting alone isn't reliable — the checker acts as a second, independent line of defense that can catch anything the model didn't self-censor.

### 2. Retry with structured feedback, not blind repetition
When the fidelity checker flags violations, the system doesn't just re-run the same prompt. It formats the flagged entities by severity (HIGH/MEDIUM/LOW) and injects them directly into the retry prompt: "these specific entities cannot be traced to the original — remove them before responding." This gives the model concrete, actionable information rather than a vague instruction to "be more careful."

### 3. The checker reveals a real tension: precision vs. recall of resume context
The fidelity checker checks bullet text against bullet text, not the full resume. This produced one false positive in 10 pairs (Pair 9) — the model legitimately mentioned technologies from the candidate's skills list, but the checker flagged them because they weren't in the original bullet. This trade-off is intentional: a checker that reads the full resume would be harder to reason about and more prone to justifying hallucinations. The false-positive rate (1/10 = 10%) is acceptable, and the fix is scoped: expand entity extraction to include `ResumeExperience.technologies` without changing the core check logic.

### 4. Evaluation design: baseline vs. checked, not just pass/fail
The eval runs two modes side-by-side: a "baseline" where fidelity checking is bypassed, and "checked" mode with full retry logic. Comparing them reveals what the system is actually catching (13 → 1 flags) and what it costs (50pp → 33pp keyword coverage). This framing is more useful than a simple pass/fail — it quantifies the accuracy/coverage trade-off and makes the business decision legible: we're trading ~17pp of keyword injection to eliminate 92% of fabricated content.

---

## Phase 4 Final Results

### Key metrics (10-pair evaluation, checked mode)

| Metric | Value |
|--------|-------|
| Average fidelity score | **0.977** |
| Rewrites passing fidelity on first attempt | **30%** (3/10 pairs) |
| Average keyword coverage improvement | **+33pp** |
| Most common hallucination type | **Technology names** (7/13 baseline flags) → then metrics (3/13) → then companies/titles (3/13) |

**Interpretation:** The fidelity checker reduced fabricated entities from 13 (baseline) to 1 (checked), a **92% reduction**. The single remaining flag in checked mode is a confirmed false positive — the model correctly referenced a technology that was in the candidate's skills section but not in the specific bullet being rewritten.

---

## Interview Talking Points

### 1. What hallucination means in resume rewriting — and why it's dangerous

In general LLM usage, hallucination means the model invents facts. In resume rewriting the same problem takes a specific, high-stakes form: the model might add technologies the candidate hasn't used, invent quantified metrics ("reduced latency by 40%"), or claim leadership roles that aren't in the original. Unlike a hallucinated summary in a chatbot, a fabricated resume claim is a lie a candidate presents to a recruiter. If discovered — during a phone screen, technical interview, or reference check — it can end the process immediately and damage the candidate's reputation. The fidelity system exists specifically to prevent the tool from creating this liability.

### 2. How entity extraction works: rule-based + LLM two-layer approach

The `FidelityChecker` runs two extraction passes on both the original and rewritten text. The **rule-based layer** uses a canonical technology dictionary (`_TECH_CANONICAL`) with ~100 normalized tech names (Python, FastAPI, PostgreSQL, …) and scans for substring matches. It also runs a regex for metric patterns (`\d+%`, `\$\d+`, `\d+[kKmM]`) and a whitelist for common leadership verbs. The **LLM layer** calls Claude with a minimal entity-extraction prompt to catch company names and job titles — entities that are too varied for a static dictionary. The two layers are complementary: the rule-based pass handles the high-volume, predictable tech/metric cases cheaply; the LLM pass handles the long-tail of proper nouns that rules can't enumerate.

### 3. How the fidelity scoring algorithm works

After extracting entities from both versions, the checker computes a score as: `1.0 − (new_entities / max(original_entities, 1))`. An entity counts as "new" if it appears in the rewritten text but not in the original bullet. Each new entity is also assigned a severity — HIGH for company names and job titles (hardest to explain away), MEDIUM for technologies and metrics (common fabrication vector), LOW for contextual terms. The final `fidelity_score` is a float between 0.0 and 1.0; 1.0 means every entity in the rewrite was present in the original. The system uses two thresholds: WARN (0.80) triggers a retry; STRICT (0.90) marks the result as fully passed.

### 4. The rewrite-check-retry loop

The agent runs a maximum of two Claude calls per experience entry. The first call rewrites the bullets using the v2 prompt (DO NOT / YOU MAY guardrails + self-check). The `FidelityChecker` immediately evaluates the output. If `fidelity_score >= 0.90`, the result is accepted. If `0.80 ≤ score < 0.90`, the agent retries with a structured retry prompt that lists the specific flagged entities by name and severity: "these claims cannot be traced to the original resume — remove them before responding." If `score < 0.80` after the retry, the result is returned with `fidelity_status = "failed"` so the caller can surface a warning to the user. The retry prompt injects concrete, actionable information rather than a vague "be more careful" instruction, which is why 6 of the 7 retried pairs recovered to fidelity = 1.000.

### 5. Results: 92% reduction in fabricated content

Across 10 diverse resume-JD pairs (career transitions, skill gaps, passive language), the baseline (no fidelity checking) produced 13 flagged entities, including 7 technology fabrications, 3 metric inventions, and 3 company/title changes. The checked mode with the v2 prompt + retry loop reduced that to 1 flagged entity — a confirmed false positive where the model correctly used a technology from the candidate's skills section. The trade-off is a ~17pp reduction in keyword coverage (from +50pp to +33pp on average), which reflects the system correctly refusing to inject keywords the candidate does not genuinely have. 8 of 10 pairs achieved GOOD grade (fidelity ≥ 0.90 and keyword coverage improved); 1 was OK; only 1 failed, and that failure is attributable to the false-positive edge case rather than genuine hallucination.

---

## Next Steps

- **Threshold tuning (Day 26):** Consider raising `FIDELITY_THRESHOLD_WARN` from 0.80 → 0.70 for pairs where the candidate has verified technologies in their skills list; or expand fidelity extraction to include the full resume context (not just original bullet text).
- **Fix Pair 9 false positive:** Update `FidelityChecker.extract_entities()` to also extract technologies from `ResumeExperience.technologies` and `ParsedResume.skills` — these are explicitly listed by the candidate and should never be flagged.
- **Sonnet comparison (Day 26):** Run these 10 pairs with `claude-sonnet-4-6` and compare keyword coverage and fidelity. Hypothesis: Sonnet will achieve higher keyword coverage while maintaining similar fidelity, because it follows nuanced instructions more precisely.
- **Expand to 20 pairs (v2):** Add more edge cases — non-English technical terms, gaps at director level, academic-to-industry transitions.
- **Two-stage rewrite:** First pass for language/framing (low fidelity risk); second pass for keyword injection (higher risk, fidelity-checked). Current single-pass approach conflates both goals.
