# RALPLAN Ingestion Fabric Phase 04: Brave Web/News Deterministic Fetchers

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Implement deterministic Brave Web Search and Brave News Search fetcher scripts that consume QueryPack-shaped input and emit SourceFetchRecord-compatible metadata. This phase adds the fetcher capability but does not wire it into scanner cron, report generation, wake policy, Discord delivery, or parent OpenClaw runtime.

## Why This Phase Exists

Phase 02 proved the current OpenClaw provider only exposes Web Search and LLM Context through a generic abstraction and is missing News Search. Phase 03 added query memory and lane watermarks so new fetchers can avoid repeating stale/zero-yield work. Phase 04 now adds the deterministic source discovery lanes needed before EvidenceAtom conversion.

## External Scout Inputs

Source class: official Brave Web/News API docs and HTTP/rate-limit references.

Integrated Phase 02/04 conclusions:
- Web Search is for broad domain/date-filtered source discovery.
- News Search is for freshness-sensitive market/news discovery and must be separate from Web Search.
- Web `count` must cap at 20; News `count` must cap at 50; `offset` must cap at 9.
- Freshness/date range must be explicit from QueryPack.
- `extra_snippets`, `summary`, and rich callback expansion must be opt-in only; fetchers default to metadata-only.
- API keys must never be exported in records or tests.
- 402/429/rate-limit responses must become explicit fetch metadata, not silent fallback to old state.
- Web pagination should respect `more_results_available`; News pagination should stop on a short page or offset cap in later pagination phases.
- Error mapping must distinguish retryable throttle/quota failures from non-retryable validation/auth failures and hard misses.

## Selected Design

Add:
- `scripts/brave_search_fetcher_common.py`
- `scripts/brave_web_search_fetcher.py`
- `scripts/brave_news_search_fetcher.py`

Fetcher behavior:
- Accept QueryPack JSON via `--pack`.
- Support `--dry-run` for request/record validation without calling Brave.
- Build endpoint-specific params with freshness/date/domain controls.
- Use `X-Subscription-Token` only from env/config at runtime and never write it to output.
- Emit SourceFetchRecord-compatible JSONL rows with metadata-only `result_refs`.
- Do not persist raw result bodies, descriptions, extra snippets, or answer synthesis.
- Consult Phase 03 `should_skip_query` in check mode and record `query_registry_should_skip` without hard-blocking by default.

## Acceptance Criteria

1. Web and News fetcher wrappers exist and call a shared deterministic common module.
2. Web fetcher maps QueryPack to `brave/web/search` with correct caps and date/freshness params.
3. News fetcher maps QueryPack to `brave/news/search` with correct caps and date/freshness params.
4. FetchRecords include endpoint, sanitized request params, status, quota/rate-limit metadata, result count, watermark key, and no execution authority.
5. FetchRecords do not include API keys, raw descriptions, extra snippets, or raw response bodies.
6. Dry-run mode works without network/API key.
7. Tests use mocked HTTP and do not call Brave.

## Non-Goals

- Do not connect fetchers to OpenClaw cron/scanner hot path.
- Do not call Brave during tests.
- Do not create EvidenceAtoms from Brave results yet.
- Do not implement LLM Context reader or Answers sidecar in this phase.
- Do not persist raw Brave Search Results into committed artifacts.

## Test Plan

- `test_brave_web_params_cap_count_and_freshness`
- `test_brave_news_params_cap_count_and_date_range`
- `test_brave_fetch_record_sanitizes_api_key_and_raw_snippets`
- `test_brave_rate_limit_error_becomes_fetch_record_metadata`
- `test_brave_dry_run_does_not_require_api_key_or_network`

## Rollback

No runtime rollback required. Remove the three fetcher scripts/tests/docs; no active job behavior changes.

## Critic Requirements

Implementation critic must verify:
- no hot-path integration
- no live API calls in tests
- no API key export
- no raw result body/snippet persistence
- rate-limit/quota failures become explicit metadata
- query registry skip is advisory/telemetry only in this phase
