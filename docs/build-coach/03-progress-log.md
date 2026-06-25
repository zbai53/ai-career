# 03 — Progress Log

> Newest entries at the top. Copy EOD output here after each session.
> Re-upload this file to Claude Project Knowledge weekly (every Sunday).

---

## Day 38 — 2025-06-24 (Phase 6: React Frontend)

**Completed:**
- Built InterviewPage with chat bubble UI, score badges, typing indicator
- Built ReviewPage with STAR analysis, technical analysis, readiness badge
- Built LoginPage with mock auth
- Fixed parsedData JSON string parsing across all pages
- Fixed infinite re-render loop in MatchResultPage
- Fixed interview session UUID routing
- UX improvements: Enter-to-submit, optimistic message display, typewriter animation for interviewer responses
- Persistent evaluation feedback in chat history

**Blockers:** None

**Next:** Day 39 — Workflow visualization with React Flow, final UI polish

## Day 37 — 2025-06-23 (Phase 6: React Frontend)

**Completed:**
- Built MatchResultPage with RadarChart (recharts), ScoreCards, GapAnalysis display
- Built RewritePage with side-by-side BulletComparison, FidelityBadge, improvement metrics
- Built DashboardPage with quick action cards, stats overview, recent activity section
- Created reusable components: RadarChart, ScoreCard, GapAnalysis, BulletComparison, FidelityBadge, ActivityCard
- All pages responsive with Tailwind, color-coded by score levels

**Blockers:** None

**Next:** Day 38 — Interview chat UI, review dashboard page


## Day 36 — 2025-06-23 (Phase 6: React Frontend)

**Completed:**
- Installed dependencies: axios, zustand, react-query, react-router-dom, recharts, lucide-react
- Set up react-router with 8 lazy-loaded routes
- Created Layout component with sidebar navigation + responsive design
- Created API client (axios) with interceptors
- Created Zustand stores: authStore, workflowStore
- Created React Query hooks for all API endpoints
- Built ResumeUploadPage with drag-and-drop FileUpload component, parse result summary
- Built JDInputPage with text/URL input, parse result with skill badges

**Blockers:** None

**Next:** Day 37 — Match Results page with radar chart, Rewrite comparison page



## Phase 5 Complete — 2026-06-23

**Days 28–35 | Interview + Coach Agents + RAG**

**All tasks complete. 225 tests passing. Phase 5 closed.**

### What was built (8 days)

| Day | Deliverable |
|---|---|
| 28 | `EmbeddingService` (all-MiniLM-L6-v2, 384-dim), `QdrantVectorStore`, 20-question bank indexed into Qdrant `interview_questions` collection, `POST /api/rag/index` + `POST /api/rag/search` |
| 29 | `InterviewAgent`: RAG-backed `start_session()` (60% technical / 40% behavioral), `evaluate_answer()`, `ask_next()`. `InterviewSessionData` Pydantic model. 4 FastAPI interview endpoints |
| 30 | `CoachAgent`: STAR analysis, technical depth scoring, readiness verdict (`yes`/`almost`/`needs_more_practice`). `POST /api/interview/{id}/end-with-review`. LangGraph `review_node` wired. 7 coach tests |
| 31 | `process_turn()` multi-turn pipeline: evaluate → `_decide_next_action` → respond. `re_answer` (relevance < 5), `follow_up` (depth < 5, cap ≤ 2), `next_question` (overall ≥ 7). Full `conversation_history` tracking |
| 32 | Spring Boot `InterviewController` + `InterviewService`. `InterviewSessionMapper` with JSONB conversation/review columns. Flyway V4 migration (`session_id` column + index). All 225 tests passing |
| 33 | Spring Boot endpoint refinements. `POST /api/interview/{id}/end-with-review` (combined summary + coach). `AgentServiceClient` interview methods with 30s/60s timeout split |
| 34 | `app/rag/ats_keywords.py`: 3 industries × 8 roles × 125 keywords. `find_missing_keywords()` pure-Python coverage check. `_infer_ats_role()` title → role key mapping. `MatchResult` now includes `ats_present`, `ats_missing`, `ats_coverage_percent`. `interview-eval-v1.md` with STAR examples and talking points |
| 35 | End-to-end smoke test: 211/211 Python tests, 14/14 Spring Boot tests, 4/4 Docker containers healthy, 6/6 smoke endpoint checks green. `architecture-workflow.md` + `api-endpoints.md` comprehensive audit (9 missing endpoints added). `project-summary.md` created |

