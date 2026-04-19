# Source Health Contract

`SourceHealth` records observed source condition. It is separate from `SourceRegistryRecord`.

Registry = expected source behavior.

Health = observed source behavior at an evaluation time.

## Authority

Source Health is a shadow audit surface in Phase 1. It does not change wake, judgment, report delivery, Discord output, thresholds, or execution authority.

## Report Shape

```json
{
  "generated_at": "2026-04-16T00:00:00Z",
  "status": "pass|degraded|fail",
  "registry_version": "finance-source-registry-v2",
  "health_policy_version": "source-health-v1-shadow",
  "source_count": 8,
  "sources": [],
  "summary": {},
  "no_execution": true
}
```

## Source Row Shape

```json
{
  "source_id": "source:yfinance",
  "evaluated_at": "2026-04-16T00:00:00Z",
  "freshness_status": "fresh|aging|stale|unknown",
  "freshness_age_seconds": 0,
  "latency_status": "ok|degraded|breached|unknown",
  "observed_latency_seconds": 0,
  "schema_status": "ok|drift|breaking_drift|unknown",
  "validation_status": "pass|warn|fail|unknown",
  "rights_status": "ok|restricted|expired|unknown",
  "coverage_status": "ok|partial|unavailable|unknown",
  "last_seen_at": "...",
  "last_success_at": "...",
  "last_error_at": null,
  "quota_status": "ok|degraded|not_applicable|unknown",
  "rate_limit_status": "ok|limited|not_applicable|unknown",
  "last_quota_error": null,
  "retry_after_sec": null,
  "x_ratelimit_remaining": null,
  "x_ratelimit_reset": null,
  "success_count": 0,
  "failure_count": 0,
  "timeout_count": 0,
  "rate_limited_count": 0,
  "freshness_lag_seconds": 0,
  "quota_remaining": null,
  "quota_reset_at": null,
  "retry_after_seconds": null,
  "breaker_state": "closed|open|half_open|unknown",
  "degraded_state": "quota_limited|fetch_failed|missing_credentials|missing_dependency|network_error|broker_session_unavailable|subscription_denied|stale|partial_data|null",
  "source_lane_unavailable_reason": null,
  "health_score": 1.0,
  "breach_reasons": [],
  "problem_details": {},
  "metric_refs": [],
  "source_refs": [],
  "health_hash": "sha256:...",
  "no_execution": true
}
```

## Status Semantics

Freshness:
- `fresh`: observed age is inside source-specific budget.
- `aging`: observed age exceeds budget but remains within twice the budget.
- `stale`: observed age exceeds twice the budget.
- `unknown`: the source has no observable timestamp or no freshness budget.

Rights:
- `ok`: public/internal use policy is known and compatible with review-only use.
- `restricted`: licensed, summary-only, internal-only, or blocked policy applies.
- `expired`: license or contract has expired.
- `unknown`: rights metadata is missing or unknown.

Provider diagnostics:
- `missing_credentials`: credential or local terminal/API token is absent.
- `network_error`: DNS, connection, timeout, or local terminal reachability failed.
- `subscription_denied`: provider plan lacks requested data, greeks, IV, or realtime permission.
- `broker_session_unavailable`: broker-local gateway/TWS session is disabled, unavailable, or not authenticated.
- `missing_dependency`: required local SDK/runtime dependency is not installed.
- `fetch_failed`: provider returned an application/schema error not covered by the above.

## Required Invariants

- `no_execution` is always true.
- Unknown state must be explicit, not silently treated as fresh or allowed.
- Quota/rate-limit degradation must be explicit; 402/429 must not be silently treated as a normal no-result fetch.
- Dry-run-only fetches must remain `unknown`, not `fresh`.
- `stale_reuse_guard` must tell downstream report surfaces when old narratives could be silently recycled because source access is degraded.
- For source lanes such as `market_structure.options_iv`, `source_lane_unavailable_reason` must distinguish missing credentials, network errors, subscription denial, quota, and stale data when possible.
- Health hashes must be deterministic for the same row payload.
- Health is appendable to history for later source ROI and coverage learning.
- Packet manifests may include `source_health_hash` only as audit metadata in Phase 1.

## Forbidden In Phase 1

- Hard-gating wake from Source Health.
- Blocking Discord delivery from Source Health alone.
- Mutating thresholds from Source Health.
- Hiding source data from review because Source Health is weak.
