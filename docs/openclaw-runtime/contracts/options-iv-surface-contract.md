# Options IV Surface Contract

`OptionsIVSurface` is a deterministic review-only surface compiled from options chain / flow proxy data.

It does not execute trades, mutate thresholds, wake the user, or support JudgmentEnvelope as primary evidence until a later cutover explicitly approves it.

## Report Shape

```json
{
  "generated_at": "...",
  "status": "pass|degraded|empty",
  "contract": "options-iv-surface-v1-shadow",
  "source": "state/options-flow-proxy.json",
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
  "provider_set": ["nasdaq option-chain"],
  "chain_snapshot_age_seconds": 120,
  "chain_staleness": "fresh|aging|stale|unknown",
  "proxy_only": true,
  "provider_confidence": 0.35,
  "confidence_penalties": ["missing_iv_surface"],
  "iv_observation_count": 0,
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
