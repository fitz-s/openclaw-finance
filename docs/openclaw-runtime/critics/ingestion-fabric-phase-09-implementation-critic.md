# Ingestion Fabric Phase 09 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-09-source-health-quota-monitor-ralplan.md`
- `docs/openclaw-runtime/contracts/source-health-contract.md`
- `scripts/source_health_monitor.py`
- `tests/test_source_health_monitor_phase09.py`

Checks:
- Source health monitor aggregates SourceAtoms, Brave fetch records, Brave Answers sidecars, Brave API capability audit quota failures, and reducer report metadata.
- Brave 402 / `USAGE_LIMIT_EXCEEDED` becomes explicit degraded source health.
- 429/rate-limited SourceFetchRecords become `quota_status=degraded`, `rate_limit_status=limited`, `coverage_status=unavailable`.
- Dry-run-only records are explicit unknown, not fresh success.
- SourceAtom rows contribute freshness lag and rights status.
- Rows include success/failure/timeout/rate-limit counts, freshness lag, quota remaining/reset, retry-after, breaker state, degraded state, health score, and problem details.
- `stale_reuse_guard` is machine-readable and active when source access or freshness is degraded.
- Script writes `state/source-health.json` and appends history, but does not mutate wake/report/delivery/thresholds.
- No live API calls are made.

Risks:
- Health score is a simple heuristic; later phases should tune it against source ROI/outcomes.
- Current monitor reads finance-local state; parent market-ingest handoff remains Phase 12.
- Existing report surfaces do not yet consume `stale_reuse_guard` as a hard UX requirement.

Required follow-up:
- Phase 10 should feed source health into undercurrent/campaign mutation metadata.
- Phase 11 should expose source health and context gaps in follow-up slices.

Commit gate: pass.
