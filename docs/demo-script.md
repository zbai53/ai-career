# Demo Video Script — AI Career Assistant

A word-for-word video recording script for a 3-minute demo.
Total runtime: ~3:00. Timestamps are targets, not hard stops.

**Setup before recording:**
- Run `bash docs/screenshots/demo-data-setup.sh` to pre-populate data
- Open Chrome at `http://localhost:3000` (or your deployed URL), fullscreen
- Have a PDF resume ready for the live drag-and-drop
- Close DevTools, notifications, and all other apps
- Record with QuickTime Player: **File → New Screen Recording → 1280×800**
- Upload finished recording to **YouTube (Unlisted)** and **Bilibili**, then add both links to README.md

---

## 0:00 – 0:15 | Intro

**Show:** Dashboard

**Say (verbatim):**

> "Hi, I'm Bai. I built AI Career — a multi-agent system that automates the job search workflow from resume optimization to mock interviews. Let me show you how it works."

---

## 0:15 – 0:40 | Resume Upload

**Show:** Upload page → parsed result

**Do:**
1. Click "Upload Resume" in the sidebar
2. Drag and drop a PDF resume onto the upload zone
3. Wait ~3–5 s for the parse result to appear
4. Point at the parsed name, skills list, and education

**Say:**

> "Our Resume Agent uses Claude to extract structured data from any PDF format — name, work history, skills, education. Notice it pulled all of this out automatically with no manual tagging."

**Navigate to:** `http://localhost:3000/upload`

---

## 0:40 – 1:00 | JD Input

**Show:** JD input page → parsed result

**Do:**
1. Click "Input JD" in the sidebar
2. Paste a real job description into the text area
3. Click Parse
4. Point at the required skills badges, preferred skills, and salary range

**Say:**

> "The JD Agent identifies exactly what the employer is looking for — required vs. preferred skills, seniority level, and compensation range. This is what the resume gets scored against."

**Navigate to:** `http://localhost:3000/jd`

---

## 1:00 – 1:25 | Match Scoring

**Show:** Match results page with radar chart and gap analysis

**Do:**
1. Click "Run Match" (or use the pre-run result from the setup script)
2. Let the radar chart animate in
3. Point at the overall score
4. Scroll down to the gap analysis section

**Say:**

> "The Match Agent scores your fit across skills, experience, and keywords — no more guessing. The radar chart shows exactly where you're strong and where the gaps are. Here I can see I'm missing a couple of required keywords, and the gap analysis below tells me exactly what to address before applying."

**Navigate to:** `http://localhost:3000/match/<match_id>`

---

## 1:25 – 1:50 | Resume Rewrite

**Show:** Rewrite page with side-by-side bullet comparison and fidelity badge

**Do:**
1. Click "Rewrite Resume" (or navigate to the pre-run rewrite result)
2. Point at a before/after bullet pair — scroll slowly so both are visible
3. Point at the green fidelity badge

**Say:**

> "The Rewrite Agent optimizes your bullets for this specific JD. But here's what makes it different — there's a fidelity checker that prevents hallucination. It uses dual entity extraction — regex plus Claude NER — to verify every claim in the rewritten bullet was actually in your original resume. It won't claim you did something you didn't. If the fidelity score drops below 0.90, the agent retries with the flagged entities explicitly listed in the prompt."

**Navigate to:** `http://localhost:3000/rewrite/<rewrite_id>`

---

## 1:50 – 2:25 | Mock Interview

**Show:** Interview chat with a question, answer, evaluation, and follow-up

**Do:**
1. Navigate to the interview session (or click "Practice Interview" from the rewrite page)
2. Show the first question in the chat UI
3. Type a short answer and submit
4. Point at the real-time evaluation score that appears
5. Show the follow-up question the agent asks

**Say:**

> "The Interview Agent retrieves relevant questions from a 200+ question bank using RAG — semantic search over Qdrant so the questions actually match this JD and your background. It evaluates your answers in real-time using the STAR framework, and asks follow-ups when you're too vague. Watch — I gave a high-level answer and it probed for specifics."

**Navigate to:** `http://localhost:3000/interview/<session_id>`

---

## 2:25 – 2:45 | Workflow Visualization

**Show:** React Flow workflow page

**Do:**
1. Navigate to `/workflow`
2. Pan slowly across the node graph
3. Point at the conditional routing edge between Match and Rewrite

**Say:**

> "Under the hood, 6 agents are orchestrated by a LangGraph state machine with conditional routing — a low match score triggers a rewrite loop before the interview starts. Each node has its own retry logic and prompt. Every Claude call is logged to a database so I can track token usage and latency across the full pipeline."

**Navigate to:** `http://localhost:3000/workflow`

---

## 2:45 – 3:00 | Closing

**Show:** Workflow page or Dashboard

**Say:**

> "Built with Spring Boot, FastAPI, LangGraph, React, and Qdrant. The system includes PII anonymization, fidelity checking, and full observability. This is AI Career — turning hours of job search preparation into 30 minutes."

---

## Timing Summary

| Timestamp | Section | Duration |
|-----------|---------|----------|
| 0:00 – 0:15 | Intro | 15 s |
| 0:15 – 0:40 | Resume Upload | 25 s |
| 0:40 – 1:00 | JD Input | 20 s |
| 1:00 – 1:25 | Match Scoring | 25 s |
| 1:25 – 1:50 | Resume Rewrite | 25 s |
| 1:50 – 2:25 | Mock Interview | 35 s |
| 2:25 – 2:45 | Workflow Visualization | 20 s |
| 2:45 – 3:00 | Closing | 15 s |
| **Total** | | **~3:00** |

---

## Recording Tips

- **Resolution:** 1280×800 via QuickTime Player → File → New Screen Recording → select window
- **Upload:** YouTube (Unlisted) + Bilibili; add both URLs to the video links section in `README.md`
- **If a step is slow:** Say "The first call is slower — the model is loading" and keep moving. Don't wait on screen.
- **If something fails live:** Use the pre-populated data from `demo-data-setup.sh` — have the IDs from the script output ready in a sticky note.
- **Key talking points that get follow-up questions:** the fidelity checker (anti-hallucination), the LangGraph conditional routing, and cost (~$0.01 per full run).

## Alternate Lengths

- **1-minute cut:** Dashboard → Match radar chart → Rewrite comparison. Skip live calls, use pre-populated data.
- **5-minute cut:** Expand the Interview section — type a real 3-sentence answer and walk through the STAR evaluation feedback line by line.
