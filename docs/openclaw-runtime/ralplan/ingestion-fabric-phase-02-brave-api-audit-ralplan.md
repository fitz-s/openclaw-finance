# RALPLAN Ingestion Fabric Phase 02: Brave API Capability Audit And Activation Boundary

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Before implementing Brave deterministic fetchers or changing finance ingestion behavior, produce a reviewer-visible audit of current OpenClaw Brave usage, missing Brave API capabilities, quota/rate-limit state, official Brave endpoint roles, and the correct activation boundaries for Brave Web, Brave News, Brave LLM Context, and Brave Answers.

This phase is an extension package, not a hotfix. It uses an external scout pass against official Brave documentation and integrates the result into local audit artifacts. It must not activate new Brave endpoints, modify gateway config, change finance scanner prompts, change report delivery, or change source ranking.

## External Scout Inputs

Scout source class: official Brave API documentation only.

Reviewed sources:
- Brave Web Search documentation: https://api-dashboard.search.brave.com/documentation/services/web-search
- Brave News Search documentation: https://api-dashboard.search.brave.com/documentation/services/news-search
- Brave LLM Context documentation: https://api-dashboard.search.brave.com/documentation/services/llm-context
- Brave Answers documentation: https://api-dashboard.search.brave.com/documentation/services/answers
- Brave pricing/rate-limit documentation: https://api-dashboard.search.brave.com/documentation/pricing
- Brave API terms of service: https://api-dashboard.search.brave.com/documentation/resources/terms-of-service

External scout conclusions integrated here:
- Web Search is broad discovery; current docs expose freshness/date filtering, `extra_snippets`, country/language targeting, and pagination limits.
- News Search is the correct first Brave lane for freshness-sensitive market/news discovery; it is missing from the installed OpenClaw provider.
- LLM Context is the correct selected-source reading lane, not the first-pass discovery lane. Official docs support freshness, but the current OpenClaw `llm-context` abstraction rejects `freshness`, `date_after`, and `date_before` before request execution.
- Answers is an OpenAI-compatible sidecar synthesis endpoint. Citation/entity/research modes require streaming. Answer prose is not canonical evidence; only citations can seed EvidenceAtom candidates.
- Brave Search Results have storage/redistribution restrictions. The finance system must not build a long-lived committed database of raw Brave Search Results; committed artifacts must stay sanitized.

## RALPLAN-DR Summary

### Principles

1. **Discovery is not synthesis.** Brave Web/News can discover candidate sources; Brave Answers can synthesize sidecar hypotheses; neither should bypass EvidenceAtom/ClaimAtom.
2. **Freshness must be deterministic.** Finance discovery must prefer endpoints that support freshness/date filters for time-sensitive market work.
3. **Answers are sidecar-only.** Brave `/chat/completions` output is not canonical evidence; only its citations may become EvidenceAtom candidates.
4. **Quota failure is a source-health event.** `402 USAGE_LIMIT_EXCEEDED` must degrade source health and prevent silent fallback to stale narratives.
5. **Rights are part of ingestion architecture.** Search result persistence and redistribution limits shape what can be stored in repo-visible artifacts.
6. **No active behavior change in audit phase.** This phase creates facts and decisions for implementation, not runtime activation.

### Decision Drivers

1. `review2-04-17-2026.md` identifies current OpenClaw Brave usage as a `web_search` abstraction with `llm-context` mode and weak freshness discipline.
2. Local config confirms Brave is enabled as `tools.web.search.provider=brave` and `plugins.entries.brave.config.webSearch.mode=llm-context`.
3. Local OpenClaw provider code confirms only `web/search` and `llm/context` are implemented; `news/search` and Brave Answers are not integrated.
4. Gateway logs show repeated Brave LLM Context API `402 USAGE_LIMIT_EXCEEDED` failures, meaning upstream discovery can silently starve.
5. Finance source state currently still shows too much `unknown_web` / narrative concentration, even after stale-source scoring hotfix.
6. Official Brave docs confirm Web/News/LLM Context/Answers have distinct roles; using a single generic `web_search` abstraction is too lossy for finance source governance.
7. Official terms require storage discipline; fetchers must not commit raw Brave result bodies or create a persistent search-result database without explicit rights.

