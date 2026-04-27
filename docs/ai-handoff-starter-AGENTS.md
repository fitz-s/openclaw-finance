# AGENTS.md

## Purpose
This repository is a handoff-oriented starter kit for AI-assisted software delivery.
Every agent must preserve the separation between:
1. requirements truth
2. architecture truth
3. implementation truth
4. verification truth

Do not collapse these layers.

## Operating rules
- First read `docs/01_reality_check.md` and `docs/02_end_to_end_workflow.md`.
- Before editing code, read:
  - `templates/PRD.md`
  - `templates/ARCHITECTURE.md`
  - `templates/IMPLEMENTATION_PLAN.md`
- When requirements are still ambiguous, do not jump into code generation.
- Prefer updating documents before changing code when the requested change affects scope, semantics, interfaces, or constraints.
- Keep a strict distinction between:
  - fact
  - interpretation
  - open question
  - decision
- When a recurring mistake appears, update this file or add a repo-local skill instead of repeating the same human correction.

## Required outputs for non-trivial changes
For any medium or large change, produce:
1. impact summary
2. touched files list
3. invariants that must remain true
4. verification plan
5. rollback note

## Handoff discipline
When preparing a handoff package, ensure the final zip contains:
- brief
- PRD
- architecture
- implementation plan
- task packets
- AGENTS.md
- prompts
- references
- known risks / not-now list

## Git discipline
If running in a surface that supports Git operations:
- prefer small atomic commits
- do not mix refactor + feature + docs unless explicitly requested
- summarize why each commit exists, not just what changed
