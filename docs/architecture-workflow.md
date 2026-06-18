# Workflow Architecture — LangGraph State Machine

**File:** `agent-service/app/graph/workflow.py`  
**State:** `agent-service/app/graph/state.py`  
**LangGraph version:** 1.2.5  
**Checkpointer:** `MemorySaver` (in-process; swap for `PostgresSaver` in production)

---

## Graph Diagram

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
    __start__([START]):::first
    parse_resume(parse_resume)
    parse_jd(parse_jd)
    match(match)
    rewrite(rewrite)
    interview(interview)
    review(review)
    error_handler(error_handler)
    __after_match__([after_match_router])
    __end__([END]):::last

    __start__          --> parse_resume
    parse_resume       -.-> parse_jd
    parse_resume       -.-> error_handler
    parse_jd           -.-> match
    parse_jd           -.-> error_handler
    match              -.-> __after_match__
    match              -.-> error_handler
    __after_match__    -.-> rewrite
    __after_match__    -.-> interview
    rewrite            --> match
    interview          --> review
    review             --> __end__
    error_handler      --> __end__

    classDef first fill-opacity:0
    classDef last fill:#bfb6fc
```

Solid arrows (`-->`) are unconditional edges.  
Dashed arrows (`-.->`) are conditional edges (routing functions decide at runtime).

---

## Nodes

### `parse_resume`

**Function:** `parse_resume_node(state)`  
**Phase:** Real agent (Phase 1)

Reads `state["resume_file_path"]` and calls `ResumeAgent().parse(file_path)`.  
On success, writes:

| State field | Value |
|---|---|
| `resume` | `ParsedResume.model_dump()` |
| `resume_raw_text` | `ParsedResume.raw_text` (full untruncated text) |
| `current_step` | `"parsing_resume"` |
| `agent_runs` | appended with `ResumeAgent` run log |
| `error` | `None` |

On failure, writes `current_step="error"`, `error=<message>`, and a failed `agent_run` entry.

---

### `parse_jd`

**Function:** `parse_jd_node(state)`  
**Phase:** Real agent (Phase 1)

Reads `state["jd_text"]` and calls `JDAgent().parse(jd_text)`.  
Supports raw text or a URL (routed internally by `JDAgent`).  
On success, writes `jd`, `current_step="parsing_jd"`, `agent_run`.

---

### `match`

**Function:** `match_node(state)`  
**Phase:** Real agent (Phase 2)

Reconstructs `ParsedResume` and `ParsedJobDescription` from state dicts via
`model_validate()`, then calls `MatchAgent().match(resume, jd)`.  
On success, writes:

| State field | Value |
|---|---|
| `match_result` | `MatchResult.model_dump()` with `overall_score`, `skill_score`, `experience_score`, `keyword_score`, gap analysis |
| `current_step` | `"matching"` |
| `agent_runs` | appended with `MatchAgent` run log |

This node is visited **twice** if `rewrite` runs first (the rewrite loop feeds back here).

---

### `rewrite`

**Function:** `rewrite_node(state)`  
**Phase:** Placeholder — RewriteAgent wired in Phase 4

Called when `overall_score < 70`.  Improves the resume to better fit the JD.  
After rewriting, routes back to `match` for re-scoring.  
Appends an entry to `state["rewrite_history"]`.

---

### `interview`

**Function:** `interview_node(state)`  
**Phase:** Placeholder — InterviewAgent wired in Phase 5

Called when `overall_score >= 70`.  Runs a multi-turn mock interview using
RAG-retrieved questions from Qdrant.  Appends turns to `state["interview_messages"]`.

---

### `review`

**Function:** `review_node(state)`  
**Phase:** Placeholder — CoachAgent wired in Phase 5

Runs after the interview ends.  Analyses the full conversation and writes
a structured evaluation to `state["interview_review"]`.

---

### `error_handler`

**Function:** `error_handler_node(state)`  
**Phase:** Always active

Terminal error node.  Logs `state["error"]`, sets `current_step="error"`,
then transitions to `END`.  Every real-agent node routes here on failure,
so the workflow always terminates cleanly rather than propagating exceptions.

---

### `__after_match__` (internal passthrough)

An invisible no-op node (`lambda s: {}`) used as a named intermediate point
so that the two-stage routing after `match` can compose:

1. `_check_error("__after_match__")` — diverts to `error_handler` on failure, else passes through.
2. `after_match_router` — reads `overall_score` and routes to `rewrite` or `interview`.

LangGraph conditional edges can only target named nodes, not other routers,
so this passthrough bridges the two routing steps.

---

## Routing Functions

### `_check_error(next_node)` — factory

Returns a closure that routes to `"error_handler"` when `state["error"]` is
set, otherwise to `next_node`.  Applied after every real-agent node:

| Source node | On error | On success |
|---|---|---|
| `parse_resume` | `error_handler` | `parse_jd` |
| `parse_jd` | `error_handler` | `match` |
| `match` | `error_handler` | `__after_match__` |

### `after_match_router`

Reads `state["match_result"]["overall_score"]`:

| Score | Route |
|---|---|
| `< 70` | `rewrite` |
| `>= 70` | `interview` |
| `current_step == "error"` | `END` (defensive guard for direct test calls) |

---

## Error Handling Flow

```
parse_resume_node
  ├─ missing file path  ─┐
  └─ exception caught   ─┤
                          ↓
                    error field set in state
                    failed agent_run logged
                          ↓
              _check_error("parse_jd") detects error
                          ↓
                   error_handler_node
                    logs state["error"]
                    sets current_step="error"
                          ↓
                          END
