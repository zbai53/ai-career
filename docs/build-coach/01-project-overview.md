# 01 — Project Overview

## What is this?

**AI Career Agent** — a multi-agent system that automates the job
search workflow: resume parsing → JD analysis → match scoring → resume
rewriting → mock interviews → interview coaching.

**One-line pitch (EN):** A multi-agent job search assistant that turns
hours of preparation into 30 minutes — from resume optimization to
mock interviews, end to end.

**One-line pitch (CN):** 基于多 Agent 协作的智能求职助手，把简历优化、
JD 匹配、面试模拟串成自动化流水线。

## Why this project?

The personal story (use in interviews):

> "I submitted 700+ applications in Canada and got fewer than five
> interviews. Existing tools are shallow — Jobscan only matches keywords,
> ChatGPT wrappers fabricate experience. I wanted to build something that
> truly understands the semantics of both resume and JD, and covers the
> full workflow. So I built it, and used it in my own search."

This story works in both markets:
- **Canada:** Interviewers empathize (they've reviewed bad resumes too)
- **China:** Shows product sense + technical ambition

## Architecture

```
┌─────────────────────────────────────────────┐
│           Frontend (React + Vite)            │
│  Upload / JD input / results / chat UI      │
│  React Flow for agent workflow visualization │
└─────────────────────┬───────────────────────┘
                      │ REST (JSON)
┌─────────────────────▼───────────────────────┐
│      Main Service (Spring Boot 3.2)         │
│  Auth / file upload / business logic / DB   │
│  MyBatis + PostgreSQL / Redis cache         │
└─────────────────────┬───────────────────────┘
                      │ REST + Webhook
┌─────────────────────▼───────────────────────┐
│    Agent Service (Python + FastAPI)          │
│  6 Agents orchestrated by LangGraph         │
│  RAG via Qdrant / Anthropic Claude API      │
└─────────────────────────────────────────────┘
```

**Why two services?**
- Spring Boot handles users, files, business logic — plays to Bai's Java
  strength and matches the Canadian job market (Java backend is mainstream)
- Python handles agent logic — LangGraph is Python-native, iteration is
  faster
- Microservice split is itself a resume talking point (architecture
  thinking, async communication, API contracts)

## The 6 Agents

| Agent | Job | Key technique |
|-------|-----|---------------|
| Resume Agent | Parse PDF/DOCX → structured JSON | PDF extraction + LLM structured output |
| JD Agent | Extract requirements from JD text | Prompt + NER |
| Match Agent | Multi-dimension matching score | Vector similarity + scoring algorithm |
| Rewrite Agent | Rewrite bullets for target JD | Fidelity check (no hallucination) |
| Interview Agent | Play interviewer, multi-turn | RAG question bank + state machine |
| Coach Agent | Review interview performance | Structured evaluation |

## Tech stack

| Layer | Tech | Why |
|-------|------|-----|
| Backend | Java 17, Spring Boot 3.2, MyBatis, Spring Security | Canadian market standard; Bai's strongest stack |
| Agent service | Python 3.11, FastAPI, LangGraph, LangChain | Agent ecosystem is Python-native |
| LLM | Anthropic Claude API (Sonnet for speed, Opus for depth) | Best structured output; Bai has existing relationship |
| Frontend | React 18, TypeScript, Vite, TailwindCSS | Modern SPA; Bai has React experience from Vosyn |
| Database | PostgreSQL 16 | Relational + JSONB for flexible agent outputs |
| Vector DB | Qdrant | Rust-based, fast, local-friendly, Java + Python clients |
| Cache | Redis 7 | Session, rate limiting, hot query cache |
| File storage | MinIO (local dev), S3 (prod) | S3-compatible, simple |
| Deployment | Railway (backend), Vercel (frontend), Qdrant Cloud | Free tiers available |

## Non-goals (things we will NOT build)

- ❌ One-click job application (compliance risk)
- ❌ Multi-tenant / team features (B2B = scope creep)
- ❌ Mobile app (web is enough for portfolio)
- ❌ Payment / subscription system (future optional)
- ❌ Real-time voice interview (too complex for MVP)
- ❌ Job board scraping (legal gray area)

## Differentiation from existing products

| Product | Gap | Our edge |
|---------|-----|----------|
| Final Round AI | Only real-time interview help, weak on resume | Full pipeline |
| Jobscan | Keyword matching only, no agents | Semantic matching + multi-agent |
| Simplify | Auto-fill forms, no content optimization | Content generation + rewriting |
| BOSS 智能简历 | One-shot rewrite, no system | Full workflow + fidelity check |
| Coze bots | Prompt wrappers, no engineering depth | Self-built architecture, extensible |

## Learning goals

By the end of this project, Bai should be able to:
1. Design and implement a multi-agent system with state machine orchestration
2. Build a RAG pipeline from scratch (embedding → indexing → retrieval)
3. Architect a Java + Python microservice system with async communication
4. Implement LLM output evaluation (fidelity checking, scoring)
5. Design GDPR/PIPEDA-compliant data flows
6. Explain every architectural decision in a job interview (EN and CN)
