# Context Gap Contract

`ContextGap` records a load-bearing missing source lane or weak claim context.

It is the system's explicit alternative to generic speculation.

## Shape

```json
{
  "gap_id": "gap:<stable-hash>",
  "campaign_id": null,
  "claim_id": "claim:<stable-hash>",
  "missing_lane": "market_structure",
  "why_load_bearing": "Narrative-only claim lacks price/volume confirmation.",
  "what_claims_remain_weak": [],
  "which_source_could_close_it": [],
  "cost_of_ignorance": "low|medium|high|unknown",
  "no_execution": true
}
```

## Rules

- Gaps do not block delivery in Phase 2.
- Gaps do not mutate thresholds or wake policy.
- Gaps are used to preserve known unknowns for later campaign/follow-up phases.
- Missing source lane must be explicit.
- `no_execution` is always true.
