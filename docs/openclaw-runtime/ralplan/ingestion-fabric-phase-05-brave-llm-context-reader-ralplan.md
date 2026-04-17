# RALPLAN Ingestion Fabric Phase 05: Brave LLM Context Selected Reader

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Add a Brave LLM Context selected-reader lane. It reads already scoped source candidates for grounding metadata, but it is not first-pass discovery and does not produce canonical claims directly.

## External Scout Inputs

Official Brave LLM Context docs show:
- Endpoint: `GET|POST /res/v1/llm/context`.
- Query `q` is required, max 400 chars / 50 words.
- `count`, `maximum_number_of_urls`, token budgets, snippet budgets, freshness, `context_threshold_mode`, and Goggles are supported.
- Response contains `grounding` arrays with extracted snippets and `sources` metadata keyed by URL.
- Brave recommends handling empty grounding gracefully, checking rate-limit headers, respecting the 1-second sliding window, and using smaller token budgets when possible.
- Brave does not document a direct source allowlist field for LLM Context; source selection is indirect through query operators, freshness, Goggles, domains, and threshold mode.
- Narrative docs and API reference differ on the total `maximum_number_of_snippets` ceiling, so the implementation keeps the ceiling configurable instead of hardcoding a single value.

## Selected Design

Add `scripts/brave_llm_context_fetcher.py`.

Rules:
- QueryPack must be scoped by `selected_urls`, `allowed_domains`, or `goggles`; otherwise the reader blocks. This prevents LLM Context from becoming first-pass discovery.
- Use POST by default to keep request shape stable for larger parameter sets.
- Cap query, count, URL, token, and snippet budgets to official ranges.
- Keep total snippet ceiling configurable (`maximum_number_of_snippets_cap`) to handle Brave doc/API-ref mismatch.
- Preserve local recall (`poi`/`map`) only as separate metadata counts; do not merge it into generic source refs.
- Persist only metadata, snippet counts, and snippet digests. Do not persist raw snippets or full context bodies.
- Emit SourceFetchRecord-compatible metadata with `endpoint=brave/llm/context`, `source_id=source:brave_llm_context`, `selected_source_reading=true`, `raw_context_persisted=false`, and `evidence_candidate_only=true`.
- Dry-run works without API key/network.

## Acceptance Criteria

1. LLM Context reader refuses unscoped first-pass discovery QueryPacks.
2. Request params enforce official caps and freshness/date mapping.
3. Mocked responses produce context refs with URL/hostname/title/age/snippet_count/snippet_digest but no raw snippets.
4. 402/429/error responses become explicit metadata.
5. Dry-run works without API key or network.
6. No scanner/wake/report/delivery behavior changes.

## Non-Goals

- Do not implement Brave Answers.
- Do not wire reader into cron/hot path.
- Do not convert context directly into canonical ClaimAtom.
- Do not persist raw context snippets.

## Test Plan

- `test_llm_context_blocks_unscoped_first_pass_discovery`
- `test_llm_context_params_cap_budget_and_scope_domains`
- `test_llm_context_record_keeps_digests_not_raw_snippets`
- `test_llm_context_rate_limit_error_metadata`
- `test_llm_context_dry_run_requires_no_api_key_or_network`