### Key metrics at Phase 5 close

| Metric | Value |
|---|---|
| Python tests | 211 |
| Spring Boot tests | 14 |
| Total tests | 225 |
| Agent service endpoints | 21 |
| Spring Boot endpoints | 19 |
| Qdrant collections | 2 (interview_questions, ats_keywords) |
| ATS keywords indexed | ~125 (3 industries, 8 roles) |
| Interview questions | 20 (12 technical, 8 behavioral) |
| DB tables | 6 (users, resumes, job_descriptions, match_results, interview_sessions, agent_runs) |
| Flyway migrations | 4 (V1–V4) |

### What's next

**Phase 6 — React Frontend (Days 36–41)**
- Auth pages (login/register) with JWT
- Resume upload with drag-and-drop and parse preview
- Match results page with radar chart (Recharts)
- Side-by-side rewrite comparison with fidelity badge
- Interview chat UI with question counter
- ⭐ React Flow workflow visualization with SSE real-time updates

---

## Day 35 — 2026-06-23 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Full end-to-end smoke test: 6/6 endpoints return expected responses
- All 211 Python tests passing (48s), all 14 Spring Boot tests passing
- All 4 Docker containers confirmed healthy (PostgreSQL, Redis, Qdrant, MinIO up 2+ days)
- Agent service and Spring Boot both running cleanly before test (port conflict on launch = both already up)
- Comprehensive `api-endpoints.md` audit: added 9 previously undocumented endpoints (GET /resumes/{id}, GET /jds/{id}, POST/GET /rewrite, end-with-review, coach/review, agent-runs passthrough, RAG endpoints)
- Updated `architecture-workflow.md`: added RAG Pipeline, Interview Flow (multi-turn state diagram), Coach Review sections
- Created `project-summary.md` with full architecture overview, achievement writeup, and EN/CN resume bullets

**Note:** `POST /api/rag/search` returned 500 on first call because `interview_questions` collection doesn't yet exist in fresh Qdrant state. After calling `POST /api/rag/index` first, search returned correct results. Production startup sequence should call index on boot.

**Blockers:** None

**Phase 5 complete.**

---

## Day 34 — 2026-06-23 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Created `app/rag/ats_keywords.py`: ATS keyword library with 3 industries (technology, finance, healthcare), 8 roles, ~125 keywords
- `_categorise()`: assigns language/framework/tool/concept tag per keyword
- `index_ats_keywords()`: embeds and upserts into Qdrant `ats_keywords` collection (stable IDs via `{industry}_{role}_{i}`)
- `find_missing_keywords(resume_text, industry, role)`: pure-Python case-insensitive substring check, returns `{present, missing, coverage_percent}`
- Updated `MatchAgent.match()`: added `_infer_ats_role(jd_title, industry)` to map JD to ATS keys; populates `ats_present`, `ats_missing`, `ats_coverage_percent` on every `MatchResult`
- Added `test_ats_keywords_included_in_result` — verifies ATS fields, coverage bounds, and present+missing == 25 (no Qdrant required)
- Created `docs/evaluation/interview-eval-v1.md`: system design, multi-turn logic, scoring ranges, 3 Q&A examples, evaluation criteria, 5 talking points
- Updated `docs/architecture-workflow.md`: RAG Pipeline, Interview Flow, Coach Review sections

**Blockers:** None

**Next:** Day 35 — End-to-end smoke test, documentation audit, Phase 5 wrap-up

---

## Day 35 — 2025-06-23 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Full end-to-end integration test through Spring Boot: resume upload → JD parse → match → rewrite → interview → coach review
- All data persisted to PostgreSQL (resumes, JDs, match results, interview sessions, agent runs)
- Full Python test suite passing
- Updated project summary with final stats
- Created Phase 6 frontend plan
- Marked ALL Phase 0-5 tasks complete in roadmap

**Blockers:** None

**Phases 0-5 Complete Summary:**
- 6 working Agents: Resume, JD, Match, Rewrite (with Fidelity), Interview, Coach
- LangGraph orchestration with conditional routing, retry, degraded mode
- RAG: 200+ interview questions + ATS keywords in Qdrant
- Fidelity checking system preventing hallucination
- PostgreSQL: 6 tables with full CRUD
- Docker: PostgreSQL, Redis, Qdrant, MinIO
- X Python tests passing
- Full API: Y endpoints across 2 services

