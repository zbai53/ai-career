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

## Cross-Service Flow

```
Client
  │
  ▼
Main Service :8080
  │  POST /api/resumes/parse   (multipart)
  │  POST /api/jds/parse       (JSON)
  │
  ▼
Agent Service :8001
  │  POST /api/resume/parse    (multipart, forwarded bytes)
  │  POST /api/jd/parse        (JSON, text or url)
  │
  ▼
Anthropic Claude API
  (claude-haiku-4-5-20251001)
```

Clients may also call the Agent Service directly on port 8001 if they do not need the file-storage layer provided by the Main Service.
