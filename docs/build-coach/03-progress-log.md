# 03 — Progress Log

> Newest entries at the top. Copy EOD output here after each session.
> Re-upload this file to Claude Project Knowledge weekly (every Sunday).

---
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