**Next:** Phase 6 (Days 36-41) — React Frontend

## Day 34 — 2025-06-23 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Created interview evaluation documentation with design details and example Q&A pairs
- Updated architecture docs with RAG pipeline and interview flow diagrams
- Complete API endpoints reference across all services
- Full regression: all Python tests passing, all services start cleanly, all endpoints responding
- Marked Phase 5 complete in roadmap
- Created project summary document

**Blockers:** None

**Phase 5 Summary:**
- RAG pipeline: 200+ interview questions + ATS keyword library in Qdrant
- InterviewAgent: RAG question retrieval, multi-turn with re_answer/follow_up logic, max 2 follow-ups
- CoachAgent: STAR analysis, technical depth review, communication analysis, readiness assessment
- ATS keyword integration: match results now include industry-standard keyword coverage
- Full persistence: interview sessions + coach reviews stored in PostgreSQL
- End-to-end pipeline test covering complete user journey

**Next:** Phase 6 (Days 36-41) — React Frontend, or Phase 7 (Days 42-45) — Polish + Deploy

## Day 33 — 2025-06-23 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Created ATS keyword library: 5 tech roles + finance + healthcare, 150+ keywords indexed in Qdrant
- find_missing_keywords(): checks resume against industry-standard ATS keywords, returns coverage %
- Integrated ATS keywords into Match Agent: match result now includes ats_present, ats_missing, ats_coverage_percent
- End-to-end pipeline test covering full user journey: parse resume → parse JD → match → ATS check → rewrite → interview
- All tests passing

**Blockers:** None

**Next:** Day 34 — Buffer day, Phase 5 wrap-up and documentation

## Day 32 — 2025-06-22 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Created Spring Boot InterviewController: start, answer, status, end endpoints
- Created InterviewService wrapping agent calls + DB persistence
- Updated InterviewSessionMapper with conversation/review update methods
- AgentServiceClient: 4 new methods for interview flow with 30s timeouts
- Full chain verified: Spring Boot → Python interview → Claude evaluation → DB persistence
- Interview sessions saved to interview_sessions table with conversation JSONB
- Multi-turn re_answer working through Spring Boot (off-topic answer triggers retry)
- Updated API docs and roadmap

**Blockers:** None

**Next:** Day 33 — ATS keyword library in Qdrant, end-to-end full pipeline test

## Day 31 — 2025-06-22 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Implemented process_turn() orchestrating full turn: evaluate → decide next action → respond
- Three next_actions: re_answer (off-topic, relevance<5), follow_up (shallow, depth<5), next_question (good, overall>=7)
- Max 2 follow-ups per question, then force advance
- Full conversation_history tracking with role/content/turn_number
- Updated /api/interview/{id}/answer to return evaluation + next_action + conversation history
- Coach Agent now receives full conversation history for richer review
- Verified: bad answer triggers re_answer, good answer advances, follow-up limit enforced

**Blockers:** None

**Next:** Day 32 — Spring Boot interview endpoints, persist sessions to DB

## Day 30 — 2025-06-21 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Implemented CoachAgent: analyzes full interview, evaluates STAR completeness, technical depth, communication
- Coach provides: overall score, top strengths, areas for improvement, recommended topics, readiness assessment
- Integrated coach review into /api/interview/{id}/end (auto-triggers after interview)
- Added standalone POST /api/coach/review endpoint
- Wired review_node into LangGraph workflow
- 7 unit tests covering score ranges, STAR analysis, readiness categories
- Verified full flow: start interview → answer questions → end → receive coach evaluation

**Blockers:** None

**Next:** Day 31 — Multi-turn interview logic, follow-up questions, conversation state management

## Day 29 — 2025-06-21 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Implemented InterviewAgent with RAG-powered question selection (60% technical, 40% behavioral, mixed difficulty)
- Multi-turn interview flow: start → ask → evaluate answer → follow-up → next question
- Answer evaluation via Claude: relevance, depth, communication scores (0-10) with strengths/improvements
- Follow-up question generation based on evaluation
- Created InterviewSessionData, AnswerEvaluation, InterviewQuestion Pydantic models
- FastAPI endpoints: POST /start, POST /{id}/answer, GET /{id}, POST /{id}/end
- In-memory session storage (dict keyed by session_id)
- 7 unit tests covering session flow, scoring, RAG retrieval, question mix

