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

## Cross-Service Flow

```
Client
  │
  ▼
Main Service :8080
  │  POST /api/resumes/parse      (multipart) ──────────────┐
  │  POST /api/jds/parse          (JSON)                     │
  │  POST /api/match              (JSON: resumeId + jdId) ───┤
  │  GET  /api/match/{id}         (DB lookup, no agent call) │
  │  GET  /api/agent-runs/recent  (DB lookup, no agent call) │
  │                                                           │
  ▼                                                           │
Agent Service :8001  ◄─────────────────────────────────────┘
  │  POST /api/resume/parse    (multipart, forwarded bytes)
  │  POST /api/jd/parse        (JSON, text or url)
  │  POST /api/match           (JSON: resume + jd objects)
  │
  ▼
Anthropic Claude API
  (claude-haiku-4-5-20251001)
  └── resume_agent: full parse
  └── jd_agent:     full parse
  └── match_agent:  gap analysis only (scoring is pure Python)
```

Clients may also call the Agent Service directly on port 8001 if they do not need the persistence layer provided by the Main Service.
