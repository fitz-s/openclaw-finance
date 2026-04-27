# 04. ChatGPT Pro / Codex / GitHub 边界

## 你最容易混淆的三层

### 层 1：ChatGPT 对话
更适合：
- 讨论需求
- 讨论架构
- 审阅设计
- 发现遗漏
- 生成交接文档

### 层 2：Codex coding surface
更适合：
- 真正改代码
- 跑命令
- 执行验证
- review diff
- 在支持的 surface 里 commit / push / PR

### 层 3：GitHub
更适合：
- 持久化 repo 真相
- PR 协作
- comment-driven review
- CI / automation trigger

---

## 关于“能不能直接写 repo”
不要把所有 surface 混成一句话。

更准确的 operational answer 是：

### 普通聊天里的 GitHub connector
主要解决的是“让 ChatGPT 访问仓库上下文”。

### Codex app / local / worktree
在支持的模式下，可以直接：
- commit
- push
- create pull request

### cloud / review / comment workflows
更自然的是：
- 提 proposal
- 做 review
- 处理 PR comment
- 跟着 diff 演进

---

## 所以应该怎么选
如果你要最高确定性：
1. 用 ChatGPT / Codex chat 产出 handoff 文档
2. 在本地 repo 里让 Claude Code / Codex 做真实改动
3. Git 提交与 PR 流程尽量走本地或 Codex app 支持的 Git surface
4. 不把“云端自动回写”当成唯一可靠路径

---

## 最佳实践
- 大任务：先文档锁定，再代码落地
- 高风险改动：先本地 / worktree，后 PR
- recurring workflow：沉淀到 `AGENTS.md` + `.agents/skills/`
- 每轮 patch：必须回写文档和验证命令
