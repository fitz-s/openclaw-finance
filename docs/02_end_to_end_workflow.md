# 02. 端到端完整流程

## Phase 0 — Seed Brief
先写一页 `PROJECT_BRIEF.md`，只回答：
- 你到底要解决什么问题
- 谁是用户
- 成功标准是什么
- 什么不做
- 目前已知的技术/业务/权限约束是什么

不要一开始写大而全 PRD。  
先锁 problem，防止模型替你偷换目标。

## Phase 1 — Claude Code 需求审判（Requirement Tribunal）
目标：
- 找需求里没写但决定成败的 load-bearing branches
- 暴露 hidden assumptions
- 把 vague wish 变成 explicit decisions / open questions / tradeoffs

推荐方式：
1. 优先用 `gstack /office-hours`
2. 如果你的环境里 superpowers brainstorming 可稳定调用，也可以并用
3. 如果 skill 有兼容问题，就直接使用本包提供的 `prompts/01_claude_code_requirements.txt`

这一阶段的产物：
- `PRD.md`
- `OPEN_QUESTIONS.md`
- `RISKS.md`
- 初版 `ARCHITECTURE.md`

## Phase 2 — ChatGPT Pro / Codex 方案定稿
目标：
- 压缩需求分歧
- 补齐遗漏
- 给出实施主路径
- 列出 not-now list
- 产出 task decomposition

这一阶段不是“让它直接闷头写 50 个文件”。  
而是让它做：
- requirements closure
- architecture lock
- decision register
- execution plan

产物：
- 最终 `PRD.md`
- 最终 `ARCHITECTURE.md`
- `IMPLEMENTATION_PLAN.md`
- `TASK_PACKET.md`
- `VERIFICATION_PLAN.md`

## Phase 3 — 生成 handoff zip
用 `scripts/build_handoff_zip.py`，把必要文件打包成：
- 文档真相层
- Prompt 层
- Agent guidance 层
- 引用/资料层
- 初始目录结构

这个 zip 的目的不是给人看，是给下游 agent **稳定继承上下文**。

## Phase 4 — 本地 Claude Code / Codex 生成首版 scaffold
在 VS Code 打开解压后的目录，让本地 agent 做：
- 项目框架
- 目录结构
- 基础配置
- CI / lint / test harness
- 核心 interfaces
- 最小工作闭环

不要让它第一步就把全部细节业务逻辑写满。  
首要目标是：**让 repo 变成可持续迭代的工程面**。

## Phase 5 — GitHub 接入
把 repo 推到 GitHub 后：
- 连接 ChatGPT 的 GitHub app
- 在支持的 Codex surface 中使用 repo
- 进入 PR / review / patch loop

## Phase 6 — 持续迭代
把 recurring guidance 写回：
- `AGENTS.md`
- `.agents/skills/*`
- 测试脚本
- lint / typecheck / CI
否则每一轮都要重新教育 agent。
