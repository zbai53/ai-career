# Match Algorithm Evaluation — v1

**Date:** 2026-06-17  
**Model:** `claude-haiku-4-5-20251001`  
**Script:** `agent-service/tests/run_match_tuning.py`  
**Candidate fixture:** Jordan Lee — full-stack engineer, ~2 years experience

---

## 1. Scoring Algorithm

### Overall formula

```
overall_score = skill_score × 0.45
             + experience_score × 0.30
             + keyword_score × 0.25
```

All three components are on a 0–100 scale.

---

### Skill score — 45% weight (0–100)

Computed purely in Python; no LLM involved.

**Match weights per JD skill:**

| Match type | Weight | Example |
|---|---|---|
| Exact match after normalisation | 1.0 | `"k8s"` vs `"Kubernetes"` |
| Whole-word token containment | 0.5 | `"React Native"` vs `"React"` |
| No relationship | 0.0 | `"Java"` vs `"JavaScript"` |

**Synonym dictionary** — 137-entry `SKILL_SYNONYMS` dict maps every known alias
(lowercased) to a canonical form before comparison:

```
"k8s" / "kubernetes"            → "kubernetes"
"js" / "es6" / "javascript"    → "javascript"
"postgres" / "pg" / "psql"     → "postgresql"
"springboot" / "spring framework" → "spring boot"
"tf"                            → "tensorflow"
"sklearn"                       → "scikit-learn"
```

**Partial matching** — a word-boundary regex `(?<![a-z0-9])term(?![a-z0-9])`
prevents `"java"` from matching inside `"javascript"` while correctly letting
`"react"` match inside `"react native"`. Minimum 3-character token length.

**Score composition:**

```
required_score  = Σ best_weight(skill) / count(required)  × 70
preferred_score = Σ best_weight(skill) / count(preferred) × 30
skill_score     = required_score + preferred_score
```

If a category has no skills, its full points are awarded (no penalty for
JDs that omit preferred or required lists entirely).

---

### Experience score — 30% weight (0–100)

Computed purely in Python; no LLM involved.

```
experience_score = min(100, years_score + technology_relevance × 30)
```

**Years score** (`_compute_experience_score_base`):

| gap = JD minimum − candidate years | Score |
|---|---|
| ≤ −2 — exceeds by 2+ years | 70 |
| (−2, 0] — meets requirement | 60 |
| (0, 1] — within 1 year short | 45 |
| (1, 2] — 1–2 years short | 30 |
| > 2 — more than 2 years short | 15 |
| No requirement specified | 60 (neutral) |

**Technology relevance bonus** (0–30 pts) — fraction of JD *required* skills
that appear in any experience entry's `technologies` list (after normalisation).
Returns 0 when there are no required skills.

**Overlap merging** — `calculate_years_of_experience()` converts YYYY-MM
start/end pairs to date intervals, substitutes today for current roles,
then merges overlapping intervals before summing, so concurrent jobs aren't
double-counted.

---

### Keyword score — 25% weight (0–100)

Computed purely in Python; no LLM involved.

```
keyword_score = matched_count / total_jd_keywords × 100
```

Case-insensitive substring search of each JD keyword in `resume.raw_text`.
Full score when the JD defines no keywords.

**Limitation:** this is a literal text-search, not synonym-aware. `"ML"` in
raw_text will not match a JD keyword of `"machine learning"`.

---

### Gap analysis — Claude only

After all numeric scores are computed, one Claude call generates:
`missing_required_skills`, `missing_preferred_skills`,
`improvement_suggestions`, `interview_focus_areas`, and `overall_assessment`.
A strict-prompt retry handles bad JSON; a local fallback dict is returned on
double failure. Token count from both calls is tracked in the agent_run log.

---

## 2. Candidate Fixture

**Name:** Jordan Lee  
**Total experience:** ~2.04 years (one current role, 2024-06 → present)  
**Skills (13):** Java, Python, JavaScript, TypeScript, React, Spring Boot,
PostgreSQL, SQL, Docker, Git, REST API, CI/CD, HTML/CSS  
**Experience technologies:** Java, Spring Boot, PostgreSQL, React, JavaScript,
TypeScript, REST API, Git, SQL, Docker  
**Raw text keywords:** Java Python JavaScript TypeScript React Spring Boot
PostgreSQL SQL Docker Git REST API CI/CD microservices backend development
HTML CSS agile scrum

---

## 3. Test Results

All five pairs were run on 2026-06-17. Numeric scores are deterministic
(pure Python); the `overall_assessment` excerpts are from the Claude call.

### Pair 1 — Backend Java Engineer (expected 60–80)

