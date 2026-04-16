# Source Atom Contract

`EvidenceAtom` preserves source-level context before scanner observations are compressed into report-friendly fields.

It is a shadow substrate in Phase 2. It is not wake, judgment, delivery, or execution authority.

## Purpose

- Preserve source identity, timestamps, bounded source text, symbols, rights, and lineage.
- Provide a stable trace base for later ClaimGraph, ContextGap, Undercurrent, CampaignProjection, and follow-up routing.
- Make missing or weak context explicit without changing current finance report behavior.

## Minimal Shape

```json
{
  "atom_id": "atom:<stable-hash>",
  "source_id": "source:unknown_web",
  "source_class": "news_policy",
  "source_lane": "news_policy_narrative",
  "published_at": "...",
  "observed_at": "...",
  "ingested_at": "...",
  "event_time": "...",
  "timezone": "UTC",
  "entity_ids": [],
  "symbol_candidates": [],
  "region": null,
  "sector": null,
  "supply_chain_nodes": [],
  "modality": "text",
  "raw_ref": "finance-scan:<id>",
  "raw_snippet": "bounded snippet",
  "raw_uri": null,
  "raw_table_ref": null,
  "language": "unknown",
  "freshness_budget_seconds": 0,
  "reliability_score": 0.0,
  "uniqueness_score": 0.0,
  "compliance_class": "unknown",
  "redistribution_policy": "unknown",
  "lineage_chain": [],
  "point_in_time_hash": "sha256:...",
  "source_refs": [],
  "no_execution": true
}
```

## Invariants

- `raw_snippet` is bounded and must not become an artifact dump.
- `point_in_time_hash` is deterministic for the atom payload.
- `no_execution` is always true.
- Atoms may be generated from scanner state, but they must not mutate scanner state.
- Atoms are not part of `ContextPacket` authority in Phase 2.

## Forbidden In Phase 2

- Using atoms to change wake score or wake class.
- Using atoms to alter JudgmentEnvelope.
- Delivering raw atoms to Discord primary surfaces.
- Treating atoms as execution/trade input.
