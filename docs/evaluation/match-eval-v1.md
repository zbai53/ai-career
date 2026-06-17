# Match Algorithm Evaluation — v1

**Date:** 2026-06-17  
**Model:** `claude-haiku-4-5-20251001`  
**Script:** `agent-service/tests/run_match_tuning.py`

---

## 1. Scoring Algorithm

### 1.1 Overall Score

```
overall_score = skill_score × 0.45
             + experience_score × 0.30
             + keyword_score × 0.25
```

All three component scores are on a 0–100 scale. Weights reflect the assumption
that technical skill alignment is the strongest hiring signal, followed by
experience depth, then keyword coverage.

---

### 1.2 Skill Score (0–100)

Computed in `_compute_skill_score()` using weighted matching.

**Match weights per JD skill:**

| Match type | Weight |
|---|---|
| Exact match after normalisation (incl. synonyms) | 1.0 |
| Whole-word token containment (partial / specialisation) | 0.5 |
| No relationship | 0.0 |

**Required skill contribution (max 70 pts):**
```
required_score = Σ best_weight(skill) / total_required × 70
```

**Preferred skill contribution (max 30 pts):**
```
preferred_score = Σ best_weight(skill) / total_preferred × 30
```

If a category has no skills at all, its full credit is awarded automatically
(e.g. no required skills → 70 pts free).

**Skill normalisation** (`normalize_skill()`):  
A 137-entry `SKILL_SYNONYMS` dict maps every known alias (lowercase) to a
canonical form before comparison. Examples:
- `"k8s"` → `"kubernetes"`
- `"js"`, `"es6"`, `"es2015"` → `"javascript"`
- `"postgres"`, `"pg"`, `"psql"` → `"postgresql"`
- `"springboot"`, `"spring framework"` → `"spring boot"`

**Partial matching** (`_word_contained()`):  
A word-boundary regex `(?<![a-z0-9])term(?![a-z0-9])` is used so that
`"React Native"` matches `"React"` (partial, 0.5) but `"Java"` does **not**
match `"JavaScript"` (no boundary). Minimum length of 3 chars required to avoid
spurious hits from short tokens like `"go"`.

---

### 1.3 Experience Score (0–100)

Computed as: `experience_score = min(100, years_score + relevance × 30)`

**Years score** (`_compute_experience_score_base()`):

| Gap = JD min − candidate years | Score |
|---|---|
| ≤ −2 (exceeds by 2+ years) | 70 |
| (−2, 0] (meets requirement) | 60 |
| (0, 1] (within 1 year short) | 45 |
| (1, 2] (1–2 years short) | 30 |
| > 2 (more than 2 years short) | 15 |
| No JD requirement specified | 60 (neutral) |

**Technology relevance** (`calculate_technology_relevance()`):  
Counts how many JD *required* skills appear in any experience entry's
`technologies` list (after normalisation). Returns a ratio 0.0–1.0.
Adds up to 30 bonus points. Returns 0.0 when there are no required skills
(no bonus applies).

**Overlap merging** (`calculate_years_of_experience()`):  
Converts all experience `start_date`/`end_date` fields (YYYY-MM) to date
intervals, substitutes today for `is_current=True` or null end dates, then
merges overlapping intervals before summing. This prevents counting overlapping
internships or consulting work twice.

---

### 1.4 Keyword Score (0–100)

Computed in `_compute_keyword_score()`.

```
keyword_score = matched_count / total_jd_keywords × 100
```

Case-insensitive substring search of each JD keyword in `resume.raw_text`.
Full score (100) when the JD has no keywords. Measures ATS keyword coverage
rather than semantic skill alignment.

---

### 1.5 Gap Analysis (Claude)

After all numeric scores are computed, a single Claude call (`_call_gap_analysis`)
generates:
- `missing_required_skills` / `missing_preferred_skills`
- `improvement_suggestions` (3–5 resume-rewrite actions)
- `interview_focus_areas` (3–5 study topics)
- `overall_assessment` (2–3 sentence narrative)

This is the only non-deterministic part of the pipeline. A retry with a strict
prompt handles bad JSON; a local fallback dict is returned if both attempts fail.

---

## 2. Candidate Profile (Test Fixture)

**Name:** Jordan Lee  
**Years of experience:** ~2 years (single role, 2024-06 → present)  
**Background:** Full-stack engineer, backend-leaning

**Skills (13):**
Java, Python, JavaScript, TypeScript, React, Spring Boot, PostgreSQL, SQL,
Docker, Git, REST API, CI/CD, HTML/CSS

