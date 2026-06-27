# AI Career — Multi-Agent Job Search Assistant
## Project Summary

**Repository:** `ai-career` (monorepo)
**Status:** Phases 0–7 complete (through Day 43)
**Date:** 2026-06-26

---

## What It Does

An end-to-end job search assistant that takes a candidate's resume and a job description, then:

1. Parses both into structured JSON using LLM-backed agents
2. Scores the match across six dimensions (skills, experience, ATS keywords, seniority, education, culture fit)
3. Rewrites resume bullets to better fit the JD — with a fidelity guardrail to prevent hallucination
4. Runs a RAG-powered multi-turn mock interview
5. Produces a structured coaching review with readiness verdict and per-question feedback

---

## Architecture

```
React Frontend (Vite + TypeScript + TailwindCSS)
  ├── 10 pages, 22 components
  ├── React Query (data fetching) + Zustand (workflow state, toasts)
  ├── React Flow (workflow visualization) + Recharts (radar chart)
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
  ├── 6 Agents (each backed by claude-haiku-4-5-20251001)
  ├── LangGraph state machine (conditional routing, retry, degraded mode)
  ├── PII masker (pre-LLM anonymization: name, email, phone, address)
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

## The Six Agents

| Agent | Model | Input | Output | Claude used for |
|---|---|---|---|---|
| `ResumeAgent` | claude-haiku-4-5 | PDF / DOCX file | `ParsedResume` (Pydantic) | Full structured parse |
| `JDAgent` | claude-haiku-4-5 | Raw text or URL | `ParsedJobDescription` (Pydantic) | Full structured parse |
| `MatchAgent` | claude-haiku-4-5 | Resume + JD | `MatchResult` (scores + gap analysis) | Gap analysis only; scoring is pure Python |
| `RewriteAgent` + `FidelityChecker` | claude-haiku-4-5 | Resume + JD + match result | `RewriteResult` + `FidelityReport` | Bullet rewriting; fidelity entity extraction |
| `InterviewAgent` | claude-haiku-4-5 | JD + resume + RAG questions | `InterviewSessionData` (multi-turn) | Answer evaluation + follow-up generation |
| `CoachAgent` | claude-haiku-4-5 | Completed session + JD + resume | `CoachReview` (readiness verdict) | STAR analysis + per-question feedback |

---

## Codebase Metrics

Numbers from `wc -l` as of 2026-06-26:

| Layer | Files counted | Lines of code |
|---|---|---|
| Python (agent-service/app/**/*.py) | 22 source files | **7,600** |
| Java (backend/src/**/*.java) | — | **3,231** |
| TypeScript/TSX (frontend/src/**/*.{ts,tsx}) | — | **5,109** |
| **Total** | | **15,940** |

**Frontend breakdown:**
- React components (`frontend/src/components/`): **22**
- React pages (`frontend/src/pages/`): **10**

**Largest Python files:** `workflow.py` (989 lines), `main.py` (890), `match_agent.py` (701)

---

## Test Coverage

**Total: 225 automated tests**

| Suite | Tests | Result | Scope |
|---|---|---|---|
| Python — pytest | **211** | ✓ PASS (~47s) | All 6 agents, RAG, LangGraph workflow, fidelity checker, full pipeline |
| Spring Boot — Maven | **14** | ✓ PASS | Controller + mapper integration tests |

All 225 tests pass. Python tests run in ~47s without external network calls (Claude API fully mocked via `unittest.mock.patch`). Spring Boot tests use an in-memory H2 database.

Notable test classes:
- `TestMultiTurnLogic` (7 tests) — follow-up cap, re-answer routing, conversation history integrity
- `TestFidelityCheckFlagsHallucination` — entity injection detection
- `TestWorkflowIntegration` — full LangGraph graph execution with mocked agents
- `TestMatchAgent::test_ats_keywords_included_in_result` — ATS coverage in match output

---

## API Surface

**Total: 41 endpoints across 2 services**

**Agent Service (port 8001) — 21 endpoints**

| Group | Endpoints |
|---|---|
| Health | `GET /health`, `GET /health/llm` |
| Resume / JD | `POST /api/resume/parse`, `POST /api/jd/parse` |
| Match / Rewrite | `POST /api/match`, `POST /api/rewrite` |
| Pipeline / Workflow | `POST /api/pipeline/run`, `POST /api/workflow/run`, `GET /api/workflow/status/{id}`, `GET /api/workflow/visualize`, `GET /api/workflow/visualize/html` |
| RAG | `POST /api/rag/index`, `POST /api/rag/search` |
| Interview | `POST /api/interview/start`, `POST /api/interview/{id}/answer`, `GET /api/interview/{id}`, `POST /api/interview/{id}/end`, `POST /api/interview/{id}/end-with-review` |
| Coach | `POST /api/coach/review` |
| Agent Runs | `POST /api/agent-runs` |

**Spring Boot (port 8080) — 20 endpoints**

| Group | Endpoints |
|---|---|
| Health | `GET /health`, `GET /health/agent` |
| Resume / JD | `POST /api/resumes/parse`, `GET /api/resumes/{id}`, `POST /api/jds/parse`, `GET /api/jds/{id}` |
| Match / Rewrite | `POST /api/match`, `GET /api/match/{id}`, `POST /api/rewrite`, `GET /api/rewrite/{id}` |
| Workflow | `POST /api/workflow/run`, `POST /api/workflow/full`, `GET /api/workflow/full/{id}`, `GET /api/workflow/status/{id}` |
| Interview | `POST /api/interviews/start`, `POST /api/interviews/{id}/answer`, `GET /api/interviews/{id}`, `POST /api/interviews/{id}/end` |
| Agent Runs | `GET /api/agent-runs/recent` |
| User Data | `DELETE /api/users/me/data` |

---

## Database Schema

**6 tables** managed by Flyway migrations (V1–V4):

| Table | Purpose | Key columns |
|---|---|---|
| `users` | User accounts (reserved for auth) | `id`, `email`, `created_at` |
| `resumes` | Parsed resume records | `id`, `user_id`, `file_path`, `parsed_data` (JSONB) |
| `job_descriptions` | Parsed JD records | `id`, `user_id`, `title`, `parsed_data` (JSONB) |
| `match_results` | Match scores + gap analysis | `id`, `resume_id`, `jd_id`, `overall_score`, `gap_analysis` (JSONB) |
| `rewrite_results` | Rewrite output + fidelity | `id`, `resume_id`, `jd_id`, `user_id`, `rewrite_data` (JSONB), `fidelity_status` |
| `interview_sessions` | Interview state + history | `id`, `session_id` (UUID), `conversation` (JSONB), `review` (JSONB), `status` |
| `agent_runs` | Observability log | `id`, `agent_name`, `duration_ms`, `token_count`, `status`, `model_name` |

JSONB columns store the full Pydantic model dumps from the agent service.

---

## Key Technical Achievements

### 1. LangGraph State Machine

**File:** `agent-service/app/graph/workflow.py`

- `JobHelperState` (TypedDict) carries all agent outputs through the graph
- Conditional routing after `match`: score < 70 → `rewrite` → back to `match` (max 2 loops); score ≥ 70 → `interview` → `review`
- `retry_node` wrapper: auto-retries each node up to 2 times on failure with 1s backoff
- Degraded mode: if Claude gap analysis fails, `match_node` falls back to Python-only scores rather than failing the whole workflow
- `MemorySaver` checkpointing: every state transition is persisted; workflows can resume from the last completed node
- Mermaid visualization endpoint (`GET /api/workflow/visualize/html`) renders the live graph in-browser

### 2. Fidelity Checking System

**File:** `agent-service/app/agents/fidelity_checker.py`

Prevents the RewriteAgent from hallucinating new facts into the resume:

- **Dual extraction:** regex patterns for dates, metrics, numbers + Claude-assisted extraction for company names, job titles, technologies
- **Severity classification:** HIGH (fake company/title/date), MEDIUM (unverified metric/technology), LOW (safe rephrasing)
- **Thresholds:** STRICT (≥ 0.90 to pass), WARN (≥ 0.80), FAILED (< 0.80)
- **Retry loop:** if `fidelity_score < 0.80`, the agent retries once with flagged entities listed explicitly in the prompt
- **Result:** `FidelityReport` with per-flag severity, attached to every `RewriteResult`

### 3. PII Masking Pipeline

**File:** `agent-service/app/utils/pii_masker.py`

Pre-LLM anonymization that satisfies GDPR / PIPEDA right-to-erasure requirements:

- Detects and replaces: full name (first-line heuristic), email, phone (NA formats), city/province/state
- Substitution is stateless per-call: `mask(text) → (masked_text, mapping)` then `unmask(response, mapping)` after Claude
- Both `ResumeAgent` and `RewriteAgent` use the masker; mapping is passed to the retry path so text is not double-masked
- `DELETE /api/users/me/data` (Spring Boot) triggers FK-safe deletion across all 6 user-owned tables in a single transaction

### 4. RAG Pipeline

**Files:** `agent-service/app/rag/question_index.py`, `app/rag/ats_keywords.py`

Two Qdrant collections, both using `all-MiniLM-L6-v2` (384-dim):

| Collection | Contents | Size |
|---|---|---|
| `interview_questions` | Technical + behavioral questions with role/type/difficulty metadata | 20 questions (expandable) |
| `ats_keywords` | Industry-standard ATS keywords per role | ~125 keywords across 3 industries, 8 roles |

### 5. Multi-Turn Mock Interviews

**File:** `agent-service/app/agents/interview_agent.py`

`process_turn()` runs a three-step pipeline per answer:

1. `evaluate_answer()` → Claude scores relevance, depth, communication (each 1–10)
2. `_decide_next_action()` → priority rules: `re_answer` (relevance < 5) > `follow_up` (depth < 5, cap ≤ 2) > `next_question` (overall ≥ 7)
3. `respond()` → Claude generates the follow-up probe, re-prompt, or next question

### 6. React Frontend

**Directory:** `frontend/src/`

22 components + 10 pages built from scratch with Tailwind CSS:

- React Flow for live LangGraph workflow visualization
- Recharts radar chart (6-dimension match scoring)
- Zustand toast store called from axios interceptors (global error handling outside React)
- React Query with graceful fallback hooks (silent 404 handling for optional endpoints)
- ErrorBoundary + Suspense with LoadingPage fallback for lazy-loaded routes
- Mobile-responsive layout: fixed bottom tab bar on small screens, sidebar on desktop

---

## Phases Completed

| Phase | Days | Status | What was built |
|---|---|---|---|
| 0 — Environment Setup | 1–3 | ✓ Complete | Monorepo, Docker Compose, three services with `/health` endpoints, Anthropic API verified |
| 1 — Resume + JD Agents | 4–9 | ✓ Complete | PDF/DOCX extraction, Claude structured parse, Pydantic validation, retry logic, unit tests |
| 2 — Match Agent + DB | 10–15 | ✓ Complete | 6-dimension scoring, skill synonyms, Flyway migrations, MyBatis mappers, agent_runs observability |
| 3 — LangGraph Orchestration | 16–21 | ✓ Complete | State machine, conditional routing, retry_node, degraded mode, checkpointing, Mermaid visualization |
| 4 — Rewrite + Fidelity | 22–27 | ✓ Complete | RewriteAgent, FidelityChecker (dual extraction, severity, retry), evaluation harness, prompt versioning |
| 5 — Interview + Coach + RAG | 28–35 | ✓ Complete | Qdrant RAG, InterviewAgent (multi-turn), CoachAgent (STAR analysis), ATS keyword library, Spring Boot interview persistence |
| 6 — React Frontend | 36–41 | ✓ Complete | 10 pages, 22 components, React Flow viz, radar chart, chat UI, mobile layout, error boundaries, real data hooks |
| 7 — Polish + Deploy | 42–45 | ✓ Complete (Day 43) | PII masking, GDPR data deletion endpoint, Dockerfiles, docker-compose update, README, deployment guide, demo script |

---

## What I Learned

### Technical skills gained

**LLM engineering**
- Structured output extraction: prompting Claude to return validated Pydantic models reliably, with retry on parse failure
- Hallucination mitigation: entity extraction + consistency checking is more reliable than prompt constraints alone
- Token economics: Haiku vs Sonnet trade-offs — Haiku handles structured extraction well; Sonnet was unnecessary for this use case
- PII handling: stateless mask/unmask pattern that survives retry loops without double-masking

**Python / agent architecture**
- LangGraph state machines: conditional branching, retry wrappers, checkpoint persistence — materially different from linear LangChain
- Pydantic for validation: using models as the contract between the LLM output and downstream code caught many subtle schema drift bugs
- RAG fundamentals: embedding choice (all-MiniLM-L6-v2 is fast and sufficient for 20-question retrieval), Qdrant collection setup, metadata filtering
- FastAPI dependency injection and background tasks

**Java / Spring Boot**
- MyBatis as an alternative to JPA: more control over SQL, better fit for JSONB columns
- Flyway migrations: baseline-on-migrate, V-versioning, handling schema evolution without downtime
- Spring Security stateless config for REST APIs
- `@Transactional` for FK-safe multi-table deletion

**React / Frontend**
- React Query stale-while-revalidate: `staleTime`, `retry`, and internal `try/catch` for silent fallback hooks
- Zustand outside React: calling store methods from axios interceptors without hook restrictions
- React Flow: mapping a LangGraph graph schema to nodes + edges dynamically
- Tailwind responsive design: mobile-first with bottom tab bar + sidebar layout swap

**DevOps / infrastructure**
- Multi-stage Docker builds (separate builder and runtime images — cuts image size significantly)
- nginx as an SPA server + reverse proxy in a single container
- docker-compose service dependencies and env_file patterns

---

## What I'd Do Differently

**1. Start the frontend earlier**

I treated the frontend as Phase 6 after 5 phases of backend/agent work. In practice, having a UI to test against from Phase 3 onward would have caught UX issues and API shape mismatches much earlier. Build the thinnest possible UI slice alongside each backend feature.

**2. Design the API contract before coding agents**

I wrote agents first, then designed Spring Boot controllers around whatever the agents returned. This led to several shape mismatches (e.g., `rewriteData: string` vs. direct JSON object) that required fixes after the fact. An OpenAPI spec written first would have prevented this.

**3. Use a real vector DB from day one**

I initially planned to defer Qdrant and use in-memory lists. Adding it in Phase 5 required retrofitting the RAG search into the InterviewAgent. Having Qdrant in docker-compose from Phase 0 would have made this seamless.

**4. Add streaming responses**

The rewrite endpoint can take 30–60 seconds with no progress feedback. Server-Sent Events (SSE) streaming the rewrite as each bullet completes would dramatically improve perceived performance. I planned this but deferred it.

**5. Real authentication from the start**

Every controller has `private static final long HARDCODED_USER_ID = 1L;`. Adding JWT/OAuth2 after the fact means touching every controller. A minimal auth stub (JWT filter + user context) from Phase 0 would have made the compliance work (PII masking, data deletion) cleaner to reason about.

**6. Persist agent state in Redis, not in-memory**

Interview sessions are stored in a Python in-process dict. This means a restart loses all active sessions. Redis with TTL-based eviction would give the same performance with durability. I deprioritized this because demo sessions are short-lived, but it's the obvious next step for a real deployment.

---

## Resume Bullet Points

**EN (Canadian market):**
1. Designed and implemented a multi-agent job-search assistant with 6 specialized agents (Resume, JD, Matching, Rewriter, Interviewer, Coach), orchestrated via LangGraph state machine with conditional routing, retry logic, and checkpoint persistence
2. Built resume fidelity evaluation system using dual entity extraction (regex + LLM) with severity classification (HIGH/MEDIUM/LOW) to prevent hallucination during rewrites; integrated PII masking before every LLM call (GDPR/PIPEDA compliant)
3. Constructed domain-specific RAG pipeline (interview question bank + ATS keyword library) using Qdrant vector database and sentence-transformers (`all-MiniLM-L6-v2`); interview agent selects contextually relevant questions via semantic search with role/type/difficulty filters
4. Implemented multi-turn mock interview agent with adaptive question routing (re-answer/follow-up/advance logic) and post-session CoachAgent review (STAR analysis, per-question feedback, readiness verdict)
5. Built full-stack React frontend (10 pages, 22 components, React Flow workflow visualization, Recharts radar chart) on top of Java Spring Boot REST API and Python FastAPI agent service; 225 automated tests (211 Python + 14 Spring Boot), all passing; containerized with Docker Compose

**CN (Chinese market):**
1. 设计并实现多 Agent 协作智能求职助手，6 个独立 Agent 基于 LangGraph 状态机编排，支持条件路由、自动重试、断点续传
2. 实现简历事实保真评估系统：双重实体抽取（正则 + LLM）+ 严重性分级（HIGH/MEDIUM/LOW），防止 LLM 改写引入幻觉内容；LLM 调用前自动 PII 脱敏（符合 GDPR/PIPEDA 要求）
3. 构建领域知识 RAG 系统：使用 Qdrant 向量数据库 + `all-MiniLM-L6-v2` 嵌入模型，支持面试题库语义检索（角色/类型/难度过滤）和 ATS 关键词覆盖率分析
4. 实现多轮模拟面试 Agent：动态路由（重答/追问/推进）+ 后处理 Coach Agent（STAR 分析、每题反馈、准备度判定）
5. 构建完整 React 前端（10 个页面、22 个组件、React Flow 工作流可视化、Recharts 雷达图），后端采用 Spring Boot + Python/FastAPI 双服务架构；225 个自动化测试全部通过；Docker Compose 一键部署
