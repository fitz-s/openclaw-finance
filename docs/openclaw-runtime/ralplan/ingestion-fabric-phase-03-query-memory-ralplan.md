# RALPLAN Ingestion Fabric Phase 03: Query Registry, Lane Watermarks, Source Memory Index

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Implement the first repetition-control layer from `review2-04-17-2026.md`: query registry, lane watermarks, and source memory index. This phase does not add new sources and does not change the active scanner/report hot path. It creates deterministic shadow tools that later Brave/Web/News fetchers can use before making requests.

## Why This Phase Exists

The current system repeats stale narratives because dedup happens too late and at the wrong layer. `finance_worker.py` still works around `theme`/`summary` text. Review2 requires moving repetition control to:

- Query history: which query packs produced useful or useless output.
- Claim novelty: whether a new claim is genuinely new by subject/predicate/horizon, not by wording.
- Lane watermarks: whether a lane/entity/domain is already saturated or stale.
- Source memory: whether an entity/event/domain/predicate combination is already known.

## RALPLAN-DR Summary

### External Scout Inputs

Scout source class: implementation patterns from primary/high-quality engineering references.

Integrated findings:
- Canonical request fingerprints need schema/versioned canonical JSON and cryptographic hashes. This is reflected as `query_schema_version`, `normalization_profile_version`, `query_fingerprint`, and canonical hash generation in the query registry.
- Query/search normalization must be versioned to avoid future analyzer drift aliasing old and new query behavior.
- Source memory should be metadata/hash/checkpoint oriented, not raw-content oriented. This phase stores IDs, domains, event dates, digests, novelty, and retention class, not raw result bodies.
- Watermarks must remain lane-independent. This phase records `merge_policy=lane_independent`, per-lane allowed lateness, `max_event_time`, and `watermark_time`.
- Rate-limit-aware ingestion needs persisted retry metadata. This phase records `retry_after_sec`, `x_ratelimit_remaining`, `x_ratelimit_reset`, `next_eligible_at`, and `last_error_class` in QueryRunRecord metadata.

Reference links recorded by scout:
- RFC 8785 JSON Canonicalization: https://www.rfc-editor.org/rfc/rfc8785
- NIST hash functions: https://csrc.nist.gov/Projects/hash-functions
- Apache Beam watermarks/allowed lateness: https://beam.apache.org/documentation/programming-guide/
- Spark Structured Streaming watermarks: https://spark.apache.org/docs/3.5.8/structured-streaming-programming-guide.html
- AWS retry/backoff reliability guidance: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_limit_retries.html
- GitHub REST API rate-limit best practices: https://docs.github.com/en/enterprise-cloud@latest/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- RFC 6585 429 Too Many Requests: https://www.rfc-editor.org/rfc/rfc6585.html
- Google Cloud Search indexing queues/checkpoints: https://developers.google.com/workspace/cloud-search/docs/guides/queues
- Elastic text analysis normalization: https://www.elastic.co/docs/manage-data/data-store/text-analysis

### Principles

1. **No source activation yet.** This phase prepares the memory layer before Brave fetchers.
2. **No hot-path mutation.** Query skip decisions are available to future fetchers but not wired into current scanner jobs in this phase.
3. **Claim-level novelty beats theme text.** Same subject/predicate/horizon should be treated as overlap even if the prose is different.
4. **Watermarks are lane-specific.** Market structure, news, filings, alt-data, internal/private notes, and human field notes need different freshness semantics.
5. **Memory is metadata-first.** Do not store raw restricted search results; keep source memory as IDs, domains, timestamps, claim keys, and safe metadata.

### Selected Design

Add two scripts:

1. `scripts/query_registry_compiler.py`
   - Defines QueryRunRecord helpers.
   - Computes stable query hashes from QueryPack semantics.
   - Computes outcome (`high_yield`, `low_yield`, `stale_repeat`, `failed`).
   - Computes cooldowns for low-yield/stale-repeat/rate-limited queries.
   - Exposes `should_skip_query(pack, recent)` for future fetchers.
   - Writes/reads `state/query-registry.jsonl` when used from CLI.

2. `scripts/source_memory_index.py`
   - Reads EvidenceAtom rows and ClaimGraph claims.
   - Builds `state/source-memory-index.json` shadow artifact.
   - Builds `state/lane-watermarks.json` shadow artifact.
   - Groups memory by lane + entity + event_date + source_domain + predicate + horizon.
   - Scores claim novelty by subject + predicate + horizon + direction overlap.

## Acceptance Criteria

1. Query registry can suppress repeated zero-yield / stale-repeat queries without relying on prose theme equality.
2. Source memory index groups claims by subject/predicate/horizon/source-domain/event date, not `theme` text.
3. Lane watermarks record latest effective fetch and latest novel claim by lane/entity/domain.
4. Artifacts are shadow-only, review-only, and carry `no_execution=true`.
5. No runtime config, wake policy, report delivery, thresholds, or scanner prompt changes.
6. Tests cover zero-yield query suppression, claim novelty, source memory grouping, and lane watermark output.

## Non-Goals

- Do not implement Brave fetchers in this phase.
- Do not call Brave APIs.
- Do not modify OpenClaw parent runtime.
- Do not mutate `finance_worker.py` behavior yet.
- Do not persist raw Brave Search Results.

## Test Plan

- `test_query_registry_suppresses_zero_yield_repeat_queries`
- `test_query_registry_does_not_skip_high_yield_queries`
- `test_claim_novelty_uses_subject_predicate_horizon_not_theme_text`
- `test_source_memory_index_groups_by_claim_identity_not_summary`
- `test_lane_watermarks_emit_latest_fetch_and_novel_claim_times`

## Risk Register

1. **Premature blocking risk.** If `should_skip_query` is wired too early, it could suppress genuinely fresh market events.
   Mitigation: keep phase shadow-only and add watermarks before fetcher activation.

2. **Over-grouping risk.** Subject/predicate/horizon may collapse different catalysts.
   Mitigation: source memory key also includes event date and source domain.

3. **Under-grouping risk.** Event time precision may create one key per timestamp.
   Mitigation: use event date for saturation keys and keep exact timestamps as metadata.

4. **Rights risk.** Source memory could become a raw-source cache by accident.
   Mitigation: store IDs/domains/timestamps/claim keys, not raw snippets or result bodies.

## Rollback

No runtime rollback is required. Remove the two shadow scripts/tests/docs and the generated shadow state outputs if the design changes.

## Critic Requirements

The implementation critic must verify:
- shadow-only scope
- no source/API calls
- no scanner/report behavior changes
- no raw source/result persistence
- query skip only exposed as helper, not wired into production
- tests cover both skip and non-skip cases
