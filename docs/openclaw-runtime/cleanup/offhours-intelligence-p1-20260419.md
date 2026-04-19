# Offhours Intelligence P1 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P1 wires the P0 calendar aperture and Brave budget guard into the existing offhours scan chain. It does not change cron cadence, Discord delivery policy, wake thresholds, or Brave Answers authority.

## Implemented

- Added `scripts/offhours_source_router.py` to compile `state/offhours-source-router-state.json` from `SessionApertureState` plus `BraveBudgetGuard` dry-run preflight.
- Updated `scripts/finance_scanner_job.py` so `offhours-scan` prepends `offhours_source_router.py` and passes scanner mode through to QueryPack planning and parent cutover; `market-hours-scan` remains unchanged.
- Updated `scripts/query_pack_planner.py` so offhours QueryPacks receive compact `session_aperture`, `budget_request`, and `activation_mode` metadata only when router state is fresh and scanner mode is `offhours-scan`.
- Updated `scripts/finance_parent_market_ingest_cutover.py` to pass scanner mode and include runtime-control source health when invoked from the offhours path.
- Updated `scripts/brave_source_activation.py` to check/reserve Search budget before live Brave Search/News activation and to emit explicit `blocked` pack results when budget is denied.
- Fixed activation ordering so QueryRegistry cooldown skips do not consume budget.
- Updated `scripts/source_health_monitor.py` to surface budget/aperture state as optional observability only via `--include-runtime-control-state`.
- Restricted runtime-control source-health inclusion to `scanner_mode=offhours-scan` so market-hours cutovers cannot inherit stale offhours budget state.
- Updated `scripts/native_scanner_offhours.py` to include calendar-aware aperture metadata while retaining legacy `window` compatibility.
- Updated runtime snapshot export with sanitized `offhours-source-router-state.json` and P1 scout/ralplan/critic/closeout manifest entries.

## Explicitly Not Activated

- No cron frequency/cadence mutation.
- No Discord delivery mutation.
- No wake threshold lowering.
- No Brave Answers activation.
- No broker or execution authority.

## Smoke Evidence

A real offhours scanner smoke was run:

```bash
python3 scripts/finance_scanner_job.py --mode offhours-scan
```

Observed result:

- Scanner status: `scanner=ok mode=offhours-scan`
- Gate result after final run: `gate=hold send=false`
- Brave activation selected 4 packs.
- QueryRegistry skipped 1 pack without consuming budget.
- 2 live Search/News attempts were rate-limited.
- 1 pack was explicitly blocked by `aperture_cap_exhausted`.
- `state/brave-budget-state.json` reached `search_aperture=6`, the configured weekend aperture cap.
- Re-running `offhours_source_router.py` after the smoke correctly reports `budget_allowed=false` and `should_consider_source_activation=false`.

## Verification

```bash
python3 -m pytest -q tests/test_parent_market_ingest_cutover_p1_offhours.py tests/test_finance_scanner_job_p1_offhours.py tests/test_query_pack_planner_p1_offhours.py tests/test_brave_source_activation_budget_p1.py tests/test_source_health_monitor_p1_budget.py tests/test_native_scanner_offhours_p1.py tests/test_offhours_snapshot_p1.py
# 12 passed

python3 -m pytest -q tests/test_brave_source_activation_budget_p1.py tests/test_finance_scanner_job_p4.py tests/test_source_health_monitor_phase09.py tests/test_source_health_monitor_p1_budget.py
# 16 passed

python3 -m pytest -q tests
# 316 passed

python3 -m compileall -q scripts tools tests
# pass

python3 tools/audit_operating_model.py
# pass, error_count=0

python3 tools/audit_benchmark_boundary.py
# pass, blocking_reasons=[]

python3 scripts/finance_parent_market_ingest_cutover.py --dry-run --scanner-mode offhours-scan
# pass

python3 tools/export_openclaw_runtime_snapshot.py
# pass
```

## Residual Risks

- Current Brave live attempts are rate-limited in this environment, so P1 proves budget/gating mechanics, not improved source yield.
- Weekend/holiday offhours cadence is still not expanded; this is intentionally reserved for a later phase after current-path budget behavior is visible.
- The session calendar still uses the P0 2026 explicit table. Later phases should add a maintained calendar source or generated annual table.

## Next Phase

P2 should have its own internal explorer, external scout, ralplan, implementation, critic, commit, and push. Recommended P2 target: Brave Answers/LLM Context compression gate and usage reporting, still sidecar-only and budget-aware.