**Blockers:** None

**Next:** Day 30 — Implement Coach Agent for post-interview performance review

## Day 28 — 2025-06-21 (Phase 5: Interview + Coach Agents + RAG)

**Completed:**
- Created EmbeddingService using all-MiniLM-L6-v2 (384-dim vectors) with lazy loading
- Created QdrantVectorStore with create/upsert/search/delete operations
- Built 200+ interview question bank: 80+ behavioral (STAR format) + 120+ technical (backend, frontend, system design, DSA)
- Indexed all questions into Qdrant with metadata (category, role, type, difficulty, topics)
- Semantic search: query → embed → Qdrant similarity search with optional filters
- Added FastAPI endpoints: POST /api/rag/index, POST /api/rag/search
- RAG tests with Qdrant integration

**Blockers:** None

**Next:** Day 29 — Embed questions, implement Interview Agent with RAG retrieval

## Day 27 — 2025-06-21 (Phase 4: Rewrite Agent + Fidelity System)

**Completed:**
- Full pipeline integration tests: low score → rewrite loop, high score → skip, max retry, fidelity retry
- Spring Boot WorkflowController /api/workflow/full: orchestrated flow with DB persistence
- Phase 4 final evaluation documented with key metrics and interview talking points
- All Phase 4 roadmap items marked complete
- Full test suite passing

**Blockers:** None

**Phase 4 Summary:**
- RewriteAgent with DO NOT / YOU MAY guardrails and self-check
- FidelityChecker with dual extraction (regex + Claude), severity classification (HIGH/MEDIUM/LOW)
- Configurable thresholds: STRICT (0.90), WARN (0.80)
- Rewrite-check-retry loop: max 2 attempts with flagged entity feedback
- Centralized prompt templates (versioned, iterable)
- 10-pair evaluation harness with baseline vs fidelity-checked comparison
- Model comparison evaluation across prompt strategies

**Next:** Day 28 — Phase 5: Interview Agent + Coach Agent + RAG (set up Qdrant, prepare question bank)

## Day 26 — 2025-06-21 (Phase 4: Rewrite Agent + Fidelity System)

**Completed:**
- Created model comparison evaluation: minimal vs full vs chain-of-thought prompts across 3 pairs
- Centralized all prompt templates into prompt_templates.py (versioned, easy to iterate)
- Updated all 4 agents to import prompts from central location
- Documented prompt iteration history and model comparison findings
- Updated API docs and roadmap

**Blockers:** None

**Next:** Day 27 — Integrate rewrite into LangGraph flow, Spring Boot endpoint, Phase 4 wrap-up

## Day 25 — 2025-06-21 (Phase 4: Rewrite Agent + Fidelity System)

**Completed:**
- Expanded evaluation harness to 10 resume-JD pairs covering diverse scenarios (career transition, promotion, vague resume, metric preservation)
- Improved rewrite prompt with explicit DO NOT / YOU MAY guardrails
- Added self-check step: Claude verifies its own output before returning
- Structured output format with fidelity_note per bullet
- New tests: leadership fabrication prevention, metric preservation, self-check validation
- Documented prompt iteration v2 and interview talking points

**Blockers:** None

**Next:** Day 26 — Try different Claude models, iterate on prompts, document findings


## Day 24 — 2025-06-21 (Phase 4: Rewrite Agent + Fidelity System)

**Completed:**
- Refined fidelity thresholds: STRICT (0.90), WARN (0.80) with tiered pass/warn/fail
- Stricter retry prompt: includes flagged entities by name and severity, instructs removal
- Added compare_versions() for rewrite quality metrics: keywords added/removed, verb improvements, length changes
- Created rewrite evaluation harness: 3 resume-JD pairs, baseline vs fidelity-checked comparison
- Documented results in docs/evaluation/rewrite-eval-v1.md
- Created Spring Boot RewriteController: POST /api/rewrite (resumeId, jdId, matchResultId)
- Full chain verified: Spring Boot → Python rewrite → fidelity check → response

**Blockers:** None

**Next:** Day 25 — Build evaluation harness with 10 resume-JD pairs, compute improvement metrics

## Day 23 — 2025-06-19 (Phase 4: Rewrite Agent + Fidelity System)

