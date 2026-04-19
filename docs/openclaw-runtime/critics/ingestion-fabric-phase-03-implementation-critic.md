# Ingestion Fabric Phase 03 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-03-query-memory-ralplan.md`
- `scripts/query_registry_compiler.py`
- `scripts/source_memory_index.py`
- `tests/test_query_memory_phase03.py`

Checks:
- Query registry is shadow-only and not wired into scanner/report/wake delivery.
- Query fingerprinting includes schema and normalization profile version.
- Low-yield/stale-repeat/rate-limited query outcomes produce cooldown/next-eligible metadata.
- High-yield query runs are not suppressed by `should_skip_query`.
- Rate-limit metadata is captured without probing APIs.
- Source memory groups by lane, entity, event date, domain, predicate, and horizon, not theme/summary text.
- Claim novelty uses subject + predicate + horizon + direction overlap.
- Lane watermarks are lane-independent and include max event time, watermark time, allowed lateness, latest fetch, and latest novel claim time.
- Persisted artifacts are metadata-only and record `restricted_payload_present=false`.
- No raw source snippets, raw search result bodies, OpenClaw config changes, Brave calls, wake changes, or delivery changes were introduced.

Risks:
- Query skip logic is intentionally conservative but still must remain shadow-only until fetchers provide enough yield telemetry.
- Source memory grouping by event date can still over-collapse same-day multi-catalyst stories; later phases may add event_class/catalyst hashes if needed.
- Watermark defaults are heuristic and need source-registry-backed budgets before active gating.

Required follow-up:
- Phase 04 Brave Web/News fetchers should call `should_skip_query` in dry-run/telemetry mode first, not hard-block mode.
- Phase 04 must write SourceFetchRecord-compatible metadata without persisting raw Brave Search Results.
- Phase 09 source health should consume rate-limit and quota fields from query records/fetch records.

Commit gate: pass.
