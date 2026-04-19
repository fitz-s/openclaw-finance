# Options IV Surface Contract

`OptionsIVSurface` is a deterministic review-only surface compiled from derived
options-IV provider observations first, then degraded options chain / flow proxy
data as fallback.

It does not execute trades, mutate thresholds, wake the user, or support JudgmentEnvelope as primary evidence until a later cutover explicitly approves it.

## Report Shape

```json
{
  "generated_at": "...",
  "status": "pass|degraded|empty",
  "contract": "options-iv-surface-v1-shadow",
  "source": "state/options-iv-provider-snapshot.json + state/options-flow-proxy.json",
  "surface_policy_version": "options-iv-surface-v2-shadow",
  "primary_source_status": "ok|partial|degraded|missing",
  "primary_provider_set": [],
  "source_health_refs": [],
  "rights_policy": "derived_only|unknown",
  "point_in_time_replay_supported": false,
  "derived_only": true,
  "raw_payload_retained": false,
  "symbol_count": 0,
  "symbols": [],
  "summary": {},
  "shadow_only": true,
  "no_execution": true
}
```

## Symbol Row Shape

```json
{
  "symbol": "RGTI",
  "event_count": 4,
  "provider_set": ["polygon_options_iv"],
  "source_health_refs": ["source:polygon_options_iv"],
  "rights_policy": "derived_only",
  "derived_only": true,
  "raw_payload_retained": false,
  "point_in_time_replay_supported": true,
  "chain_snapshot_age_seconds": 120,
  "chain_staleness": "fresh|aging|stale|unknown",
  "proxy_only": false,
  "provider_confidence": 0.35,
  "confidence_penalties": [],
  "iv_observation_count": 0,
  "iv_rank": null,
  "iv_percentile": null,
  "term_structure": {},
  "avg_implied_volatility": null,
  "max_implied_volatility": null,
  "call_put_skew": null,
  "max_volume_oi_ratio": 2.4,
  "unusual_contract_count": 2,
  "top_contracts": [],
  "no_execution": true
}
```

## Required Semantics

- Missing IV must be explicit, not treated as neutral.
- Stale chain snapshots must lower provider confidence.
- Proxy-only surfaces must disclose their limitations.
- IV/skew/term-structure fields may be null, but nulls must produce confidence penalties when load-bearing.
- This artifact is source context, not execution advice.
- `SourceFetchRecord.status` remains `ok|partial|rate_limited|failed`; provider-specific
  failures belong in `error_class`, `application_error_code`, `problem_details`,
  and source-health `degraded_state`, not top-level status expansion.
- Nasdaq/yfinance cannot satisfy `primary_source_status=ok`; they can only produce
  proxy fallback rows with `missing_primary_options_iv_source` confidence penalties.
- Raw vendor payloads and credentials must not be retained in this artifact.
- The surface may enter report/context packs only as derived source context. It is
  not JudgmentEnvelope primary evidence, wake authority, threshold authority, or
  execution authority.
