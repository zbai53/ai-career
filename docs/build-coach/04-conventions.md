# 04 — Engineering Conventions

## Repository structure

```
ai-career/
├── backend/                 # Spring Boot main service
│   ├── src/main/java/com/aicareer/
│   │   ├── config/          # Spring config, security, CORS
│   │   ├── controller/      # REST controllers
│   │   ├── service/         # Business logic
│   │   ├── mapper/          # MyBatis mappers
│   │   ├── model/           # Domain models / DTOs
│   │   └── util/            # Helpers (PII masker, etc.)
│   └── src/main/resources/
│       ├── application.yml
│       └── db/migration/    # Flyway SQL scripts
├── agent-service/           # Python + FastAPI
│   ├── app/
│   │   ├── agents/          # One file per agent
│   │   ├── graph/           # LangGraph state + graph definition
│   │   ├── models/          # Pydantic schemas
│   │   ├── rag/             # Vector store + embedding logic
│   │   └── main.py          # FastAPI app
│   ├── tests/
│   └── requirements.txt
├── frontend/                # React + Vite
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── api/             # API client (axios)
│       └── stores/          # Zustand stores
├── docker-compose.yml
├── docs/
│   ├── build-coach/         # These files
│   ├── schemas/             # JSON schema docs
│   ├── evaluation/          # Eval results and notes
│   └── architecture.md      # System architecture doc
├── .env.example
└── README.md
```

## Git conventions

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

<optional body>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

**Scopes:** `backend`, `agent`, `frontend`, `infra`, `docs`

**Examples:**
```
feat(agent): implement resume parsing agent with PDF support
fix(backend): handle null JD source URL in match endpoint
test(agent): add 5 real-resume test cases for resume agent
docs: update architecture diagram with RAG flow
refactor(frontend): extract match score radar into reusable component
chore(infra): add Qdrant to docker-compose
```

### Branch strategy

Work on `main` for solo development. Use feature branches only if a
change spans 3+ days:

```
feat/interview-agent
feat/react-workflow-viz
fix/fidelity-false-positives
```

### Commit frequency

At least 1 meaningful commit per session. "Meaningful" = not just
whitespace or comment changes. The GitHub contribution graph matters.

## Java / Spring Boot conventions

- **Java version:** 17 (LTS)
- **Spring Boot version:** 3.2.x
- **Package naming:** `com.aicareer.<module>`
- **Controller naming:** `XxxController` → maps to `/api/xxx`
- **Service naming:** `XxxService` (interface) + `XxxServiceImpl`
- **DTO naming:** `XxxRequest`, `XxxResponse`
- **MyBatis:** XML mappers in `resources/mapper/`. Avoid annotations for
  complex queries.
- **Flyway:** Migration files: `V1__create_users_table.sql`,
  `V2__create_resumes_table.sql`, etc.
- **Error handling:** Global `@ControllerAdvice` with standardized error
  response format:
  ```json
  {
    "error": "RESUME_PARSE_FAILED",
    "message": "Could not extract text from uploaded PDF",
    "timestamp": "2025-06-04T12:00:00Z"
  }
  ```
- **Logging:** SLF4J. Log agent calls with duration and token count.
- **Testing:** JUnit 5 + Mockito. Integration tests use Testcontainers
  for PostgreSQL.

## Python conventions

- **Python version:** 3.11+
- **Formatter:** `ruff format`
- **Linter:** `ruff check`
- **Type hints:** Required on all function signatures
- **Pydantic:** All LLM inputs and outputs must have a Pydantic model
- **Agent file naming:** `agents/resume_agent.py`,
  `agents/jd_agent.py`, etc.
- **Testing:** pytest. Each agent gets at least 5 test cases with real
  data.
- **Error handling:** Never let an agent crash silently. Catch exceptions,
  log them, return a structured error to Spring Boot.

## React conventions

- **State management:** Zustand (not Redux — overkill for this project)
- **Data fetching:** TanStack Query (React Query)
- **HTTP client:** axios with a configured instance in `api/client.ts`
- **Styling:** TailwindCSS utility classes. No CSS modules, no styled-
  components.
- **Component structure:** One component per file. Named exports.
  Props typed with TypeScript interfaces.
- **Pages:** One file per route in `pages/`. Lazy loaded.

## API contract

Spring Boot ↔ Python service communication:

- **Protocol:** HTTP REST (JSON)
- **Async pattern:** For long tasks (resume parsing, matching, rewriting):
  Spring Boot sends request → Python returns `202 Accepted` with
  `task_id` → Python sends result via webhook when done → Spring Boot
  persists result.
- **Health check:** Both services expose `GET /health` returning
  `{"status": "ok"}`.
- **Error format:** Same JSON structure across both services.

## Data privacy rules

These are code-level rules, not just documentation:

1. **Before any LLM call:** Replace PII (name, email, phone, address)
   with placeholders: `[NAME]`, `[EMAIL]`, `[PHONE]`, `[ADDRESS]`
2. **After LLM response:** Replace placeholders back with real values
3. **File storage:** Raw resume files get a 24h TTL in S3/MinIO
4. **Database:** Never store raw resume text — only parsed JSON
5. **Logging:** Never log PII. The `agent_runs` table stores
   `input_summary` and `output_summary`, not full content
6. **User deletion:** `DELETE /api/users/me/data` cascades to all
   related tables
