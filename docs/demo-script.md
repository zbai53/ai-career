# 3-Minute Demo Script

A structured walkthrough for showing AI Career to interviewers, recruiters, or potential collaborators.
Total runtime: ~3 minutes. Each section has a suggested talking time.

**Setup before you start:**
- Run `bash docs/screenshots/demo-data-setup.sh` to pre-populate data
- Open Chrome at `http://localhost:3000` (or your deployed URL)
- Have a PDF resume ready for the live upload
- Keep DevTools closed — full browser window looks cleaner

---

## Overview (15 seconds)

**What to show:** Dashboard

**What to say:**

> "This is AI Career — a multi-agent job search assistant I built from scratch. It takes your resume and a job posting, and in about 2 minutes walks you through matching, targeted rewriting, and a full mock interview. Let me show you the full loop."

**Navigate to:** `http://localhost:3000`

Point out:
- The workflow progress steps in the sidebar (Upload → JD → Match → Interview)
- Stats cards showing data from previous runs
- Recent activity feed

---

## Step 1 — Resume Upload (30 seconds)

**What to show:** Upload page → parse result

**What to say:**

> "First, upload your resume. I support PDF and DOCX. The Resume Agent sends it to Claude, which extracts your name, work history, skills, and education into structured JSON."

**Do:**
1. Click "Upload Resume" in the sidebar
2. Drag a PDF onto the upload zone (or click to browse)
3. Wait ~3–5 seconds for the parse result to appear
4. Point at the parsed name, skills section, and experience count

> "Notice it pulled out skills, job titles, and dates automatically — no manual tagging. It also masks PII before sending to the model, so your personal details never leave the device in raw form."

**Navigate to:** `http://localhost:3000/upload`

---

## Step 2 — JD Input (20 seconds)

**What to show:** JD input page → parsed result

**What to say:**

> "Next, paste a job description — or give it a URL and the JD Agent scrapes and parses it. It extracts the title, required skills, preferred skills, and seniority level."

**Do:**
1. Click "Input JD" in the sidebar
2. Paste a job description (or type a URL and click Fetch)
3. Click Parse
4. Point at the required skills badges and the job title

**Navigate to:** `http://localhost:3000/jd`

---

## Step 3 — Match Results (30 seconds)

**What to show:** Match results page with radar chart

**What to say:**

> "Now the Match Agent scores your resume against the JD across six dimensions: skills, experience, keywords, seniority, education, and culture fit. You get an overall score and a radar chart so you can see exactly where the gaps are."

**Do:**
1. Click "Run Match" — or navigate to the pre-run match from the script
2. Let the radar chart animate in
3. Point at the overall score (e.g. "72%")
4. Hover over a dimension on the radar chart

> "Here I'm missing Kafka and Kubernetes — required skills I haven't listed. The gap analysis below tells me exactly what to add or highlight. And if the score is below 70, the system automatically triggers a rewrite."

**Navigate to:** `http://localhost:3000/match/<match_id>`

---

## Step 4 — Resume Rewrite (30 seconds)

**What to show:** Rewrite comparison page

**What to say:**

> "This is the part that took the most engineering effort. The Rewrite Agent rewrites each bullet point to better match the JD — and here's the key: it has a fidelity checker that verifies nothing was hallucinated."

**Do:**
1. Navigate to the rewrite result (or click "Rewrite Resume" from the match page and wait)
2. Point at a before/after bullet pair
3. Point at the fidelity badge (green "Passed")

> "See how it changed 'Built REST API using Java' to something that speaks the JD's language — distributed systems, high availability. But it only uses what was actually in my original resume. The fidelity score here is 0.95 — it passed on the first attempt. If it failed, the agent retries with the flagged entities listed explicitly in the prompt."

> "It also injects missing ATS keywords and shows you exactly which action verbs were strengthened."

**Navigate to:** `http://localhost:3000/rewrite/<rewrite_id>`

---

## Step 5 — Mock Interview (30 seconds)

**What to show:** Interview chat page mid-conversation

**What to say:**

> "After rewriting, the system can drop you straight into a mock interview. The Interview Agent uses RAG over your resume and the JD to generate targeted questions — 60% technical, 40% behavioral, matching your target role."

**Do:**
1. Navigate to the interview session from the script (or click "Practice Interview" from the rewrite page)
2. Show the chat UI with the first question visible
3. Type a short answer and submit
4. Point at the follow-up question that appears

> "If your answer lacked depth, it probes with a follow-up. If you were off-topic, it re-asks. After all questions are answered, the Coach Agent runs a full review."

**Navigate to:** `http://localhost:3000/interview/<session_id>`

---

## Step 6 — Coach Review (20 seconds)

**What to show:** Review page with scores and STAR analysis

**What to say:**

> "The Coach Agent gives you STAR-based feedback on every answer — did you set the situation, describe your task, explain your actions, quantify the result? You get a readiness badge and a list of topics to focus on before the real interview."

**Do:**
1. Navigate to the review page
2. Point at the readiness badge (e.g. "Almost Ready" or "Ready")
3. Point at one per-question score row
4. Scroll to the strengths/improvements section

**Navigate to:** `http://localhost:3000/review/<session_id>`

---

## Wrap-up (15 seconds)

**What to show:** Workflow visualization page

**What to say:**

> "Under the hood, this is a LangGraph workflow with conditional routing — it matches, decides whether to rewrite, runs the interview, and reviews. Each node is a separate agent with its own prompt, retry logic, and fidelity checks. Every Claude call is logged to a database so I can track token usage and latency across the full pipeline."

**Do:**
1. Navigate to `/workflow`
2. Point at the node graph — completed nodes, routing edges

> "The whole stack is open source: React frontend, Java Spring Boot backend, Python FastAPI agent service, Qdrant for vector search. Total cost per full run is about a cent."

**Navigate to:** `http://localhost:3000/workflow`

---

## Timing Summary

| Step | Feature | Time |
|------|---------|------|
| 0 | Overview — Dashboard | 0:15 |
| 1 | Resume Upload + Parse | 0:30 |
| 2 | JD Input + Parse | 0:20 |
| 3 | Match + Radar Chart | 0:30 |
| 4 | Resume Rewrite + Fidelity | 0:30 |
| 5 | Mock Interview (RAG) | 0:30 |
| 6 | Coach Review (STAR) | 0:20 |
| 7 | Wrap-up + Workflow Viz | 0:15 |
| **Total** | | **~3:10** |

---

## Tips

- **If a step is slow:** "The first call is slower because the model is cold-starting — in production I'd pre-warm the endpoints." Keep moving, don't wait.
- **If something fails live:** Navigate to the pre-populated data from `demo-data-setup.sh`. The script exists precisely for this.
- **For a 5-minute version:** Expand Steps 4 and 5 — show a live rewrite call and type a real answer into the interview.
- **For a 1-minute version:** Dashboard → Match radar chart → Rewrite comparison → Review badge. Skip live calls entirely, use pre-populated data.
- **Biggest talking points:** The fidelity checker (anti-hallucination), the LangGraph conditional routing, and the cost (~$0.01 per full run). These tend to get the most follow-up questions.
