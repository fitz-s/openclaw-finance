# 03. Claude Code Skills 策略

## 推荐优先级

### 1) gstack `/office-hours`
适合：
- 第一轮需求探查
- 用户、场景、 wedge、边界、决策前置讨论
- 从模糊 idea 压缩成 design doc

为什么推荐：
- 它本身就是一个成体系流程的一部分，不只是单个 prompt
- 后续还可以衔接 review / test / ship 相关技能链

### 2) superpowers brainstorming
适合：
- idea 到 design 的自然协作式推进
- 一问一答式 refinement

但现实注意：
- 某些环境下存在 skill invocation 问题
- 所以它更适合作为“可用则用”的第二选择，而不是唯一依赖

### 3) 直接 structured prompt fallback
如果外部 skill 环境不稳定，就直接用本仓库 `prompts/01_claude_code_requirements.txt`。  
不要因为 skill 不可用，就让整个 workflow 停摆。

---

## gstack 的一个现实坑
如果你在 Claude Code plan mode 里跑 `/office-hours`，之后又手动改了 plan，可能会出现：
- `.gstack/...` 里的设计稿变旧
- `.claude/plans/...` 是新版本
- 下游 gstack skill 继续读取旧文档

本仓库里提供了：
- `scripts/sync_gstack_plan.sh`

用途：
把更新后的 `.claude/plans/*.md` 同步回 `.gstack/...`，避免下游继续吃 stale design doc。

---

## 最稳的策略
1. skill 先做 discovery
2. 关键结论落回仓库内文档
3. 后续 agent 永远读 repo 内的 canonical docs
4. 不把“某个 skill 的对话状态”当成唯一真相层
