# AI Handoff Current Repo Configuration

## What was integrated

Copied from `/Users/leofitz/Downloads/ai-handoff-complete-implementation`:

- `docs/01_reality_check.md` through `docs/07_sources_and_validation.md`
- `prompts/*.txt`
- `templates/*.md`
- `.agents/skills/requirements-tribunal/SKILL.md`
- `.agents/skills/handoff-packager/SKILL.md`
- `scripts/build_handoff_zip.py`
- `scripts/sync_gstack_plan.sh`
- `references/SOURCES.md`
- `START_HERE.md`

The package `README.md` and `AGENTS.md` were preserved as references:

- `docs/ai-handoff-starter-README.md`
- `docs/ai-handoff-starter-AGENTS.md`

## Why root AGENTS was not overwritten

This repo already has a live OpenClaw Finance `AGENTS.md` with review-only finance boundaries, commit protocol, verification commands, parent runtime mirror rules, and workflow routing. Replacing it with the generic starter-kit `AGENTS.md` would remove critical finance constraints.

Instead, the root `AGENTS.md` includes a short handoff overlay and links to this document.

## Additional local/user configuration still needed

These cannot be safely completed from repo code alone:

- If using ChatGPT GitHub connector, authorize the repository in ChatGPT settings and GitHub app permissions.
- If using Claude Code / gstack, install/enable those tools in the local user environment.
- If using repo-local `.agents/skills` in a tool that does not auto-discover them, manually copy or symlink them into that tool's skill path.
- If distributing the handoff zip externally, review whether to include sanitized reviewer packets; the default zip intentionally does not include full source or runtime `state/`.

## How to use in this repo

1. Read `START_HERE.md`.
2. Read `docs/01_reality_check.md` and `docs/02_end_to_end_workflow.md`.
3. Read the finance-specific truth surfaces in `templates/`.
4. For requirement closure, use `prompts/01_claude_code_requirements.txt` or `.agents/skills/requirements-tribunal/SKILL.md`.
5. For final lock, use `prompts/02_chatgpt_pro_finalize.txt`.
6. For implementation, use actual repo worktree, not the zip as a source snapshot.
7. Generate zip with `python3 scripts/build_handoff_zip.py --project-name openclaw-finance`.

## Verification

- `python3 scripts/build_handoff_zip.py --project-name openclaw-finance`
- `python3 -m pytest -q tests`
- `python3 -m compileall -q scripts tools tests`
- `python3 tools/audit_operating_model.py`
- `python3 tools/audit_benchmark_boundary.py`
