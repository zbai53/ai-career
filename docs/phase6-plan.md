# Phase 6 — React Frontend Plan (Days 36–41)

**Goal:** Build a visually impressive, fully functional UI that demos the complete AI Career workflow.  
**Stack:** Vite + React 18 + TypeScript + TailwindCSS (already scaffolded in `frontend/`)

---

## Libraries to Add

```bash
npm install axios zustand @tanstack/react-query recharts reactflow
npm install -D @types/reactflow
```

| Library | Purpose |
|---|---|
| `axios` | HTTP client for Spring Boot API calls (port 8080) |
| `zustand` | Lightweight global state (auth token, current resume/JD IDs) |
| `@tanstack/react-query` | Server state, caching, loading/error states for API calls |
| `recharts` | Radar chart for match dimension scores (skill / experience / keyword) |
| `reactflow` | Workflow visualization — renders the LangGraph state machine |

---

## Pages

| Page | Route | Key function |
|---|---|---|
| Login / Register | `/login`, `/register` | JWT auth → store token in zustand |
| Resume Upload | `/resume` | Drag-and-drop upload → `POST /api/resumes/parse` → show parsed JSON |
| JD Input | `/jd` | Textarea + URL option → `POST /api/jds/parse` → show parsed JSON |
| Match Results | `/match` | Trigger `POST /api/match` → radar chart + gap analysis list |
| Rewrite Comparison | `/rewrite` | Side-by-side original vs rewritten bullets + fidelity score badge |
| Interview Chat | `/interview` | Chat bubble UI → `POST /api/interviews/{id}/answer` |
| Review Dashboard | `/review` | Per-question scores, STAR feedback, readiness verdict card |
| Workflow Visualization | `/workflow` | React Flow graph with live node highlighting via SSE |

---

## Key Components

### `FileUpload`
- Drag-and-drop zone + click-to-browse
- Accepts `.pdf` and `.docx`
- Shows upload progress bar and parsed result preview
- Uses: `POST /api/resumes/parse`

### `RadarChart`
- Recharts `<RadarChart>` with three axes: Skill Score, Experience Score, Keyword Score
- Overall score displayed as large centered number
- Color-coded: green ≥ 70, yellow 50–69, red < 50
- Uses: match result from `GET /api/match/{id}`

### `ChatBubble`
- Right-aligned user messages, left-aligned agent messages
- Typing indicator (animated dots) while waiting for response
- Question counter badge ("Question 3 / 5")
- "End Interview" button → `POST /api/interviews/{id}/end`

### `ScoreCard`
- Displays a single numeric score (0–10) with label and color tier
- Used on the Review Dashboard for per-question evaluation
- Slots: relevance, depth, communication, overall

### `WorkflowGraph` (showpiece)
- React Flow canvas rendering LangGraph nodes and edges
- Node states: `idle` (grey), `active` (blue, pulsing), `complete` (green), `failed` (red)
- SSE stream from `GET /api/workflow/status/{id}` updates node state in real time
- Mirrors the Mermaid diagram in `docs/` but interactive

---

## Day-by-Day Plan

### Day 36 — Auth + Routing
- Login / Register pages with form validation
- JWT stored in zustand (`useAuthStore`)
- Axios interceptor attaches `Authorization: Bearer <token>` to all requests
- Protected route wrapper (`<RequireAuth>`)
- Spring Boot: confirm `/api/auth/login` and `/api/auth/register` endpoints exist (or scaffold stubs)

### Day 37 — Resume Upload Page
- `FileUpload` component with drag-and-drop
- `POST /api/resumes/parse` → display parsed resume as collapsible JSON tree
- Persist `resumeId` in zustand for downstream pages
- Loading state, error toast on failure

### Day 38 — JD Input + Match Results
- JD page: textarea + optional URL field → `POST /api/jds/parse`
- Persist `jdId` in zustand
- Trigger `POST /api/match` → poll or wait for response
- `RadarChart` for dimension scores
- Gap analysis: list of missing skills with "Rewrite" and "Practice Interview" buttons

### Day 39 — Rewrite Comparison
- Split-pane view: original bullets (left) vs rewritten bullets (right)
- Fidelity score badge (STRICT / WARN / FAILED color-coded)
- Highlight keywords that were added (green underline)
- Flagged entities shown in a collapsible panel
- Uses: `POST /api/rewrite` + `GET /api/rewrite/{id}`

### Day 40 — Interview Chat + Review Dashboard
- `ChatBubble` list, auto-scroll to latest message
- Input box disabled while agent is responding
- "End Interview" → `POST /api/interviews/{id}/end` → redirect to Review
- Review Dashboard: `ScoreCard` grid per question, overall readiness verdict banner

### Day 41 — Workflow Visualization (showpiece)
- `WorkflowGraph` component using React Flow
- Nodes: Resume Parser, JD Parser, Match Agent, Rewrite Agent, Interview Agent, Coach Agent
- Edges with conditional labels (score ≥ 70 → interview, score < 70 → rewrite)
- SSE from Spring Boot updates node colour in real time as workflow executes
- "Run Full Workflow" button triggers `POST /api/workflow/full`
- Export as PNG button (React Flow's built-in)

---

## State Shape (zustand)

```typescript
interface AppState {
  token: string | null;
  userId: number | null;
  resumeId: number | null;
  jdId: number | null;
  matchResultId: number | null;
  rewriteResultId: number | null;
  interviewSessionId: string | null;
}
```

---

## API Calls Summary

| Action | Method | Spring Boot endpoint |
|---|---|---|
| Login | POST | `/api/auth/login` |
| Upload resume | POST | `/api/resumes/parse` |
| Parse JD | POST | `/api/jds/parse` |
| Run match | POST | `/api/match` |
| Get match | GET | `/api/match/{id}` |
| Run rewrite | POST | `/api/rewrite` |
| Get rewrite | GET | `/api/rewrite/{id}` |
| Start interview | POST | `/api/interviews/start` |
| Submit answer | POST | `/api/interviews/{id}/answer` |
| End interview | POST | `/api/interviews/{id}/end` |
| Get interview | GET | `/api/interviews/{id}` |
| Run full workflow | POST | `/api/workflow/full` |
| Workflow status (SSE) | GET | `/api/workflow/status/{id}` |

---

## Definition of Done

- [ ] All 7 pages render without console errors
- [ ] Full user journey works end-to-end: upload resume → paste JD → see match → rewrite → interview → review
- [ ] Workflow visualization shows node state changes in real time
- [ ] Responsive layout (desktop-first, min-width 768px)
- [ ] No hardcoded API responses — all data from live Spring Boot service
