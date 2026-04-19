# Offhours Intelligence P1 Implementation Critic

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Verdict

Safe to commit after the source-health mode isolation fix.

## Findings And Resolution

### High: market-hours source health could inherit stale offhours control state

Finding:

- `finance_parent_market_ingest_cutover.py` initially ran `source_health_monitor.py --include-runtime-control-state` for all scanner modes.
- That meant a market-hours cutover could read `state/offhours-source-router-state.json`, `state/brave-budget-state.json`, and `state/session-aperture-state.json`, then degrade source health based on an offhours budget decision.

Resolution:

- `--include-runtime-control-state` is now added only when `scanner_mode == 'offhours-scan'`.
- `tests/test_parent_market_ingest_cutover_p1_offhours.py` asserts market-hours source health does not include runtime-control state and offhours does.

### Medium: manifest referenced missing P1 critic artifact

Finding:

- `snapshot-manifest.json` and `tools/export_openclaw_runtime_snapshot.py` listed `docs/openclaw-runtime/critics/offhours-intelligence-p1-implementation-critic.md` before the file existed.

Resolution:

- This critic artifact now exists and cites the source review.

## Confirmed Boundaries

- No cron cadence mutation.
- No Discord delivery mutation.
- No wake threshold lowering.
- No Brave Answers activation or Answers authority.
- QueryRegistry cooldown skips run before budget checks and do not consume budget.
- Budget-denied packs are explicit `blocked` pack results.
- `market-hours-scan` does not attach offhours aperture/budget metadata.
- P1 scout/ralplan/closeout docs reference `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Required Verification

```bash
python3 -m pytest -q tests/test_parent_market_ingest_cutover_p1_offhours.py tests/test_finance_scanner_job_p1_offhours.py tests/test_query_pack_planner_p1_offhours.py tests/test_brave_source_activation_budget_p1.py tests/test_source_health_monitor_p1_budget.py tests/test_native_scanner_offhours_p1.py tests/test_offhours_snapshot_p1.py
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 tools/export_openclaw_runtime_snapshot.py
```
