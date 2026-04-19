# ARCHITECTURE

## 1. System boundary
This repo is the OpenClaw-embedded finance subsystem. It is review-only capital governance and user-visible reporting through parent OpenClaw/Discord delivery. The AI handoff layer is documentation/guidance infrastructure only; it does not execute trades, change delivery, mutate wake thresholds, or call broker APIs.

## 2. Main components
- Existing finance runtime: `scripts/`, `state/`, `docs/openclaw-runtime/`, `tests/`, OpenClaw parent cron/runtime mirrors.
- Handoff exoskeleton: `docs/01_*` through `docs/07_*`, `prompts/`, `templates/`, `.agents/skills/`, `references/`, `scripts/build_handoff_zip.py`, `scripts/sync_gstack_plan.sh`.
- Root guidance integration: existing `AGENTS.md` remains authoritative and points to handoff workflow for major changes.

## 3. Data flow
Major change request -> requirements tribunal prompt/skill -> filled truth docs -> ChatGPT/Codex final lock -> handoff zip -> local Codex/Claude Code implementation in actual repo -> tests/audits -> commit/push/PR loop.

## 4. Interfaces / contracts
- `AGENTS.md`: root operating contract for agents.
- `templates/*.md`: canonical handoff truth surfaces for this repo.
- `prompts/*.txt`: repeatable model prompts for requirement, finalization, scaffold, patch, and PR review loops.
- `.agents/skills/*/SKILL.md`: local skill surfaces for requirements tribunal and handoff packaging.
- `scripts/build_handoff_zip.py`: packages the handoff/guidance layer, not the full source repo.

## 5. Key invariants
- Finance remains review-only: no execution, no broker mutation, no threshold mutation, no live authority escalation.
- Discord/user-visible delivery remains parent OpenClaw owned and safety gated.
- Handoff docs must distinguish facts, decisions, risks, open questions, and not-now items.
- No starter-kit placeholder `src/` or `tests/` overwrites existing repo source/tests.

## 6. Failure modes
- Generic starter-kit AGENTS overwrites finance AGENTS and breaks OpenClaw-specific instructions.
- Handoff zip is mistaken for a full code snapshot and downstream agent lacks actual repo context.
- Future agents update code without updating truth docs, causing documentation drift.
- Handoff docs include secrets or live runtime state that should remain local.

## 7. Verification surface
- `python3 scripts/build_handoff_zip.py --project-name openclaw-finance`
- `python3 -m pytest -q tests`
- `python3 -m compileall -q scripts tools tests`
- `python3 tools/audit_operating_model.py`
- `python3 tools/audit_benchmark_boundary.py`
- `python3 tools/export_openclaw_runtime_snapshot.py`

## 8. Rollback considerations
- Remove `docs/01_*` through `docs/07_*`, `prompts/`, `templates/`, `.agents/skills/`, `references/`, copied handoff scripts, `START_HERE.md`, generated `dist/` zip.
- Revert the small `AGENTS.md` handoff overlay section only; do not touch existing finance AGENTS content.

## 9. Not-now architecture items
- Full repo snapshot packaging.
- Automated GitHub connector/account configuration.
- Sanitized reviewer-packet inclusion in handoff zip.
- New CI pipeline for handoff validation.
