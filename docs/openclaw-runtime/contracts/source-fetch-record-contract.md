# SourceFetchRecord Contract

`SourceFetchRecord` records a deterministic source fetch attempt before results become EvidenceAtoms.

## Shape

```json
{
  "fetch_id": "fetch:<hash>",
  "pack_id": "query-pack:<hash>",
  "source_id": "source:brave_news",
  "lane": "news_policy_narrative",
  "endpoint": "brave/news/search",
  "request_params": {},
  "fetched_at": "...",
  "status": "ok|partial|rate_limited|failed",
  "quota_state": null,
  "result_count": 0,
  "watermark_key": "news_policy_narrative:reuters.com:oil",
  "error_code": null,
  "application_error_code": null,
  "error_class": "missing_credentials|network_error|subscription_denied|schema_drift|application_error|server_error|null",
  "no_execution": true
}
```

## Rules

- FetchRecord is source operation metadata, not market judgment.
- Rate limits and quota failures must be explicit.
- FetchRecords feed EvidenceAtom creation but cannot directly drive reports.
- Failed fetches should update source health, not silently fall back to old state.
- Top-level `status` must not be expanded for provider-specific failures. Use
  `status=failed` plus `error_class` / `application_error_code` for missing
  credentials, network errors, subscription denial, schema drift, and provider
  application errors.
