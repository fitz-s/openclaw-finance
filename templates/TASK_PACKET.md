# TASK_PACKET

## Task
Integrate AI handoff starter kit into OpenClaw Finance as a non-runtime exoskeleton.

## Objective
Enable future AI agents to inherit requirements, architecture, implementation, and verification truth without changing live finance behavior.

## Inputs
- `/Users/leofitz/Downloads/ai-handoff-complete-implementation`
- Existing OpenClaw Finance repo at `/Users/leofitz/.openclaw/workspace/finance`
- Current root `AGENTS.md`
- Current P0-P9 finance runtime commits on `main`

## Files likely involved
- `AGENTS.md`
- `docs/01_reality_check.md` through `docs/07_sources_and_validation.md`
- `prompts/*.txt`
- `templates/*.md`
- `.agents/skills/*/SKILL.md`
- `scripts/build_handoff_zip.py`
- `scripts/sync_gstack_plan.sh`
- `docs/ai-handoff-current-repo-config.md`

## Invariants
- Existing finance runtime behavior must not change.
- Existing source/tests must not be overwritten by starter-kit placeholders.
- Root `AGENTS.md` remains finance/OpenClaw authoritative.
- Handoff zip is not a full repo snapshot.

## Steps
1. Copy starter-kit guidance assets safely.
2. Fill finance-specific handoff documents.
3. Add root AGENTS overlay pointing to handoff workflow.
4. Build handoff zip.
5. Run tests/audits.

## Verification
- `python3 scripts/build_handoff_zip.py --project-name openclaw-finance`
- `python3 -m pytest -q tests`
- `python3 tools/audit_operating_model.py`

## Rollback / blast radius
- Remove copied handoff docs/prompts/templates/.agents/references/scripts and generated zip.
- Revert only the handoff overlay in `AGENTS.md`.
- No runtime rollback should be needed because runtime behavior is unchanged.
