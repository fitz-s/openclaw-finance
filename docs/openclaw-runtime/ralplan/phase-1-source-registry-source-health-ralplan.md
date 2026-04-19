# RALPLAN Phase 1: Source Registry 2.0 + Source Health

Status: approved_for_implementation
Go for implementation: true

Phase 0 commit: `19f5501 Prepare information dominance phase gates`

## Task Statement

Upgrade the parent OpenClaw market-ingest source registry into a lane-aware Source Registry 2.0 and add Source Health shadow outputs for OpenClaw Finance.

This phase is planning-only until this RALPLAN is approved. Implementation must remain shadow-first and review-only.

## Current Facts From Local Exploration

Fact: The current source registry lives outside the finance repo at `/Users/leofitz/.openclaw/workspace/services/market-ingest/config/source-registry.json`.

Fact: The current registry is `finance-source-registry-v1` and has 8 source records: Reuters, Bloomberg, SEC EDGAR, issuer press release, portfolio Flex, yfinance, low-quality blocked, unknown web.

Fact: The current registry record schema is `/Users/leofitz/.openclaw/workspace/schemas/source-registry-record.schema.json` and has `additionalProperties=false`. Phase 1 cannot simply add fields to JSON; it must update schema and tests.

Fact: Current registry fields are:
- `source_id`
- `source_kind`
- `layer_hint`
- `reliability_tier`
- `latency_class`
- `license_usage`
- `domain_patterns`
- `raw_capture_policy`
- `title_only_policy`
- `eligible_for_wake`
- `eligible_for_judgment_support`

Fact: [`source_promotion.py`](../../../../services/market-ingest/normalizer/source_promotion.py) currently uses source registry matching, title flags, timestamp presence, source latency/license, and reliability tier to decide `ACCEPT`, `CONTEXT_ONLY`, or `QUARANTINE`.

Fact: [`semantic_normalizer.py`](../../../../services/market-ingest/normalizer/semantic_normalizer.py) emits `EvidenceRecord` rows with a narrow `source_quality` block.

Fact: [`packet_compiler/compiler.py`](../../../../services/market-ingest/packet_compiler/compiler.py) writes `source_manifest` with `producer`, `record_hash`, and `alignment_hash` only.

Fact: [`wake_policy/policy.py`](../../../../services/market-ingest/wake_policy/policy.py) already scores `freshness`, `novelty`, `source_reliability`, `contradiction_impact`, and `position_relevance`.

Fact: Parent tests already exist for source promotion, semantic normalization, temporal alignment, packet compilation, wake policy, and judgment validation.

Fact: Finance repo snapshots parent dependency inventory and drift, so intentional parent changes must refresh snapshot artifacts.

## External Research Findings

OpenLineage pattern: model lineage as run/job/dataset events with `inputs`, `outputs`, dataset `namespace` and `name`, plus extensible facets. Dataset facets cover schema, datasource, version, data quality metrics/assertions, ownership, tags, and column lineage. This maps well to `lineage_policy`, `dataset_identity`, `source_manifest`, and source health facets.

DataHub pattern: freshness should be an assertion with an evaluation schedule, change window, and change source. This maps directly to `freshness_budget`, `evaluation_schedule`, `change_window`, and `change_source` rather than a single global stale threshold.

OpenMetadata pattern: source metadata should expose source, owner, tier, type, usage, schema, profiler/data quality, lineage, custom properties, executions, and version history. This supports typed custom fields rather than free-form tags.

Great Expectations / Deequ pattern: validation runs should be durable artifacts with validation definitions, suites, actions, and metric history. This maps to `source-health.json` plus append-only `source-health-history.jsonl` rather than dashboard-only status.

Feast / Tecton pattern: point-in-time correctness requires event timestamps, TTLs, and replayable historical retrieval. This maps to `point_in_time_policy`, `event_time_field`, `ttl_seconds`, and `replay_supported`.

Delta/Iceberg/Hudi pattern: time travel depends on snapshots/versions and retention. This maps to `versioning_mode`, `snapshot_ref`, `snapshot_retention_days`, and `replay_retention_policy`.

SEC/market-data compliance pattern: EDGAR has fair-access constraints; real-time exchange/TRACE market data can require vendor/redistribution agreements. This maps to first-class `compliance_class`, `redistribution_policy`, `allowed_uses`, `rate_limit_policy`, and `declared_user_agent_required`.

