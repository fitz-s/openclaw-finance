# Source Registry 2.0 Contract

`SourceRegistryRecord` defines the expected behavior, rights, lineage, and freshness contract for a market-ingest source.

This is not an execution authority. It is a deterministic metadata contract used by source promotion, packet manifests, source health, and later EvidenceAtom / CampaignProjection layers.

## Authority

Canonical market-report authority remains:

`ContextPacket -> WakeDecision -> JudgmentEnvelope -> product report -> validator -> decision log -> delivery safety`

Source Registry 2.0 may annotate and rank source trust. It must not by itself authorize execution, mutate thresholds, or bypass delivery safety.

## Required Compatibility

Phase 1 preserves all v1 fields:

```json
{
  "source_id": "source:sec_edgar",
  "source_kind": "official_filing",
  "layer_hint": "L4_actor_intent",
  "reliability_tier": "T0_official_or_exchange",
  "latency_class": "near_realtime",
  "license_usage": "allowed",
  "domain_patterns": ["sec.gov"],
  "raw_capture_policy": "hash_only",
  "title_only_policy": "allow_if_confirmed",
  "eligible_for_wake": true,
  "eligible_for_judgment_support": true
}
```

## V2 Required Fields

Identity and lane:
- `source_class`
- `source_lane`
- `source_sublane`
- `modality`
- `asset_horizon`
- `coverage_universe`
- `coverage_regions`
- `coverage_asset_classes`

Freshness and latency:
- `freshness_budget_seconds`
- `expected_latency_seconds`
- `evaluation_schedule`
- `change_window_seconds`
- `change_source`

Reliability and additivity:
- `reliability_prior`
- `uniqueness_prior`
- `redundancy_group`
- `substitutability_score`
- `cost_class`
- `promotion_policy`

Lineage and replay:
- `lineage_policy`
- `upstream_refs`
- `downstream_refs`
- `point_in_time_policy`
- `event_time_field`
- `ttl_seconds`
- `versioning_mode`
- `snapshot_retention_days`
- `replay_supported`

Compliance and rights:
- `compliance_class`
- `redistribution_policy`
- `allowed_uses`
- `attribution_required`
- `rate_limit_policy`
- `declared_user_agent_required`
- `contract_source_ref`

## Lanes

Allowed `source_lane` values:
- `market_structure`
- `corp_filing_ir`
- `real_economy_alt`
- `news_policy_narrative`
- `human_field_private`
- `internal_private`
- `derived_context`

Allowed `source_sublane` examples:
- `market_structure.price_volume`
- `market_structure.options_iv`
- `market_structure.options_flow_proxy`
- `market_structure.rates_fx_commodities`
- `market_structure.crypto_gold_spx`
- `corp_filing_ir.sec_filings`
- `corp_filing_ir.earnings_transcripts`
- `corp_filing_ir.issuer_ir`
- `real_economy_alt.jobs`
- `real_economy_alt.shipping`
- `real_economy_alt.power_weather`
- `news_policy_narrative.entity_event`
- `human_field_private.expert_transcript`
- `internal_private.watch_intent`
- `internal_private.thread_unknowns`

## Options / IV Discipline

`market_structure.options_iv` is a first-class sublane. It must not be represented as generic price context.

Required options/IV metadata when available:
- `iv_rank`
- `iv_percentile`
- `iv_term_structure`
- `skew`
- `open_interest_change`
- `volume_open_interest_ratio`
- `unusual_contract_concentration`
- `chain_snapshot_age_seconds`
- `provider_confidence`
- `point_in_time_replay_supported`

If an options chain is stale, delayed, or proxy-only, downstream confidence must be penalized and operator surfaces must disclose the limitation.

## Compliance Rules

- `unknown` rights are degraded, not implicitly allowed.
- `blocked` rights cannot wake or support judgment.
- `internal_private` sources cannot be redistributed externally.
- Market-data-like sources must carry an explicit redistribution policy.
- SEC EDGAR sources must carry fair-access policy metadata, including the 10 requests/second constraint and declared user-agent requirement.

## Phase 1 Shadow Rule

In Phase 1, registry v2 metadata may flow into source health and packet manifests for audit only. It must not change:
- wake classification
- report delivery
- Discord output
- actionability
- thresholds
- execution authority

## No-Execution Boundary

Every downstream use remains `review-only`. Source metadata can explain confidence and freshness; it cannot issue trading instructions.
