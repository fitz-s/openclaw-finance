# VERIFICATION_PLAN

## Mandatory commands
- `python3 scripts/build_handoff_zip.py --project-name openclaw-finance`
- `python3 -m pytest -q tests`
- `python3 -m compileall -q scripts tools tests`
- `python3 tools/audit_operating_model.py`
- `python3 tools/audit_benchmark_boundary.py`
- `python3 tools/export_openclaw_runtime_snapshot.py`
- `rg '\{\{[A-Z0-9_]+\}\}' templates docs/ai-handoff-current-repo-config.md OPEN_QUESTIONS.md RISKS.md || true`

## What each command proves
- `build_handoff_zip.py` -> handoff bundle can be generated from repo-local truth surfaces.
- `pytest` -> existing finance behavior and new handoff smoke tests remain valid.
- `compileall` -> Python scripts/tools/tests remain syntactically valid.
- `audit_operating_model.py` -> operating-model invariants still pass.
- `audit_benchmark_boundary.py` -> benchmark/source-boundary audit still passes.
- `export_openclaw_runtime_snapshot.py` -> reviewer-visible runtime mirrors still generate.
- placeholder scan -> canonical handoff docs are filled, not generic templates.

## Failure interpretation
- Zip build failure means copied handoff structure is incomplete or script path assumptions are wrong.
- Test/audit failure means handoff integration unexpectedly touched runtime assumptions.
- Placeholder scan hit means handoff docs are not ready for downstream agent use.

## Pre-merge checklist
- [ ] Docs synced
- [ ] Zip builds
- [ ] Tests pass
- [ ] Compileall passes
- [ ] Audits pass
- [ ] Rollback path known