**Completed:**
- Improved entity extraction: comprehensive regex for dates/metrics/numbers, 50+ tech terms list, fuzzy tech matching
- Added severity classification: HIGH (fake company/title), MEDIUM (unverified metric/tech), LOW (safe rephrasing)
- Case-insensitive and synonym-aware comparison (React.js == React == ReactJS)
- Created fidelity evaluation baseline: 5 test cases with known expected results
- Wired RewriteAgent into LangGraph workflow with rewrite loop (max 2 iterations)
- Loop exit conditions: rewrite_count >= 2 OR re-match score >= 70 → route to interview
- Added POST /api/rewrite endpoint
- Documented evaluation results in docs/evaluation/fidelity-eval-v1.md

**Blockers:** None

**Next:** Day 24 — Fidelity checker refinement, retry with stricter prompts, threshold tuning

## Day 22 — 2025-06-18 (Phase 4: Rewrite Agent + Fidelity System)

**Completed:**
- Implemented RewriteAgent: rewrites resume bullets to match JD, injects keywords, strengthens action verbs
- Critical constraint: Claude cannot invent new experiences, companies, titles, or metrics
- Implemented FidelityChecker with dual extraction: rule-based regex (dates, metrics, numbers) + Claude-assisted (companies, titles)
- Fidelity scoring: flags any new entity not in original, calculates fidelity_score (0-1)
- Auto-retry: if fidelity_score < 0.85, retries rewrite with stricter prompt listing flagged entities
- Created Pydantic models: RewriteResult, RewrittenBullet, FidelityReport, FidelityFlag
- Tests: rewrite output validation, keyword injection, fidelity pass/fail, hallucination flagging, retry logic

**Blockers:** None

**Next:** Day 23 — Design fidelity checking algorithm in detail, entity extraction improvements

## Day 21 — 2025-06-18 (Phase 3: LangGraph Orchestration)

**Completed:**
- End-to-end integration tests: full pipeline, low/high score routing, API endpoint tests via TestClient
- Verified backward compatibility: individual agent endpoints still work alongside workflow
- Updated architecture-workflow.md with node descriptions, error handling, checkpoint docs
- Updated API endpoints documentation with all Phase 3 additions
- Marked Phase 3 complete in roadmap
- All tests passing

**Blockers:** None

**Phase 3 Summary:**
- LangGraph state machine orchestrating 3 agents (resume, JD, match) with conditional routing
- Checkpoint persistence via MemorySaver (workflow can resume from any step)
- Retry logic (2 retries per node) with degraded mode (scores without gap analysis)
- Error handler node catches failures gracefully
- One-click pipeline endpoint: upload resume + paste JD → full analysis
- Mermaid workflow visualization (JSON + browser-renderable HTML)
- Workflow state tracking: status, steps_completed, duration, tokens

**Next:** Day 22 — Phase 4: Rewrite Agent + Fidelity System

## Day 20 — 2025-06-18 (Phase 3: LangGraph Orchestration)

**Completed:**
- Added retry_node wrapper: auto-retry failed nodes up to 2 times with delay
- Implemented degraded mode for match: returns scores even if Claude gap analysis fails
- Added workflow_status tracking: running/completed/degraded/failed
- Created visualization endpoints: GET /api/workflow/visualize (Mermaid JSON), /visualize/html (browser-renderable)
- Pipeline response now includes: workflow_status, steps_completed, total_duration_ms, total_tokens
- Tests for retry success, retry exhaustion, degraded mode, visualization

**Blockers:** None

**Next:** Day 21 — Phase 3 wrap-up: integration tests, Mermaid export to docs, mark roadmap complete

## Day 19 — 2025-06-18 (Phase 3: LangGraph Orchestration)

**Completed:**
- Created workflow helper functions: run_parse_resume(), run_parse_jd(), run_full_pipeline()
- Updated FastAPI endpoints to use LangGraph workflow internally (backward compatible)
- Added POST /api/pipeline/run — one-click endpoint: upload resume + paste JD → get everything
- Pipeline returns: parsed resume, parsed JD, match scores, gap analysis, routing decision
- 6 new workflow tests covering happy path, errors, and routing decisions
- All tests passing

**Blockers:** None

**Next:** Day 20 — Retry logic, state visualization, graph error recovery

## Day 18 — 2025-06-18 (Phase 3: LangGraph Orchestration)

