# DECISIONS

## Decided
- Keep the existing OpenClaw Finance `AGENTS.md` as root authority; do not overwrite it with the starter-kit AGENTS.
- Copy starter-kit docs/prompts/templates/.agents skills/scripts as a repo-local handoff layer.
- Treat `templates/*.md` as filled canonical handoff docs for this repo, not unfilled template placeholders.
- Generate handoff zip from documentation/guidance only; real code remains in the true repo/worktree.

## Decided with caution
- Copy generic starter-kit docs into `docs/01_*` through `docs/07_*`; these are workflow docs and must not override finance runtime contracts.
- Add `.agents/skills` even though existing Codex skills live under `~/.codex/skills`; these repo-local skills are handoff references unless a tool surface explicitly supports them.
- Add scripts into existing `scripts/` only because file names do not conflict with finance runtime scripts.

## Escalate later
- Whether handoff zips should include sanitized reviewer packets.
- Whether CI should enforce handoff doc placeholder-free status.
- Whether `build_handoff_zip.py` should support a finance-specific include list.

## Why these decisions exist
This repo is a live finance subsystem with strict OpenClaw and review-only constraints. The starter kit is useful as an exoskeleton, but replacing core guidance or runtime files would be a regression. The integration therefore adds durable handoff surfaces while preserving current authority boundaries.
