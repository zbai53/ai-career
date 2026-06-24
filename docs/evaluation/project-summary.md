# AI Career — Multi-Agent Job Search Assistant
## Project Summary

**Repository:** `ai-career` (monorepo)  
**Status:** Phases 0–5 of 7 complete  
**Date:** 2026-06-23

---

## What It Does

An end-to-end job search assistant that takes a candidate's resume and a job description, then:

1. Parses both into structured JSON using LLM-backed agents
2. Scores the match across three dimensions (skills, experience, ATS keywords)
3. Rewrites resume bullets to better fit the JD — with a fidelity guardrail to prevent hallucination
4. Runs a RAG-powered multi-turn mock interview
5. Produces a structured coaching review with readiness verdict and per-question feedback

---

## Architecture

```
React Frontend (Vite + TypeScript + TailwindCSS)
        │ HTTP
        ▼
Spring Boot Backend (Java 21, port 8080)
  ├── REST controllers (Resume, JD, Match, Rewrite, Workflow, Interview, AgentRuns)
  ├── MyBatis ORM → PostgreSQL (6 tables)
  ├── Flyway migrations (V1–V4)
  └── AgentServiceClient → HTTP → Python Agent Service
        │
        ▼
Python Agent Service (FastAPI, port 8001)
  ├── 6 Agents (each backed by Claude claude-haiku-4-5-20251001)
  ├── LangGraph state machine (conditional routing, retry, degraded mode)
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
- **Retry loop:** if `fidelity_score < 0.80`, the agent retries once with the flagged entities listed explicitly in the prompt
- **Result:** `FidelityReport` with per-flag severity, attached to every `RewriteResult`

### 3. RAG Pipeline

**Files:** `agent-service/app/rag/question_index.py`, `app/rag/ats_keywords.py`

Two Qdrant collections, both using `all-MiniLM-L6-v2` (384-dim):

| Collection | Contents | Size |
|---|---|---|
| `interview_questions` | Technical + behavioral questions with role/type/difficulty metadata | 20 questions (expandable) |
| `ats_keywords` | Industry-standard ATS keywords per role | ~125 keywords across 3 industries, 8 roles |

- `InterviewAgent.start_session()` fetches 60% technical + 40% behavioral questions via semantic search filtered by role
- `find_missing_keywords()` is pure Python (dict lookup) — no Qdrant call at query time; ATS coverage appears in every `MatchResult`

### 4. Multi-Turn Mock Interviews

**File:** `agent-service/app/agents/interview_agent.py`

`process_turn()` runs a three-step pipeline per answer:

1. `evaluate_answer()` → Claude scores relevance, depth, communication (each 1–10)
2. `_decide_next_action()` → priority rules: `re_answer` (relevance < 5) > `follow_up` (depth < 5, cap ≤ 2) > `next_question` (overall ≥ 7)
3. `respond()` → Claude generates the follow-up probe, re-prompt, or next question

Full `conversation_history` (role/content/turn_number) is tracked across all turns and passed to `CoachAgent` for richer feedback.

### 5. Agent-Run Observability

**File:** `agent-service/app/utils/agent_logger.py`

Every Claude call logs:
- `agent_name`, `model_name`, `status` (success/error)
- `duration_ms` (wall-clock time)
- `token_count` (input + output tokens)
- `input_summary` and `output_summary` (first 100 chars each)
- `created_at` (UTC ISO-8601)

Spring Boot persists all `agent_run` entries to the `agent_runs` table, queryable via `GET /api/agent-runs/recent`.

---

## Database Schema

**6 tables** managed by Flyway migrations (V1–V4):

| Table | Purpose | Key columns |
|---|---|---|
| `users` | User accounts (reserved for auth) | `id`, `email`, `created_at` |
| `resumes` | Parsed resume records | `id`, `user_id`, `file_path`, `parsed_data` (JSONB) |
| `job_descriptions` | Parsed JD records | `id`, `user_id`, `title`, `parsed_data` (JSONB) |
| `match_results` | Match scores + gap analysis | `id`, `resume_id`, `jd_id`, `overall_score`, `gap_analysis` (JSONB) |
| `interview_sessions` | Interview state + history | `id`, `session_id` (UUID), `conversation` (JSONB), `review` (JSONB), `status` |
| `agent_runs` | Observability log | `id`, `agent_name`, `duration_ms`, `token_count`, `status`, `model_name` |

JSONB columns store the full Pydantic model dumps from the agent service. Flyway V4 added `session_id VARCHAR(100) UNIQUE` to `interview_sessions` and the corresponding index.

---

## Test Coverage

**Total: 225 tests**

| Suite | Tests | Scope |
|---|---|---|
| Python — pytest | 211 | All 6 agents, RAG, LangGraph workflow, fidelity checker, full pipeline |
| Spring Boot — Maven | 14 | Controller + mapper integration tests |

All 225 tests pass. Python tests run in ~48s without any external network calls (Claude API fully mocked via `unittest.mock.patch`). Spring Boot tests use an in-memory H2 database.

Notable test classes:
- `TestMultiTurnLogic` (7 tests) — follow-up cap, re-answer routing, conversation history integrity
- `TestFidelityCheckFlagsHallucination` — entity injection detection
- `TestWorkflowIntegration` — full LangGraph graph execution with mocked agents
- `TestMatchAgent::test_ats_keywords_included_in_result` — ATS coverage in match output

---

## API Surface

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

**Spring Boot (port 8080) — 19 endpoints**

| Group | Endpoints |
|---|---|
| Health | `GET /health`, `GET /health/agent` |
| Resume / JD | `POST /api/resumes/parse`, `GET /api/resumes/{id}`, `POST /api/jds/parse`, `GET /api/jds/{id}` |
| Match / Rewrite | `POST /api/match`, `GET /api/match/{id}`, `POST /api/rewrite`, `GET /api/rewrite/{id}` |
| Workflow | `POST /api/workflow/run`, `POST /api/workflow/full`, `GET /api/workflow/full/{id}`, `GET /api/workflow/status/{id}` |
| Interview | `POST /api/interviews/start`, `POST /api/interviews/{id}/answer`, `GET /api/interviews/{id}`, `POST /api/interviews/{id}/end` |
| Agent Runs | `GET /api/agent-runs/recent` |

---

## Phases Completed

| Phase | Days | Status | What was built |
|---|---|---|---|
| 0 — Environment Setup | 1–3 | ✓ Complete | Monorepo, Docker Compose, three services with `/health` endpoints, Anthropic API verified |
| 1 — Resume + JD Agents | 4–9 | ✓ Complete | PDF/DOCX extraction, Claude structured parse, Pydantic validation, retry logic, 47 unit tests |
| 2 — Match Agent + DB | 10–15 | ✓ Complete | 3-dimension scoring, skill synonyms, Flyway migrations, MyBatis mappers, agent_runs observability |
| 3 — LangGraph Orchestration | 16–21 | ✓ Complete | State machine, conditional routing, retry_node, degraded mode, checkpointing, Mermaid visualization |
| 4 — Rewrite + Fidelity | 22–27 | ✓ Complete | RewriteAgent, FidelityChecker (dual extraction, severity, retry), evaluation harness, prompt versioning |
| 5 — Interview + Coach + RAG | 28–35 | ✓ Complete | Qdrant RAG, InterviewAgent (multi-turn), CoachAgent (STAR analysis), ATS keyword library, Spring Boot interview persistence |
| 6 — React Frontend | 36–41 | ○ Planned | Auth, resume upload, match radar chart, rewrite side-by-side, interview chat UI, React Flow visualization |
| 7 — Polish + Deploy | 42–45 | ○ Planned | GDPR/PIPEDA compliance, Railway/Vercel deploy, demo video, portfolio write-up |

---

## Resume Bullet Points (use after project is complete)

**EN (Canadian market):**
1. Designed and implemented a multi-agent job-search assistant with 6 specialized agents (Resume, JD, Matching, Rewriter, Interviewer, Coach), orchestrated via LangGraph state machine with conditional routing, retry logic, and checkpoint persistence
2. Built resume fidelity evaluation system using dual entity extraction (regex + LLM) with severity classification (HIGH/MEDIUM/LOW) to prevent hallucination during rewrites; achieved measurable reduction in fabricated content vs. unchecked baseline
3. Constructed domain-specific RAG pipeline (interview question bank + ATS keyword library) using Qdrant vector database and sentence-transformers (`all-MiniLM-L6-v2`); interview agent selects contextually relevant questions via semantic search with role/type/difficulty filters
4. Implemented multi-turn mock interview agent with adaptive question routing (re-answer/follow-up/advance logic) and post-session CoachAgent review (STAR analysis, per-question feedback, readiness verdict)
5. Designed GDPR/PIPEDA-compliant data flow: agent_runs observability table tracks every LLM call with token count, latency, and model ID; 225 automated tests (211 Python + 14 Spring Boot) with all Claude calls mocked

**CN (Chinese market):**
1. 设计并实现多 Agent 协作智能求职助手，6 个独立 Agent 基于 LangGraph 状态机编排，支持条件路由、自动重试、断点续传
2. 实现简历事实保真评估系统：双重实体抽取（正则 + LLM）+ 严重性分级（HIGH/MEDIUM/LOW），防止 LLM 改写引入幻觉内容
3. 构建领域知识 RAG 系统：使用 Qdrant 向量数据库 + `all-MiniLM-L6-v2` 嵌入模型，支持面试题库语义检索（角色/类型/难度过滤）和 ATS 关键词覆盖率分析
4. 实现多轮模拟面试 Agent：动态路由（重答/追问/推进）+ 后处理 Coach Agent（STAR 分析、每题反馈、准备度判定）
5. 基于 Spring Boot + Python/FastAPI 双服务架构，MyBatis 持久化 6 张核心表，agent_runs 可观测性表跟踪每次 LLM 调用的 Token 消耗与延迟；225 个自动化测试全部通过