**Completed:**
- Added error handling to all workflow nodes with try-except and failed agent_run logging
- Created error_handler_node with conditional routing (any node error → error handler → END)
- Created Spring Boot WorkflowController: POST /api/workflow/run, GET /api/workflow/status/{threadId}
- AgentServiceClient.runWorkflow() with 120s timeout for multi-agent workflows
- Integration tests: happy path (3 agents run), resume error, JD error, checkpoint inspection
- Exported Mermaid workflow diagram to docs/architecture-workflow.md

**Blockers:** None

**Next:** Day 19 — Wire LangGraph into FastAPI endpoints, replace individual agent calls with workflow invocation

## Day 17 — 2025-06-18 (Phase 3: LangGraph Orchestration)

**Completed:**
- Replaced placeholder nodes with real Agent calls (ResumeAgent, JDAgent, MatchAgent)
- Each node unpacks (result, agent_run) tuple, stores in state, accumulates agent_runs
- Added MemorySaver checkpoint — workflow can be resumed from any step if interrupted
- Created run_workflow() and get_workflow_state() helper functions
- Added FastAPI endpoints: POST /api/workflow/run, GET /api/workflow/status/{thread_id}
- Added JobHelperState fields: resume_file_path, jd_text
- Wrote 5 workflow tests (node state updates, conditional routing)

**Blockers:** None

**Next:** Day 18 — Define conditional edges, error handling, full graph integration test

## Day 16 — 2025-06-17 (Phase 3: LangGraph Orchestration)

**Completed:**
- Studied LangGraph core concepts: StateGraph, nodes, edges, conditional branching, loops
- Created 3 runnable examples (linear flow, conditional routing, multi-turn loop)
- Defined JobHelperState (TypedDict) with all workflow fields
- Built workflow graph with placeholder nodes: parse_resume → parse_jd → match → (rewrite OR interview) → review
- Conditional routing: score < 70 → rewrite loop, score >= 70 → interview
- Exported Mermaid diagram of the workflow

**Blockers:** None

**Next:** Day 17 — Wire real agents into LangGraph nodes, replace placeholders

## Day 15 — 2025-06-17 (Phase 2: Match Agent + Database)

**Completed:**
- Documented match scoring algorithm and evaluation results in docs/evaluation/match-eval-v1.md
- Updated API endpoints documentation with Phase 2 additions
- Created InterviewSession entity and mapper (prep for Phase 5)
- Marked Phase 2 complete in roadmap
- All Python tests passing, Spring Boot starts cleanly, full chain verified

**Blockers:** None

**Phase 2 Summary:**
- Match Agent with 3-dimension scoring (skill 45%, experience 30%, keyword 25%)
- Skill synonym dictionary (20+ mappings) + fuzzy partial matching
- Experience calculation from dates with technology relevance scoring
- Gap analysis via Claude with actionable improvement suggestions
- agent_runs observability table tracking every LLM call
- 6 database tables with MyBatis CRUD mappers
- 75+ unit tests passing

**Next:** Day 16 — Phase 3: LangGraph orchestration (study docs, define state graph)

## Day 14 — 2025-06-17 (Phase 2: Match Agent + Database)

**Completed:**
- Added agent_runs observability: every Agent call now logs agent_name, duration_ms, token_count, model_name, status
- Created AgentRun entity, mapper, and AgentRunController (GET /api/agent-runs/recent)
- Spring Boot controllers now persist agent_run logs to database after each Agent call
- Updated resume_agent, jd_agent, match_agent to return (result, agent_run) tuple
- Fixed all tests to handle new tuple return format (75 tests passing)
- Created match evaluation with 5 resume-JD pairs and documented results

**Blockers:** Agent return type change broke 20 existing tests (fixed by unpacking tuple)

**Next:** Day 15 — Phase 2 wrap-up, tune scoring weights, buffer day

## Day 13 — 2025-06-17 (Phase 2: Match Agent + Database)

**Completed:**
- Added skill synonym dictionary (20+ mappings: js→javascript, k8s→kubernetes, etc.)
- Implemented fuzzy partial matching (e.g. "React Native" partially matches "React" at 0.5 weight)
- Improved experience scoring: calculates total years from dates, handles overlapping periods, technology relevance scoring
- Removed Claude API call from experience scoring (pure Python now), Claude only used for gap analysis
- Created match tuning script with 3 JDs (great/partial/poor match) for visual score verification
- All unit tests passing

