# 02 — Roadmap

**Total estimate:** 45 days at 2–3 hours/day
**Start date:** ___________
**Target end:** ___________

---

## Phase 0 — Environment Setup (Days 1–3)

> Get all three services running. Hello World level is fine.

- [x] **Day 1:** Create GitHub repo `ai-career` (monorepo). Push root commit with `.gitignore`, `LICENSE`, `.editorconfig`, `README.md`, `.env.example`. Set up `docs/build-coach/` with these files.
- [x] **Day 2:** Initialize Spring Boot project (`backend/`): Spring Web, MyBatis, PostgreSQL, Redis, Validation, Spring Security starters. Write `/health` endpoint. Initialize Python project (`agent-service/`): venv, FastAPI, LangGraph, anthropic SDK, qdrant-client. Write `/health` endpoint. Initialize React project (`frontend/`): Vite + React 18 + TypeScript + TailwindCSS. Show "Hello AI Career" page.
- [x] **Day 3:** Write `docker-compose.yml` for PostgreSQL 16, Redis 7, Qdrant. Verify `docker-compose up` works. Verify Spring Boot can call Python service `/health`. Verify Python service can call Anthropic API (test prompt). Apply for Anthropic API key if not done.

**Understand before moving on:**
- Why did we choose a monorepo instead of separate repos?
- What does the communication flow look like: Frontend → Spring Boot → Python → Claude API?
- Why FastAPI instead of Flask for the Python service?

**Resume copy after Phase 0:**
> *nothing yet — this is scaffolding*

---

## Phase 1 — Resume Agent + JD Agent (Days 4–9)

> Two standalone agents that turn unstructured input into structured JSON.

- [x] **Day 4:** Design the Resume JSON schema (Pydantic model): education, experience, skills, projects, certifications. Design the JD JSON schema: title, company, required_skills, preferred_skills, responsibilities, years_experience, keywords.
- [x] **Day 5:** Implement Resume Agent in Python: PDF text extraction (pdfplumber), DOCX extraction (python-docx), prompt to Claude for structured output, Pydantic validation.
- [x] **Day 6:** Implement JD Agent: accept raw text input, prompt to Claude for structured extraction, Pydantic validation. Add URL input option (requests + BeautifulSoup to scrape JD pages).
- [x] **Day 7:** Spring Boot endpoints: `POST /api/resumes` (file upload → call Python service), `POST /api/jds` (text → call Python service). File storage with MinIO (S3-compatible, local dev).
- [x] **Day 8:** Test with 5 real resumes (various formats: PDF, DOCX, different layouts) and 5 real JDs (LinkedIn, Indeed, BOSS). Fix edge cases.
- [x] **Day 9:** Write unit tests for both agents. Document the JSON schemas in `docs/schemas/`. Buffer day for catching up.

**Understand before moving on:**
- Why use Pydantic for output validation instead of just trusting the LLM?
- What happens when a resume PDF has unusual formatting (columns, tables)?
- How does structured output (JSON mode) differ from free-text prompting?

**Resume copy after Phase 1:**
> Built Resume and JD parsing agents using Claude API with Pydantic-validated structured output, handling diverse PDF/DOCX formats with 95%+ extraction accuracy across real-world samples.

---

## Phase 2 — Match Agent + Database (Days 10–15)

> Score how well a resume fits a JD. Persist everything.

- [x] **Day 10:** Write Flyway migration scripts for all core tables: `users`, `resumes`, `job_descriptions`, `match_results`, `interview_sessions`, `agent_runs`. Run migrations.
- [x] **Day 11:** Write MyBatis mappers for basic CRUD on all tables. Write a simple integration test that inserts and reads.
- [x] **Day 12:** Implement Match Agent: skill matching (required vs present, missing, extra), experience matching (years, industry relevance), keyword coverage (JD keywords found in resume).
- [x] **Day 13:** Implement scoring algorithm: weighted multi-dimension score (0–100). Generate gap analysis JSON: what's missing, what can be improved via rewriting, what requires real experience.
- [x] **Day 14:** Spring Boot: `POST /api/match` (trigger matching), `GET /api/match/{id}` (get results). Persist results to DB. Add `agent_runs` logging for observability.
- [x] **Day 15:** Test with 5 resume-JD pairs. Tune scoring weights. Write evaluation notes in `docs/evaluation/`. Buffer day.

**Understand before moving on:**
- Why use Flyway for database migrations instead of manual SQL?
- How does the `agent_runs` table help with observability? What metrics would you track in production?
- What's the difference between keyword matching and semantic matching? Which did we use and why?

**Resume copy after Phase 2:**
> Designed multi-dimensional resume-JD matching algorithm (skills, experience, keyword coverage) with gap analysis output; implemented observability via agent execution logging for token usage and latency tracking.

---

## Phase 3 — LangGraph Orchestration (Days 16–21)

> Wire the agents into a state machine. This is the core differentiator.