```

The same pattern repeats after `parse_jd` and `match`.

Key properties:
- **No exceptions propagate** out of node functions — all are caught internally.
- **Every failure is logged** as a `status="error"` entry in `state["agent_runs"]`.
- **State is always valid** when the graph exits, whether success or failure.
- **Checkpoint is written** even on error paths, so the failure state is inspectable via `get_workflow_state(thread_id)`.

---

## State Schema

Defined in `app/graph/state.py` as `JobHelperState(TypedDict)`.

| Field | Type | Set by | Purpose |
|---|---|---|---|
| `user_id` | `str` | Caller | Scopes DB writes; used as default `thread_id` |
| `resume_file_path` | `Optional[str]` | Caller | Input to `parse_resume` node |
| `jd_text` | `Optional[str]` | Caller | Input to `parse_jd` node |
| `resume` | `Optional[dict]` | `parse_resume` | `ParsedResume.model_dump()` |
| `resume_raw_text` | `Optional[str]` | `parse_resume` | Full extracted text for fidelity checking |
| `jd` | `Optional[dict]` | `parse_jd` | `ParsedJobDescription.model_dump()` |
| `match_result` | `Optional[dict]` | `match` | `MatchResult.model_dump()` with all scores |
| `rewrite_history` | `list[dict]` | `rewrite` | One entry per rewriting attempt |
| `interview_messages` | `list[dict]` | `interview` | Running conversation log |
| `interview_review` | `Optional[dict]` | `review` | Structured coach evaluation |
| `current_step` | `str` | Every node | Progress label for frontend SSE |
| `error` | `Optional[str]` | Error paths | Last error message; `None` on success |
| `agent_runs` | `list[dict]` | Every agent node | Accumulated `log_agent_run()` dicts |

---

## Checkpoint & Resume

### How checkpointing works

The graph is compiled with `checkpointer=MemorySaver()`.  After every node
transition LangGraph serialises the full `JobHelperState` and stores it under
a `(thread_id, checkpoint_id)` key.  The latest snapshot is always retrievable
by `thread_id` alone.

```python
# Invoke a workflow — thread_id defaults to user_id
final_state = run_workflow(
    user_id="user-42",
    resume_file_path="/tmp/jane_doe.pdf",
    jd_text="We are hiring a backend engineer...",
    thread_id="user-42-run-001",   # optional explicit ID
)