Reference links:
- OpenLineage dataset facets: https://openlineage.io/docs/spec/facets/dataset-facets/
- OpenLineage example lineage events: https://openlineage.io/docs/spec/examples/
- DataHub freshness assertions: https://docs.datahub.com/docs/managed-datahub/observe/freshness-assertions/
- DataHub metadata model: https://docs.datahub.com/docs/metadata-modeling/metadata-model/
- dbt source freshness: https://docs.getdbt.com/docs/deploy/source-freshness
- OpenMetadata data asset model: https://docs.open-metadata.org/latest/how-to-guides/guide-for-data-users/data-asset-tabs
- Great Expectations checkpoint actions: https://docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/create_a_checkpoint_with_actions/
- Feast point-in-time joins: https://docs.feast.dev/getting-started/concepts/point-in-time-joins
- SEC EDGAR fair access: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- NYSE market data documents: https://www.nyse.com/connectivity/documents
- FINRA real-time data agreements: https://www.finra.org/filing-reporting/trace/content-licensing/real-time-end-day-market-data-agreements

## Principles

1. Shadow-first, authority-preserving: Source health may annotate confidence but must not change wake dispatch, delivery, or report blocking until a later explicit cutover.
2. Typed metadata over tags: use schema-backed fields for freshness, lineage, compliance, rights, and replay; avoid unstructured labels for load-bearing policy.
3. Preserve point-in-time auditability: every health and registry assertion must be replayable or at least timestamped with source, evaluator, and policy version.
4. Rights and compliance are first-class: redistribution/internal-use restrictions must be machine-visible before any new source can affect operator surfaces.
5. Additivity matters: source quality is not only reliability; it includes uniqueness, coverage, redundancy, freshness, cost, and contribution to useful campaigns.

## Decision Drivers

1. Blast radius control: Parent market-ingest is load-bearing and external to finance repo, so Phase 1 must be incremental and test-backed.
2. Future campaign quality: Later EvidenceAtom, Undercurrent, CampaignProjection, and follow-up depend on richer source identity and health.
3. Compliance safety: Market data and private/field sources require explicit use/redistribution rules before they become operator-visible facts.

## Viable Options

### Option A: Minimal schema extension, no new health compiler

Add Source Registry 2.0 fields directly to `source-registry.json` and schema. Existing promotion/normalizer reads fields opportunistically but no new `source-health.json` is emitted.

Pros:
- Smallest diff.
- Lowest immediate risk.
- Easy rollback.

Cons:
- Does not create durable health history.
- Later phases still need another pass for source health.
- Easy to let fields become documentation-only with no runtime effect.

### Option B: Registry v2 + shadow Source Health compiler

Extend registry/schema and add a deterministic `source_health_compiler.py` that reads registry plus current state artifacts and emits `services/market-ingest/state/source-health.json` and `source-health-history.jsonl`. Packet compiler only includes health hashes/summary in `source_manifest`; wake/delivery behavior stays unchanged.

Pros:
- Best balance of value and safety.
- Creates a durable substrate for Phase 2+.
- Keeps active authority chain unchanged.
- Lets tests prove source health without changing delivery.

Cons:
- Larger parent blast radius than Option A.
- Requires new schema and test coverage.
- Needs careful snapshot/drift refresh discipline.

### Option C: Adopt external metadata framework semantics directly

Implement OpenLineage/DataHub/OpenMetadata-compatible models as first-class internal objects now.

Pros:
- Closest to industry-standard shape.
- Easier future export/integration.

Cons:
- Too much scope for Phase 1.
- Risks adding framework-shaped complexity before OpenClaw-specific needs are stable.
- Could distract from deterministic finance hot path.

## Selected Plan

Choose Option B: Registry v2 + shadow Source Health compiler.

Rationale: Option B builds the missing substrate without cutting into active wake/report/delivery authority. It gives later phases real source health and provenance objects while preserving rollback and review-only constraints.

## Rejected Options

Rejected: Option A only | Too shallow; it would create a richer config file but not a source health system.

Rejected: Option C direct framework adoption | Too broad; OpenClaw should borrow patterns, not import a generic metadata platform as a design constraint.

Rejected: Hard-gating wake by source health in Phase 1 | Unsafe; this would alter active report behavior before shadow metrics have been observed.

Rejected: Adding new premium/private data sources in Phase 1 | Wrong layer; Phase 1 defines source governance before adding source acquisition.

## Proposed Source Registry 2.0 Fields

