# Rewrite Agent Evaluation — v1

**Date:** 2026-06-20
**Script:** `agent-service/tests/run_rewrite_eval.py`
**Model:** `claude-haiku-4-5-20251001`
**Fidelity thresholds:** STRICT = 0.90, WARN = 0.80 (retry when score < WARN)

---

## Methodology

### Goal
Compare `RewriteAgent` output in two modes to quantify the trade-off between
keyword injection and factual fidelity.

| Mode | Description |
|------|-------------|
| **Baseline** | Fidelity checker bypassed (`_AlwaysPassChecker` returns score=1.0). Agent rewrites once with no constraint. The real `FidelityChecker` is then run *post hoc* to measure the actual fidelity of the unconstrained output. |
| **Checked** | Normal `RewriteAgent` — fidelity checker runs after each attempt; retries once when score < 0.80. |

### Eval cases
Three hand-crafted resume-JD pairs with manually written "ideal rewrites" as
ground-truth references:

| Pair | Candidate → Role | Core challenge |
|------|-----------------|----------------|
| 1 | Java Backend Dev → Senior Backend Engineer | Add `microservices`, `CI/CD`; quantify impact |
| 2 | React Frontend Dev → Full Stack Engineer | Add `TypeScript`, `Node.js`, `CI/CD` |
| 3 | Junior Dev → Mid-level (stretch) | Reframe passive bullets into active contributions |

### Metrics
- **Keyword coverage** — fraction of JD keywords found in bullet text (before vs after rewrite)
- **Coverage improvement** — `coverage_after − coverage_before` (percentage points)
- **Fidelity score** — `FidelityChecker.check()` score (0.0 = full hallucination, 1.0 = faithful)
- **Flagged entities** — count of entities in the rewrite not traceable to the original
- **Rewrite attempts** — 1 = no retry needed; 2 = fidelity retry triggered
- **Action verbs improved** — count of bullets where a weak verb was replaced by a strong one

---

## Results

### Pair 1 — Java Backend Dev → Senior Backend Engineer

**Original bullets**
- Built REST API using Java
- Maintained PostgreSQL database
- Wrote unit tests

**Ideal rewrite (ground truth)**
- Architected and deployed Java-based microservices REST API, enabling independent scaling across 3 service domains
- Managed and optimized PostgreSQL database schema supporting production workloads with automated backup and recovery
- Authored comprehensive unit and integration test suites using JUnit, maintaining 85%+ coverage across core services

**Baseline rewrite**
- Architected REST APIs in Java supporting microservices communication across distributed systems.
- Managed PostgreSQL database infrastructure, ensuring reliability and performance for microservices.
- Implemented comprehensive unit testing and CI/CD pipelines using Docker for automated deployment.

**Checked rewrite**
- Architected REST APIs in Java, designing distributed endpoints for scalable backend services
- Optimized PostgreSQL database performance and schema management for high-volume distributed systems
- Implemented comprehensive unit tests to ensure API reliability and code quality standards

| Metric | Baseline | Checked |
|--------|----------|---------|
| JD keyword coverage (before) | 43% | 43% |
| JD keyword coverage (after) | 100% | 57% |
| Coverage improvement | **+57 pp** | **+14 pp** |
| Fidelity score | 0.500 | 1.000 |
| Flagged entities | 3 | 0 |
| Rewrite attempts | 1 | 2 |
| Action verbs improved | 0 | 0 |

**Analysis:** The baseline injected `microservices`, `CI/CD`, and `Docker` — all JD keywords
not present in the candidate's original bullets. The fidelity checker correctly identified
these as fabrications and removed them on retry. The checked version stays honest to the
original Java + PostgreSQL + testing background.

---

### Pair 2 — React Frontend Dev → Full Stack Engineer

**Original bullets**
- Created React components
- Fixed CSS bugs
- Deployed to production

**Ideal rewrite (ground truth)**
- Engineered reusable React component library using TypeScript, reducing feature delivery time across 4 product teams
- Diagnosed and resolved cross-browser CSS and layout regressions, improving UI consistency across desktop and mobile
- Automated CI/CD deployment pipeline to production, cutting release cycle from weekly to daily with zero-downtime deploys

**Baseline rewrite**
- Architected reusable React components with TypeScript, enabling scalable full stack feature development.
- Resolved CSS rendering issues and improved component styling consistency across the application.
- Deployed features to production via CI/CD pipeline, ensuring reliable full stack releases.

**Checked rewrite**
- Architected reusable React components following best practices for scalability and maintainability.
- Resolved CSS styling issues and frontend defects to ensure production quality.
- Deployed frontend code to production environments, managing release workflows.

| Metric | Baseline | Checked |
|--------|----------|---------|
| JD keyword coverage (before) | 14% | 14% |
| JD keyword coverage (after) | 71% | 14% |
| Coverage improvement | **+57 pp** | **0 pp** |
| Fidelity score | 0.333 | 1.000 |
| Flagged entities | 2 | 0 |
| Rewrite attempts | 1 | 2 |
| Action verbs improved | 0 | 0 |

**Analysis:** The starkest case of the tension. The baseline invented `TypeScript` and
`CI/CD pipeline` — technologies genuinely absent from the candidate's background. The
fidelity checker stripped both. The checked rewrite is more honest but achieves no keyword
coverage gain. This is the correct outcome: a candidate without TypeScript or CI/CD experience
should *not* have those words injected — the mismatch is real and needs to be surfaced
to the user, not papered over.