# Inspect the checkpoint at any time (even mid-run from another process)
snap = get_workflow_state("user-42-run-001")
print(snap["values"]["current_step"])  # e.g. "matching"
print(snap["next"])                    # [] = complete, [...] = in progress
```

### Snapshot structure

`get_workflow_state(thread_id)` returns a dict with four keys:

| Key | Type | Description |
|---|---|---|
| `values` | `dict` | Full `JobHelperState` at the last completed node |
| `next` | `list[str]` | Node(s) that will run next; `[]` means the workflow has finished |
| `metadata` | `dict` | LangGraph internal metadata, including `step` counter |
| `created_at` | `str` | ISO-8601 UTC timestamp of the checkpoint |

### Workflow resumption

Because every state change is checkpointed, a paused or interrupted workflow
can be resumed by calling `workflow_graph.invoke(None, config=_make_config(thread_id))`.
LangGraph restores the last saved state and continues from the next pending node.

```python
# Resume from wherever the graph last stopped
workflow_graph.update_state(cfg, partial_state, as_node="parse_jd")
workflow_graph.invoke(None, config=cfg)
```

This is also how the demo main-block works: pre-built resume + JD dicts are
injected as if `parse_jd` just completed, then the graph continues from `match`.

### Production upgrade

In production, replace `MemorySaver` with `PostgresSaver` pointing at the same
PostgreSQL instance used by the Spring Boot backend:

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver(conn_string=os.getenv("DATABASE_URL"))
workflow_graph = _build_graph().compile(checkpointer=checkpointer)
```

Benefits:
- Checkpoints survive process restarts.
- State is readable cross-process (e.g. the Spring Boot poll endpoint can read it).
- Multiple workflow workers can share the same checkpoint store.

---

## Error Handling

### Three-layer defence

Each real-agent node (`parse_resume`, `parse_jd`, `match`) is protected by
three nested layers that execute in order:

```
[retry_node wrapper]
  └─ [node function]
       └─ try/except → sets state["error"]
  └─ on error → retry up to 2 times with sleep(1s)
  └─ on exhaustion → error bubbles out of retry_node
[_check_error routing]
  └─ state["error"] set? → route to error_handler
  └─ otherwise         → continue to next node
[error_handler_node]
  └─ logs error, sets current_step="error", workflow_status="failed" → END
```

### Retry logic — `retry_node` wrapper

Every real-agent node is registered in the graph wrapped with
`retry_node(node_fn, max_retries=2, delay_seconds=1.0)`.

| Attempt | Behaviour |
|---|---|
| 1st call | Node runs normally |
| Failure detected (`state["error"]` is set) | Sleep 1 s, retry with original inputs |
| 2nd call | Same node runs again |
| Success on retry N | Tag the successful `agent_run` with `{"retry_count": N}`, merge `retry_counts` into state, return |
| All retries exhausted | Keep `state["error"]`, bubble out to `_check_error` → `error_handler` |

`retry_counts` accumulates node-name → retry-count pairs across all retries in
the run and is stored in `state["retry_counts"]`.

Failed attempts are logged in `state["agent_runs"]` with `status="error"` before
each retry, so the full attempt history is preserved in the final state.

### Degraded mode — `match_node`

`match_node` has a second fallback layer specifically for the gap-analysis step.
`MatchAgent.match()` calls Claude only for the qualitative gap analysis; skill,
experience, and keyword scores are computed in pure Python beforehand.

If `MatchAgent.match()` raises (e.g. Claude API timeout), `match_node` falls
back to `_compute_degraded_match_result(resume_dict, jd_dict)`:

1. Computes Python-only skill and keyword scores from the raw dicts.
2. Sets `match_result["gap_analysis"] = {"error": "Gap analysis unavailable", ...}`.
3. Sets `match_result["status"] = "degraded"`.
4. Sets `state["workflow_status"] = "degraded"`.
5. Returns **no error** — routing continues normally.

The degraded result still has a numeric `overall_score` so `after_match_router`
can route to `rewrite` or `interview` as usual.  `review_node` preserves
`workflow_status = "degraded"` rather than overwriting it with `"completed"`.

```
MatchAgent.match() raises
        │
        ▼
_compute_degraded_match_result()
        │
        ├─ success → return match_result with status="degraded"
        │                    workflow_status="degraded"
        │                    error=None
        │
        └─ also fails → return error, route to error_handler as normal
```

### `workflow_status` values

| Value | Set by | Meaning |
|---|---|---|
| `"running"` | Initial state | Workflow is in progress |
| `"completed"` | `review_node` | Workflow finished successfully |
| `"degraded"` | `match_node` | Match ran without gap analysis; workflow still completed |
| `"failed"` | `error_handler_node` | Workflow terminated due to an unrecoverable error |

---

## Workflow Nodes

Detailed state read/write contract for every node.

