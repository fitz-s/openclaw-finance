# Ingestion Fabric Phase 04 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-04-brave-web-news-fetchers-ralplan.md`
- `scripts/brave_search_fetcher_common.py`
- `scripts/brave_web_search_fetcher.py`
- `scripts/brave_news_search_fetcher.py`
- `tests/test_brave_web_news_fetchers_phase04.py`

Checks:
- Web and News fetchers are separate wrappers over a shared deterministic common module.
- Fetchers consume QueryPack-shaped input and emit SourceFetchRecord-compatible metadata.
- Fetchers are not wired into scanner cron, report delivery, wake policy, threshold mutation, or OpenClaw parent runtime.
- Dry-run mode works without API key or network.
- Web count caps at 20, News count caps at 50, offset caps at 9, and freshness/date range params are explicit.
- `extra_snippets` defaults to false; payload expansion is opt-in only.
- Request params are sanitized and never include API keys.
- Result persistence is metadata-only: URL/domain/page_age/page_fetched/source metadata; raw response bodies, descriptions, extra snippets, thumbnails, icons, and answer synthesis are not persisted.
- 402/429-style throttle/quota errors become explicit metadata with error class, retryability, and quota headers.
- Query registry skip is advisory telemetry only through `query_registry_should_skip`; it does not hard-block in this phase.

Risks:
- Live Brave API behavior is not exercised because tests use mocks and the local quota is degraded.
- Pagination is not yet multi-page; wrappers fetch one page and record metadata. Multi-page handling should be a later controlled expansion.
- API-version pinning is not implemented yet; add once schema stability is required for production fetches.
- Metadata persistence still carries Brave Search Result-derived URLs/source metadata; keep state local and do not commit raw result files.

Required follow-up:
- Phase 05 should add selected-source LLM Context reader only after source candidates exist.
- Before active cron integration, add source health handling for 402/429 and a quota-aware scheduler/backoff loop.
- Add pagination only with query registry/lane watermark guardrails and explicit result caps.

Commit gate: pass.
