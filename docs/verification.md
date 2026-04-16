# Verification

Local OpenClaw workspace verification used for this export:

```bash
python3 -m json.tool docs/openclaw-runtime/finance-cron-jobs.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/finance-model-roles.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/finance-job-prompt-contract.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/snapshot-manifest.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/operating-model-audit.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/parent-dependency-inventory.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/parent-dependency-drift.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/wake-threshold-attribution.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/report-usefulness-score.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/thesis-spine-telemetry-summary.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/ibkr-watchlist-freshness-drill.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/benchmark-boundary-audit.json >/dev/null
python3 -m json.tool docs/openclaw-runtime/runtime-gap-review.json >/dev/null
python3 -m compileall -q scripts tools
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

Package 9 local runtime verification:

```bash
python3 scripts/finance_llm_context_pack.py
python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json
python3 scripts/finance_decision_report_render.py
python3 scripts/finance_report_product_validator.py
python3 scripts/finance_decision_log_compiler.py
python3 scripts/finance_report_delivery_safety.py
pytest -q tests/test_llm_context_pack.py tests/test_finance_job_prompt_contract.py tests/test_prompt_snapshot_contract.py tests/test_judgment_context_pack_gate.py
```

Capital competition verification:

```bash
python3 scripts/capital_graph_compiler.py
python3 scripts/scenario_exposure_compiler.py
python3 scripts/displacement_case_builder.py
python3 scripts/capital_agenda_compiler.py
python3 scripts/finance_decision_report_render.py --report-mode capital_delta
pytest -q tests/test_capital_graph_compiler.py tests/test_displacement_case_builder.py tests/test_capital_agenda_compiler.py tests/test_capital_delta_report_render.py
```

Output surfaces verification:

```bash
python3 scripts/announce_card_compiler.py
python3 scripts/finance_report_reader_bundle.py
pytest -q tests/test_announce_card_compiler.py tests/test_report_reader_bundle.py tests/test_followup_answer_guard.py
pytest -q tests/test_discord_operator_surfaces.py
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
