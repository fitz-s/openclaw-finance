# Undercurrent Card Contract

`UndercurrentCard` captures peacetime or dark-signal accumulation that does not necessarily justify an immediate wake.

It is used by Campaign Projection to make `PACKET_UPDATE_ONLY` visible as board mutation rather than alert spam.

## Schema

```json
{
  "undercurrent_id": "undercurrent:<stable-hash>",
  "human_title": "人话标题",
  "source_type": "invalidator_cluster|opportunity_accumulation|crowding|hedge_gap|scenario_drift",
  "persistence_score": 0.0,
  "velocity": 0.0,
  "divergence": "none|low|medium|high",
  "crowding": "none|low|medium|high",
  "hedge_gap": "none|partial|uncovered|unknown",
  "promotion_reason": "why this may become a campaign",
  "kill_conditions": ["..."],
  "linked_refs": {
    "thesis": [],
    "scenario": [],
    "opportunity": [],
    "invalidator": [],
    "capital_graph": []
  },
  "source_freshness": {
    "status": "fresh|mixed|stale|unknown",
    "source_refs": []
  },
  "no_execution": true
}
```

## Rules

- `PACKET_UPDATE_ONLY` may update undercurrents without user alert.
- Repeated weak signals should increase persistence/velocity, not create spam.
- An undercurrent can promote to a campaign but never bypasses judgment/product/delivery safety.
- A stale or degraded source must be explicit in `source_freshness`.
