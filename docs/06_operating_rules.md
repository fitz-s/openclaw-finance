# 06. Operating Rules（高成功率运行法）

## Rule 1 — 先锁 problem，再锁 code
最贵的错误不是代码 bug，而是目标偷换。

## Rule 2 — 一切大任务都要有 not-now list
不把边界写出来，agent 会自动扩张任务范围。

## Rule 3 — 每次修正都尽量沉淀为 durable guidance
优先写回：
- `AGENTS.md`
- skills
- scripts
- test
- lint rule
- CI

## Rule 4 — 文档和代码都必须有 verification surface
只写“方案”不写“怎么验证”，下游会漂。

## Rule 5 — patch loop 必须小步
不要一次做 feature + refactor + infra + docs + tests 全混。

## Rule 6 — 让模型做它强的事
顶级模型最强的不是“直接打一坨代码”，而是：
- 发现遗漏
- 识别 hidden branches
- 压缩复杂决策面
- 提炼 durable guidance
- 设计验证与 rollback

## Rule 7 — 让本地环境做真实执行
代码最终正确性，还是最依赖真实 repo、真实命令、真实 test harness。
