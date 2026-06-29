# LinkedIn Post — Build in Public

## English Version

🚀 I just finished building AI Career — a multi-agent job search assistant that I wish I had during my 700+ application marathon in Canada.

The system covers the full pipeline:
📄 Resume parsing (PDF/DOCX → structured JSON)
🎯 JD analysis & multi-dimension matching
✍️ AI-powered resume rewriting with hallucination prevention
🎤 RAG-powered mock interviews with real-time coaching

Tech stack: Spring Boot + FastAPI + LangGraph + React + Qdrant + Claude API

The most challenging part? Building the fidelity checker that prevents the LLM from fabricating resume content. The system extracts entities from both the original and rewritten versions, flags any new claims, and retries with stricter constraints.

6 agents, 45 days, built solo. Open source on GitHub.

#AI #LangGraph #JobSearch #OpenSource #BuildInPublic

---

## 中文版

🚀 我花了 45 天，独立构建了 AI Career —— 一个多智能体求职助手。这是我在加拿大海投 700+ 份简历期间最希望拥有的工具。

系统覆盖求职全流程：
📄 简历解析（PDF/DOCX → 结构化 JSON）
🎯 JD 分析 & 多维度匹配评分
✍️ AI 简历改写（含幻觉防护机制）
🎤 RAG 驱动的模拟面试 + 实时 Coach 反馈

技术栈：Spring Boot + FastAPI + LangGraph + React + Qdrant + Claude API

最难的部分？构建保真校验器（Fidelity Checker）—— 防止大模型在改写简历时无中生有。系统从原始版本和改写版本中分别抽取实体，标记任何新增声明，并在失败时以更严格的约束重试。

6 个 Agent，45 天，独立开发。已开源在 GitHub。

#AI #LangGraph #求职 #开源 #BuildInPublic