### `parse_resume`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `resume_file_path` | input | Must be set by caller; missing → immediate error |
| **Writes** | `resume` | output | `ParsedResume.model_dump()` dict |
| | `resume_raw_text` | output | Full untruncated text from the file |
| | `current_step` | output | `"parsing_resume"` on success, `"error"` on failure |
| | `agent_runs` | append | `log_agent_run()` dict from `ResumeAgent` |
| | `error` | output | `None` on success; error string on failure |

**Agent called:** `ResumeAgent().parse(file_path)`  
**Wrapped with:** `retry_node(parse_resume_node, max_retries=2)`  
**Phase:** 1 (production-ready)

---

### `parse_jd`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `jd_text` | input | Raw text or a `https://` URL |
| **Writes** | `jd` | output | `ParsedJobDescription.model_dump()` dict |
| | `current_step` | output | `"parsing_jd"` on success |
| | `agent_runs` | append | `log_agent_run()` dict from `JDAgent` |
| | `error` | output | `None` on success; error string on failure |

**Agent called:** `JDAgent().parse(jd_text)` (routes internally to `parse_text` or `parse_url`)  
**Wrapped with:** `retry_node(parse_jd_node, max_retries=2)`  
**Phase:** 1 (production-ready)

---

### `match`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `resume` | input | Must be populated by `parse_resume` |
| | `jd` | input | Must be populated by `parse_jd` |
| **Writes** | `match_result` | output | `MatchResult.model_dump()` dict (or degraded dict) |
| | `current_step` | output | `"matching"` |
| | `workflow_status` | output | `"running"` on full success; `"degraded"` if gap analysis failed |
| | `agent_runs` | append | `log_agent_run()` dict from `MatchAgent` |
| | `error` | output | `None` unless both full match and degraded fallback fail |

**Agent called:** `MatchAgent().match(resume, jd)` → falls back to `_compute_degraded_match_result()` on failure  
**Wrapped with:** `retry_node(match_node, max_retries=2)`  
**Visited twice** when the rewrite loop fires (score < 70 on first pass).  
**Phase:** 2 (production-ready; gap analysis via Claude)

---

### `rewrite`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `resume`, `jd`, `match_result` | input | Gap analysis drives rewrite strategy |
| **Writes** | `resume` | output | Rewritten resume dict (Phase 4) |
| | `match_result` | output | Placeholder bumps `overall_score` to 75 to exit loop |
| | `current_step` | output | `"rewriting"` |
| | `rewrite_history` | append | One entry per attempt (Phase 4) |

**Agent called:** `RewriteAgent` — **not yet wired (Phase 4 placeholder)**  
**Edge:** unconditional → `match` (re-scores after rewrite)

---

### `interview`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `match_result`, `jd` | input | Score and JD drive question selection |
| **Writes** | `interview_messages` | append | Running conversation log |
| | `current_step` | output | `"interviewing"` |

**Agent called:** `InterviewAgent` — **not yet wired (Phase 5 placeholder)**  
**Edge:** unconditional → `review`

---

### `review`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `interview_messages` | input | Full conversation for coaching analysis |
| **Writes** | `interview_review` | output | Structured per-question evaluation |
| | `current_step` | output | `"reviewing"` |
| | `workflow_status` | output | `"completed"` (or preserves `"degraded"`) |

**Agent called:** `CoachAgent` — **not yet wired (Phase 5 placeholder)**  
**Edge:** unconditional → `END`

---

### `error_handler`

| | Field | Direction | Notes |
|---|---|---|---|
| **Reads** | `error` | input | The error message set by the failing node |
| **Writes** | `current_step` | output | `"error"` |
| | `workflow_status` | output | `"failed"` |

**Edge:** unconditional → `END`  
**Every** real-agent node routes here (via `_check_error`) when `state["error"]` is set.

---

## API Endpoints

All endpoints are served by the Agent Service on port **8001**.

### Workflow execution

#### `POST /api/workflow/run`

Invoke the full LangGraph workflow with explicit file paths.  Intended for
server-to-server calls from Spring Boot (which has already persisted the files).

**Request — `application/json`**

