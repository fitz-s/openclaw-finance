# Options IV Surface P2 Repair - 2026-04-18

## Scope

This package implements the approved P2 ralplan for options IV / volatility surface repair.

Goal: stop treating stale Nasdaq/yfinance proxy output as options truth, introduce a provider-neutral options-IV observation lane, and keep all downstream usage source-context-only until a later authority cutover.

## What Changed

### 1. Contracts and source scout

Changed:

- `docs/openclaw-runtime/contracts/options-iv-surface-contract.md`
- `docs/openclaw-runtime/contracts/source-fetch-record-contract.md`
- `docs/openclaw-runtime/contracts/source-health-contract.md`
- `docs/openclaw-runtime/contracts/source-scout-contract.md`
- `scripts/source_scout.py`

New contract semantics:

- Options IV surface is now provider observations first, Nasdaq/yfinance proxy fallback second.
- `SourceFetchRecord.status` stays aligned to `ok|partial|rate_limited|failed`.
- Provider-specific errors use `error_class`, `application_error_code`, and source-health `degraded_state`.
- Raw vendor payloads and credentials must not be retained.
- `options_iv_surface` remains source context only, not JudgmentEnvelope/wake/threshold/execution authority.

Source scout now includes:

- ORATS: high-value candidate, blocked from primary until live agreement is verified.
- ThetaData: local-terminal candidate with point-in-time support.
- Polygon Options: credential-gated plan-dependent candidate.
- Tradier Options: constrained fallback with courtesy ORATS greeks / hourly-greeks caveat.
- Nasdaq option-chain remains proxy fallback, not primary options-IV truth.

### 2. Provider fetcher

New:

- `scripts/options_iv_provider_fetcher.py`

Outputs:

- `state/options-iv-provider-snapshot.json`
- `state/options-iv-fetch-records.jsonl`

Supported adapters in this implementation:

- Polygon Options snapshot shape normalization.
- ThetaData local terminal implied-volatility/Greeks snapshot shape normalization.
- Tradier option chain with greeks shape normalization.

No credentials are assumed. Missing credentials and local terminal/network failures produce source-health-compatible fetch records:

- `status=failed`
- `error_class=missing_credentials|network_error|subscription_denied|application_error`
- `application_error_code=...`
- `raw_payload_retained=false`
- `derived_only=true`
- `no_execution=true`

### 3. Surface compiler provider-first path

Changed:

- `scripts/options_iv_surface_compiler.py`

New behavior:

- Reads `state/options-iv-provider-snapshot.json` first.
- Falls back to `state/options-flow-proxy.json` only for symbols with no provider observations.
- Emits `surface_policy_version=options-iv-surface-v2-shadow`.
- Emits `primary_source_status`, `primary_provider_set`, `source_health_refs`, `rights_policy`, `derived_only`, and `raw_payload_retained`.
- Proxy-only rows receive `missing_primary_options_iv_source` confidence penalty.
- Provider-backed rows compute derived IV metrics, call/put skew, term structure, volume/OI, provider confidence, and replay flags.

### 4. Source health integration

Changed:

- `scripts/source_health_monitor.py`

New behavior:

- Ingests `state/options-iv-fetch-records.jsonl`.
- Emits rows such as `source:polygon_options_iv`, `source:thetadata_options_iv`, `source:tradier_options_iv`.
- Distinguishes missing credentials, network errors, quota limits, subscription denial, and stale/unknown source state.
- Keeps source health advisory; it does not block delivery by itself.

### 5. Report/context wiring with authority guard

Changed:

- `scripts/finance_llm_context_pack.py`
- `scripts/finance_decision_report_render.py`
- `scripts/finance_report_product_validator.py`
- `scripts/finance_report_reader_bundle.py`
- `scripts/finance_discord_report_job.py`

New behavior:

- Report context pack includes compact `options_iv_surface_summary` as source context.
- Report envelope includes `options_iv_surface_ref`, `options_iv_surface_hash`, `options_iv_surface_summary`, and `options_iv_authority`.
- Product validator rejects retained raw vendor payloads and any attempt to let options-IV refs overlap JudgmentEnvelope evidence refs.
- Reader bundle exposes `SIV1` source-context card for follow-up/source tracing.
- Report job optionally runs `options_iv_provider_fetcher.py` before compiling the IV surface.

## Runtime Evidence

No-credential smoke:

```json
{
  "options_iv_provider_snapshot": {
    "status": "degraded",
    "observation_count": 0,
    "fetch_record_status_counts": {"failed": 2}
  },
  "options_iv_surface": {
    "status": "degraded",
    "surface_policy_version": "options-iv-surface-v2-shadow",
    "primary_source_status": "degraded"
  },
  "product_validation": {
    "status": "pass",
    "error_count": 0
  },
  "delivery_safety": {
    "status": "pass",
    "blocking_reasons": []
  }
}
```

Reader bundle now exposes `SIV1`:

```json
{
  "handle": "SIV1",
  "type": "source_context",
  "label": "Options IV surface｜source context only",
  "authority": "source_context_only_not_judgment_wake_threshold_or_execution"
}
```

## What This Still Does Not Solve

- There are still no live vendor credentials present for Polygon/Tradier in this environment.
- ThetaData local terminal is not assumed running.
- Therefore current live provider snapshot is degraded, but this is now an explicit source-health state rather than fake IV confidence.
- ORATS remains candidate-only until agreement/subscription is documented.

## Verification

Commands run:

```bash
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 scripts/options_iv_provider_fetcher.py --symbols TSLA --providers polygon,tradier --timeout 2
python3 scripts/options_iv_surface_compiler.py
python3 scripts/source_health_monitor.py
python3 scripts/finance_llm_context_pack.py
python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json
python3 scripts/finance_decision_report_render.py
python3 scripts/finance_report_product_validator.py
python3 scripts/finance_decision_log_compiler.py
python3 scripts/finance_report_delivery_safety.py
python3 scripts/finance_report_reader_bundle.py
python3 scripts/finance_report_archive_compiler.py
python3 -m pytest -q /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_openclaw_embedded_audit.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_renderer_authority_committed_evidence.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_renderer_authority_post_apply_verify.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_mainline_cutover_status.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_mainline_cutover_review_check.py
```

Results:

- Focused P2 suite: `51 passed`.
- Full finance tests: `285 passed`.
- Parent targeted tests: `33 passed`.
- Compile/audit: pass.
- Product validator: pass, `error_count=0`.
- Delivery safety: pass, no blocking reasons.
- Reader bundle smoke: `R4734` with `SIV1`.
- Report-time archive: pass, exact replay available.

## Next Package

The next useful package is not more compiler work. It is vendor activation / credential decision:

1. If ThetaData is available locally, activate and test the local terminal adapter first.
2. If Polygon or Tradier credentials exist, configure source credentials and run canary provider fetch.
3. If no vendor exists, keep this degraded-but-explicit state and move to P4 direct deterministic cron execution.