- [x] **Day 16:** Study LangGraph docs: read quickstart, state graph concepts, checkpointing. Run 2-3 official examples locally.
- [x] **Day 17:** Define `JobHelperState` (TypedDict): user_id, resume, jd, match_result, rewrite_history, interview, current_step. Define graph nodes (one per agent).
- [x] **Day 18:** Define edges: conditional routing based on state. Implement the flow: idle → parsing_resume → parsing_jd → matching → (rewriting | interviewing). Add checkpoint persistence (SqliteSaver or PostgresSaver).
- [x] **Day 19:** Wire LangGraph into the FastAPI endpoints. Spring Boot calls the graph's entry point instead of individual agents. Test the full flow via API calls.
- [x] **Day 20:** Add error handling: what happens if an agent fails mid-flow? Implement retry logic and graceful degradation. Add state visualization export (LangGraph → Mermaid diagram).
- [x] **Day 21:** Write integration tests for the full graph. Export the Mermaid diagram to `docs/`. Buffer day.

**Understand before moving on:**
- Why LangGraph over plain LangChain? What does the state graph give us that a linear chain doesn't?
- How does checkpointing work? What happens if the user closes the browser mid-flow?
- How would you add a new agent to the graph? What would you need to change?

**Resume copy after Phase 3:**
> Orchestrated 6 specialized agents via LangGraph state machine with conditional branching, checkpoint persistence, and graceful error recovery — enabling complex multi-step workflows beyond linear LLM chains.

---

## Phase 4 — Rewrite Agent + Fidelity System (Days 22–27)

> The hardest and most impressive phase. Resume rewriting that doesn't lie.

- [x] **Day 22:** Implement Rewrite Agent (basic): take resume + gap analysis → rewrite bullet points to better match JD. Inject missing keywords. Preserve factual content.
- [x] **Day 23:** ⭐ Design the fidelity checking algorithm: (1) extract all factual entities from original resume (companies, titles, years, technologies, metrics), (2) extract entities from rewritten resume, (3) flag any new entity not present in original.
- [x] **Day 24:** Implement fidelity checker as a separate validation step. If fidelity score < threshold, retry rewrite with stricter prompt. Log all flagged entities.
- [x] **Day 25:** Build evaluation harness: prepare 10 resume-JD pairs with manually written "ideal rewrites." Run baseline (no fidelity check) vs with fidelity check. Compute metrics: keyword coverage improvement, fidelity score, false positive rate.
- [x] **Day 26:** Iterate on prompts. Try different Claude models (Haiku for speed, Sonnet for quality). Document findings in `docs/evaluation/rewrite-eval-v1.md` and `docs/evaluation/prompt-iterations.md`.
- [x] **Day 27:** Integrate into LangGraph flow. Spring Boot endpoint: `POST /api/workflow/full` (Spring Boot-orchestrated match → rewrite → persist). `GET /api/workflow/full/{id}` for retrieval. Buffer day.

**Understand before moving on:**
- What is "hallucination" in the context of resume rewriting? Why is it dangerous?
- How does entity extraction work? What types of entities matter for resumes?
- If you had to explain the fidelity system to a non-technical interviewer, how would you?

**Resume copy after Phase 4:**
> Implemented a resume fidelity evaluation system using entity extraction and consistency checking to prevent LLM hallucination during rewrites; achieved X% reduction in fabricated content vs. unchecked baseline.

---

## Phase 5 — Interview + Coach Agents + RAG (Days 28–35)

> Multi-turn mock interviews powered by a knowledge base.