**JD:** FinCo Backend Java Engineer, min 3 years  
**Required:** Java, Spring Boot, PostgreSQL, REST API, Kafka  
**Preferred:** Docker, AWS, Kubernetes

| Dimension | Score | Notes |
|---|---|---|
| Skill | 66.0 | 4/5 required matched (Kafka missing); 1/3 preferred (Docker) |
| Experience | 69.0 | years_score=45 (gap=1yr), tech_rel=0.8 (4/5 req in exp techs) → 45+24 |
| Keyword | 87.5 | 7/8 keywords in raw_text; only "Kafka" absent |
| **Overall** | **72.3** | within expected 60–80 ✓ |

**Top missing required skills:** Kafka  
**Assessment:** *"Jordan is a solid mid-level backend candidate with strong fundamentals in Java, Spring Boot, Postgre…"*

---

### Pair 2 — Frontend React Engineer (expected 50–70)

**JD:** UX Startup Frontend React Engineer, min 2 years  
**Required:** React, TypeScript, JavaScript, CSS, HTML  
**Preferred:** Vue, Angular, GraphQL, Jest, Storybook

| Dimension | Score | Notes |
|---|---|---|
| Skill | 56.0 | React/TS/JS exact (3×1.0); CSS and HTML each 0.5 from "HTML/CSS"; 0/5 preferred |
| Experience | 78.0 | years_score=60 (meets 2yr), tech_rel=0.6 (React/JS/TS in exp; CSS/HTML absent) → 60+18 |
| Keyword | 50.0 | React/TS/JS + "HTML"/"CSS" substring hit (5/10); responsive, accessibility, Jest absent |
| **Overall** | **61.1** | within expected 50–70 ✓ |

**Top missing required skills:** none (all required have at least partial weight)  
**Assessment:** *"Jordan is a solid match with all required React, TypeScript, and JavaScript skills and 2+ years of r…"*

> **Note:** Claude rated this as "no missing required skills" because it considered
> the resume's HTML/CSS entry sufficient for both CSS and HTML. The numeric skill
> score (56) better reflects the partial nature of that match (0.5 weight each).

---

### Pair 3 — Data Scientist (expected 20–40)

**JD:** Analytics Inc Data Scientist, min 3 years  
**Required:** Python, Machine Learning, PyTorch, scikit-learn, Statistics  
**Preferred:** SQL, AWS, Spark, Pandas, NLP

| Dimension | Score | Notes |
|---|---|---|
| Skill | 20.0 | Only Python matched (1/5 req = 14pts) + SQL (1/5 pref = 6pts) |
| Experience | 45.0 | years_score=45 (gap=1yr), tech_rel=0.0 (Python in skills but not exp techs) → 45+0 |
| Keyword | 10.0 | Only "Python" in raw_text; no ML/stats vocabulary |
| **Overall** | **25.0** | within expected 20–40 ✓ |

**Top missing required skills:** Machine Learning, PyTorch, scikit-learn  
**Assessment:** *"Jordan is a junior full-stack engineer (~2 years) applying for a Data Scientist role requiring 3+ ye…"*

---

### Pair 4 — DevOps Engineer (expected 30–50)

**JD:** InfraOps DevOps Engineer, min 3 years  
**Required:** Docker, Kubernetes, Terraform, Linux, CI/CD  
**Preferred:** AWS, Jenkins, Ansible, Helm, Prometheus

| Dimension | Score | Notes |
|---|---|---|
| Skill | 28.0 | Docker + CI/CD matched (2/5 req = 28pts); 0/5 preferred |
| Experience | 51.0 | years_score=45 (gap=1yr), tech_rel=0.2 (Docker only in exp) → 45+6 |
| Keyword | 16.7 | Only "Docker" and "CI/CD" in raw_text (2/12) |
| **Overall** | **32.1** | within expected 30–50 ✓ |

**Top missing required skills:** Kubernetes, Terraform, Linux  
**Assessment:** *"Jordan is a junior full-stack engineer with relevant containerization and CI/CD exposure, but signif…"*

---

### Pair 5 — Junior Full Stack Developer (expected 70–90)

**JD:** GrowthApp Junior Full Stack, min 1 year  
**Required:** JavaScript, React, REST API, SQL  
**Preferred:** TypeScript, Git, CSS, Node.js

| Dimension | Score | Notes |
|---|---|---|
| Skill | 88.8 | 4/4 required (70pts) + TypeScript/Git exact + CSS partial from HTML/CSS (2.5/4 pref × 30 = 18.75) |
| Experience | 90.0 | years_score=60 (meets 1yr), tech_rel=1.0 (all 4 req in exp techs) → min(100, 60+30) |
| Keyword | 81.8 | JS/React/REST API/SQL/TS/Git/CSS/HTML/agile in raw_text (9/11) |
| **Overall** | **87.4** | within expected 70–90 ✓ |

