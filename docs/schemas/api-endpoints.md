# API Endpoints Reference

All endpoints accept and return `application/json` unless otherwise noted.

---

## Agent Service — port 8001

### Health

#### `GET /health`

Returns service liveness.

**Response 200**
```json
{ "status": "ok" }
```

---

#### `GET /health/llm`

Sends a minimal prompt to Claude to confirm the Anthropic API is reachable.

**Response 200**
```json
{ "status": "ok", "model": "claude-haiku-4-5-20251001" }
```

**Response 503**
```json
{ "status": "llm-unavailable", "error": "<exception message>" }
```

---

### Resume

#### `POST /api/resume/parse`

Parse a resume file and return structured JSON.

**Request** — `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | binary | yes | `.pdf` or `.docx` only |

**Response 200** — [`ParsedResume`](resume-schema.md) JSON object

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Unsupported file extension | `{"detail": "Unsupported file type '...'. Allowed: .pdf, .docx"}` |
| 500 | Text extraction or LLM parse failure | `{"detail": "<error message>"}` |

---

### Job Description

#### `POST /api/jd/parse`

Parse a job description from raw text or a URL.

**Request** — `application/json`

```json
{
  "text": "We are hiring a senior backend engineer ...",
  "url":  "https://example.com/jobs/123"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string \| null | conditional | Raw JD text. At least one of `text` or `url` must be provided. |
| `url`  | string \| null | conditional | Public HTTP/HTTPS URL of a job posting page. Ignored if `text` is also provided. |

**Response 200** — [`ParsedJobDescription`](jd-schema.md) JSON object

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Neither `text` nor `url` provided | `{"detail": "Provide either 'text' or 'url'."}` |
| 500 | URL fetch failure, non-HTML content, or LLM parse failure | `{"detail": "<error message>"}` |

---

### Match

#### `POST /api/match`

Match a parsed resume against a parsed job description and return similarity scores plus gap analysis.

**Request** — `application/json`

```json
{
  "resume": { /* ParsedResume object */ },
  "jd":     { /* ParsedJobDescription object */ }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resume` | object | yes | Full `ParsedResume` JSON (see [resume-schema.md](resume-schema.md)) |
| `jd` | object | yes | Full `ParsedJobDescription` JSON (see [jd-schema.md](jd-schema.md)) |

**Response 200**

```json
{
  "overall_score": 72.3,
  "skill_score": 66.0,
  "experience_score": 69.0,
  "keyword_score": 87.5,
  "missing_required_skills": ["Kafka"],
  "missing_preferred_skills": ["AWS", "Kubernetes"],
  "improvement_suggestions": ["..."],
  "interview_focus_areas": ["..."],
  "overall_assessment": "Jordan is a solid mid-level backend candidate...",
  "agent_run": {
    "agent_name": "match_agent",
    "input_summary": "resume skills=13, jd=Backend Java Engineer",
    "output_summary": "overall=72.3, skill=66.0",
    "status": "success",
    "duration_ms": 1240,
    "token_count": 850,
    "model_name": "claude-haiku-4-5-20251001",
    "error_message": null,
    "created_at": "2026-06-17T10:23:01.123456+00:00"
  }
}
```

**Score formula**

```
overall_score = skill_score × 0.45 + experience_score × 0.30 + keyword_score × 0.25
```

All component scores are on a 0–100 scale. See [match-eval-v1.md](../evaluation/match-eval-v1.md) for algorithm details.

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 422 | Malformed request body | `{"detail": [...]}` |
| 500 | Gap analysis LLM failure (after retry) | `{"detail": "<error message>"}` |

---

### Rewrite

#### `POST /api/rewrite`

Rewrite resume bullet points to better match a job description.  Accepts
already-parsed resume and JD objects plus the match result from `POST /api/match`.
For the one-shot upload flow, use `POST /api/pipeline/run` instead.

**Request** — `application/json`

```json
{
  "resume":       { /* ParsedResume object */ },
  "jd":           { /* ParsedJobDescription object */ },
  "match_result": { /* MatchResult object from POST /api/match */ }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resume` | object | yes | Full `ParsedResume` JSON (see [resume-schema.md](resume-schema.md)) |
| `jd` | object | yes | Full `ParsedJobDescription` JSON (see [jd-schema.md](jd-schema.md)) |
| `match_result` | object | yes | Full match result including `gap_analysis` (from `POST /api/match`) |

**Response 200**

```json
{
  "experiences": [
    {
      "company": "Initech",
      "title": "Backend Developer",
      "original_bullets": [
        "Built REST API using Java",
        "Maintained PostgreSQL database"
      ],
      "rewritten_bullets": [
        {
          "original": "Built REST API using Java",
          "rewritten": "Engineered RESTful APIs in Java to support distributed service communication.",
          "changes_made": [
            "Replaced weak verb 'Built' with 'Engineered'",
            "Added 'distributed service' framing to align with JD microservices context"
          ]
        },
        {
          "original": "Maintained PostgreSQL database",
          "rewritten": "Owned PostgreSQL database layer ensuring high availability and query performance.",
          "changes_made": [
            "Replaced passive 'Maintained' with ownership framing",
            "Added JD keyword 'high availability'"
          ]
        }
      ]
    }
  ],
  "keywords_injected": ["distributed", "high availability"],
  "overall_improvement_summary": "Reframed two bullets to better target the Senior Backend Engineer role by highlighting architectural context and ownership language. Fidelity checks passed on first attempt.",
  "rewrite_confidence": 0.88,
  "fidelity_report": {
    "fidelity_score": 1.0,
    "passed": true,
    "flags": []
  },
  "rewrite_attempts": 1,
  "improvement_metrics": {
    "keywords_added": ["distributed", "high availability"],
    "keywords_removed": [],
    "avg_bullet_length_change": 0.32,
    "action_verbs_improved": 2
  },
  "fidelity_status": "passed",
  "agent_run": {
    "agent_name": "rewrite_agent",
    "input_summary": "resume skills=3, jd=Senior Backend Engineer",
    "output_summary": "1 experience rewritten, fidelity=passed, attempts=1",
    "status": "success",
    "duration_ms": 2340,
    "token_count": 1120,
    "model_name": "claude-haiku-4-5-20251001",
    "error_message": null,
    "created_at": "2026-06-21T10:45:12.000000+00:00"
  }
}
```

**Response fields**

| Field | Type | Notes |
|-------|------|-------|
| `experiences` | array | One entry per resume experience; same order as input resume |
| `experiences[].rewritten_bullets` | array | One `RewrittenBullet` per original bullet, in the same order |
| `keywords_injected` | array | JD keywords successfully injected (present in rewrites, absent from originals) |
| `rewrite_confidence` | float | Model confidence 0.0–1.0 that the rewrite improves match without fabrication |
| `fidelity_report.fidelity_score` | float | 0.0 (full hallucination) → 1.0 (perfectly faithful) |
| `fidelity_report.passed` | boolean | `true` if `fidelity_score >= 0.90` (STRICT threshold) |
| `fidelity_report.flags` | array | Flagged entities by severity: `"high"` (company/title/date), `"medium"` (tech/metric), `"low"` (contextual) |
| `fidelity_status` | string | `"passed"` ≥ 0.90 · `"warning"` ≥ 0.80 · `"failed"` < 0.80 |
| `rewrite_attempts` | int | `1` = passed first try · `2` = fidelity retry triggered |
| `improvement_metrics.action_verbs_improved` | int | Count of weak verbs replaced with stronger equivalents |

**Fidelity guardrails**

The agent uses a two-layer fidelity system:

1. **Prompt constraints** — The system prompt explicitly prohibits adding technologies,
   metrics, leadership claims, or credentials not present in the original resume.
2. **Post-hoc verification** — `FidelityChecker` extracts named entities from both
   the original and rewritten bullets and flags any new entity.  If `fidelity_score < 0.80`
   (WARN threshold), the agent retries once with the flagged entities listed explicitly
   in the retry prompt.

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | `resume` or `jd` fails Pydantic validation | `{"error": "Validation failed: <detail>"}` |
| 500 | Rewrite or fidelity check failure | `{"error": "Rewrite failed: <detail>"}` |

---

### Pipeline

#### `POST /api/pipeline/run`

One-click browser-friendly endpoint: upload a resume file and paste JD text to
receive the complete workflow result (parse resume → parse JD → match → route)
in a single call.  Handles temporary file management internally.

**Request** — `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | binary | yes | `.pdf` or `.docx` |
| `jd_text` | string | yes | Raw JD text (not a URL) |
| `user_id` | string | no | Defaults to `"default"` |

**Response 200**

```json
{
  "current_step":    "reviewing",
  "resume":          { /* ParsedResume */ },
  "jd":              { /* ParsedJobDescription */ },
  "match_result": {
    "overall_score": 78.2,
    "skill_score":   70.0,
    "experience_score": 100.0,
    "keyword_score": 66.7,
    "gap_analysis":  { "..." : "..." }
  },
  "routing":         "interview",
  "workflow_status": "completed",
  "steps_completed": ["parse_resume", "parse_jd", "match"],
  "total_duration_ms": 3420,
  "total_tokens":    1840,
  "agent_runs":      [ /* log entries */ ],
  "error":           null
}
```

| Field | Type | Notes |
|-------|------|-------|
| `routing` | `"interview"` \| `"rewrite"` | `"interview"` when `overall_score >= 70` |
| `workflow_status` | string | `"completed"`, `"degraded"`, or `"failed"` |
| `steps_completed` | `list[string]` | Node names of all successful agent steps |
| `total_duration_ms` | integer | Sum of `duration_ms` across all agent runs |
| `total_tokens` | integer | Sum of `token_count` across all agent runs |

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Unsupported file extension | `{"error": "Unsupported file type '...'. Upload a .pdf or .docx file."}` |
| 500 | Any agent or graph failure | `{"error": "<message>", "workflow_status": "failed", "agent_runs": [...]}` |

---

### Workflow

#### `POST /api/workflow/run`

Invoke the full LangGraph workflow with explicit file paths.  Intended for
server-to-server calls from Spring Boot (which has already persisted the files)
rather than for browser clients.  For browser use, prefer `POST /api/pipeline/run`.

**Request** — `application/json`

```json
{
  "user_id":          "user-42",
  "resume_file_path": "/data/uploads/jane_doe.pdf",
  "jd_text":          "We are hiring a backend engineer...",
  "thread_id":        "user-42-resume-1-jd-3"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_id` | string | yes | Scopes the checkpoint namespace |
| `resume_file_path` | string \| null | no | Absolute path to the resume on the agent-service host |
| `jd_text` | string \| null | no | Raw JD text or a `https://` URL |
| `thread_id` | string \| null | no | Explicit checkpoint ID; defaults to `user_id` |

**Response 200** — Full `JobHelperState` dict merged with summary fields (same shape as `POST /api/pipeline/run`, without the `routing` field).

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 500 | Any agent or graph failure | `{"error": "<message>", "workflow_status": "failed", "agent_runs": [...]}` |

---

#### `GET /api/workflow/status/{thread_id}`

Return the current checkpoint state for a running or completed workflow.
Safe to poll repeatedly; read-only — does not advance the graph.

**Path parameter:** `thread_id` — the ID passed when invoking the workflow.

**Response 200**

```json
{
  "thread_id":    "user-42-resume-1-jd-3",
  "current_step": "matching",
  "next":         ["__after_match__"],
  "is_complete":  false,
  "error":        null,
  "match_result": null,
  "agent_runs":   2,
  "created_at":   "2026-06-18T10:15:03.421Z"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `next` | `list[string]` | Pending node names; `[]` when the workflow has finished |
| `is_complete` | boolean | `true` when `next == []` |
| `agent_runs` | integer | Count of accumulated agent_run entries (not the full list) |

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | No checkpoint found for `thread_id` | `{"error": "No checkpoint found for thread_id '...': <detail>"}` |

---

#### `GET /api/workflow/visualize`

Return the Mermaid diagram source of the compiled workflow graph.

**Response 200**

```json
{
  "mermaid": "---\nconfig:\n  flowchart:\n    curve: linear\n---\ngraph TD;\n    __start__..."
}
```

---

#### `GET /api/workflow/visualize/html`

Return an HTML page that renders the workflow diagram in the browser via
Mermaid JS (CDN-hosted).  Open directly in a browser tab.

**Response 200** — `text/html`

The rendered page includes the full graph diagram with:
- Node shapes matching LangGraph conventions (rounded boxes for nodes, diamonds for routers)
- Solid edges for unconditional transitions, dashed edges for conditional ones
- A styled layout via the linear curve Mermaid config

---

## Main Service (Spring Boot) — port 8080

### Health

#### `GET /health`

Returns service liveness.

**Response 200**
```json
{ "status": "ok" }
```

---

#### `GET /health/agent`

Proxies a liveness check to the Agent Service.

**Response 200** — Agent Service response body (passthrough)

**Response 503**
```json
{ "status": "agent-service-unavailable" }
```

---

### Resume

#### `POST /api/resumes/parse`

Upload a resume file. The backend saves the file temporarily, forwards it to the Agent Service, then deletes the local copy.

**Request** — `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | binary | yes | `.pdf` or `.docx` only |

**Response 200** — [`ParsedResume`](resume-schema.md) JSON object (forwarded from Agent Service)

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Unsupported file extension | `{"error": "Unsupported file type '...'. Upload a .pdf or .docx file."}` |
| 500 | Agent Service unreachable or parse failure | `{"error": "Failed to parse resume: <message>"}` |

---

### Job Description

#### `POST /api/jds/parse`

Submit a job description for parsing. Exactly one of `text` or `url` must be provided (Bean Validation enforced).

**Request** — `application/json`

```json
{
  "text": "We are hiring a senior backend engineer ...",
  "url":  "https://example.com/jobs/123"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string \| null | conditional | Raw JD text. At least one of `text` or `url` must be non-blank. |
| `url`  | string \| null | conditional | Public HTTP/HTTPS URL of a job posting page. |

**Response 200** — [`ParsedJobDescription`](jd-schema.md) JSON object (forwarded from Agent Service)

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Neither `text` nor `url` is provided (Bean Validation failure) | `{"error": "<constraint message>"}` |
| 500 | Agent Service unreachable, URL fetch failure, or parse failure | `{"error": "Failed to parse job description: <message>"}` |

---

### Match

#### `POST /api/match`

Match a previously-parsed resume against a previously-parsed job description. The backend fetches both records, forwards them to the Agent Service, persists the result, and saves the agent run log.

**Request** — `application/json`

```json
{
  "resumeId": 1,
  "jdId":     2
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resumeId` | Long | yes | ID of a previously parsed resume (from `POST /api/resumes/parse`) |
| `jdId` | Long | yes | ID of a previously parsed job description (from `POST /api/jds/parse`) |

**Response 200** — `MatchResult` JSON forwarded from Agent Service, merged with the persisted entity `id`

```json
{
  "id": 7,
  "resumeId": 1,
  "jdId": 2,
  "overallScore": 72.3,
  "skillScore": 66.0,
  "experienceScore": 69.0,
  "keywordScore": 87.5,
  "missingRequiredSkills": ["Kafka"],
  "missingPreferredSkills": ["AWS", "Kubernetes"],
  "improvementSuggestions": ["..."],
  "interviewFocusAreas": ["..."],
  "overallAssessment": "Jordan is a solid mid-level backend candidate...",
  "agent_run": { /* AgentRun object — see below */ }
}
```

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | Resume or JD not found | `{"error": "Resume not found: <id>"}` |
| 500 | Agent Service unreachable or match failure | `{"error": "Failed to match: <message>"}` |

---

#### `GET /api/match/{id}`

Retrieve a previously computed match result by its database ID.

**Path parameter**

| Parameter | Type | Notes |
|-----------|------|-------|
| `id` | Long | Match result ID returned from `POST /api/match` |

**Response 200** — `MatchResult` entity JSON (same shape as `POST /api/match` response)

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | No match result with that ID | `{"error": "Match result not found: <id>"}` |

---

### Workflow (Spring Boot orchestrated)

These endpoints implement the same match → rewrite flow as Python's `POST /api/pipeline/run`,
but with Spring Boot controlling the persistence order and providing retrieval by ID.
Use this path when you need direct DB control; use `POST /api/pipeline/run` for the
single-call browser-friendly upload flow.

#### `POST /api/workflow/full`

Spring Boot-orchestrated full workflow: load resume and JD from DB, call Python match,
conditionally call Python rewrite, persist both results, return combined response.

**Request** — `application/json`

```json
{
  "resumeId": 1,
  "jdId":     2
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resumeId` | Long | yes | ID of a previously parsed resume |
| `jdId` | Long | yes | ID of a previously parsed job description |

**Flow**

1. Load resume and JD from `resumes` / `job_descriptions` tables.
2. Call Python `POST /api/match` → persist to `match_results`.
3. If `overall_score < 70` → call Python `POST /api/rewrite` → persist to `rewrite_results`.
4. Persist all `agent_run` entries from both calls.
5. Return combined response.

**Response 200**

```json
{
  "match_result_id":   7,
  "overall_score":     58.4,
  "skill_score":       52.0,
  "experience_score":  60.0,
  "keyword_score":     65.0,
  "gap_analysis":      { /* full MatchResult JSON from Python */ },
  "rewrite_triggered": true,
  "rewrite_result_id": 3,
  "rewrite_attempts":  1,
  "fidelity_score":    0.95,
  "fidelity_status":   "passed",
  "fidelity_report":   { "fidelity_score": 0.95, "passed": true, "flags": [] },
  "rewrite_result":    { /* full RewriteResult JSON from Python */ }
}
```

When `overall_score >= 70` the rewrite fields are absent and `rewrite_triggered` is `false`.

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | Resume or JD not found | (empty 404 body) |
| 500 | Match or rewrite agent failure | `{"error": "Full workflow failed: <message>"}` |

---

#### `GET /api/workflow/full/{matchResultId}`

Retrieve a previously saved full workflow result by its `match_result` ID.
Includes the most recent rewrite result for the same resume+JD pair, if one exists.

**Path parameter**

| Parameter | Type | Notes |
|-----------|------|-------|
| `matchResultId` | Long | ID returned from `POST /api/workflow/full` or `POST /api/match` |

**Response 200**

```json
{
  "match_result_id":   7,
  "resume_id":         1,
  "jd_id":             2,
  "overall_score":     58.4,
  "skill_score":       52.0,
  "experience_score":  60.0,
  "keyword_score":     65.0,
  "created_at":        "2026-06-21T10:45:12",
  "gap_analysis":      { /* MatchResult JSON */ },
  "rewrite_triggered": true,
  "rewrite_result_id": 3,
  "rewrite_attempts":  1,
  "fidelity_score":    0.95,
  "fidelity_status":   "passed",
  "fidelity_report":   { "fidelity_score": 0.95, "passed": true, "flags": [] },
  "rewrite_result":    { /* RewriteResult JSON */ }
}
```

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | No match result with that ID | (empty 404 body) |
| 500 | JSON parse failure on stored data | `{"error": "Failed to retrieve workflow result: <message>"}` |

---

### Agent Runs

#### `GET /api/agent-runs/recent`

Return the most recent agent run records across all agents, ordered by `created_at` descending.

**Query parameters**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `limit` | int | 20 | Maximum number of records to return |

**Response 200**

```json
[
  {
    "id": 42,
    "userId": null,
    "agentName": "match_agent",
    "inputSummary": "resume skills=13, jd=Backend Java Engineer",
    "outputSummary": "overall=72.3, skill=66.0",
    "status": "success",
    "durationMs": 1240,
    "tokenCount": 850,
    "modelName": "claude-haiku-4-5-20251001",
    "errorMessage": null,
    "createdAt": "2026-06-17T10:23:01"
  }
]
```

**AgentRun fields**

| Field | Type | Notes |
|-------|------|-------|
| `id` | Long | Auto-generated primary key |
| `userId` | Long \| null | Reserved for future auth; currently null |
| `agentName` | string | One of `resume_agent`, `jd_agent`, `match_agent` |
| `inputSummary` | string | First 100 chars of the agent input (filename or text snippet) |
| `outputSummary` | string | Brief summary of what was produced |
| `status` | string | `"success"` or `"error"` |
| `durationMs` | int | Wall-clock time for the agent call in milliseconds |
| `tokenCount` | int | Total input + output tokens consumed across all Claude calls |
| `modelName` | string | Claude model ID used |
| `errorMessage` | string \| null | Populated only on `"error"` status |
| `createdAt` | datetime | UTC timestamp of the agent run |

---

### Interview

The interview system runs as a multi-turn mock interview session.  Spring Boot (`/api/interviews/*`) owns DB persistence; the Python agent service (`/api/interview/*`) owns in-memory session state and Claude calls.  The Python `session_id` (UUID) is the path variable used across all subsequent calls.

---

#### `POST /api/interviews/start`  *(Spring Boot)*

Start a new interview session.  Loads the resume and JD from the database, delegates to the agent service to build the question set and return the first question, and persists a new `interview_sessions` row.

**Request** — `application/json`

```json
{
  "resumeId":    1,
  "jdId":        2,
  "numQuestions": 5
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resumeId` | Long | yes | ID from `POST /api/resumes/parse` |
| `jdId` | Long | yes | ID from `POST /api/jds/parse` |
| `numQuestions` | Integer | no | Defaults to `5`; distribution is 60% technical / 40% behavioral |

**Response 200**

```json
{
  "db_id":           3,
  "session_id":      "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "question":        "Tell me about a time you had to debug a production issue under pressure.",
  "question_number": 1,
  "total_questions": 5,
  "type":            "behavioral",
  "difficulty":      "medium"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `db_id` | Long | Primary key of the `interview_sessions` row — use for DB lookups |
| `session_id` | string (UUID) | Python session identifier — use as path variable for all subsequent calls |
| `question` | string | First interview question text |
| `question_number` | int | Always `1` on start |
| `total_questions` | int | Total questions in this session |
| `type` | string | `"technical"` or `"behavioral"` |
| `difficulty` | string | `"easy"`, `"medium"`, or `"hard"` |

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `resumeId` or `jdId` not found | (empty body) |
| 500 | Agent service unreachable or question RAG failure | `{"error": "<message>"}` |

---

#### `POST /api/interviews/{sessionId}/answer`  *(Spring Boot)*

Submit a candidate answer for the currently active question.  The agent service evaluates the answer, decides the next action (`follow_up`, `re_answer`, or `next_question`), and updates conversation history.  Spring Boot persists the updated conversation to the DB.

**Path parameter:** `sessionId` — the Python UUID from `POST /api/interviews/start`

**Request** — `application/json`

```json
{
  "answer": "We were seeing 500ms latency spikes on our payments service..."
}
```

**Response 200 — mid-session**

```json
{
  "evaluation": {
    "relevance_score":     8.0,
    "depth_score":         7.0,
    "communication_score": 9.0,
    "overall_score":       7.9,
    "strengths":           ["Clear STAR structure", "Concrete metrics"],
    "improvements":        ["Add more on root cause analysis"],
    "follow_up":           "What monitoring tools did you use?",
    "next_action":         "next_question"
  },
  "next_action":          "next_question",
  "next_content":         "Walk me through how you would design a URL shortener.",
  "question_number":      2,
  "total_questions":      5,
  "follow_up_count":      0,
  "conversation_history": [
    { "role": "candidate",   "content": "We were seeing 500ms...", "turn_number": 1 },
    { "role": "interviewer", "content": "Walk me through...",      "turn_number": 2 }
  ],
  "is_complete": false
}
```

**Response 200 — session exhausted**

```json
{
  "next_action":  "done",
  "is_complete":  true,
  "message":      "Interview complete. Call POST /end for your review."
}
```

**`next_action` values**

| Value | Meaning | `next_content` |
|-------|---------|----------------|
| `next_question` | Answer was strong enough (overall ≥ 7) or follow-up cap reached | Next main question text |
| `follow_up` | Answer was on-topic but lacked depth (depth < 5) | Follow-up probe question |
| `re_answer` | Answer was off-topic (relevance < 5) | Re-prompt repeating the question |
| `done` | All questions exhausted | `null` |

**Follow-up cap:** at most 2 follow-up probes per main question; the 3rd answer always advances regardless of score.

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `sessionId` not found | (empty body) |
| 409 | Session already completed | `{"error": "Session is already completed"}` |
| 500 | Agent service evaluation failure | `{"error": "<message>"}` |

---

#### `GET /api/interviews/{sessionId}`  *(Spring Boot)*

Retrieve the current state of a session: DB metadata merged with the live agent-service state.

**Path parameter:** `sessionId` — Python UUID

**Response 200**

```json
{
  "db_id":          3,
  "session_id":     "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status":         "active",
  "question_count": 2,
  "started_at":     "2026-06-22T14:30:00",
  "ended_at":       null,
  "agent_state": {
    "session_id":             "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "jd_title":               "Senior Backend Engineer",
    "status":                 "active",
    "questions_completed":    2,
    "current_question":       { "text": "Walk me through...", "type": "technical", "difficulty": "medium" },
    "total_questions":        5,
    "current_question_index": 3,
    "questions_asked":        [ { "question_number": 1, "text": "...", "type": "behavioral", "difficulty": "medium" }, "..." ],
    "answers":                [ /* AnswerEvaluation objects */ ],
    "conversation_history":   [ /* turn objects */ ],
    "follow_up_counts":       { "0": 1 },
    "started_at":             "2026-06-22T14:30:00.000Z",
    "ended_at":               null
  }
}
```

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `sessionId` not found | (empty body) |
| 500 | Agent service unreachable | `{"error": "<message>"}` |

---

#### `POST /api/interviews/{sessionId}/end`  *(Spring Boot)*

Mark the session complete, retrieve the full summary from the agent service, and persist the final state (status, conversation history, review JSON) to the DB.

**Path parameter:** `sessionId` — Python UUID

**Request** — no body

**Response 200**

```json
{
  "session_id":         "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "jd_title":           "Senior Backend Engineer",
  "status":             "completed",
  "total_questions":    5,
  "questions_answered": 5,
  "average_scores": {
    "relevance":     7.4,
    "depth":         6.8,
    "communication": 8.1,
    "overall":       7.3
  },
  "questions": [ /* InterviewQuestion objects */ ],
  "answers": [
    {
      "question":            "Tell me about a time...",
      "answer":              "We were seeing 500ms latency...",
      "relevance_score":     8.0,
      "depth_score":         7.0,
      "communication_score": 9.0,
      "overall_score":       7.9,
      "strengths":           ["Clear STAR structure"],
      "improvements":        ["Add root cause detail"],
      "follow_up":           "What monitoring tools did you use?"
    }
  ],
  "conversation_history": [ /* full ordered turn log */ ],
  "follow_up_counts":     { "0": 1, "2": 0 },
  "started_at":           "2026-06-22T14:30:00.000Z",
  "ended_at":             "2026-06-22T14:52:14.000Z"
}
```

**DB updates on success**

| Column | Value |
|--------|-------|
| `status` | `"completed"` |
| `ended_at` | current timestamp |
| `conversation` | full `conversation_history` JSON array |
| `review` | full response JSON (summary + scores) |

**Error responses**

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `sessionId` not found | (empty body) |
| 500 | Agent service failure | `{"error": "<message>"}` |

---

## Cross-Service Flow

```
Browser / API Client
  │
  ▼
Main Service :8080
  │  POST /api/resumes/parse      (multipart) ──────────────────┐
  │  POST /api/jds/parse          (JSON)                         │
  │  POST /api/match              (JSON: resumeId + jdId)  ──────┤
  │  POST /api/workflow/run       (JSON: resumeId + jdId)  ──────┤
  │  POST /api/workflow/full      (JSON: resumeId + jdId)  ──────┤
  │  GET  /api/workflow/full/{id} (DB + agent-service calls) ────┤
  │  GET  /api/workflow/status/{threadId}  ──────────────────────┤
  │  POST /api/interviews/start            ──────────────────────┤
  │  POST /api/interviews/{id}/answer      ──────────────────────┤
  │  GET  /api/interviews/{id}             ──────────────────────┤
  │  POST /api/interviews/{id}/end         ──────────────────────┤
  │  GET  /api/match/{id}         (DB lookup, no agent call)     │
  │  GET  /api/agent-runs/recent  (DB lookup, no agent call)     │
  │                                                               │
  ▼                                                               │
Agent Service :8001  ◄───────────────────────────────────────────┘
  │
  ├── POST /api/resume/parse          (multipart, forwarded bytes)
  ├── POST /api/jd/parse              (JSON, text or url)
  ├── POST /api/match                 (JSON: resume + jd objects)
  ├── POST /api/rewrite               (JSON: resume + jd + match_result)
  ├── POST /api/pipeline/run          (multipart: file + jd_text)
  ├── POST /api/workflow/run          (JSON: file path + jd text)
  ├── GET  /api/workflow/status/{id}  (checkpoint poll, read-only)
  ├── POST /api/interview/start       (JSON: jd + resume + num_questions)
  ├── POST /api/interview/{id}/answer (JSON: answer)
  ├── GET  /api/interview/{id}        (live session state)
  ├── POST /api/interview/{id}/end    (summary + average scores)
  ├── GET  /api/workflow/visualize    (Mermaid JSON)
  └── GET  /api/workflow/visualize/html (rendered diagram page)
  │
  ▼
LangGraph Workflow (in-process)
  parse_resume → parse_jd → match → (rewrite | interview) → review
  │   retry_node wraps each real-agent node (max 2 retries)
  │   match_node falls back to degraded mode if Claude gap analysis fails
  └── MemorySaver checkpoints every node transition under thread_id
  │
  ▼
Anthropic Claude API  (claude-haiku-4-5-20251001)
  ├── resume_agent:  full structured parse (PDF/DOCX text → ParsedResume)
  ├── jd_agent:      full structured parse (text/URL → ParsedJobDescription)
  └── match_agent:   gap analysis only (skill/exp/keyword scores are pure Python)
```

**Direct agent-service access:** browser clients may call `POST /api/pipeline/run`
on port 8001 directly for a single-call upload flow that does not require the
persistence layer provided by the Main Service.

**Polling pattern:** after calling `POST /api/workflow/run`, callers may poll
`GET /api/workflow/status/{threadId}` until `is_complete == true` to show
real-time progress without blocking on the long-running workflow response.
