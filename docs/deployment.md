# Deployment Guide

## Table of Contents

1. [Local Development Setup](#1-local-development-setup)
2. [Docker Compose — All-in-One](#2-docker-compose--all-in-one)
3. [Production Deployment Options](#3-production-deployment-options)
4. [Environment Variables Reference](#4-environment-variables-reference)
5. [Monitoring](#5-monitoring)

---

## 1. Local Development Setup

Run each service separately with hot-reload. Recommended when actively developing.

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | Latest | [docker.com/get-started](https://www.docker.com/get-started/) |
| Java | 17+ | `brew install openjdk@17` |
| Python | 3.11+ | `brew install python@3.11` |
| Node | 18+ | `brew install node@18` or [nvm](https://github.com/nvm-sh/nvm) |
| Maven | Bundled | via `./mvnw` wrapper — no separate install needed |

---

### Step 1 — Clone and configure

```bash
git clone https://github.com/zbai53/ai-career.git
cd ai-career
```

Create `.env` files from the templates:

```bash
# Root .env — used by docker-compose for infrastructure passwords
cp .env.example .env

# Agent service .env — must contain ANTHROPIC_API_KEY
cp agent-service/.env.example agent-service/.env

# Backend .env — optional override of application.yml defaults
cp backend/.env.example backend/.env
```

Open `agent-service/.env` and set your API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

### Step 2 — Start infrastructure

Postgres, Redis, Qdrant, and MinIO run in Docker. The application services run on the host.

```bash
docker compose up -d postgres redis qdrant minio
```

Wait ~10 seconds for Postgres to initialize, then verify:

```bash
docker compose ps          # all four should be "running"
docker compose logs postgres | tail -5   # look for "database system is ready"
```

---

### Step 3 — Start the backend (Java)

```bash
cd backend
./mvnw spring-boot:run
```

Flyway migrations run automatically on startup and create all tables.

**Verify:** `curl http://localhost:8080/health` → `{"status":"ok"}`

---

### Step 4 — Start the agent service (Python)

```bash
cd agent-service
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload
```

On first start the service indexes the interview question bank into Qdrant automatically.

**Verify:** `curl http://localhost:8001/health` → `{"status":"ok"}`

**Verify LLM:** `curl http://localhost:8001/health/llm` → `{"status":"ok","model":"..."}`

---

### Step 5 — Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxies all `/api/*` requests to `http://localhost:8080`.

**Verify:** open `http://localhost:5173` in your browser

---

### Health check URLs

| Service | URL | Expected |
|---------|-----|----------|
| Frontend | `http://localhost:5173` | App loads |
| Backend | `http://localhost:8080/health` | `{"status":"ok"}` |
| Backend → Agent | `http://localhost:8080/health/agent` | `{"status":"ok"}` |
| Agent Service | `http://localhost:8001/health` | `{"status":"ok"}` |
| Agent LLM | `http://localhost:8001/health/llm` | `{"status":"ok","model":"..."}` |
| Qdrant | `http://localhost:6333/dashboard` | Dashboard UI |
| MinIO Console | `http://localhost:9001` | Login (minioadmin / minioadmin) |

---

## 2. Docker Compose — All-in-One

Runs every service in a container. Ideal for demos and integration testing.

### Start everything

```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY at minimum

cp agent-service/.env.example agent-service/.env
# edit agent-service/.env — set ANTHROPIC_API_KEY

docker compose up --build
```

Open `http://localhost:3000`.

### Stop and clean up

```bash
docker compose down           # stops containers, keeps volumes
docker compose down -v        # stops and deletes all data volumes
```

### Rebuild a single service

```bash
docker compose build backend
docker compose up -d backend
```

---

### Environment variables used by docker-compose

The `docker-compose.yml` passes environment to each service via `env_file`. The variables it needs in `.env` (root) are:

```bash
# Postgres
POSTGRES_DB=aicareer
POSTGRES_USER=aicareer
POSTGRES_PASSWORD=changeme

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

The agent-service and backend read from their own `env_file` entries:
- `agent-service/.env` → read by the `agent-service` container
- `backend/.env` → read by the `backend` container

---

### Troubleshooting common issues

**Port already in use**

```
Error: address already in use :::5432
```

Something else (a local Postgres, another Docker project) is bound to that port.
Either stop the conflicting process or change the host-side port in `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"    # expose as 5433 on the host instead
```

Then update `POSTGRES_HOST` / `POSTGRES_PORT` accordingly.

---

**Out of memory — containers exit immediately**

Docker Desktop defaults to 2 GB RAM. With all 7 services running (including Qdrant and the
sentence-transformer model loading), you need at least 4 GB.

Docker Desktop → Settings → Resources → Memory → set to 4 GB or more.

---

**`ANTHROPIC_API_KEY` not set — agent calls fail**

Symptom: resume parse or match returns HTTP 500; agent-service log shows `ANTHROPIC_API_KEY is not set`.

Fix:
```bash
# agent-service/.env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Then restart the container:
```bash
docker compose restart agent-service
```

---

**Qdrant collection not found on first interview**

On first start the agent service auto-indexes the question bank into Qdrant. If it starts before
Qdrant is ready, indexing may have been skipped.

Fix — manually trigger indexing:
```bash
curl -X POST http://localhost:8001/api/rag/index
# → {"status":"ok","count":20}
```

---

**Flyway migration error on backend startup**

```
FlywayException: Found non-empty schema(s) ... without schema history table
```

This happens if you ran the backend against a manually-created database. Fix:

```bash
docker compose down -v postgres    # wipe the volume
docker compose up -d postgres
# wait 10s, then restart backend
docker compose restart backend
```

---

**Frontend shows blank page or API 502**

The nginx container proxies `/api/*` to `backend:8080` by hostname. If the backend container
hasn't started yet, requests fail. Wait for the backend health check to pass:

```bash
docker compose logs backend | grep "Started"
```

Then refresh the browser.

---

## 3. Production Deployment Options

### Option A — Railway (recommended for demos)

Railway is the fastest path to a live demo URL. Free tier is sufficient for light usage.

**Services to deploy:**

| Service | Railway component | Notes |
|---------|-------------------|-------|
| Backend | Docker service (from `backend/Dockerfile`) | Set env vars in Railway dashboard |
| Agent Service | Docker service (from `agent-service/Dockerfile`) | Needs `ANTHROPIC_API_KEY` |
| Frontend | Docker service (from `frontend/Dockerfile`) | Or deploy as static site |
| PostgreSQL | Railway PostgreSQL addon | `DATABASE_URL` injected automatically |
| Redis | Railway Redis addon | `REDIS_URL` injected automatically |
| Qdrant | External — use [Qdrant Cloud](https://cloud.qdrant.io/) free tier | Set `QDRANT_HOST` + `QDRANT_PORT` |

**Steps:**

1. Create a Railway project at [railway.app](https://railway.app)
2. Add a PostgreSQL and Redis addon — Railway injects connection strings automatically
3. Deploy each Dockerfile as a separate service:
   - New Service → Deploy from GitHub → select repo → set root directory (`backend/`, `agent-service/`, `frontend/`)
4. Set environment variables per service (see Section 4)
5. Set `AGENT_SERVICE_URL` on the backend service to the Railway internal URL of the agent service
6. Set the frontend's nginx `backend` hostname to the Railway internal URL of the backend

**Notes:**
- Railway services on the same project communicate over a private network
- Generate a public domain for the frontend service only
- Railway's free tier sleeps idle services after inactivity; warm-up takes ~5 seconds

---

### Option B — AWS (production-ready)

For production traffic with SLA requirements.

| Component | AWS Service | Notes |
|-----------|-------------|-------|
| Backend container | ECS Fargate | `t3.small` task (0.5 vCPU / 1 GB) is sufficient for low traffic |
| Agent service container | ECS Fargate | `t3.medium` (1 vCPU / 2 GB) — model loading needs ~800 MB RAM |
| PostgreSQL | RDS (PostgreSQL 16) | `db.t3.micro` for dev; Multi-AZ for production |
| Redis | ElastiCache (Redis 7) | `cache.t3.micro` |
| File storage | S3 | Replace MinIO with an S3 bucket; update `MINIO_*` vars to S3 equivalents |
| Frontend | S3 + CloudFront | Build `frontend/dist/` in CI and sync to S3; CloudFront for CDN + HTTPS |
| Qdrant | Qdrant Cloud or self-hosted on EC2 | Fargate doesn't support persistent volumes well for Qdrant |

**Deployment pattern:**

1. Push Docker images to ECR
2. Define ECS task definitions for backend and agent-service
3. Create an ECS service with an ALB in front
4. Use AWS Secrets Manager for `ANTHROPIC_API_KEY` and DB credentials; inject as env vars in task definition
5. Deploy frontend: `npm run build` → `aws s3 sync dist/ s3://your-bucket` → CloudFront invalidation
6. Point CloudFront `/api/*` behavior to the ALB

---

### Option C — Vercel + Railway (hybrid)

Best cost/effort ratio: Vercel's free tier handles the frontend globally; Railway handles the backend services.

| Component | Platform | Notes |
|-----------|----------|-------|
| Frontend | Vercel | Connect GitHub repo, set root to `frontend/`, build command `npm run build`, output `dist/` |
| Backend | Railway | Docker service |
| Agent Service | Railway | Docker service |
| PostgreSQL | Railway addon | Auto-injected `DATABASE_URL` |
| Redis | Railway addon | Auto-injected `REDIS_URL` |
| Qdrant | Qdrant Cloud free tier | Set `QDRANT_HOST` + `QDRANT_PORT` on agent service |

**Vercel configuration:**

Since the frontend makes relative `/api` calls, set a rewrite rule in `vercel.json` at `frontend/`:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-backend.railway.app/api/:path*"
    }
  ]
}
```

Replace the nginx proxy approach (used in Docker) with Vercel rewrites.

**Steps:**

1. Deploy backend and agent-service to Railway first; note their public URLs
2. Add the Vercel rewrite pointing `/api/*` to the Railway backend URL
3. Connect the frontend repo to Vercel; set environment variables if needed
4. Deploy — Vercel handles CDN, HTTPS, and preview deployments automatically

---

## 4. Environment Variables Reference

### Agent Service (`agent-service/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API key. All 6 agents fail without this. Get one at [console.anthropic.com](https://console.anthropic.com/) |
| `QDRANT_HOST` | No | `localhost` | Hostname of the Qdrant vector database |
| `QDRANT_PORT` | No | `6333` | Port of the Qdrant vector database |

> The agent service has no database of its own — all persistence is handled by the Spring Boot backend.

---

### Backend (`backend/.env` or environment)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_HOST` | No | `localhost` | PostgreSQL hostname |
| `POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `POSTGRES_DB` | No | `aicareer` | Database name |
| `POSTGRES_USER` | No | `aicareer` | Database user |
| `POSTGRES_PASSWORD` | No | `changeme` | Database password — **change in production** |
| `REDIS_HOST` | No | `localhost` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | No | _(empty)_ | Redis password (leave empty if no auth) |
| `AGENT_SERVICE_URL` | No | `http://localhost:8001` | Base URL of the Python agent service |

---

### Infrastructure (root `.env`, used by `docker-compose.yml`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_DB` | No | `aicareer` | Postgres database name (must match backend value) |
| `POSTGRES_USER` | No | `aicareer` | Postgres user (must match backend value) |
| `POSTGRES_PASSWORD` | No | `changeme` | Postgres password — **change in production** |
| `MINIO_ROOT_USER` | No | `minioadmin` | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | No | `minioadmin` | MinIO admin password — **change in production** |

---

### Frontend

The frontend has no runtime environment variables. The API base URL is:

- **Dev:** hardcoded as a Vite proxy from `http://localhost:5173/api` → `http://localhost:8080`
- **Docker:** nginx proxies `/api/*` → `http://backend:8080`
- **Vercel/Railway:** use a `vercel.json` rewrite or equivalent reverse proxy

If you need to point the frontend at a different backend, edit `frontend/vite.config.ts` (dev)
or `frontend/nginx.conf` (Docker).

---

### Production secrets checklist

Before going live, change every default:

- [ ] `POSTGRES_PASSWORD` — use a strong random password (e.g. `openssl rand -base64 32`)
- [ ] `MINIO_ROOT_PASSWORD` — or replace MinIO with S3
- [ ] `ANTHROPIC_API_KEY` — store in a secrets manager (AWS Secrets Manager, Railway secrets, Vercel env)
- [ ] `REDIS_PASSWORD` — enable Redis AUTH in production
- [ ] Never commit `.env` files to git — they are in `.gitignore`

---

## 5. Monitoring

### Built-in: agent_runs table

Every Claude API call is logged to the `agent_runs` table in PostgreSQL. Query it directly
or use the `/api/agent-runs/recent` endpoint.

```sql
-- LLM cost snapshot: tokens consumed per agent in the last 7 days
SELECT
    agent_name,
    COUNT(*)                         AS calls,
    SUM(token_count)                 AS total_tokens,
    ROUND(AVG(duration_ms))          AS avg_ms,
    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors
FROM agent_runs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY agent_name
ORDER BY total_tokens DESC;
```

```sql
-- p95 latency per agent
SELECT
    agent_name,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
FROM agent_runs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_name;
```

---

### Key metrics to watch

| Metric | Source | What to look for |
|--------|--------|-----------------|
| **Requests / day** | `agent_runs` COUNT by day | Unexpected spikes may indicate loops or abuse |
| **Avg latency** | `agent_runs.duration_ms` | Resume parse > 10s or rewrite > 60s suggests model degradation |
| **Token consumption** | `agent_runs.token_count` | Track against Anthropic quota limits |
| **Error rate** | `agent_runs` WHERE `status = 'error'` | > 5% sustained error rate warrants investigation |
| **Fidelity failures** | `rewrite_results.fidelity_status` | High `"failed"` rate means rewrite prompts need tuning |
| **Interview completion** | `interview_sessions` WHERE `status = 'completed'` | Drop-off before completion = UX issue |

---

### Anthropic usage dashboard

Track API costs at [console.anthropic.com/usage](https://console.anthropic.com/usage).
The default model is `claude-haiku-4-5-20251001` — Haiku is significantly cheaper than Sonnet
and sufficient for structured extraction and scoring tasks.

Approximate cost per full workflow (parse + match + rewrite + interview):

| Operation | Typical tokens | Approx cost (Haiku) |
|-----------|---------------|---------------------|
| Resume parse | ~2,000 | ~$0.001 |
| JD parse | ~1,500 | ~$0.001 |
| Match + gap analysis | ~1,500 | ~$0.001 |
| Rewrite (1 attempt) | ~2,500 | ~$0.002 |
| Interview (5 questions) | ~5,000 | ~$0.004 |
| Coach review | ~2,000 | ~$0.002 |
| **Full workflow total** | **~14,500** | **~$0.011** |

> Prices are estimates based on Haiku input/output rates as of mid-2025. Check Anthropic's
> [pricing page](https://www.anthropic.com/pricing) for current rates.
