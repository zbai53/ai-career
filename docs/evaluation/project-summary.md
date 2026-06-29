# AI Career — Project Completion Summary

**Repository:** `ai-career` (monorepo)
**Status:** All 7 phases complete (Days 1–45)
**Completion date:** 2026-06-29

---

## Project Overview

AI Career is a full-stack, multi-agent job search assistant built over 45 days. It accepts a candidate's resume and a job description, then automates the highest-effort parts of job preparation: structured parsing, multi-dimensional match scoring, targeted resume rewriting with hallucination prevention, and a RAG-powered mock interview with STAR-based coaching feedback. The entire workflow is orchestrated by a LangGraph state machine with conditional routing, persisted via PostgreSQL, and exposed through a React frontend with live workflow visualization.

---

## Architecture

```
React Frontend (Vite + TypeScript + TailwindCSS)
  ├── 10 pages, 22 components
  ├── React Query + Zustand + React Flow + Recharts
  └── nginx in Docker (proxies /api/* to backend)
        │ HTTP REST / JSON
        ▼
Spring Boot Backend (Java 17, port 8080)
  ├── 20 REST endpoints across 8 controllers
  ├── MyBatis ORM → PostgreSQL (6 tables, JSONB for agent payloads)
  ├── Flyway migrations (V1–V4)
  └── AgentServiceClient → HTTP → Python Agent Service
        │
        ▼
Python Agent Service (FastAPI, port 8001)
  ├── 6 Agents (claude-haiku-4-5-20251001)
  ├── LangGraph state machine (conditional routing, retry, degraded mode)
  ├── PII masker (pre-LLM anonymization)
  ├── RAG: Qdrant vector store (sentence-transformers, 384-dim)
  └── In-memory interview session store
        │
        ▼
Infrastructure (Docker Compose)
  ├── PostgreSQL 16  :5432
  ├── Redis 7        :6379
  ├── Qdrant v1.9.4  :6333
  └── MinIO          :9000
```

---

## Phases Completed

| Phase | Days | Status | What was built |
|---|---|---|---|
| 0 — Environment Setup | 1–3 | ✓ Complete | Monorepo, Docker Compose, three services with `/health` endpoints |
| 1 — Resume + JD Agents | 4–9 | ✓ Complete | PDF/DOCX extraction, Claude structured parse, Pydantic validation, retry logic |
| 2 — Match Agent + DB | 10–15 | ✓ Complete | 6-dimension scoring, Flyway migrations, MyBatis mappers, agent_runs observability |
| 3 — LangGraph Orchestration | 16–21 | ✓ Complete | State machine, conditional routing, retry_node, degraded mode, checkpoint persistence |
| 4 — Rewrite + Fidelity | 22–27 | ✓ Complete | RewriteAgent, FidelityChecker (dual extraction, severity, retry), evaluation harness |
| 5 — Interview + Coach + RAG | 28–35 | ✓ Complete | Qdrant RAG, InterviewAgent (multi-turn), CoachAgent (STAR analysis), Spring Boot persistence |
| 6 — React Frontend | 36–41 | ✓ Complete | 10 pages, 22 components, React Flow viz, radar chart, chat UI, mobile layout |
| 7 — Polish + Deploy | 42–45 | ✓ Complete | PII masking, GDPR data deletion, Docker config, README, demo script, resume bullets |

---

## Final Stats

| Metric | Count |
|---|---|
| Python LOC (`agent-service/app/`) | **7,600** |
| Java LOC (`backend/src/`) | **3,264** |
| TypeScript/TSX LOC (`frontend/src/`) | **5,114** |
| **Total LOC** | **15,978** |
| Python tests (pytest) | **211** — all pass |
| Spring Boot tests (Maven) | **14** — all pass |
| **Total automated tests** | **225** |
| React components | **22** |
| React pages | **10** |
| REST endpoints (total) | **41** (21 agent-service + 20 Spring Boot) |
| Git commits | **92** |
| Development time | **45 days** at 2–3 hours/day |

---

## Key Technical Achievements

### Multi-Agent Orchestration with LangGraph

**File:** `agent-service/app/graph/workflow.py`

`JobHelperState` (TypedDict) carries all agent outputs through the graph. Conditional routing after `match`: score < 70 → `rewrite` → back to `match` (max 2 loops); score ≥ 70 → `interview` → `review`. `retry_node` wrapper auto-retries each node up to 2 times on failure with 1s backoff. `MemorySaver` checkpointing persists every state transition so workflows can resume from the last completed node.

### Fidelity Checking System (Anti-Hallucination)

**File:** `agent-service/app/agents/fidelity_checker.py`

