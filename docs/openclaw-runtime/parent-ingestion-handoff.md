# Parent Market-Ingest Handoff Plan

Status: finance-local handoff artifact
Authority: documentation and reviewer contract only
Scope: OpenClaw parent workspace integration for the Finance Intelligence Ingestion Fabric

## Boundary

This finance repository does not own the parent OpenClaw runtime authority chain. This document maps the required parent-side work, gates, rollback plan, and acceptance criteria. It does not authorize direct parent mutation.

Parent mutation requires a separate explicitly approved parent-runtime phase, a fresh parent dependency inventory, drift audit, tests in the parent workspace, and a rollback plan before restart/cutover.


## Machine-Readable Contract

The companion file `docs/openclaw-runtime/parent-ingestion-handoff-contract.json` is the machine-readable handoff contract. Parent runtime promotion should verify this contract before consuming finance-local artifacts. This is intentionally OpenAPI/Pact-like in discipline even though the interface is currently file/artifact based rather than HTTP.

Compatibility defaults:
- Additive fields are allowed.
- Renames, removals, type changes, value-format changes, wake behavior changes, and delivery behavior changes require a new contract version and a dual-run migration window.
- Parent and finance paths must run side by side until verification proves the new path is healthy.

## Current Finance-Local Artifacts Ready For Handoff

- QueryPack planner: `scripts/query_pack_planner.py`
- Query registry / source memory / lane watermarks: `scripts/query_registry_compiler.py`, `scripts/source_memory_index.py`
- Brave discovery/reader/sidecar lanes: `scripts/brave_web_search_fetcher.py`, `scripts/brave_news_search_fetcher.py`, `scripts/brave_llm_context_fetcher.py`, `scripts/brave_answers_sidecar.py`
- Worker compatibility reducer: `scripts/finance_worker.py`
- Source health monitor: `scripts/source_health_monitor.py`
- Claim-aware watcher/undercurrents: `scripts/event_watcher.py`, `scripts/undercurrent_compiler.py`
- Reader bundle slice index and follow-up route: `scripts/finance_report_reader_bundle.py`, `scripts/finance_followup_context_router.py`

## Parent Touch Map

| Parent role | Path | Required handoff change | Authority risk |
|---|---|---|---|
| source registry | `/Users/leofitz/.openclaw/workspace/services/market-ingest/config/source-registry.json` | Add Source Registry 2.0 lane/freshness/rights/quota fields for Brave Web, Brave News, LLM Context, Answers, SEC, market data, internal/private lanes. | Incorrect freshness/rights metadata can make stale or restricted sources look usable. |
| source promotion | `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/source_promotion.py` | Stop promoting free-form scanner summaries as canonical evidence; accept EvidenceAtom/ClaimAtom candidates with source health and query registry metadata. | Wrong promotion path can reintroduce summary-as-evidence failure. |
| semantic normalizer | `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/semantic_normalizer.py` | Normalize EvidenceAtom/ClaimAtom fields before report packet assembly; preserve source IDs, event time, entity IDs, compliance class, and lineage. | Early compression can erase provenance again. |
| temporal alignment | `/Users/leofitz/.openclaw/workspace/services/market-ingest/temporal_alignment/alignment.py` | Use observed/published/ingested/event time and lane-specific freshness budgets; avoid one global stale knob. | Wrong time semantics can make old news look current. |
| packet compiler | `/Users/leofitz/.openclaw/workspace/services/market-ingest/packet_compiler/compiler.py` | Include source health hash, QueryPack/fetch metadata, claim/gap references, and undercurrent board mutation metadata in packets. | Packet authority drift can alter wake/report decisions. |
| wake policy | `/Users/leofitz/.openclaw/workspace/services/market-ingest/wake_policy/policy.py` | Keep deterministic wake before model judgment; add source-health-aware disclosure and peacetime board mutation without making stale source health a trade signal. | Wake threshold mutation can create spam or silence. |
| judgment validator | `/Users/leofitz/.openclaw/workspace/services/market-ingest/validator/judgment_validator.py` | Enforce evidence refs against claim/atom/source-health lineage; reject Answers prose as authority; require insufficient-data when slices are missing. | Validator bypass can let sidecar prose or stale evidence become authority. |
| source health compiler | `/Users/leofitz/.openclaw/workspace/services/market-ingest/source_health/compiler.py` | Decide whether parent consumes finance `state/source-health.json` or owns canonical source health generation. | Dual source-health authorities can diverge. |
| live finance adapter | `/Users/leofitz/.openclaw/workspace/services/market-ingest/adapters/live_finance_adapter.py` | Consume finance-local QueryPack/fetch/claim/gap artifacts in shadow mode before active packet mutation. | Adapter cutover can break packet compilation. |

## Cutover Gates

1. Refresh `docs/openclaw-runtime/parent-dependency-inventory.json`.
2. Run `tools/audit_parent_dependency_drift.py` and record intentional drift.
3. Run parent market-ingest tests before mutation.
4. Implement parent changes behind feature flags/switches.
5. Run parent market-ingest tests after mutation.
6. Run finance full suite.
7. Run finance report path and delivery safety in dry-run/no-delivery mode.
8. Only then restart or activate parent runtime paths.

## Required Feature Flags / Switches

- `FINANCE_QUERY_PACK_PLANNER_ENABLED`
- `FINANCE_DETERMINISTIC_BRAVE_FETCHERS_ENABLED`
- `FINANCE_SOURCE_HEALTH_PARENT_CANONICAL_ENABLED`
- `FINANCE_CLAIM_GRAPH_PACKET_ENABLED`
- `FINANCE_UNDERCURRENT_BOARD_MUTATION_ENABLED`
- `FINANCE_FOLLOWUP_SLICE_REHYDRATION_ENABLED`

Default must be off unless the parent-runtime phase explicitly enables it.

## Rollback

Rollback must be coarse and fast:

1. Disable all flags above.
2. Revert parent packet compiler to current scanner/legacy observation inputs.
3. Keep finance-local shadow artifacts available for audit, but stop parent consumption.
4. Keep Discord primary report delivery on existing deterministic renderer/safety path.
5. Do not fall back to route-card-only delivery.
6. Re-run parent dependency drift and finance full suite after rollback.

## Acceptance Criteria For Parent Runtime Phase

- Parent code consumes QueryPack/fetch/claim/gap artifacts only behind flags.
- Source health degradation is disclosed in packets/boards but does not mutate thresholds by itself.
- Brave Answers prose is never accepted as evidence; only citation URLs can seed fetch/evidence candidates.
- Follow-up router uses `followup_slice_index` from reader bundle and does not use raw thread history as memory.
- Parent delivery failure falls back to complete readable Discord primary report, never route-card-only.
- All parent changes have a single rollback switch path.

## Explicit Non-Goals

- This document does not modify parent files.
- This document does not authorize live trading or execution authority.
- This document does not change wake thresholds.
- This document does not restart OpenClaw runtime.
- This document does not make finance-local source health canonical for parent automatically.

## Reviewer Checklist

- [ ] Parent touch map covers source registry, source promotion, semantic normalizer, temporal alignment, packet compiler, wake policy, and judgment validator.
- [ ] Rollback plan disables every new parent consumption path.
- [ ] Feature flags default off.
- [ ] Parent runtime phase has explicit user approval.
- [ ] Finance-local artifacts are already committed and tested before parent mutation.
