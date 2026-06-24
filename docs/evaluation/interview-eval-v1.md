# Interview System — Design & Evaluation v1

**Date:** 2026-06-23  
**Agents:** `InterviewAgent` (`app/agents/interview_agent.py`), `CoachAgent` (`app/agents/coach_agent.py`)  
**RAG:** `app/rag/question_index.py` — Qdrant collection `interview_questions`

---

## System Design

### RAG-Powered Question Selection

Questions are embedded with `all-MiniLM-L6-v2` (384-dim) and stored in Qdrant.  The built-in bank contains 20 questions:

| Distribution | Count | Notes |
|---|---|---|
| Technical | 12 | System design, coding, architecture, debugging |
| Behavioral | 8 | STAR-format leadership, conflict, deadline, teamwork |
| Difficulty mix | easy / medium / hard | Balanced across both types |

At session start, `InterviewAgent.start_session()` calls `search_questions()` for both types and assembles the final set:

```
num_questions total
  → 60% technical  (rounded up)  fetched by role + type="technical"
  → 40% behavioral (remainder)   fetched by type="behavioral"
  → combined, shuffled, capped at num_questions
```

The `role` filter is inferred from the JD title (e.g. "backend", "frontend", "general") so questions stay domain-relevant without manual tagging per session.

### Multi-Turn Decision Logic

After each candidate answer `InterviewAgent.process_turn()` runs a three-step pipeline:

```
1. evaluate_answer(question, answer)
       → AnswerEvaluation (relevance, depth, communication, overall scores)
2. _decide_next_action(evaluation, session)
       → next_action string
3. respond(next_action, session)
       → next_content (follow-up probe, re-prompt, or next question text)
```

#### Decision Rules

| Condition | `next_action` | What happens |
|---|---|---|
| `overall_score >= 7` | `next_question` | Advance to next main question |
| `depth_score < 5` AND follow-up cap not reached | `follow_up` | Ask a probing follow-up question |
| `relevance_score < 5` | `re_answer` | Re-prompt the same question |
| All questions answered | `done` | Mark session complete |

Priority order: `re_answer` > `follow_up` > `next_question`.  An off-topic answer (`relevance < 5`) always triggers `re_answer` even if depth is also low.

#### Follow-Up Cap

Each main question tracks its own follow-up count in `session.follow_up_counts` (keyed by question index).  When `follow_up_counts[i] >= 2`, the third answer always advances regardless of scores.  This prevents infinite loops and respects the candidate's time.

```python
# Key logic in _decide_next_action
follow_up_count = session.follow_up_counts.get(q_idx, 0)
if depth_score < 5 and follow_up_count < 2:
    return "follow_up"
return "next_question"
```

### State Tracking

Session state is held in `InterviewSessionData` (Pydantic model, stored in `app.main._sessions`):

| Field | Type | Updated by |
|---|---|---|
| `session_id` | UUID string | `start_session()` |
| `questions` | `list[InterviewQuestion]` | `start_session()` |
| `answers` | `list[AnswerEvaluation]` | `process_turn()` after each answer |
| `conversation_history` | `list[dict]` | `process_turn()` — every turn appended |
| `follow_up_counts` | `dict[int, int]` | `_decide_next_action()` |
| `current_question_index` | int | advanced on `next_question` |
| `status` | `"active"` \| `"completed"` | `end_session()` / `/end` endpoint |

`conversation_history` entries use monotonically increasing `turn_number` and alternate `role: "candidate"` / `role: "interviewer"`.  This gives `CoachAgent` a full dialogue context rather than just scores.

---

## Coach Review Framework

`CoachAgent.review(session, jd, resume)` receives the completed `InterviewSessionData` and produces a structured `CoachReview`.

### Per-Answer Evaluation Dimensions

| Dimension | What Claude assesses |
|---|---|
| STAR structure | For behavioral: does the answer have Situation, Task, Action, Result? |
| Technical accuracy | For technical: is the content factually correct? |
| Depth | Does the answer go beyond surface-level description? |
| Practical application | Does the candidate connect concepts to real experience? |
| Communication | Clarity, conciseness, confidence from the written text |

### Readiness Verdict

| Verdict | Condition |
|---|---|
| `yes` | Candidate is ready for this role; strong across most dimensions |
| `almost` | Solid foundation; 1-2 specific areas need improvement |
| `needs_more_practice` | Significant gaps in technical accuracy, depth, or STAR structure |

### Coach Review Output Fields

```json
{
  "overall_score":   74.5,
  "readiness":       "almost",
  "strengths":       ["Strong command of DB fundamentals", "..."],
  "improvements":    ["Quantify results in STAR stories", "..."],
  "per_question_feedback": [
    {
      "question":  "Walk me through designing a URL shortener.",
      "type":      "technical",
      "score":     7.5,
      "feedback":  "Good coverage of hashing and redirect flow. Missing cache layer discussion."
    }
  ],
  "focus_topics":   ["System design trade-offs", "NoSQL use cases"]
}
```

---

## Scoring Ranges

### Answer Evaluation (per turn — `evaluate_answer`)

| Score range | Interpretation |
|---|---|
| 9–10 | Excellent: comprehensive, concrete, well-structured |
| 7–8 | Good: solid answer, minor gaps |
| 5–6 | Adequate: on-topic but surface-level |
| 3–4 | Weak: partially relevant or vague |
| 1–2 | Poor: off-topic or fundamentally incorrect |

