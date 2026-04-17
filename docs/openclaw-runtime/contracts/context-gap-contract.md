# Context Gap Contract

`ContextGap` records a load-bearing missing source lane or weak claim context.

It is the system's explicit alternative to generic speculation.

## Shape

```json
{
  "gap_id": "gap:<stable-hash>",
  "campaign_id": null,
  "linked_campaign_id": null,
  "claim_id": "claim:<stable-hash>",
  "missing_lane": "market_structure",
  "source_lane_present": "news_policy_narrative",
  "why_load_bearing": "Narrative-only claim lacks price/volume confirmation.",
  "what_claims_remain_weak": [],
  "weak_claim_ids": [],
  "which_source_could_close_it": [],
  "suggested_sources": [],
  "cost_of_ignorance": "low|medium|high|unknown",
  "closure_condition": "A market_structure claim supports or contradicts the weak claim.",
  "gap_status": "open|closed|deferred",
  "no_execution": true
}
```

## Rules

- Gaps do not block delivery in Phase 2.
- Gaps do not mutate thresholds or wake policy.
- Gaps are used to preserve known unknowns for later campaign/follow-up phases.
- Missing source lane must be explicit.
- `gap_status` starts as `open` and may be closed only by later source evidence or explicit reviewer action.
- `closure_condition` must explain what evidence would close the gap.
- `weak_claim_ids` and `suggested_sources` are canonical aliases for future follow-up/replay while legacy fields remain compatible.
- `no_execution` is always true.