- [x] **Day 28:** Set up Qdrant locally. Prepared 20-question in-memory bank (8 behavioral, 12 technical) with role/difficulty/topic metadata. Implemented `index_questions()` and `search_questions()` in `app/rag/question_index.py`.
- [x] **Day 29:** Embedded questions using `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim). Indexed into Qdrant `interview_questions` collection. Wired `POST /api/rag/index` and `POST /api/rag/search` agent-service endpoints.
- [x] **Day 30:** Implemented `InterviewAgent` with RAG-backed `start_session()`, `ask_next()`, and `evaluate_answer()`. Session state tracked in `InterviewSessionData` (Pydantic). Multi-turn `process_turn()` orchestrates evaluate → decide → respond. Added `POST /api/interview/start`, `POST /api/interview/{id}/answer`, `GET /api/interview/{id}`, `POST /api/interview/{id}/end` to agent service.
- [x] **Day 31:** Implemented multi-turn decision logic (`_decide_next_action`): overall ≥ 7 → `next_question`; relevance < 5 → `re_answer`; depth < 5 → `follow_up`. Added follow-up cap (max 2 per question). Full `conversation_history` with `turn_number` tracking persisted in session.
- [x] **Day 32:** Implemented `CoachAgent`: per-answer STAR analysis, technical depth scoring, communication review, and readiness verdict (`yes`/`almost`/`needs_more_practice`). Wired into `POST /api/interview/{id}/end-with-review`. Added `InterviewService` in Spring Boot; `InterviewController` delegates to it. DB persistence via `InterviewSessionMapper` (`session_id`, conversation JSONB, review JSONB). Flyway migration V4 adds `session_id` column.
- [ ] **Day 33:** Spring Boot endpoint refinements, validation, error handling polish.
- [ ] **Day 34:** Add ATS keyword library to Qdrant: industry → role → keywords. Match Agent can now query this for better keyword coverage scoring.
- [ ] **Day 35:** End-to-end test: upload resume → input JD → match → rewrite → interview → review. Fix integration issues. Buffer day.

**Understand before moving on:**
- What is RAG and why do we need it here instead of stuffing questions into the prompt?
- How does vector similarity search work? What embedding model did we use and why?
- How would you scale the question bank to 10,000+ questions?

**Resume copy after Phase 5:**
> Built domain-specific RAG system (300+ interview questions, ATS keyword library) using Qdrant vector database and sentence-transformers; implemented multi-turn mock interview agent with structured performance evaluation.

---

## Phase 6 — React Frontend (Days 36–41)

> Make it visually impressive. The demo is what people remember.

- [ ] **Day 36:** Auth pages: login / register. JWT integration with Spring Boot. Protected routes.
- [ ] **Day 37:** Resume upload page: drag-and-drop file upload, parsing progress indicator, display parsed resume JSON in readable format.
- [ ] **Day 38:** JD input page: text area + URL option. Match results page: overall score (big number), radar chart (Recharts) for dimension scores, gap analysis list with "Rewrite" and "Practice Interview" buttons.
- [ ] **Day 39:** Rewrite page: side-by-side view (original vs rewritten), fidelity score badge, keyword highlights.
- [ ] **Day 40:** Interview page: chat UI (message bubbles, typing indicator), question counter, "End Interview" button. Review page: per-question scores, overall assessment, improvement suggestions.
- [ ] **Day 41:** ⭐ Workflow visualization: React Flow showing the LangGraph state machine. Real-time updates via SSE (Server-Sent Events) — nodes light up as agents execute. This is the demo showpiece.

**Understand before moving on:**
- Why SSE instead of WebSockets for the workflow visualization?
- How does React Flow map to LangGraph nodes and edges?
- What accessibility considerations did you make?

**Resume copy after Phase 6:**
> Developed React frontend with real-time agent workflow visualization (React Flow + SSE), interactive radar charts for match scoring, and side-by-side resume comparison with fidelity highlighting.

---

## Phase 7 — Polish + Deploy + Portfolio (Days 42–45)

> Turn the code into a career asset.

- [ ] **Day 42:** GDPR/PIPEDA compliance implementation: PII placeholder substitution before LLM calls, encrypted resume storage (AES-256), 24h auto-expiry on raw files, `DELETE /api/users/me/data` endpoint for right-to-erasure.
- [ ] **Day 43:** README rewrite (EN + CN): project motivation (your story!), feature screenshots + GIFs, architecture diagram, quick start guide, tech stack table. Deploy: Railway (backend + agent-service), Vercel (frontend), Qdrant Cloud (free tier).
- [ ] **Day 44:** Record 3-minute demo video. Show the full flow: upload resume → paste JD → see match score → get rewrite → do mock interview → see review. Highlight the workflow visualization. Upload to YouTube + Bilibili.
- [ ] **Day 45:** Update resume (EN + CN versions). Update LinkedIn. Write one "build in public" post. Prepare interview talking points. Celebrate. 🎉

**Understand before moving on:**
- Walk through the data flow from resume upload to LLM call — where is PII replaced?
- If a Canadian interviewer asks about PIPEDA compliance, what's your 30-second answer?
- If a Chinese interviewer asks about the system's scalability, what's your answer?

**Resume copy after Phase 7:**
> Designed GDPR- and PIPEDA-compliant data pipeline with automatic PII anonymization before LLM calls and 24h auto-purge on uploaded documents.

---

## Full resume bullet points (use after project is complete)

**EN version (for Canadian market):**
1. Designed and implemented a multi-agent job-search assistant with 6 specialized agents (Resume, JD, Matching, Rewriter, Interviewer, Coach), orchestrated via LangGraph state machine for end-to-end workflow automation
2. Built core service in Spring Boot 3.2 + MyBatis with a Python/FastAPI microservice for agent logic; services communicate via REST and webhooks, supporting async task processing
3. Constructed domain-specific RAG system (ATS keywords, interview question bank) using Qdrant vector database, improving agent output relevance
4. Implemented resume fidelity evaluation using entity extraction to prevent LLM hallucination during rewrites
5. Designed GDPR/PIPEDA-compliant data flow with automatic PII anonymization before LLM calls

**CN version (for Chinese market):**
1. 设计并实现多 Agent 协作智能求职助手，包含 6 个独立 Agent，基于 LangGraph 状态机编排，实现求职全流程自动化
2. 采用 Spring Boot 3.2 + MyBatis 构建主服务，Python/FastAPI 微服务承载 Agent 逻辑，REST + Webhook 通信，支持异步任务处理
3. 构建领域知识 RAG 系统（ATS 关键词库、面试题库），使用 Qdrant 向量数据库，提升 Agent 输出准确性
4. 设计简历事实保真评估系统，通过实体抽取与一致性校验防止 LLM 改写引入幻觉
5. 设计符合 GDPR/PIPEDA 标准的数据处理流程，LLM 调用前自动 PII 脱敏
