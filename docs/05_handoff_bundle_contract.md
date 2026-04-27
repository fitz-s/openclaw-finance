# 05. Handoff Bundle Contract

handoff zip 必须满足“下游 agent 解压后就知道该怎么继续”的 contract。

## 必选内容

### 1. Problem truth
- `PROJECT_BRIEF.md`
- `PRD.md`
- `OPEN_QUESTIONS.md`

### 2. Architecture truth
- `ARCHITECTURE.md`
- `DECISIONS.md`
- `RISKS.md`

### 3. Execution truth
- `IMPLEMENTATION_PLAN.md`
- `TASK_PACKET.md`
- `VERIFICATION_PLAN.md`

### 4. Agent guidance
- `AGENTS.md`
- `.agents/skills/*`（如果有）

### 5. Prompt layer
- 给 Claude Code 的 prompt
- 给 ChatGPT Pro / Codex 的 prompt
- 给 patch/review loop 的 prompt

### 6. References
- 外部资料
- 官方文档
- issue/workaround
- 任何会影响正确实施的引用

## 可选内容
- 样板目录结构
- `.env.example`
- `Makefile`
- `docker-compose.yml`
- `requirements.txt` / `package.json`
- 迁移/数据示例
- mock API schema

## 不应该把什么塞进去
- 大量无关聊天记录
- 没有被确认为 canonical 的草稿
- 冗长但不产生约束的“灵感”
- 多个互相冲突的架构版本

## Bundle 的目标
不是“看上去很全”，而是：
- 下游 agent 不会偷换目标
- 不会忽视关键约束
- 不会把 open question 当成 settled truth
- 不会因为缺上下文而乱补