**Experience technologies:**
Java, Spring Boot, PostgreSQL, React, JavaScript, TypeScript, REST API, Git, SQL, Docker

**Raw text keywords:**
Java, Python, JavaScript, TypeScript, React, Spring Boot, PostgreSQL, SQL,
Docker, Git, REST API, CI/CD, microservices, backend, development, HTML, CSS, agile, scrum

---

## 3. Test Pairs and Expected Scores

Numeric scores are **deterministic** (pure Python). The expected ranges below
are derived analytically from the algorithm. The `overall_assessment` text
varies per Claude run.

### Pair 1 — Backend Java Engineer (expected overall: 60–80)

**JD:** FinCo Backend Java Engineer, min 3 years  
**Required skills:** Java, Spring Boot, PostgreSQL, REST API, Kafka (5)  
**Preferred skills:** Docker, AWS, Kubernetes (3)

| Dimension | Expected score | Reasoning |
|---|---|---|
| Skill | ~66 | 4/5 required (Kafka missing) + 1/3 preferred (Docker) |
| Experience | ~69 | years_score=45 (gap=1yr), tech_rel=0.8 (4/5 req in exp) → 45+24 |
| Keyword | ~87 | 7/8 keywords in raw_text (Java, Spring Boot, Postgres, REST API, microservices, Docker, CI/CD) |
| **Overall** | **~72** | 66×0.45 + 69×0.30 + 87×0.25 |

**Key gap:** Kafka not on resume or in experience technologies.

---

### Pair 2 — Frontend React Engineer (expected overall: 50–70)

**JD:** UX Startup Frontend React Engineer, min 2 years  
**Required skills:** React, TypeScript, JavaScript, CSS, HTML (5)  
**Preferred skills:** Vue, Angular, GraphQL, Jest, Storybook (5)

| Dimension | Expected score | Reasoning |
|---|---|---|
| Skill | ~56 | React/TS/JS exact (3×1.0) + CSS/HTML partial from "HTML/CSS" (2×0.5) = 4/5 req; 0/5 pref |
| Experience | ~78 | years_score=60 (meets 2yr), tech_rel=0.6 (React/JS in exp, TypeScript too, but CSS/HTML not in exp techs) → 60+18 |
| Keyword | ~50 | React/TS/JS + "HTML"/"CSS" substring match in raw_text (5/10 keywords) |
| **Overall** | **~61** | 56×0.45 + 78×0.30 + 50×0.25 |

**Key gaps:** Pure CSS/HTML depth, no testing (Jest), no component library
experience (Vue, Angular, Storybook). Preferred skills score is 0/5.

---

### Pair 3 — Data Scientist (expected overall: 20–40)

**JD:** Analytics Inc Data Scientist, min 3 years  
**Required skills:** Python, Machine Learning, PyTorch, scikit-learn, Statistics (5)  
**Preferred skills:** SQL, AWS, Spark, Pandas, NLP (5)

| Dimension | Expected score | Reasoning |
|---|---|---|
| Skill | ~20 | Only Python (1/5 req) + SQL (1/5 pref) match |
| Experience | ~45 | years_score=45 (gap=1yr), tech_rel=0.0 — Python is a resume *skill* but not listed in experience `technologies`, so 0/5 req match → no bonus |
| Keyword | ~10 | Only Python in raw_text; no ML/stats keywords |
| **Overall** | **~25** | 20×0.45 + 45×0.30 + 10×0.25 |

**Key gaps:** Entire ML domain. Resume has Python but none of the specialised
stack (PyTorch, scikit-learn, Pandas, statistics). Experience score is
misleadingly moderate because Python appears in technologies.

---

### Pair 4 — DevOps Engineer (expected overall: 30–50)

**JD:** InfraOps DevOps Engineer, min 3 years  
**Required skills:** Docker, Kubernetes, Terraform, Linux, CI/CD (5)  
**Preferred skills:** AWS, Jenkins, Ansible, Helm, Prometheus (5)

| Dimension | Expected score | Reasoning |
|---|---|---|
| Skill | ~28 | Docker+CI/CD (2/5 req); 0/5 preferred |
| Experience | ~51 | years_score=45 (gap=1yr), tech_rel=0.2 (only Docker in exp) → 45+6 |
| Keyword | ~17 | Docker+CI/CD in raw_text (2/12 keywords) |
| **Overall** | **~32** | 28×0.45 + 51×0.30 + 17×0.25 |

**Key gaps:** Kubernetes, Terraform, Linux (ops-layer tools), cloud platforms,
and all monitoring/orchestration tooling. This is a domain mismatch rather than
a seniority gap.

---

