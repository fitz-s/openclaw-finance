# 完整实现：把“文章里的 workflow”变成可运行系统

本仓库是一个 **AI coding handoff starter kit**。  
目标不是讨论概念，而是把下面这件事真正做出来：

> 先用 Claude Code/skills 把需求和歧义压缩；  
> 再用 ChatGPT Pro / Codex 进行高强度需求定稿与架构分解；  
> 再导出一个 handoff zip；  
> 再由本地 Claude Code / Codex 接着写代码；  
> 再接 GitHub，进入可持续的 review / PR / patch 循环。

## 目录
- `docs/`：现实边界、完整流程、GitHub/Codex 产品边界、handoff contract
- `prompts/`：可直接投喂的 prompt pack
- `templates/`：需求文档、架构文档、实现计划、任务包模板
- `.agents/skills/`：本地 skill 样板
- `scripts/`：打包和同步脚本
- `src/`、`tests/`：代码落点

## 核心结果
你不需要从零重想“应该怎么和模型协作”。
你只需要：
1. 填模板
2. 跑流程
3. 打 zip
4. 让 agent 接着干活
