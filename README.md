# AI Career — Multi-Agent Job Search Assistant

[![Build](https://img.shields.io/badge/build-passing-brightgreen)](#quick-start)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)
[![Java](https://img.shields.io/badge/Java-17-orange?logo=openjdk)](https://openjdk.org/)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Claude](https://img.shields.io/badge/Claude-API-black?logo=anthropic)](https://anthropic.com/)

**A multi-agent job search assistant that turns hours of preparation into 30 minutes — from resume optimization to mock interviews, end to end.**

基于多 Agent 协作的智能求职助手，把简历优化、JD 匹配、面试模拟串成自动化流水线。

---

## Motivation

I submitted 700+ job applications in Canada and got fewer than 5 interviews.

The process was brutal: tailor your resume for each JD, pray it passes ATS, research the company, practice common questions, run through STAR stories alone at midnight. Each application took 2–3 hours done right. Most of the time I cut corners, and it showed.

I built AI Career to automate the repeatable parts — not to game the system, but to free up mental energy for the parts that actually matter: real preparation, real answers, real confidence walking into the room.

---

## Screenshots

| Screen | Description |
|--------|-------------|
| ![Dashboard](docs/screenshots/dashboard.png) | **Dashboard** — activity feed, workflow progress, and quick stats at a glance |
| ![Upload](docs/screenshots/upload.png) | **Resume Upload** — drag-and-drop PDF/DOCX; agent parses to structured JSON |
| ![Match](docs/screenshots/match.png) | **Match Results** — radar chart across 6 dimensions with gap analysis |
| ![Rewrite](docs/screenshots/rewrite.png) | **Rewrite Comparison** — before/after bullet view with fidelity score |
| ![Interview](docs/screenshots/interview.png) | **Interview Chat** — multi-turn mock interview with real-time follow-up questions |
| ![Review](docs/screenshots/review.png) | **Coach Review** — STAR scoring, per-answer breakdown, improvement tips |
| ![Workflow](docs/screenshots/workflow.png) | **Workflow Visualization** — live React Flow graph showing agent execution state |

> Screenshots are placeholders — add images to `docs/screenshots/` after running the app.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Browser (React 18 + Vite)          │
│  Dashboard · Upload · Match · Rewrite ·      │
│  Interview · Review · Workflow               │
└────────────────────┬────────────────────────┘
                     │ REST / JSON
                     ▼
┌─────────────────────────────────────────────┐
│        Spring Boot 3.2  (port 8080)          │
│  Controllers · MyBatis · PostgreSQL · Redis  │
└────────────────────┬────────────────────────┘
                     │ REST
                     ▼
┌─────────────────────────────────────────────┐
│    Python Agent Service  (port 8001)         │
│    FastAPI · LangGraph · LangChain           │
└──────────┬──────────────────────┬───────────┘
           │                      │
           ▼                      ▼
  Anthropic Claude API       Qdrant Vector DB
  (claude-sonnet-4-6)        (interview RAG)
```

---

## The 6 Agents

| Agent | Job | Key Technique |
|-------|-----|---------------|
| **Resume Agent** | Parse PDF/DOCX → structured JSON with skills, experience, education | Multi-pass extraction + PII masking before LLM call |
| **JD Agent** | Extract requirements, skills, and responsibilities from any job posting | URL scraping + structured Claude prompt |
| **Match Agent** | Score resume vs JD across 6 dimensions, identify gaps | Radar chart scoring with weighted dimension analysis |
| **Rewrite Agent** | Rewrite resume bullets to target the JD without hallucinating | LangGraph loop with fidelity checker (anti-hallucination guard) |
| **Interview Agent** | Run multi-turn mock interviews with adaptive follow-up questions | RAG over resume + JD via Qdrant; conversational memory |
| **Coach Agent** | Score and review interview performance, give STAR-based feedback | Per-answer STAR analysis with improvement suggestions |

---

## Key Features

- **Multi-dimension matching with radar chart** — visualize fit across Skills, Experience, Education, Culture, Keywords, and Seniority
- **Resume rewriting with fidelity check** — anti-hallucination guard ensures every rewritten bullet traces back to your original experience
- **RAG-powered mock interviews with follow-ups** — questions grounded in your actual resume and the target JD
- **Coach review with STAR analysis** — structured feedback on Situation, Task, Action, Result for each answer
- **LangGraph orchestration with conditional routing** — agents loop, retry, and branch based on confidence scores
- **Real-time workflow visualization** — live React Flow graph showing which agent is running and what it returned

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Query, Zustand, React Flow, Recharts |
| Backend | Java 17, Spring Boot 3.2, MyBatis, PostgreSQL 16, Redis 7 |
| Agent Service | Python 3.11, FastAPI, LangGraph, LangChain, sentence-transformers |
| LLM | Anthropic Claude API (`claude-sonnet-4-6`) |
| Vector DB | Qdrant v1.9 (interview context RAG) |
| File Storage | MinIO (dev) / S3-compatible (prod) |
| Infrastructure | Docker, docker-compose, nginx |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Node 18+ (frontend dev only)
- Java 17+ (backend dev only)
- Python 3.11+ (agent service dev only)
- An [Anthropic API key](https://console.anthropic.com/)

### One-command (Docker, all services)

```bash
git clone https://github.com/zbai53/ai-career.git
cd ai-career
cp .env.example .env        # fill in ANTHROPIC_API_KEY and DB credentials
docker compose up --build   # starts postgres, redis, qdrant, minio, backend, agent-service, frontend
```

Open [http://localhost:3000](http://localhost:3000).

### Manual (development mode)

```bash
# 1. Clone and configure
git clone https://github.com/zbai53/ai-career.git
cd ai-career
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, DB passwords, etc.

# 2. Start infrastructure
docker compose up -d postgres redis qdrant minio

# 3. Start backend (Java)
cd backend
./mvnw spring-boot:run

# 4. Start agent service (Python)
cd agent-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload

# 5. Start frontend
cd frontend
npm install
npm run dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8080 |
| Agent Service | http://localhost:8001 |
| MinIO Console | http://localhost:9001 |
| Qdrant Dashboard | http://localhost:6333/dashboard |

---

## API Documentation

Full endpoint reference: [`docs/schemas/api-endpoints.md`](docs/schemas/api-endpoints.md)

Schema definitions: [`docs/schemas/resume-schema.md`](docs/schemas/resume-schema.md) · [`docs/schemas/jd-schema.md`](docs/schemas/jd-schema.md)

---

## Project Structure

```
ai-career/
├── frontend/                  # React 18 + Vite SPA
│   ├── src/
│   │   ├── api/               # React Query hooks + axios client
│   │   ├── components/        # Layout, ErrorBoundary, ToastContainer, ...
│   │   ├── pages/             # Dashboard, Upload, Match, Rewrite, Interview, ...
│   │   └── stores/            # Zustand (workflow state, toast)
│   ├── nginx.conf
│   └── Dockerfile
│
├── backend/                   # Spring Boot 3.2 REST API
│   └── src/main/java/com/aicareer/
│       ├── controller/        # REST controllers
│       ├── service/           # Business logic + DataDeletionService
│       ├── mapper/            # MyBatis mappers
│       ├── model/             # Entities + DTOs
│       └── config/            # Security, CORS
│
├── agent-service/             # Python FastAPI + LangGraph agents
│   └── app/
│       ├── agents/            # resume, jd, match, rewrite, interview, coach
│       ├── utils/             # pii_masker, fidelity checker
│       └── main.py
│
├── docs/
│   ├── schemas/               # API + data schemas
│   └── build-coach/           # Dev log + conventions
│
└── docker-compose.yml
```

---

## License

MIT © 2024 [zbai53](https://github.com/zbai53)