All three dimensions (relevance, depth, communication) use the same 1–10 scale.  `overall_score = (relevance + depth + communication) / 3`, rounded to one decimal.

### Coach Review (`overall_score`)

| Score range | Readiness level |
|---|---|
| 80–100 | `yes` — ready to interview at this level |
| 60–79 | `almost` — close, targeted practice needed |
| 0–59 | `needs_more_practice` — foundational gaps remain |

---

## Example Q&A Pairs

### Example 1 — Strong Answer (overall ≥ 7 → `next_question`)

**Question (behavioral):** "Tell me about a time you had to debug a production issue under pressure."

**Answer:** "In Q3 last year our payments service started throwing 500ms latency spikes during peak traffic. I was on-call and had about 20 minutes before the SLA breach.  I pulled Datadog traces and narrowed it to a single slow query — a missing index on the `transactions` table after a schema migration had been deployed that morning.  I added the index online (no lock), deployed in 5 minutes, and latency dropped to 80ms.  We added a pre-deploy query-plan check to our CI pipeline to prevent recurrence."

**Evaluation:**
```json
{
  "relevance_score":     9,
  "depth_score":         9,
  "communication_score": 8,
  "overall_score":       8.7,
  "next_action":         "next_question",
  "strengths":           ["Concrete timeline and metrics", "Clear root cause → fix → prevention structure"],
  "improvements":        ["Could quantify business impact (transactions affected, revenue at risk)"]
}
```

---

### Example 2 — Off-Topic Answer (relevance < 5 → `re_answer`)

**Question (technical):** "Explain the CAP theorem and how it applies to distributed databases."

**Answer:** "I really enjoy working with databases.  I've used MySQL and MongoDB a lot in my projects and they work great for most use cases.  I think picking the right database is all about your team's familiarity with it."

**Evaluation:**
```json
{
  "relevance_score":     2,
  "depth_score":         1,
  "communication_score": 6,
  "overall_score":       3.0,
  "next_action":         "re_answer",
  "next_content":        "Let me rephrase: CAP theorem states that a distributed system can guarantee at most two of Consistency, Availability, and Partition Tolerance simultaneously. With that in mind, could you walk me through how you'd choose between a CP database like HBase and an AP database like Cassandra for a specific use case?"
}
```

---

### Example 3 — Shallow Answer (depth < 5 → `follow_up`)

**Question (technical):** "How does database indexing improve query performance?"

**Answer:** "Indexing makes queries faster by helping the database find data without scanning every row."

**Evaluation:**
```json
{
  "relevance_score":     8,
  "depth_score":         3,
  "communication_score": 7,
  "overall_score":       6.0,
  "next_action":         "follow_up",
  "next_content":        "Good start. Can you walk me through the internal structure of a B-tree index and explain when you'd choose a composite index over a single-column index?"
}
```

Follow-up answer improves depth score to 7 → system advances to `next_question`.

---

## Evaluation Criteria

### What was measured

| Criterion | Method |
|---|---|
| Multi-turn routing correctness | Unit tests: `TestMultiTurnLogic` (7 tests in `tests/test_interview_agent.py`) |
| Follow-up cap enforcement | Direct state injection test (`session.follow_up_counts = {0: 2}` before `process_turn`) |
| Conversation history integrity | Verify `turn_number` monotonicity and role alternation across 4 turns |
| RAG retrieval relevance | Manual inspection of top-5 results for 5 different role/type queries |
| Coach review structure | Field presence and type validation; readiness verdict consistency |

### Known limitations

- **In-memory sessions:** `_sessions` dict is lost on service restart; no persistence of live sessions between restarts (DB row persists the final state only).
- **20-question bank:** Small enough that semantic search can return the same question twice if `num_questions` is high and filters are narrow.  Deduplication by `question_number` is not yet implemented.
- **Claude as evaluator:** `evaluate_answer` prompts Claude with no reference answer.  Scores can vary slightly on identical inputs depending on sampling temperature.  Setting `temperature=0` (or near 0) in the prompt would improve consistency.
- **English-only:** Evaluation prompts are written in English; non-English answers will receive lower communication scores even if technically correct.

---

## Interview System — Talking Points for Job Interviews

1. **RAG-backed question selection:** Questions are embedded with `all-MiniLM-L6-v2` and retrieved from Qdrant using semantic search, filtered by role and type — this means the system selects contextually relevant questions for each JD rather than serving a static list.

2. **Multi-turn state machine:** The interview agent implements a three-way decision rule (re-answer, follow-up, advance) based on per-turn evaluation scores, with a follow-up cap per question to prevent infinite loops — this mirrors how a real interviewer adapts based on answer quality.

3. **Separation of concerns:** The Python agent service owns in-memory session state and all Claude calls; the Spring Boot backend owns DB persistence and REST authentication.  This keeps the LLM logic isolated and independently testable.

4. **Evaluation without reference answers:** The `CoachAgent` produces per-question feedback and a readiness verdict purely from the conversation history and JD context — no pre-written answer keys required, which scales to arbitrary JDs and roles.

5. **Full observability:** Every Claude call is logged via `log_agent_run()` with token counts, latency, model ID, and input/output summaries — the same structure used across all six agents — making it easy to monitor cost and quality in production.