## Viable Options

### Option A - Directly switch OpenClaw Brave mode from `llm-context` to `web`

Pros:
- Gets `freshness` / `date_after` / `date_before` filters back through existing `web_search` abstraction.
- Lower implementation effort.

Cons:
- Still leaves scanner as free-form `web_search` user.
- Still does not expose Brave News endpoint.
- Still does not emit SourceFetchRecord / QueryPack artifacts.
- May reduce grounding chunks versus llm-context.
- Does not address rights-aware result persistence.

Verdict: useful as emergency config fallback, not the ingestion architecture.

### Option B - Add Brave Answers directly to finance scanner

Pros:
- Fast richer answers with citations.
- May make Discord follow-up sound better quickly.

Cons:
- Turns synthesis into pseudo-source authority.
- Increases hallucination/over-compression risk.
- Conflicts with `Never compress before provenance`.
- Does not solve source freshness or query repetition by itself.
- Research/citation modes require streaming and are a poor fit for deterministic hot path gating.

Verdict: rejected for hot path; acceptable only as sidecar with citations extracted into EvidenceAtom candidates.

### Option C - Add deterministic Brave News/Web/Context/Answers lanes after audit

Pros:
- Aligns with review2 source fabric.
- Lets finance use `news/search` for freshness-sensitive discovery.
- Lets `web/search` do domain/date-filtered source discovery.
- Keeps `llm/context` for selected source reading only.
- Keeps `answers` sidecar-only and citation-gated.
- Enables SourceFetchRecord, query registry, quota health, replay, and rights-aware storage.

Cons:
- More work than changing config.
- Requires API/quota/rate-limit handling.
- Requires source rights/export discipline.

Verdict: selected follow-up direction after this audit.

## Selected Plan For Phase 02

Phase 02 produces a deterministic audit artifact and tests only.

### Audit Questions

1. What Brave mode is configured locally?
2. Which Brave endpoints does installed OpenClaw currently implement?
3. Which Brave endpoints are missing but required by review2?
4. Does current `llm-context` mode support freshness/date filters through OpenClaw?
5. What does official Brave documentation say each endpoint is for?
6. Is Brave quota currently healthy or degraded?
7. What rights/storage limits must later fetchers obey?
8. What is the correct authority boundary for each Brave endpoint?
9. What should Phase 03/04/05/06 implement next?

### Output Artifacts

- `docs/openclaw-runtime/brave-api-capability-audit.json`
- `tools/export_brave_api_capability_audit.py`
- `tests/test_brave_api_capability_audit_phase02.py`
- `docs/openclaw-runtime/critics/ingestion-fabric-phase-02-implementation-critic.md`

### Audit Artifact Shape

```json
{
  "contract": "brave-api-capability-audit-v1",
  "configured_provider": "brave",
  "configured_mode": "llm-context|web|null",
  "implemented_endpoints": ["brave/web/search", "brave/llm/context"],
  "missing_endpoints": ["brave/news/search", "brave/answers/chat_completions"],
  "endpoint_inventory": {
    "brave/news/search": {
      "authority_boundary": "fresh_news_discovery",
      "supports_freshness": true,
      "current_openclaw_provider_status": "missing"
    }
  },
  "known_mode_limits": {
    "openclaw_llm_context_rejects_freshness": true,
    "official_llm_context_supports_freshness_but_current_openclaw_abstraction_blocks_it": true
  },
  "rights_and_storage_boundary": {
    "do_not_persist_raw_search_results_as_database": true,
    "committed_artifacts_must_be_sanitized": true
  },
  "authority_boundaries": {
    "brave/web/search": "source_discovery",
    "brave/news/search": "fresh_news_discovery",
    "brave/llm/context": "selected_source_reading",
    "brave/answers/chat_completions": "sidecar_synthesis_only"
  },
  "no_secrets_exported": true,
  "no_api_calls_made_by_exporter": true,
  "no_runtime_config_change": true,
  "no_execution": true
}
```