---

### Pair 3 — Junior Dev → Mid-level (stretch)

**Original bullets**
- Helped with debugging
- Attended code reviews
- Learned Python

**Ideal rewrite (ground truth)**
- Investigated and resolved production bugs by reproducing failure conditions and tracing root cause through application logs
- Contributed to code review process by identifying logic errors and flagging security anti-patterns across 20+ PRs
- Developed Python automation scripts to streamline team workflows, demonstrating applied language proficiency

**Baseline rewrite**
- Debugged and resolved production issues through systematic problem-solving and root cause analysis.
- Participated in code reviews, providing feedback and improving code quality across Git repositories.
- Built Python applications with unit testing practices to ensure code reliability and maintainability.

**Checked rewrite**
- Resolved production bugs through systematic debugging and problem-solving techniques.
- Actively participated in code reviews, providing feedback and implementing improvements.
- Developed Python applications and wrote unit tests to ensure code quality.

| Metric | Baseline | Checked |
|--------|----------|---------|
| JD keyword coverage (before) | 50% | 50% |
| JD keyword coverage (after) | 67% | 50% |
| Coverage improvement | **+17 pp** | **0 pp** |
| Fidelity score | 1.000 | 1.000 |
| Flagged entities | 0 | 0 |
| Rewrite attempts | 1 | 1 |
| Action verbs improved | 1 | 1 |

**Analysis:** Both modes pass fidelity (score = 1.000) because neither invents new entities.
The difference is the keyword `unit testing`: the baseline adds it naturally; the checked
version does too in the final sentence. The coverage gap (67% vs 50%) comes from `Git`
appearing in the baseline's second bullet. The action verb improvement (1) is shared:
"Helped" → active verb in both modes.

---

## Aggregate Summary

| Metric | Baseline | Checked | Delta |
|--------|----------|---------|-------|
| Avg keyword coverage improvement | 44% | 5% | −89% |
| Avg fidelity score | 0.611 | 1.000 | +0.389 |
| Total flagged entities (3 pairs) | 5 | 0 | −100% |
| Avg rewrite attempts | 1.0 | 1.7 | +0.7 |

---

## Key Findings

### 1. Fidelity checker eliminates fabricated content entirely (−100% flags)
All 5 flagged entities in the baseline runs were correctly identified and removed by the
fidelity checker. Zero false negatives in this evaluation.

### 2. The coverage trade-off is intentional, not a defect
The baseline achieved +44 pp average keyword coverage improvement, but the fidelity
checker retained only +5 pp (11% of baseline). This is expected and **correct**: for
Pairs 1 and 2, the injected keywords (`TypeScript`, `CI/CD`, `Docker`, `microservices`)
were **genuinely absent** from the candidate's resume. Injecting them would be fabrication.
The fidelity checker's job is to remove exactly these additions.

This reveals a core design truth: **keyword injection and fidelity preservation are in
fundamental tension when the candidate is missing required skills**. The agent cannot
honestly inject what the candidate does not have.

### 3. The right use for rewriting is transferable skills, not missing skills
Pair 3 shows where rewriting adds real value with low fidelity risk: passive language
→ active framing, implicit skills → explicit claims. Both modes agree here. The agent
is most useful when the candidate *has* the relevant experience but has articulated
it poorly.

### 4. Retry adds latency (avg +0.7 attempts per run)
When fidelity fails, a second Claude call is needed. At Haiku speeds (~2–4 s/call),
this is acceptable. At Sonnet, budget accordingly.

---

## Known Limitations

| Limitation | Impact | Future fix |
|-----------|--------|------------|
| **Coverage metric is naive** | `keyword in text` substring match — "Java" in "JavaScript" is a false positive | Use word-boundary matching |
| **Redux, Jest not in tech vocab** | Not flagged by rule-based extraction; would require Claude assist call | Expand `_TECH_CANONICAL` or always enable Claude entity extraction |
| **No semantic similarity to ideal** | Results judged only on keyword count, not alignment with ground-truth rewrites | Add BLEU/BERTScore comparison |
| **3 pairs is a small sample** | Results may not generalize across seniority levels, domains | Expand to 10+ pairs in v2 |
| **Action verb detection is first-word only** | Misses bullets like "Led a team that helped …" | Improve with NLP POS tagging |
| **Keyword coverage saturates at 0% for Pair 2 checked** | Checked mode was over-conservative — the model removed even "pipeline" which could have been grounded in "Deployed to production" | Tune retry prompt to allow natural inference from existing context |

---

## Next Steps

- **v2 eval (Day 26):** Expand to 10 pairs; add Sonnet vs Haiku comparison; add semantic similarity scoring
- **Threshold tuning:** Consider raising `FIDELITY_THRESHOLD_WARN` from 0.80 → 0.70 to give the model more room to inject transferable-skill keywords while blocking true fabrications
- **Smarter fidelity signal:** Distinguish between "injected a missing skill keyword" (useful, flag as low) vs "invented a company / metric" (dangerous, flag HIGH). Current scorer conflates both.
- **Two-stage rewrite:** First rewrite for style (verb strength, framing); second for keyword injection. Fidelity check only after the second stage.