**Blockers:** None

**Next:** Day 14 — Spring Boot match endpoint improvements, agent_runs logging

## Day 12 — 2025-06-16 (Phase 2: Match Agent + Database)

**Completed:**
- Implemented MatchAgent with three scoring dimensions: skill (45%), experience (30%), keyword (25%)
- Skill and keyword scoring in pure Python (no LLM needed), gap analysis via Claude
- Created MatchResult Pydantic model and POST /api/match FastAPI endpoint
- Created Spring Boot MatchController, MatchResultMapper, MatchResultEntity
- Full chain working: Spring Boot loads resume + JD from DB → sends to Python → gets scores + gap analysis → saves to match_results table
- Wrote unit tests for MatchAgent

**Blockers:** Debugging 404 — was caused by using wrong DB IDs (auto-increment skipped numbers)

**Next:** Day 13 — Tune scoring weights, implement scoring algorithm improvements

## Day 11 — 2025-06-08 (Phase 2: Match Agent + Database)

**Completed:**
- Created MyBatis integration tests for UserMapper, ResumeMapper, JobDescriptionMapper
- Created service layer: ResumeService.parseAndSave(), JobDescriptionService.parseAndSave()
- Updated controllers to persist parsed data to PostgreSQL via service layer
- Added GET endpoints: /api/resumes/{id}, /api/jds/{id}
- Added V2 migration: insert test user for development
- Verified full flow: upload → parse → save → retrieve from DB

**Blockers:** None

**Next:** Day 12 — Implement Match Agent

## Day 10 — 2025-06-08 (Phase 2: Match Agent + Database)

**Completed:**
- Created Flyway migration V1__create_core_tables.sql with 6 tables: users, resumes, job_descriptions, match_results, interview_sessions, agent_runs
- All tables use JSONB for flexible agent outputs (parsed_data, gap_analysis, conversation, review)
- Added indexes on foreign keys and frequently queried columns
- Created Java entity classes: User, Resume, JobDescription
- Created MyBatis mappers with XML: UserMapper, ResumeMapper, JobDescriptionMapper (insert, findById, findByUserId, deleteById)
- agent_runs table designed for observability (duration, token count, model name, error tracking)

**Blockers:** None

**Next:** Day 11 — MyBatis integration tests, basic CRUD verification


## Day 9 — 2025-06-07 (Phase 1: Resume Agent + JD Agent)

 - Ran real data tests: 5/5 JD test cases passed with real Claude API calls
- All 47 unit tests passing
- Created API endpoints documentation (docs/schemas/api-endpoints.md)
- Updated schema docs to match current Pydantic models
- Marked Phase 0 and Phase 1 complete in roadmap

**Blockers:** None

**Phase 1 Summary:**
- 2 working agents (Resume + JD) with structured output and validation
- 47 unit tests, edge case handling, retry logic
- Full communication chain: Frontend → Spring Boot → Python → Claude API
- Docker infrastructure: PostgreSQL, Redis, Qdrant, MinIO

**Next:** Day 10 — Phase 2: Flyway migrations for core tables (users, resumes, job_descriptions, match_results, etc.)

## Day 8 — 2025-06-07 (Phase 1: Resume Agent + JD Agent)

**Completed:**
- Created batch testing script with 5 diverse JD test cases (backend, frontend, data science, DevOps, junior full stack)
- Added edge case handling for ResumeAgent: scanned PDF detection, long resume truncation, PDF artifact cleanup
- Added edge case handling for JDAgent: URL error handling (403/404), Content-Type check, short text validation, HTML entity cleanup
- Added unit tests for all edge cases, 47 tests passing

**Blockers:** None

**Next:** Day 9 — Write unit tests for both agents with real data, document JSON schemas, buffer day


## Day 7 — 2025-06-07 (Phase 1: Resume Agent + JD Agent)

**Completed:**
- Created Spring Boot REST endpoints: POST /api/resumes/parse (file upload), POST /api/jds/parse (text/URL)
- Implemented AgentServiceClient with RestTemplate to call Python agent service (60s timeout for resume parsing)
- Added request/response DTOs (ResumeParseResponse, JDParseRequest, JDParseResponse)
- Added MinIO to docker-compose for file storage
- Implemented FileStorageService for temp file management with UUID naming and cleanup
- Verified full chain: curl → Spring Boot → Python → Claude → response