### Pair 5 — Junior Full Stack Developer (expected overall: 70–90)

**JD:** GrowthApp Junior Full Stack, min 1 year  
**Required skills:** JavaScript, React, REST API, SQL (4)  
**Preferred skills:** TypeScript, Git, CSS, Node.js (4)

| Dimension | Expected score | Reasoning |
|---|---|---|
| Skill | ~89 | 4/4 required (70) + 2.5/4 preferred (TS, Git exact; CSS partial) = 89 |
| Experience | ~100 | years_score=60 (meets 1yr requirement), tech_rel=1.0 (all 4 req in exp) → min(100, 90) |
| Keyword | ~82 | JS/React/REST API/SQL/TypeScript/Git/CSS/HTML/agile in raw_text (9/11 keywords) |
| **Overall** | **~87** | 89×0.45 + 100×0.30 + 82×0.25 |

**Key gap:** Node.js (preferred) not on resume. The "junior" framing converts
the candidate's relative inexperience into a positive: they comfortably exceed
the 1-year bar.

---

## 4. Summary Table

| Pair | JD Title | Exp. Range | Skill | Exp | KW | Overall |
|---|---|---|---|---|---|---|
| 1 | Backend Java Engineer | 60–80 | ~66 | ~69 | ~87 | ~72 |
| 2 | Frontend React Engineer | 50–70 | ~56 | ~78 | ~50 | ~61 |
| 3 | Data Scientist | 20–40 | ~20 | ~45 | ~10 | ~25 |
| 4 | DevOps Engineer | 30–50 | ~28 | ~51 | ~17 | ~32 |
| 5 | Junior Full Stack | 70–90 | ~89 | ~100 | ~82 | ~87 |

---

## 5. Observations

### What works well

1. **Domain mismatch penalty is meaningful.** Pairs 3 and 4 score distinctly
   below pairs where the candidate actually works in the same domain. The gap
   isn't just experience-based; the skill and keyword dimensions together create
   a clear signal that these are wrong fits.

2. **Seniority sensitivity.** Pair 1 vs Pair 5 demonstrate the algorithm's
   ability to distinguish between a role the candidate is slightly under-qualified
   for (72) vs one where they are comfortably over-qualified (80). The 8-point
   spread comes primarily from the experience dimension and skill depth.

3. **Synonym matching prevents false negatives.** Without `SKILL_SYNONYMS`,
   "k8s" vs "Kubernetes", "postgres" vs "PostgreSQL", etc. would all score zero,
   grossly underestimating overlaps.

4. **Partial match (0.5 weight) handles specialisation correctly.** "HTML/CSS"
   on the resume correctly gives partial credit for both "CSS" and "HTML" as JD
   requirements, rather than counting as a complete miss.

### Known limitations and potential improvements

1. **Experience score is inflated for Pairs 3 and 4** (~51 each despite domain
   mismatch). The tech-relevance bonus adds 6 pts because Python/Docker appear in
   experience even though the candidate has no practical ML or ops experience.
   *Potential fix:* Weight technology relevance by relevance of the entire
   experience entry to the JD domain (could use Claude or an embedding similarity).

2. **Keyword score is a blunt instrument.** It is a pure substring match in
   `raw_text`, so it rewards candidates who list many tools in their raw text
   section without context. A keyword that appears once in a single line is
   indistinguishable from one the candidate has 5 years of experience with.
   *Potential fix:* Score keywords weighted by how many times they appear across
   different experience entries.

3. **No normalisation of keyword matching.** "machine learning" in a JD keyword
   list won't match "ML" or "ml" in raw_text since keyword matching is substring,
   not synonym-based. This creates an asymmetry with the skill score which *does*
   use synonyms.
   *Potential fix:* Apply `normalize_skill()` to both JD keywords and tokens
   extracted from raw_text before matching.

4. **Experience years are computed purely from dates, not depth.** Two candidates
   with identical years but wildly different role seniority (staff eng vs intern)
   receive the same years_score.
   *Potential fix:* Incorporate title seniority signals (junior/mid/senior/staff)
   extracted from the parsed resume.

5. **Claude gap analysis is the only narrative layer.** If the Claude call fails,
   the fallback returns no suggestions. The numeric scores are always available,
   but the user-facing text is fully dependent on LLM availability.
   *Potential fix:* Pre-generate suggestion templates from the missing-skill lists
   as a deterministic fallback.

6. **No semantic similarity.** Skills like "software engineering" and "backend
   development" that are semantically close score 0 against each other. A future
   version could use embedding-based similarity (via Qdrant, already in the
   stack) for a second-pass semantic re-rank.
