# 01. 现实边界校准（Reality Check）

这篇文章的主线是对的，但它把几个产品层混在了一起。真正落地时，必须拆清：

## A. ChatGPT GitHub connector
这是 **连接代码仓库上下文** 的层。  
你在 ChatGPT 里授权 GitHub app，然后选择 ChatGPT 可以访问哪些 repository。  
这不自动等于“普通聊天窗口就拥有完整本地开发能力”。

## B. Codex / coding surface
这是 **真正读写代码、跑命令、做 review、PR workflow** 的层。  
Codex 可以在隔离环境中处理代码任务；在支持的本地 / worktree 模式下，还可以直接 commit、push、create pull request。  
因此，“ChatGPT Pro 不能提交 commit”这句话太绝对了：  
更准确的说法是——**要看你处在哪个产品 surface**。

## C. zip handoff
zip 不是一个“把几份 md 随便压缩起来”的动作。  
它应该是一个 **contracted handoff artifact**，用于把：
- problem framing
- requirement closure
- architecture decisions
- implementation decomposition
- execution prompts
- known risks
一起稳定传给下游 coding agent。

## D. Claude Code skills
文章里提到“先用 Claude Code 找靠谱 Skill 讨论需求”，这个方向是对的。  
但现实上你要注意：
- `gstack /office-hours` 很适合做第一轮需求收敛
- `superpowers brainstorming` 的思路也对
- 但具体插件/skill 在真实环境中会有兼容性和调用问题，不能把它当作绝对稳定依赖

## 一句话修正版
正确说法不是：
> ChatGPT Pro 一把从需求写到全部代码

而是：
> 用 Claude Code / skills 做第一轮需求审判；  
> 用 ChatGPT Pro / Codex 做高强度方案定稿；  
> 用 handoff zip 把 truth surfaces 打包；  
> 用本地 Claude Code / Codex 写第一版 scaffold 和代码；  
> 再用 GitHub + Codex/PR loop 做持续迭代。
