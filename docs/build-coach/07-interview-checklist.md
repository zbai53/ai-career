# 07 — Interview Checklist

A pre-interview preparation checklist for when you're about to present AI Career in a technical interview or portfolio review.

---

## Before the Interview

- [ ] Review all 30 questions in `05-interview-prep.md`
- [ ] Practice the top 5 answer frameworks out loud (fidelity checker, LangGraph routing, RAG pipeline, PII masking, scalability)
- [ ] Run the demo end-to-end and make sure everything works (`bash docs/screenshots/demo-data-setup.sh`)
- [ ] Have the architecture diagram ready to draw on whiteboard (3 boxes: React → Spring Boot → Python Agent Service; 4 infra: Postgres, Redis, Qdrant, MinIO)
- [ ] Prepare 2-minute project walkthrough (problem → solution → hardest part → results)

---

## Key Talking Points to Memorize

**Why two services (Java + Python)?**
Spring Boot handles persistence, auth, and HTTP orchestration — things it does cleanly with MyBatis and Flyway. Python owns the LLM calls and LangGraph graph — the agent ecosystem (LangGraph, anthropic SDK, sentence-transformers, Qdrant client) is Python-native. Splitting them gives you the right tool for each layer and keeps the agent service independently deployable and testable.

**Why LangGraph over LangChain?**
LangGraph models the workflow as a state machine with explicit nodes, conditional edges, and checkpoint persistence. LangChain chains are linear and stateless — you can't easily express "if score < 70 go back to rewrite, max 2 loops" or resume a failed workflow from the last successful node. LangGraph makes those patterns first-class.

**How fidelity checking works?**
Dual entity extraction on both the original resume and the rewritten version. Regex handles dates, metrics, and numbers (deterministic). Claude-assisted NER handles company names, job titles, and technologies (harder to regex reliably). Any entity in the rewrite that wasn't in the original is flagged with severity (HIGH for company/title/date, MEDIUM for metric/technology). Fidelity score = 1 − weighted_penalty. Below 0.90 STRICT threshold → retry with flagged entities listed explicitly in the prompt.

**What is RAG and why not fine-tuning?**
RAG (Retrieval-Augmented Generation) fetches relevant context at inference time — here, the most semantically similar interview questions and ATS keywords for a given JD and resume. Fine-tuning bakes knowledge into model weights, which requires a training dataset, GPU time, and retraining whenever the question bank changes. RAG lets you update the question bank by upserting into Qdrant with no model changes. For a domain that changes (new roles, new technologies), RAG is clearly the right call.

**How you handle PII?**
Stateless mask/unmask before every LLM call. `mask(text)` returns `(masked_text, mapping)` where each PII token is replaced with a placeholder (`[NAME_1]`, `[EMAIL_1]`, etc.). Claude sees only the masked text. After the response, `unmask(response, mapping)` restores the originals. The mapping is passed through the retry path so text is never double-masked. On the persistence side, `DELETE /api/users/me/data` triggers FK-safe cascading deletion across all 6 user-owned tables in a single `@Transactional` call.

**What breaks at 1,000 concurrent users?**
Three bottlenecks: (1) Interview sessions are stored in a Python in-process dict — horizontal scaling of the agent service loses session state. Fix: Redis with TTL. (2) Each rewrite call can take 30–60s — 1,000 concurrent connections would exhaust the Spring Boot thread pool. Fix: async endpoints + a queue (Redis + Celery or Spring Batch). (3) Qdrant is single-instance in Docker Compose. Fix: Qdrant Cloud or a replicated cluster. The PostgreSQL side (MyBatis connection pool) is fine up to several hundred concurrent queries.

---

## Common Follow-Up Questions

**"How would you add a 7th agent?"**
Add a new node function to `workflow.py`, define its input/output keys in `JobHelperState`, wire it into the graph with `add_node` + `add_edge`, and add a conditional edge if it needs routing logic. The retry wrapper is reusable — wrap it with `retry_node(new_agent_node)`. Write tests in `tests/test_workflow.py` for the new node in isolation and as part of the integration graph.

**"How would you scale this?"**
Short-term: move interview sessions to Redis, add an async task queue (Celery or Spring's `@Async`) for long-running rewrite/interview calls, return a job ID and poll or use SSE for status. Medium-term: extract each agent into its own service if load profiles diverge. Long-term: use Qdrant Cloud + managed PostgreSQL (RDS/Supabase) + deploy agent service on AWS Fargate (stateless, auto-scales). The Spring Boot layer is already stateless — it scales horizontally today.

**"What was the hardest bug?"**
The fidelity checker false-positiving on metric rephrasing. "Reduced latency by 40%" rewritten as "cut response time by 40%" was flagged as a new metric because the regex matched `40%` in both but the surrounding text differed. Fixed by normalizing numeric values before comparison (strip units, compare floats) and downgrading pure-rephrasing flags from MEDIUM to LOW severity.

**"How do you monitor LLM costs?"**
Every Claude call writes a row to `agent_runs` (agent_name, model_name, token_count, duration_ms, status). The deployment guide includes SQL queries for weekly token usage by agent and p95 latency by model. At current Haiku pricing and usage, a full workflow run costs ~$0.01. You could add a budget alert by querying `SUM(token_count)` against a daily threshold and sending a webhook.
