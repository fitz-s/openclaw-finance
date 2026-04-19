# RALPLAN Ingestion Fabric Phase 09: Source Health And Quota Monitor

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Expose Brave quota/rate-limit failures and source freshness degradation as first-class source-health signals. The monitor must make degraded source access visible without mutating wake thresholds, blocking Discord delivery, or pretending stale state is fresh.

## RALPLAN-DR Summary

### External Scout Inputs

Source class: metrics, freshness SLO, rate-limit, circuit breaker, stale marker, and problem-details guidance.

Integrated findings:
- Source health should be multi-signal, not a single Boolean flag.
- Freshness is an SLO/window condition, not just a last-seen timestamp.
- Quota telemetry should expose limit/remaining/reset/retry-after semantics when available.
- Missing or frozen telemetry should be explicit unknown/stale, not success.
- Circuit breaker/degraded state should be machine-readable.
- Degradation details should be structured for downstream surfaces.

Reference links from scout:
- OpenTelemetry metrics: https://opentelemetry.io/docs/concepts/signals/metrics/
- Google Cloud data freshness SLIs: https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring/sli-metrics/data-proc-metrics
- Envoy outlier detection: https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/outlier
- GitHub rate-limit docs: https://docs.github.com/en/enterprise-cloud@latest/rest/using-the-rest-api/rate-limits-for-the-rest-api
- RFC 6585 429: https://datatracker.ietf.org/doc/html/rfc6585
- RFC 9457 problem details: https://datatracker.ietf.org/doc/html/rfc9457
- Prometheus staleness model: https://prometheus.io/docs/prometheus/latest/querying/basics/

### Principles

1. **Degradation is data.** 402/429/rate-limit/failed fetch records must become explicit source-health rows.
2. **Unknown is not OK.** Missing timestamps, unknown rights, and dry-run-only sources are explicit unknown states.
3. **Shadow-only in this phase.** Source health informs audit/undercurrent/follow-up later; it does not hard gate wake/delivery now.
4. **No silent stale recycle.** Reports can see `stale_reuse_guard` and source-health summary instead of recycling old narratives invisibly.
5. **Deterministic rows.** Health hashes must be stable for the same row payload.

### Selected Design

Add `scripts/source_health_monitor.py`:
- Reads SourceAtoms, Brave Web/News/LLM Context fetch records, Brave Answers sidecar records, query registry, reducer report, and Brave API capability audit.
- Emits `state/source-health.json` and optional history JSONL.
- Produces source rows for source atoms and Brave endpoints.
- Adds quota/rate-limit fields: `quota_status`, `rate_limit_status`, `last_quota_error`, `retry_after_sec`, `x_ratelimit_remaining`, `x_ratelimit_reset`.
- Adds source-health metrics: success/failure/timeout/rate-limit counts, freshness lag, quota remaining/reset, retry-after, breaker state, degraded state, and health score.
- Adds problem-details-style degradation metadata for downstream surfaces.
- Adds `stale_reuse_guard` summary so downstream reports know source access was degraded.
- Keeps `no_execution=true` and `shadow_only=true`.

Update source-health contract to include quota/rate-limit fields and stale reuse guard semantics.

## Acceptance Criteria

1. Brave 402 / `USAGE_LIMIT_EXCEEDED` audit rows degrade Brave source health.
2. SourceFetchRecord rows with `rate_limited` or 429 degrade source health.
3. Dry-run-only fetch records are explicit `unknown`, not `fresh`.
4. SourceAtom rows contribute freshness/rights status by source.
5. Output has deterministic `health_hash` rows and summary.
6. Tests prove source-health monitor does not mutate wake/report/delivery authority.

## Test Plan

- `test_source_health_marks_brave_quota_audit_as_degraded`
- `test_source_health_marks_rate_limited_fetch_record`
- `test_source_health_dry_run_is_unknown_not_fresh`
- `test_source_health_atoms_contribute_freshness_and_rights`
- `test_source_health_cli_writes_report_and_history`

## Non-Goals

- Do not block Discord delivery.
- Do not mutate thresholds or wake policy.
- Do not call Brave APIs.
- Do not edit parent market-ingest runtime.

## Critic Requirements

Implementation critic must verify:
- no active gating
- 402/429 explicit degradation
- unknown/dry-run explicit unknown
- deterministic hashes
- no live API calls