**Top missing required skills:** none  
**Assessment:** *"Jordan is an exceptionally strong match for this Junior Full Stack Developer role, with all required…"*

---

## 4. Summary Table

| Pair | Expected | Skill | Exp | KW | Overall | In range? |
|---|---|---|---|---|---|---|
| 1 — Backend Java Engineer | 60–80 | 66.0 | 69.0 | 87.5 | **72.3** | ✓ |
| 2 — Frontend React Engineer | 50–70 | 56.0 | 78.0 | 50.0 | **61.1** | ✓ |
| 3 — Data Scientist | 20–40 | 20.0 | 45.0 | 10.0 | **25.0** | ✓ |
| 4 — DevOps Engineer | 30–50 | 28.0 | 51.0 | 16.7 | **32.1** | ✓ |
| 5 — Junior Full Stack | 70–90 | 88.8 | 90.0 | 81.8 | **87.4** | ✓ |

All five pairs landed within their expected ranges on the first real run.

---

## 5. Observations

### What feels right

**Domain mismatch penalty is clear.** Pairs 3 and 4 score 25 and 32 respectively
against a candidate who has no ML or infrastructure background. The 40+ point gap
from pair 1 (72) and pair 5 (87) reflects a genuine domain difference, not just
a seniority gap.

**Seniority is correctly differentiated.** Pair 1 (72) vs Pair 5 (87) differ
primarily in the experience dimension and preferred-skill coverage. The candidate
is moderately under-qualified for the senior role and comfortably over-qualified
for the junior one — both of which the scores reflect.

**Synonym matching prevents obvious false negatives.** Without the synonym dict,
`k8s` vs `Kubernetes`, `postgres` vs `PostgreSQL`, and `js` vs `JavaScript`
would all score 0. The 137-entry dict eliminates the most common alias gaps.

**The Java/JavaScript boundary holds.** The word-boundary regex correctly gives
`"Java"` zero weight against `"JavaScript"` even though `"java"` is a substring.
This was a known bug before the regex fix.

### What feels off

**Pair 2 experience score (78) is too generous for a frontend role.**
The candidate's ~2 years meet the 2-year minimum (years_score = 60), and React,
JavaScript, and TypeScript appear in the experience technologies list (+18 tech
bonus). But the work is backend-oriented; the candidate has never shipped a
frontend-focused product. The algorithm has no concept of role-type alignment
within the experience dimension.

**Pair 3 experience score (45) is misleadingly moderate for a data science role.**
Python is on the resume skills list but not in the experience technologies list,
so technology relevance correctly returns 0. However, the years_score alone (45)
suggests a mild experience shortfall when the real issue is a complete domain
mismatch. A score around 15–20 would feel more accurate.

**Pair 4 experience score (51) is also inflated.** Docker appears in the
experience technologies (contributing +6 relevance bonus), but the candidate's
DevOps exposure is incidental — Docker was used for local development, not
infrastructure management. A single tool match in experience tech shouldn't
produce the same tech-relevance score as genuine ops work.

**Keyword matching asymmetry with skill matching.** The skill score uses
synonym normalisation (`"k8s"` → `"kubernetes"`) but the keyword score is a
raw substring search. If a JD keyword is `"machine learning"` and the resume
only writes `"ML"`, the keyword score takes the miss even though the skill
score with synonyms would catch it. This creates an inconsistency.

---

## 6. Known Limitations

| Limitation | Impact | Potential fix |
|---|---|---|
| Keyword matching is literal text search | `"ML"` won't match `"machine learning"` in keywords | Apply `normalize_skill()` to keyword matching too, or use token-level synonym expansion |
| No semantic skill similarity | `"backend development"` and `"server-side engineering"` score 0 against each other | Embedding-based similarity via Qdrant (already in the stack) |
| Experience depth not captured | 2 years as a staff engineer vs 2 years in a bootcamp project score identically | Extract seniority signals (title, team size, scope) from parsed experience |
| Technology relevance is binary | One Docker mention gives the same +6 pts whether Docker is incidental or central | Weight by how many distinct experience entries mention the technology |
| No role-type alignment in experience | A frontend JD matched to a backend resume gets a high experience score if total years meet the bar | Add JD role-type classification and penalise cross-domain experience |
| Claude gap analysis is the only narrative layer | On LLM failure, improvement suggestions are empty | Pre-generate template suggestions from missing-skill lists as deterministic fallback |
