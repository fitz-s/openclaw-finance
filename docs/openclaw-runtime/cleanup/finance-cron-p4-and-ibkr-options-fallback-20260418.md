# Finance Cron P4 + IBKR Options Fallback - 2026-04-18

## Scope

This package continues after P2 options-IV surface repair and vendor decision handoff.

It does two bounded things:

1. Tightens active finance cron jobs around deterministic stdout wrappers to reduce agent-token timeout and progress-text risk.
2. Adds an optional IBKR TWS/Gateway read-only options-IV adapter as one provider lane / fallback, without claiming brokerage session authority by default.

## P4 Cron Wrapper Changes

New:

- `scripts/finance_scanner_job.py`
- `tools/patch_finance_cron_p4.py`
- `tests/test_finance_scanner_job_p4.py`
- `tests/test_finance_cron_p4_patch.py`

Active OpenClaw cron patched:

- `finance-subagent-scanner`
- `finance-subagent-scanner-offhours`
- `finance-premarket-brief`
- `finance-midday-operator-review`
- `finance-premarket-delivery-watchdog`

Scanner jobs now call only:

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_scanner_job.py --mode market-hours-scan
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_scanner_job.py --mode offhours-scan
```

Report jobs still call:

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_discord_report_job.py --mode marketday-review
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_discord_report_job.py --mode morning-watchdog
```

But now they use `lightContext=true` and lower timeouts:

- scanner: `timeoutSeconds=300`
- report jobs: `timeoutSeconds=420`

This does not create a true shell-command cron type because current OpenClaw CLI still exposes these jobs as `agentTurn`. It does reduce the prompt surface to one deterministic command and one machine stdout line.

## IBKR Options IV Adapter

New:

- `scripts/ibkr_options_iv_adapter.py`
- `tests/test_ibkr_options_iv_adapter.py`

Changed:

- `scripts/options_iv_provider_fetcher.py`
- `scripts/source_health_monitor.py`
- `scripts/source_scout.py`
- related tests

IBKR behavior:

- Provider id: `ibkr`
- Source health id: `source:ibkr_options_iv`
- Endpoint label: `ibkr/tws/reqMktData/model_option_computation`
- Activation mode: `broker_session_local_gateway`
- Default state: disabled unless `IBKR_OPTIONS_IV_ENABLED=1`
- Scope: known/held option contracts only, normally from portfolio state
- No watchlist-wide option chain discovery in this package
- No order API use
- No brokerage session claim
- No execution authority

If disabled or unavailable, it writes a normal source fetch record:

```json
{
  "status": "failed",
  "error_class": "broker_session_unavailable",
  "application_error_code": "ibkr_options_iv_disabled",
  "source_id": "source:ibkr_options_iv"
}
```

Source health then reports:

```json
"source:ibkr_options_iv": "broker_session_unavailable"
```

If later enabled with a read-only TWS/Gateway session and `ibapi` installed, the adapter can request model option computation ticks for explicit known option contracts and normalize:

- model implied volatility
- delta
- gamma
- vega
- theta
- underlying price

## Runtime Evidence

Focused scanner wrapper smoke:

```text
scanner=ok mode=offhours-scan gate=hold send=false
```

Final smoke summary:

```json
{
  "options_iv_provider_snapshot": {
    "status": "degraded",
    "observation_count": 0,
    "fetch_record_status_counts": {"failed": 3}
  },
  "source_health": {
    "source:ibkr_options_iv": "broker_session_unavailable",
    "source:polygon_options_iv": "missing_credentials",
    "source:tradier_options_iv": "missing_credentials"
  },
  "scanner_job": {
    "status": "pass",
    "gate": "hold"
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

## Verification

Commands run:

```bash
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 scripts/options_iv_provider_fetcher.py --symbols TSLA --providers polygon,tradier,ibkr --timeout 2
python3 scripts/options_iv_surface_compiler.py
python3 scripts/source_health_monitor.py
python3 scripts/finance_scanner_job.py --mode offhours-scan
python3 scripts/finance_llm_context_pack.py
python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json
python3 scripts/finance_decision_report_render.py
python3 scripts/finance_report_product_validator.py
python3 scripts/finance_decision_log_compiler.py
python3 scripts/finance_report_delivery_safety.py
python3 scripts/finance_report_reader_bundle.py
```

Results:

- Full finance tests: `295 passed`.
- Scanner wrapper focused tests: pass.
- Cron patch focused tests: pass.
- Product validator: pass, `error_count=0`.
- Delivery safety: pass.
- Reader bundle smoke: `R12F8`.

## Remaining Work

- True direct shell cron type remains unavailable through current OpenClaw CLI; finance still uses `agentTurn` but now with tiny deterministic command prompts.
- IBKR adapter is disabled by default. To activate later, install/verify `ibapi`, start a read-only TWS/Gateway session, set `IBKR_OPTIONS_IV_ENABLED=1`, and run a canary on explicit held option contracts.
- Vendor credentials for Polygon/Tradier remain absent; source health correctly reports missing credentials.
