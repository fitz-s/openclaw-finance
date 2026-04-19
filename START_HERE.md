# AI 编码交接包：完整实现版

这个包不是“文章复述”，而是把那篇文章真正压成一套可执行 workflow + 文件结构 + prompt pack + packager 脚本。

## 你现在拿到的是什么
- 一套可以直接 unzip 后放进 VS Code 的项目起始结构
- 一套把 **Claude Code / ChatGPT Pro / Codex / GitHub** 分工拆清楚的流程
- 一套用于 **需求讨论 → 最终需求定稿 → 架构设计 → handoff zip → 本地编码 → GitHub 迭代** 的模板
- 两个可直接复用的本地 skill：
  - `requirements-tribunal`
  - `handoff-packager`
- 两个实用脚本：
  - `scripts/sync_gstack_plan.sh`：处理 gstack `/office-hours` + Claude Code plan mode 的文件不同步问题
  - `scripts/build_handoff_zip.py`：把文档、prompt、AGENTS、实现计划打成 handoff zip

## 推荐使用顺序
1. 先读 `docs/01_reality_check.md`
2. 再读 `docs/02_end_to_end_workflow.md`
3. 把 `templates/` 里的文件填起来
4. 用 `prompts/01_claude_code_requirements.txt` 在 Claude Code 里做第一轮需求审判
5. 用 `prompts/02_chatgpt_pro_finalize.txt` 在 ChatGPT Pro / Codex chat 里做最终定稿
6. 用 `python scripts/build_handoff_zip.py --project-name your-project` 生成 handoff zip
7. 打开整个项目目录，让 Claude Code / Codex 本地生成第一版代码
8. 再连接 GitHub，进入 PR / review / patch loop

## 这套实现修正了原文章的三个混淆
1. **ChatGPT GitHub connector** 和 **Codex coding surface** 不是同一个层。
2. “让 Pro 写代码”在今天更准确的说法应是：
   - 普通 ChatGPT 对话：更适合需求、方案、架构、文档、审阅
   - Codex app / Codex cloud / local Codex：更适合真正落地代码、跑命令、做 PR 流程
3. “zip handoff”不应只是随便压缩几个 md，而应有明确 contract；否则下游 agent 还是会丢上下文。

## 最重要的原则
不要把顶级模型先拿去“直接写第一坨代码”。
先让它做：
- problem framing
- requirement closure
- architecture lock
- risk surface enumeration
- implementation decomposition

真正的首版 scaffold，更适合交给本地 Claude Code / Codex 去做，因为本地环境最接近真实 repo 和真实命令执行面。
