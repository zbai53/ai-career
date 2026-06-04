# 05 — Interview Prep

> 30 questions a hiring manager might ask about this project.
> Grouped by topic. Practice answering each in ≤2 minutes.
> Mark ✅ when you can answer confidently without notes.

---

## Motivation & product sense

- [ ] 1. Why did you build this? What problem does it solve?
- [ ] 2. Who is the target user? How did you validate the need?
- [ ] 3. How is this different from Jobscan / Final Round AI / ChatGPT?
- [ ] 4. If you had 3 more months, what feature would you add first?
- [ ] 5. Would you charge for this? How would you price it?

## Architecture & design

- [ ] 6. Walk me through the system architecture. Why two services?
- [ ] 7. Why Spring Boot for the main service and Python for agents?
- [ ] 8. How do the services communicate? What happens if the agent service is slow?
- [ ] 9. Why LangGraph instead of LangChain? What does the state machine give you?
- [ ] 10. How would you add a 7th agent to the system? What changes?
- [ ] 11. How do you handle a user closing the browser mid-workflow?
- [ ] 12. Draw the database schema on a whiteboard. Explain each table.

## Agents & LLM engineering

- [ ] 13. What is a "multi-agent system"? Why not one big prompt?
- [ ] 14. How does the Resume Agent handle a two-column PDF layout?
- [ ] 15. What is "hallucination" in resume rewriting? Why is it dangerous?
- [ ] 16. Explain your fidelity checking algorithm step by step.
- [ ] 17. How did you evaluate the Rewrite Agent's output quality?
- [ ] 18. What prompt engineering techniques did you use? Give an example.
- [ ] 19. How does the Interview Agent decide which question to ask next?
- [ ] 20. How does the Coach Agent score interview answers?

## RAG & vector search

- [ ] 21. What is RAG? Why do you need it instead of fine-tuning?
- [ ] 22. What embedding model did you use? Why that one?
- [ ] 23. How is Qdrant different from a traditional database for this use case?
- [ ] 24. How would you scale the question bank to 10,000+ entries?

## Data & compliance

- [ ] 25. How do you handle PII in this system? Walk me through the data flow.
- [ ] 26. What is PIPEDA? How does your system comply with it?
- [ ] 27. What happens when a user requests data deletion?
- [ ] 28. How do you prevent sensitive data from leaking into LLM logs?

## Scalability & production

- [ ] 29. What would break first if 1,000 users hit this simultaneously?
- [ ] 30. How do you monitor LLM costs in production? What metrics do you track?

---

## Answer frameworks for the top 5 questions

### Q1: Why did you build this?

**Framework:** Personal story → pain point → existing gaps → your solution

> "I went through a tough job search — 700+ applications, fewer than 5
> interviews. The tools I tried were shallow: Jobscan matches keywords but
> doesn't understand context, ChatGPT wrappers will fabricate experience
> you never had. I wanted something that covers the full pipeline — from
> understanding the JD to practicing the interview — with safeguards
> against hallucination. So I built it and used it in my own search."

### Q6: Walk me through the architecture.

**Framework:** Start with the user → follow the data flow → explain each
decision

> "The user interacts with a React frontend. Requests go to a Spring Boot
> service that handles auth, file storage, and business logic. For anything
> involving LLM reasoning — parsing, matching, rewriting, interviewing —
> Spring Boot delegates to a Python/FastAPI microservice running LangGraph.
> The agents are orchestrated as a state machine, so the flow can branch
> (rewrite vs. interview) and resume if interrupted. We split Java and
> Python because LangGraph is Python-native but the Canadian market values
> Java backend skills. The two services talk via REST, with webhooks for
> long-running tasks."

### Q9: Why LangGraph over LangChain?

**Framework:** What they are → what's different → why it matters here

> "LangChain is great for linear chains — A then B then C. But our flow
> isn't linear: after matching, the user might rewrite OR practice
> interviews. Interviews are multi-turn loops. LangGraph models this as a
> state graph with conditional edges, so we can branch, loop, and
> checkpoint. The checkpoint feature is key — if the user leaves mid-
> interview, we can resume from exactly where they stopped. LangChain
> can't do that natively."

### Q15: What is hallucination in resume rewriting?

**Framework:** Define → example → why dangerous → your solution

> "Hallucination here means the LLM invents experience you never had.
> For example, your original says 'used React' and the rewrite says 'led
> a team of 5 to migrate from Angular to React' — the leadership and
> Angular parts are fabricated. This is dangerous because if you get an
> interview and can't back it up, you're done. Our fidelity checker
> extracts all factual entities — companies, titles, years, metrics — from
> both versions and flags any new entity not in the original. If the score
> is below threshold, we retry with a stricter prompt."

### Q25: How do you handle PII?

**Framework:** List the measures → walk through the data flow

> "Three layers. First, before any LLM call, we replace PII — name, email,
> phone, address — with placeholders like [NAME]. The LLM never sees real
> PII. After the response, we swap placeholders back. Second, raw uploaded
> files are stored in S3 with a 24-hour TTL — auto-deleted after that. We
> only persist the parsed JSON, not the raw text. Third, all data is
> encrypted at rest, and the user can hit one endpoint to delete everything
> we have on them — that cascades through all tables. This covers PIPEDA
> in Canada and GDPR in Europe."
