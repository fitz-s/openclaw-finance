# Brave Source Activation P1 - 2026-04-18

## Scope

This package implements the P1 repair from `source-freshness-deep-check-20260418.md`: Brave source lanes now perform real activation attempts from deterministic QueryPacks and report explicit credential/quota/network degradation.

It does not promote Brave answer text, change wake authority, change thresholds, or implement the options IV vendor path.

## What Changed

### 1. Added deterministic activation runner

New file:

- `scripts/brave_source_activation.py`

Behavior:

- Reads `state/query-packs/scanner-planned.jsonl`.
- Selects bounded high-priority packs, default max `4`.
- Runs Brave News first, then Brave Web as fallback when appropriate.
- Writes SourceFetchRecords to:
  - `state/brave-news-search-results.jsonl`
  - `state/brave-web-search-results.jsonl`
- Writes an activation report to `state/brave-source-activation-report.json`.
- Updates `state/query-registry.jsonl` so repeated low-yield/failed/rate-limited queries are cooled down.
- Never treats fetch records as market judgment or execution authority.

### 2. Connected activation into parent cutover

Changed:

- `scripts/finance_parent_market_ingest_cutover.py`

New order:

1. `finance_llm_context_pack.py`
2. `query_pack_planner.py`
3. `brave_source_activation.py`
4. `source_health_monitor.py`
5. parent live adapter / health / packet / wake pipeline

This matters because source health now sees real Brave fetch attempts before reports and gates are rendered.

### 3. Connected finance fetchers to OpenClaw SecretRef

Changed:

- `scripts/brave_search_fetcher_common.py`

Behavior:

- First checks `BRAVE_SEARCH_API_KEY` / `BRAVE_API_KEY` env vars.
- If env vars are absent, resolves the existing OpenClaw SecretRef at `plugins.entries.brave.config.webSearch.apiKey` via the configured `keychain_exec` provider.
- Secret values are used only in-process for the outbound Brave request.
- Secrets are not printed or written to state.

### 4. Source health now distinguishes credential, quota, and network failures

Changed:

- `scripts/source_health_monitor.py`

New degradation semantics:

- `missing_credentials` for missing API key.
- `quota_limited` for 402/429 or Brave quota/rate-limit failures.
- `network_error` for transport failures.
- `source_lane_unavailable_reasons` is now included in `stale_reuse_guard`.

## Runtime Smoke Evidence

Activation smoke after SecretRef bridge:

```json
{
  "status": "pass",
  "selected_pack_count": 1,
  "fetch_record_count": 1,
  "status_counts": {"rate_limited": 1},
  "endpoint_counts": {"brave/news/search": 1},
  "fallback_count": 0
}
```

Source health after smoke:

```json
{
  "source:brave_news": "quota_limited",
  "source:brave_llm_context": "quota_limited",
  "source:brave_answers": "unknown"
}
```

Full parent cutover smoke:

```json
{
  "status": "pass",
  "brave_source_activation": "ok",
  "finance_source_health": "degraded",
  "parent_live_finance_adapter": "ok",
  "parent_wake_policy": "PACKET_UPDATE_ONLY"
}
```

A later full report-chain smoke had `fetch_record_count=0` because query registry cooldown skipped the same recently rate-limited query packs. That is expected quota-aware behavior.

## Remaining Blockers

- Brave source lane is now active, but the current key/quota state is degraded: Brave News returns rate-limited/quota-limited rather than fresh results.
- Brave Answers remains sidecar/dry-run and should stay out of the hot path unless explicitly invoked for citation-only sidecar use.
- Options IV remains proxy-only/stale; that is P2.
- Deterministic cron work is still wrapped in OpenClaw agent turns; that is P4.

## Verification

Commands run:

```bash
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 scripts/finance_parent_market_ingest_cutover.py
python3 scripts/finance_llm_context_pack.py
python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json
python3 scripts/finance_decision_report_render.py
python3 scripts/finance_report_product_validator.py
python3 scripts/finance_decision_log_compiler.py
python3 scripts/finance_report_delivery_safety.py
python3 scripts/finance_report_reader_bundle.py
```

Results:

- Finance tests: `273 passed`.
- Parent finance cutover tests: `33 passed`.
- Compile/audit: pass.
- Product validator: pass, `error_count=0`.
- Delivery safety: pass, no blocking reasons.
- Reader bundle smoke: `RC482`.

## Next Package

P2 should target options IV: replace stale proxy-only IV surface with a real vendor or a stricter unavailable-state that prevents reports from implying options confidence when IV is missing.
