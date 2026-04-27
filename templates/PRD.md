# PRD

## 1. Problem statement
OpenClaw Finance needs a repo-local handoff layer that packages stable problem, architecture, implementation, and verification truth for downstream AI agents without disturbing the existing live finance subsystem.

## 2. Users and use cases
### Primary user
Fitz, operating OpenClaw Finance through Discord and local Codex/Claude Code/Codex App workflows.

### Core use cases
1. Run a requirements tribunal before a major finance change to expose hidden branches, risks, and decisions.
2. Produce a stable handoff bundle for another AI agent/reviewer without copying raw runtime state or pretending the zip is a full source mirror.
3. Keep future patches grounded in current finance invariants and verification commands.

## 3. Functional requirements
- [x] Integrate starter-kit docs, prompts, templates, scripts, references, and `.agents/skills` into this repo.
- [x] Preserve existing root `AGENTS.md` as the authority and merge in only compatible handoff guidance.
- [x] Populate finance-specific handoff truth documents from current repo reality.
- [x] Provide `scripts/build_handoff_zip.py` and `scripts/sync_gstack_plan.sh` in this repo.
- [x] Generate a first handoff zip for this repo.
- [x] Document what additional configuration is needed before using the handoff with external agents.

## 4. Non-functional requirements
- [x] No runtime behavior mutation.
- [x] No new dependencies.
- [x] Handoff artifacts must be reviewer-safe and must not expose secrets, raw Flex XML, broker account identifiers, or raw licensed/vendor payloads.
- [x] Existing test/audit suite must remain green.

## 5. Constraints
- Existing finance repo is not a blank starter project; starter-kit files are an exoskeleton only.
- Existing `scripts/`, `docs/`, and `AGENTS.md` have live operational meaning and must not be overwritten blindly.
- Handoff zip is a stable context bundle; real code remains in the true repo/worktree.

## 6. Success metrics
- `python3 scripts/build_handoff_zip.py --project-name openclaw-finance` produces a zip.
- Root handoff templates have no unfilled double-brace placeholder markers in the core finance documents.
- `python3 -m pytest -q tests` passes after integration.
- `python3 tools/audit_operating_model.py` and `python3 tools/audit_benchmark_boundary.py` pass.

## 7. Non-goals
- Do not create a new app shell, dashboard, or standalone terminal.
- Do not rework finance runtime code in this package.
- Do not connect GitHub/ChatGPT settings from code; those are user/account configuration steps.

## 8. Open questions
- Should handoff zip include sanitized `docs/openclaw-runtime/reviewer-packets/` in a later package?
- Should `build_handoff_zip.py` gain a finance-specific manifest mode that includes selected runtime snapshot files?

## 9. Risk notes
- Future agents may assume `templates/` are generic placeholders unless these filled docs are treated as canonical.
- Handoff bundles can go stale quickly after runtime changes unless refreshed during phase closeout.