Identity:
- `source_id`
- `source_class`
- `source_kind`
- `modality`
- `platform`
- `namespace`
- `logical_name`
- `physical_name`
- `aliases`
- `owner`
- `domain`
- `tier`

Finance lane:
- `source_lane`: `market_structure | corporate_filing | real_economy_alt_data | news_policy_narrative | human_field | internal_private | derived_context`
- `asset_horizon`: `intraday | multi_day | quarterly | structural`
- `coverage_universe`
- `coverage_regions`
- `coverage_asset_classes`

Freshness/latency:
- `freshness_budget_seconds`
- `expected_latency_seconds`
- `evaluation_schedule`
- `change_window_seconds`
- `change_source`: `audit_log | information_schema | last_modified_column | file_mtime | api_observed_at | manual_attestation | unknown`

Reliability/additivity:
- `reliability_prior`
- `uniqueness_prior`
- `redundancy_group`
- `substitutability_score`
- `cost_class`
- `promotion_policy`

Lineage/replay:
- `lineage_policy`
- `upstream_refs`
- `downstream_refs`
- `point_in_time_policy`
- `event_time_field`
- `ttl_seconds`
- `versioning_mode`
- `snapshot_retention_days`
- `replay_supported`

Compliance/rights:
- `compliance_class`: `public | licensed | internal_private | human_field_compliant | restricted | blocked | unknown`
- `redistribution_policy`: `internal_only | summary_only | public_allowed | blocked | unknown`
- `allowed_uses`
- `attribution_required`
- `rate_limit_policy`
- `declared_user_agent_required`
- `contract_source_ref`

Compatibility:
- Keep existing fields for v1 consumers during Phase 1.

## Proposed SourceHealth Shape

`SourceHealth` should be separate from registry config. Registry says expected behavior; health says observed behavior.

Fields:
- `source_id`
- `evaluated_at`
- `registry_version`
- `health_policy_version`
- `freshness_status`: `fresh | aging | stale | unknown`
- `freshness_age_seconds`
- `latency_status`: `ok | degraded | breached | unknown`
- `observed_latency_seconds`
- `schema_status`: `ok | drift | breaking_drift | unknown`
- `validation_status`: `pass | warn | fail | unknown`
- `rights_status`: `ok | restricted | expired | unknown`
- `coverage_status`: `ok | partial | unavailable | unknown`
- `last_seen_at`
- `last_success_at`
- `last_error_at`
- `breach_reasons`
- `metric_refs`
- `source_refs`
- `health_hash`
- `no_execution: true`

## Authority Boundary Impact

Phase 1 may add metadata and shadow health state. It must not:
- dispatch reports
- suppress reports
- change wake thresholds
- change actionability
- change delivery safety outcome
- mutate active Discord output
- authorize execution

Allowed active-chain touch:
- `packet.source_manifest` may include `source_registry_hash` and `source_health_hash` for audit only.
- `source_quality_summary` may include additional counts as informational fields if validators tolerate them.

## Files Likely Touched

Parent workspace:
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/config/source-registry.json`
- `/Users/leofitz/.openclaw/workspace/schemas/source-registry-record.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/source-health.schema.json`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/source_promotion.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/semantic_normalizer.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/packet_compiler/compiler.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/source_health/compiler.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/tests/test_source_promotion.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/tests/test_source_health.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/tests/test_packet_compiler_wake_policy.py`

Finance repo:
- `docs/openclaw-runtime/contracts/source-registry-v2-contract.md`
- `docs/openclaw-runtime/contracts/source-health-contract.md`
- `tools/export_parent_dependency_inventory.py`
- `tools/export_openclaw_runtime_snapshot.py`
- `docs/openclaw-runtime/parent-dependency-inventory.json`
- `docs/openclaw-runtime/parent-dependency-drift.json`
- `docs/openclaw-runtime/snapshot-manifest.json`
- `tests/test_information_dominance_phase1_contract.py`

## Data Migration / Shadow-Mode Posture

Migration should be additive:
1. Extend schema to allow v2 fields while retaining v1 required fields.
2. Add v2 fields to existing 8 source records.
3. Add source health compiler with default `unknown` health for unavailable signals.
4. Write `source-health.json` and append `source-health-history.jsonl` under market-ingest state.
5. Add source registry and health hashes to packet `source_manifest` as audit-only.
6. Do not change wake classification, delivery safety, or Discord output.

## Test Plan

