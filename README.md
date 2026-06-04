# AI Career

A multi-agent job search assistant that turns hours of preparation into 30 minutes — from resume optimization to mock interviews, end to end.

基于多 Agent 协作的智能求职助手，把简历优化、JD 匹配、面试模拟串成自动化流水线。

## Architecture

```
Frontend (React + Vite)
        │
        ▼  REST
Main Service (Spring Boot 3.2)
        │
        ▼  REST + Webhook
Agent Service (Python + FastAPI + LangGraph)
        │
        ▼
Anthropic Claude API + Qdrant Vector DB
```

## Agents

| Agent | Job |
|-------|-----|
| Resume Agent | Parse PDF/DOCX → structured JSON |
| JD Agent | Extract requirements from job description |
| Match Agent | Multi-dimension matching score + gap analysis |
| Rewrite Agent | Rewrite resume bullets for target JD (with fidelity check) |
| Interview Agent | Multi-turn mock interview powered by RAG |
| Coach Agent | Score and review interview performance |

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Java 17, Spring Boot 3.2, MyBatis, PostgreSQL, Redis |
| Agent Service | Python 3.11, FastAPI, LangGraph, LangChain |
| LLM | Anthropic Claude API |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Vector DB | Qdrant |
| File Storage | MinIO (dev) / S3 (prod) |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys and passwords

# 2. Start infrastructure
docker-compose up -d

# 3. Start backend (Java)
cd backend && ./mvnw spring-boot:run

# 4. Start agent service (Python)
cd agent-service && python -m uvicorn app.main:app --port 8001

# 5. Start frontend
cd frontend && npm run dev
```

## Status

🚧 Under active development — see [roadmap](docs/build-coach/02-roadmap.md) for progress.

## License

MIT