```json
{
  "user_id":          "user-42",
  "resume_file_path": "/data/uploads/jane_doe.pdf",
  "jd_text":          "We are hiring a backend engineer...",
  "thread_id":        "user-42-run-001"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `user_id` | string | yes | Scopes the checkpoint namespace |
| `resume_file_path` | string \| null | no | Absolute path on the agent-service host |
| `jd_text` | string \| null | no | Raw JD text or a `https://` URL |
| `thread_id` | string \| null | no | Explicit checkpoint ID; defaults to `user_id` |

**Response 200** — Full `JobHelperState` dict plus summary fields:

```json
{
  "current_step":    "reviewing",
  "resume":          { /* ParsedResume */ },
  "jd":              { /* ParsedJobDescription */ },
  "match_result":    { "overall_score": 78.2, "skill_score": 70.0, "..." : "..." },
  "workflow_status": "completed",
  "steps_completed": ["parse_resume", "parse_jd", "match"],
  "total_duration_ms": 3420,
  "total_tokens":    1840,
  "agent_runs":      [ /* log entries */ ],
  "error":           null
}
```

---

#### `POST /api/pipeline/run`

One-click browser-friendly endpoint: upload a resume file and paste JD text,
receive the full pipeline result in a single call.  Handles temporary file
management internally.

**Request — `multipart/form-data`**

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | binary | yes | `.pdf` or `.docx` |
| `jd_text` | string | yes | Raw JD text |
| `user_id` | string | no | Defaults to `"default"` |

**Response 200**

```json
{
  "current_step":    "reviewing",
  "resume":          { /* ParsedResume */ },
  "jd":              { /* ParsedJobDescription */ },
  "match_result":    { "overall_score": 78.2, "..." : "..." },
  "routing":         "interview",
  "workflow_status": "completed",
  "steps_completed": ["parse_resume", "parse_jd", "match"],
  "total_duration_ms": 3420,
  "total_tokens":    1840,
  "agent_runs":      [ /* log entries */ ],
  "error":           null
}
```

`routing` is `"interview"` when `overall_score >= 70`, otherwise `"rewrite"`.

**Error responses**

| Status | Condition |
|---|---|
| 400 | Unsupported file extension |
| 500 | Any agent or graph failure |

---

### Workflow monitoring

#### `GET /api/workflow/status/{thread_id}`

Return the current checkpoint state for a running or completed workflow.
Safe to poll repeatedly; does not advance the graph.

**Path parameter:** `thread_id` — the ID passed to `POST /api/workflow/run`.

**Response 200**

```json
{
  "thread_id":    "user-42-run-001",
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
|---|---|---|
| `next` | `list[string]` | Pending node names; `[]` when workflow is finished |
| `is_complete` | boolean | `true` when `next == []` |
| `agent_runs` | integer | Count of accumulated agent_run entries (not the full list) |

---

### Workflow visualisation

#### `GET /api/workflow/visualize`

Return the Mermaid diagram source of the compiled graph.

**Response 200**

```json
{ "mermaid": "graph TD;\n    __start__([<p>__start__</p>]):::first\n    ..." }
```

---

#### `GET /api/workflow/visualize/html`

Return an HTML page that renders the workflow diagram in the browser via
Mermaid JS (CDN-hosted).  Open directly in a browser tab — no JSON parsing
required.

**Response 200** — `text/html`

The page includes:
- A `<div class="mermaid">` block containing the diagram source.
- A `<script>` tag loading Mermaid from `cdn.jsdelivr.net`.
- Minimal CSS for readable presentation.

---

## Invocation from Spring Boot

`WorkflowController.java` → `AgentServiceClient.runWorkflow()` → `POST /api/workflow/run`

The Spring Boot layer:
1. Loads `Resume` and `JobDescription` entities from the database.
2. Builds `threadId = "user-{userId}-resume-{resumeId}-jd-{jdId}"`.
3. Passes `resume.filePath` and `jd.rawText` to the agent-service.
4. Receives the final `JobHelperState` JSON (including summary fields).
5. Iterates `state["agent_runs"]` and persists each entry via `AgentRunService.saveFromResponse()`.
6. Returns the full state to the frontend.

The `workflowRestTemplate` bean uses a **120-second read timeout** (separate
from the standard 60-second `agentRestTemplate`) because the full pipeline can
take 30–90 seconds depending on resume length and LLM latency.

The workflow status endpoint (`GET /api/workflow/status/{threadId}`) can be
polled to show real-time progress in the frontend before the workflow completes.