Prevents the RewriteAgent from inventing new facts. Dual extraction: regex for dates, metrics, and numbers; Claude-assisted NER for company names, job titles, and technologies. Severity classification: HIGH (fake company/title/date), MEDIUM (unverified metric/technology), LOW (safe rephrasing). Thresholds: STRICT ≥ 0.90, WARN ≥ 0.80, FAILED < 0.80. On failure, the agent retries once with flagged entities listed explicitly in the prompt. `FidelityReport` is attached to every `RewriteResult`.

### RAG Pipeline with Qdrant

**Files:** `agent-service/app/rag/question_index.py`, `app/rag/ats_keywords.py`

Two Qdrant collections using `all-MiniLM-L6-v2` (384-dim): `interview_questions` (technical + behavioral with role/type/difficulty metadata) and `ats_keywords` (~125 keywords across 8 roles). The InterviewAgent uses semantic search at session start to select the most contextually relevant questions for each candidate's target role.

### Real-Time Workflow Visualization

**File:** `frontend/src/pages/WorkflowPage.tsx`

React Flow renders the LangGraph state machine as a live node graph. Agent nodes, routing edges (including the rewrite loop), and current execution state are all visible. The Mermaid visualization endpoint (`GET /api/workflow/visualize/html`) on the agent service renders the same graph server-side for embedding.

### GDPR/PIPEDA Compliance

**File:** `agent-service/app/utils/pii_masker.py`

Stateless mask/unmask pattern: `mask(text) → (masked_text, mapping)` before every LLM call, `unmask(response, mapping)` after. Masks full name, email, phone (NA formats), city/province/state. Mapping is passed through the retry path so text is never double-masked. `DELETE /api/users/me/data` in Spring Boot performs FK-safe cascading deletion across all 6 user-owned tables in a single `@Transactional` operation.

---

## What I Learned

- **Designing multi-agent systems with state machine orchestration** — LangGraph conditional branching, retry wrappers, degraded mode, and checkpoint persistence are fundamentally different from linear chains; the state machine model forces you to think about failure modes explicitly
- **Building a RAG pipeline from scratch** — embedding model selection (all-MiniLM-L6-v2 is fast and sufficient), Qdrant collection setup, metadata filtering, and the practical trade-off between vector similarity and exact-match filters
- **Java + Python microservice architecture** — HTTP orchestration between Spring Boot and FastAPI, handling shape mismatches between Pydantic models and Java entities, JSONB as a flexible storage layer for agent payloads
- **LLM output evaluation and hallucination prevention** — entity extraction + consistency checking is more reliable than prompt constraints alone; structured retry with specific flagged entities in the prompt is more effective than generic "be accurate" instructions
- **React real-time UI with SSE** — Zustand outside React (from axios interceptors), React Query graceful fallback hooks, React Flow for dynamic graph rendering, Recharts radar chart for multi-dimensional scoring

---

## What I'd Do Differently

- **Start with simpler rule-based matching before adding Claude** — the Python-only scoring (skill overlap, keyword coverage) turned out to be the most reliable part; Claude gap analysis is the most expensive and least deterministic. Validate the rule-based baseline first.
- **Use WebSockets instead of SSE for bidirectional communication** — SSE works for pushing progress updates, but the interview chat required a separate POST endpoint per turn. WebSockets would unify the transport and enable real-time streaming of partial Claude responses.
- **Add more comprehensive evaluation datasets** — 211 tests cover control flow and edge cases well, but there's no golden dataset of (resume, JD) → expected match score pairs. A 50-pair eval set with human-labeled scores would give a meaningful accuracy baseline.

---

## Interview Readiness

- Can explain every architectural decision (why LangGraph vs LangChain, why MyBatis vs JPA, why Haiku vs Sonnet, why Qdrant vs pgvector)
- Can demo the full flow in 3 minutes (see `docs/demo-script.md`)
- Can discuss trade-offs and alternatives for each major component
- Has prepared answers for the top 30 interview questions in `docs/build-coach/05-interview-prep.md`

---

## The Six Agents

| Agent | Input | Output | Claude used for |
|---|---|---|---|
| `ResumeAgent` | PDF / DOCX file | `ParsedResume` (Pydantic) | Full structured parse |
| `JDAgent` | Raw text or URL | `ParsedJobDescription` (Pydantic) | Full structured parse |
| `MatchAgent` | Resume + JD | `MatchResult` (scores + gap analysis) | Gap analysis only; scoring is pure Python |
| `RewriteAgent` + `FidelityChecker` | Resume + JD + match | `RewriteResult` + `FidelityReport` | Bullet rewriting; fidelity entity extraction |
| `InterviewAgent` | JD + resume + RAG questions | `InterviewSessionData` (multi-turn) | Answer evaluation + follow-up generation |
| `CoachAgent` | Completed session + JD + resume | `CoachReview` (readiness verdict) | STAR analysis + per-question feedback |

---

## Resume Bullets

See `docs/resume-bullets.md` for polished EN and CN versions ready to paste into a real resume.
