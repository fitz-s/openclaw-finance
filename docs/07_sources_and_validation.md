# 07. 外部来源与验证要点

本包基于以下几类现实信息整理：
- OpenAI 官方关于 GitHub connector、Codex、AGENTS.md、skills、PR workflow 的文档
- gstack /office-hours 的仓库与 issue
- superpowers brainstorming 的仓库与 issue
- Anthropic 官方 Claude Code 文档（用于确认 Claude Code 是正式 coding surface）

## 核心校准结论
1. GitHub connector 确实存在，且可以在 ChatGPT 中配置仓库访问。
2. Codex 是独立的 coding surface，不应与普通聊天完全混同。
3. Codex 官方文档明确强调 `AGENTS.md` 和 repo-local skills 是 durable guidance 的关键载体。
4. `gstack /office-hours` 适合第一轮需求压缩，但有 plan mode stale file 风险。
5. superpowers brainstorming 作为方法论是好的，但在某些环境下存在实际调用问题，因此不应成为单点依赖。
