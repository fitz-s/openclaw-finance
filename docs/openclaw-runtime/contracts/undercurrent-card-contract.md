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
  "acceleration_score": 0.0,
  "cross_lane_confirmation": 0,
  "source_diversity": 0,
  "contradiction_load": 0,
  "known_unknowns": [],
  "source_health_refs": [],
  "source_health_summary": {
    "degraded_count": 0,
    "degraded_sources": []
  },
  "undercurrent_score": 0.0,
  "cross_lane_confirmation_score": 0.0,
  "contradiction_load_score": 0.0,
  "freshness_penalty": 0.0,
  "capital_relevance_score": 0.0,
  "promotion_candidate": false,
  "promotion_blockers": [],
  "peacetime_update_eligible": true,
  "packet_update_visibility": "board_mutation_only",
  "wake_impact": "none",
  "shadow_inputs": {},
  "no_execution": true
}
```

## Rules

- `PACKET_UPDATE_ONLY` may update undercurrents without user alert.
- Repeated weak signals should increase persistence/velocity, not create spam.
- An undercurrent can promote to a campaign but never bypasses judgment/product/delivery safety.
- A stale or degraded source must be explicit in `source_freshness`.

## Phase 3 Shadow Enrichment

Phase 3 may enrich cards with Source Health, EvidenceAtom, ClaimGraph, and ContextGap metadata. These fields are advisory and shadow-only. They must not alter wake class, thresholds, delivery safety, Discord output, JudgmentEnvelope, or execution authority.

Required enriched fields when shadow inputs are available:
- `acceleration_score`
- `cross_lane_confirmation`
- `source_diversity`
- `contradiction_load`
- `known_unknowns`
- `source_health_refs`
- `source_health_summary`
- `shadow_inputs`

`known_unknowns` are context gaps, not conclusions.

## Phase 06 Promotion Semantics

Undercurrent promotion metadata is advisory. It must not alter wake class in this phase.

Promotion candidates require:
- source diversity of at least 2
- cross-lane confirmation score at least 0.45
- contradiction load score no higher than 0.35
- capital relevance score at least 0.50
- persistence score at least 0.55 after normalization
- no severe freshness penalty

`PACKET_UPDATE_ONLY` may use undercurrents for board mutation only. It must not become alert spam or execution language.
