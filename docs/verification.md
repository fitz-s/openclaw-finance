# Verification

Local OpenClaw workspace verification used for this export:

```bash
python3 -m json.tool docs/openclaw-runtime/finance-cron-jobs.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/finance-model-roles.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/snapshot-manifest.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/operating-model-audit.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/parent-dependency-inventory.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/parent-dependency-drift.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/wake-threshold-attribution.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/report-usefulness-score.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/ibkr-watchlist-freshness-drill.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/benchmark-boundary-audit.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/runtime-gap-review.json >/dev/null
python3 -m compileall -q scripts tools
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

Runtime integration verification from the parent OpenClaw workspace:

```bash
pytest -q \
  workspace/ops/tests/test_ibkr_watchlist_fetcher.py \
  workspace/ops/tests/test_watchlist_resolver.py \
  workspace/ops/tests/test_portfolio_failure_invalidation.py \
  workspace/ops/tests/test_price_fetcher_semantics.py \
  workspace/ops/tests/test_options_flow_proxy_fetcher.py \
  workspace/ops/tests/test_finance_decision_report_product.py \
  workspace/ops/tests/test_finance_unknown_discovery_audit.py \
  workspace/ops/tests/test_finance_wake_rate_report_audit.py \
  workspace/ops/tests/test_finance_native_scanner_shadow.py
```

Runtime audit verification:

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_report_delivery_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_ideal_architecture_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_runtime_blocker_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_native_runtime_status.py
```

The GitHub workflow can validate repository-local JSON snapshots and Python syntax. Full runtime tests require the parent OpenClaw workspace and local runtime state.