Parent tests:
- Source registry v2 records validate against schema.
- Existing v1 required fields remain present.
- Every source has source lane, modality, freshness budget, compliance class, redistribution policy, and promotion policy.
- Source health compiler emits one health record per registry source.
- Missing state emits `unknown`/`unavailable` health, not failure.
- SEC EDGAR source carries fair-access/rate-limit/user-agent policy.
- Market-data-like sources carry redistribution policy.
- Packet compiler includes source registry/health hashes in manifest without changing wake class.
- Existing source promotion, normalizer, temporal alignment, packet, wake, and judgment tests still pass.

Finance tests:
- Phase 1 contracts exist and are included in snapshot manifest.
- Parent dependency inventory includes source health compiler/schema.
- Runtime drift audit reports intentional changed hashes after refresh.
- No delivery safety behavior changes.

Verification commands:

```bash
python3 -m pytest -q /Users/leofitz/.openclaw/workspace/services/market-ingest/tests
python3 -m pytest -q tests/test_information_dominance_phase1_contract.py
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/export_parent_dependency_inventory.py
python3 tools/audit_parent_dependency_drift.py
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

## Rollback Plan

Rollback should be clean:
- Revert schema additions and source registry v2 fields.
- Remove `source_health/compiler.py` and tests.
- Remove source health hash from packet manifest.
- Refresh parent dependency inventory back to prior hashes.
- Delete generated `source-health.json` and `source-health-history.jsonl` if they cause confusion.

Because Phase 1 is shadow-only, rollback should not affect Discord delivery or report generation.

## Acceptance Criteria

- Source Registry 2.0 schema validates existing and new fields.
- All current source records are migrated to v2 while preserving v1 compatibility fields.
- Source health compiler emits deterministic shadow health records.
- Packet manifest records source registry and source health hashes for audit only.
- Active wake classifications are unchanged for fixture tests.
- No cron/gateway/Discord runtime config changes.
- All parent market-ingest tests pass.
- All finance repo tests pass.
- Parent dependency inventory/drift snapshots are intentionally refreshed.

## Residual Risks

- Parent repo changes are outside finance repo ownership and require careful snapshot discipline.
- Health fields can become theater if no later phase uses them.
- Compliance metadata may create false confidence unless unknown/restricted states are explicit.
- Source health could be misread as a hard gate if operator surfaces are unclear.
- External data frameworks differ in terminology; OpenClaw should adopt patterns, not exact schemas.

## Architect Review

Verdict: APPROVE WITH NARROWING.

Strongest steelman antithesis: Phase 1 could be deferred until EvidenceAtom exists, because source health without atom-level consumption may become metadata theater. The counterargument is valid; the mitigation is to keep Phase 1 shadow-only and require packet manifest hashes plus source health history as concrete artifacts consumed by Phase 2.

Tradeoff tension: A richer registry makes future intelligence better but increases parent schema blast radius. The selected plan manages this by retaining all v1 fields, adding v2 fields under schema control, and avoiding active wake/delivery behavior changes.

Tradeoff tension: Compliance/redistribution fields are necessary, but unknown values can become false safety. The plan must treat `unknown` as explicit degraded state, not as allowed.

Required changes accepted into final plan:
- Keep v1 compatibility fields required throughout Phase 1.
- Add source health as a separate observed artifact, not embedded-only registry fields.
- Add packet manifest hashes only as audit metadata.
- Defer hard gating and source acquisition to later phases.

## Critic Review

Verdict: APPROVE.

Quality checks:
- Principle-option consistency: passes; Option B matches shadow-first and typed metadata principles.
- Fair alternatives: passes; Options A and C are real and rejected for concrete reasons.
- Risk mitigation: passes; rollback and parent blast radius are explicit.
- Testability: passes; acceptance criteria are observable through schema validation, source health output, packet manifest hashes, and unchanged wake classifications.
- Boundary discipline: passes; no cron/gateway/Discord/wake threshold/execute changes are allowed in Phase 1.

Critic caveat: implementation must not smuggle a behavioral gate through `source_quality_summary`. Any active behavior change requires a separate RALPLAN.

## Final RALPLAN Verdict

Go for implementation: true.

Recommended implementation mode: solo executor or one bounded executor lane, not team mode, because Phase 1 has shared schema surfaces and parent dependencies where merge conflicts are likely.

Implementation stop rule: this RALPLAN approves Phase 1 implementation scope, but the current RALPLAN turn stops at planning unless the operator explicitly asks to start implementation.
