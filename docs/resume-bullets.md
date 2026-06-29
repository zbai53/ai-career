# Resume Bullets — AI Career Assistant

## English (Canadian Market)

**AI Career Assistant** | Personal Project | Python · Java · TypeScript · LangGraph · React
*github.com/zbai53/ai-career*

- Designed and implemented a multi-agent job-search assistant with 6 specialized LangGraph agents (resume parser, JD analyzer, match scorer, resume rewriter, interview coach, fidelity checker), using conditional branching and MemorySaver checkpoint persistence to enable reliable, resumable workflows
- Built a production-grade polyglot backend: Spring Boot 3.2 + MyBatis/PostgreSQL REST API orchestrating a Python/FastAPI microservice, with agent-run observability logging (token usage, latency, cost) and graceful error recovery across service boundaries
- Engineered a resume fidelity evaluation system using dual entity extraction (regex + Claude-assisted NER) to prevent hallucination in AI-rewritten bullets; configurable thresholds (STRICT 0.90 / WARN 0.80) with automatic retry up to 3 attempts before flagging for human review
- Built a domain-specific RAG pipeline ingesting 200+ curated interview questions and ATS keywords into Qdrant (all-MiniLM-L6-v2, 384-dim vectors), enabling semantically relevant question selection and real-time ATS coverage scoring
- Developed a React 18 frontend with React Flow + SSE-based live workflow visualization, Recharts radar chart for multi-dimensional match scoring, and a multi-turn interview chat UI featuring typewriter animation and STAR framework evaluation feedback
- Implemented a GDPR/PIPEDA-compliant data pipeline with stateless PII anonymization (mask/unmask surviving retry loops) before all LLM calls, and a cascading user data deletion API covering 6 tables in FK-safe order

---

## 中文（国内市场）

**AI 求职助手** | 个人项目 | Python · Java · TypeScript · LangGraph · React
*github.com/zbai53/ai-career*

- 设计并实现了基于 LangGraph 状态机的多智能体求职系统，包含 6 个专业 Agent（简历解析、JD 分析、匹配评分、简历改写、面试教练、真实性校验），支持条件分支路由与 MemorySaver 断点续跑，全流程可观测
- 构建生产级异构后端：Spring Boot 3.2 + MyBatis/PostgreSQL REST API 编排 Python/FastAPI 微服务，集成 Agent 运行日志（Token 用量、延迟、成本），跨服务边界具备完善的错误恢复机制
- 开发简历改写真实性校验引擎，融合正则与 Claude NER 双重实体抽取防止 AI 幻觉；设置 STRICT（0.90）/ WARN（0.80）可配置阈值，失败自动重试最多 3 次，超限后标记人工审核
- 构建领域专属 RAG 管道，将 200+ 精选面试题与 ATS 关键词向量化入 Qdrant（all-MiniLM-L6-v2，384 维），实现语义相关题目动态召回与实时 ATS 覆盖率评分
- 使用 React 18 开发前端，集成 React Flow + SSE 实时工作流可视化、Recharts 雷达图多维匹配评分展示，以及支持打字机动画与 STAR 框架评分反馈的多轮对话面试模拟界面
- 实现符合 GDPR/PIPEDA 的数据合规管道：所有 LLM 调用前进行无状态 PII 脱敏（mask/unmask 可在重试循环中存活），并提供按 FK 安全顺序级联删除 6 张表的用户数据清除 API