## Implementation Boundaries

Allowed:
- Read local OpenClaw config with secrets redacted.
- Inspect installed OpenClaw Brave provider code.
- Parse gateway logs for Brave 402 quota failures without exporting API keys.
- Incorporate official Brave docs as reviewer-visible endpoint capability metadata.
- Write sanitized reviewer-visible audit JSON.
- Add tests around audit semantics.

Forbidden:
- Do not call Brave APIs in Phase 02.
- Do not modify `openclaw.json`.
- Do not change `webSearch.mode`.
- Do not add Brave fetchers yet.
- Do not alter finance scanner prompt or cron jobs.
- Do not change wake, delivery, JudgmentEnvelope, thresholds, or execution authority.
- Do not commit raw Brave result snippets or long-lived search result caches.

## Acceptance Criteria

1. Audit confirms configured Brave mode.
2. Audit confirms OpenClaw currently implements only `web/search` and `llm/context` for Brave web_search provider.
3. Audit explicitly marks `news/search` and `chat/completions` Answers as missing from current OpenClaw provider.
4. Audit records quota failures if present and sanitizes all secrets.
5. Audit records official endpoint roles and activation boundaries.
6. Audit records rights/storage boundary for Brave Search Results.
7. Tests prove the audit does not treat Brave Answers as canonical authority.
8. Phase 02 can be committed independently with no runtime behavior changes.

## Test Plan

- `test_brave_audit_detects_current_llm_context_mode_and_missing_endpoints`
- `test_brave_audit_documents_llm_context_time_filter_gap`
- `test_brave_audit_records_official_endpoint_roles`
- `test_brave_audit_preserves_rights_and_storage_boundary`
- `test_brave_audit_exports_no_obvious_api_secret`

## Risk Register

1. **Installed OpenClaw dist path may change.**
   Mitigation: audit should fail softly and report endpoint detection unavailable.

2. **Quota logs are historical, not live billing truth.**
   Mitigation: label quota status as log-derived.

3. **Brave docs/API may evolve.**
   Mitigation: later fetcher implementation must verify official docs again before code.

4. **User may want immediate source activation.**
   Mitigation: do not skip audit; source activation without this map recreates the current abstraction problem.

5. **Persistence conflicts with Brave rights.**
   Mitigation: Phase 04 must store only sanitized SourceFetchRecord metadata and must not commit raw Brave Search Results.

## Rollback

No runtime rollback needed. Phase 02 adds only docs/tool/test artifacts.
If incorrect, remove audit artifacts and revise the plan; no source ingestion behavior changes.

## Follow-Up Staffing Guidance

Recommended next phases:

- Phase 03: Query registry, lane watermarks, source memory index.
- Phase 04: Brave News/Web deterministic fetchers.
- Phase 05: Brave LLM Context selected-reader fetcher.
- Phase 06: Brave Answers sidecar.

Phase 03 should happen before high-volume Brave fetchers so the system does not repeat stale/zero-yield queries at higher scale.

## Architect Review

Self-review verdict: APPROVE WITH BOUNDARY.

Reasoning:
- This phase is correctly scoped as audit, not activation.
- External scout results improve the plan by adding official endpoint limits and rights/storage constraints.
- The strongest alternative is switching Brave mode to `web` immediately for freshness filters, but that is a config workaround, not a source fabric.
- The selected audit-first path prevents hidden coupling between `web_search` convenience and finance canonical ingestion.

## Critic Review

Implementation critic must verify:
- no secrets exported
- no API calls made
- no runtime config change
- no active finance behavior change
- Brave Answers remains sidecar-only
- official docs are included as capability metadata, not treated as runtime authority