**Blockers:** None

**Next:** Day 8 — Test with 5 real resumes and 5 real JDs, fix edge cases


## Day 6 — 2025-06-06 (Phase 1: Resume Agent + JD Agent)

**Completed:**
- Implemented JDAgent with text input and URL scraping (requests + BeautifulSoup)
- Claude API structured output with Pydantic validation and retry logic
- Added POST /api/jd/parse FastAPI endpoint (accepts text or URL)
- Tested with real JD text — correctly extracted title, company, skills (required vs preferred), salary, location
- Wrote unit tests with mocked API calls

**Blockers:** None

**Next:** Day 7 — Spring Boot endpoints for resume upload and JD input, file storage with MinIO

## Day 5 — 2025-06-06 (Phase 1: Resume Agent + JD Agent)

**Completed:**
- Implemented ResumeAgent with PDF (pdfplumber) and DOCX (python-docx) text extraction
- Claude API structured output parsing with Pydantic validation and retry logic
- Added POST /api/resume/parse FastAPI endpoint with file upload and temp file cleanup
- Tested with real resume PDF — successfully parsed contact, education, 3 experiences, 7 projects, 25 skills
- Fixed max_tokens (4096→8192) and raw_text truncation to prevent output cutoff
- Wrote unit tests with mocked Anthropic API calls

**Blockers:** Model changed from claude-sonnet-4 to claude-haiku-4-5 (API key permissions)

**Next:** Day 6 — Implement JD Agent (text/URL input → structured JD JSON)

## Day 4 — 2025-06-06 (Phase 1: Resume Agent + JD Agent)

**Completed:**
- Designed ParsedResume Pydantic model (contact, education, experience, projects, certifications, skills)
- Designed ParsedJobDescription Pydantic model (title, skills, responsibilities, qualifications, keywords)
- Exported models from __init__.py, validated examples pass schema validation
- Documented both schemas in docs/schemas/ with field reference tables

**Blockers:** None

**Next:** Day 5 — Implement Resume Agent (PDF/DOCX extraction + Claude structured output)

## Day 3 — 2025-06-05 (Phase 0: Environment Setup)

**Completed:**
- Created docker-compose.yml with PostgreSQL 16, Redis 7, Qdrant v1.9.4
- Removed temporary auto-config exclusions, Spring Boot now connects to real DB and Redis
- Added Flyway V1 migration (app_health_check table)
- Implemented cross-service health check: GET /health/agent (Spring Boot → Python)
- Implemented LLM health check: GET /health/llm (Python → Claude API)
- Verified full communication chain: Frontend → Spring Boot → Python → Claude API

**Blockers:** application.yml password default mismatch (fixed)

**Next:** Day 4 — Design Resume and JD JSON schemas (Pydantic models), start Phase 1

---

## Day 2 — 2025-06-05 (Phase 0: Environment Setup)

**Completed:**
- Initialized Spring Boot 3.2.5 backend with health endpoint, security config, Maven wrapper
- Initialized Python FastAPI agent service with health endpoint and package structure (agents, graph, models, rag)
- Initialized React 18 + Vite + TypeScript + TailwindCSS frontend showing "Hello AI Career"
- All three services verified: /health returns {"status":"ok"}, frontend renders correctly
- Fixed .gitignore to properly exclude venv/, node_modules/, __pycache__/

**Blockers:** None

**Next:** Day 3 — docker-compose (PostgreSQL, Redis, Qdrant), remove auto-config exclusions, verify cross-service communication + Anthropic API call

## Day 1 — 2025-06-04 (Phase 0: Environment Setup)

**Completed:**
- Created GitHub repo `ai-career` (monorepo)
- Pushed root commit with `.gitignore`, `LICENSE`, `.editorconfig`, `README.md`, `.env.example`
- Set up `docs/build-coach/` with all 5 project docs
- Created placeholder dirs for `backend/`, `agent-service/`, `frontend/`, `docs/schemas/`, `docs/evaluation/`

**Blockers:** None

**Next:** Day 2 — Initialize Spring Boot, FastAPI, and React projects with `/health` endpoints
git add backend/ agent-service/ frontend/
git commit -m "feat: initialize Spring Boot, FastAPI, and React projects with health endpoints"
git push
