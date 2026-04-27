# IMPLEMENTATION_PLAN

## Stage 0 — Confirm truth surfaces
- [x] Inspect starter-kit package contents.
- [x] Confirm existing repo root files and avoid overwriting runtime source/tests.
- [x] Preserve existing `AGENTS.md` authority.

## Stage 1 — Foundation
- [x] Create `ai-upgrade-foundation` branch.
- [x] Copy starter-kit docs/prompts/templates/scripts/references/.agents skills into repo.
- [x] Store generic starter-kit AGENTS as `docs/ai-handoff-starter-AGENTS.md` instead of replacing root AGENTS.
- [x] Add root AGENTS handoff overlay.

## Stage 2 — Core truth docs
- [x] Fill `templates/PROJECT_BRIEF.md`.
- [x] Fill `templates/PRD.md`.
- [x] Fill `templates/ARCHITECTURE.md`.
- [x] Fill `templates/IMPLEMENTATION_PLAN.md`.
- [x] Fill task packet, verification plan, decisions, risks, open questions, and not-now list.

## Stage 3 — Verification
- [x] Build handoff zip.
- [x] Run tests and audits.
- [x] Confirm no runtime behavior changed.
- [x] Confirm no placeholder markers remain in canonical handoff docs.

## Stage 4 — Expansion
- [ ] Optional later: finance-specific `build_handoff_zip.py` mode that includes selected sanitized runtime snapshots.
- [ ] Optional later: CI check that handoff docs have no placeholders.
- [ ] Optional later: include sanitized reviewer packets when explicitly requested.

## Per-stage output contract
For each later handoff-driven phase, output:
- touched files
- why
- verification result
- what remains
- rollback note
