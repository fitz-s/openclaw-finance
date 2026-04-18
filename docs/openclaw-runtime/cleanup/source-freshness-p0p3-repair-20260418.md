# Source Freshness P0/P3 Repair - 2026-04-18

## What Changed

This package fixes the first two blockers from `source-freshness-deep-check-20260418.md`.

### P0 - Fresh unknown-web confirmed headlines are no longer invisible

Parent runtime files changed:

- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/source_promotion.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/semantic_normalizer.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/adapters/live_finance_adapter.py`

Behavior now:

- Confirmed-event headline metadata from unknown/restricted web remains `allowed_for_wake=false`.
- If it has a raw ref and timestamps, and is not clickbait/speculative/low-quality, it can become `allowed_for_judgment_support=true`.
- Such records carry `support_requires_primary_confirmation=true` and `support_scope=confirmed_headline_metadata_only`.
- `targeted` and `closes` now count as confirmed-event language, covering the Hormuz headline class that was previously missed.

Observed result after rerunning live adapter:

- Parent live evidence count: `46`.
- `allowed_for_judgment_support=True`: `44` records, up from `38` before the repair.
- `allowed_for_wake=True`: `0` records, unchanged by design.
- `support_requires_primary_confirmation=True`: `6` records.
- NDTV / Times of India / Il Sole 24 ORE Hormuz headlines are now support-only context instead of fully non-supporting context.

This prevents fresh confirmed headlines from being swallowed while preserving the rule that unknown web cannot wake the operator or act as primary authority without confirmation.

### P3 - Gate now exposes parent live evidence freshness

Finance runtime file changed:

- `scripts/gate_evaluator.py`

Behavior now:

- `report-gate-state.json` includes `legacyDataStale`, `legacyScanAgeMinutes`, and `liveEvidenceFreshness`.
- `liveEvidenceFreshness` reports record count, latest event time, latest ingest time, support counts, wake-allowed counts, context-only counts, primary-confirmation counts, and warnings.
- Legacy scanner stale can be cleared only by fresh parent live evidence that is judgment-supporting.
- Fresh context-only evidence without judgment support is disclosed but does not clear stale.

Observed result after rerunning gate:

- `dataStale=false`
- `legacyDataStale=false`
- `liveEvidenceFreshness.record_count=46`
- `liveEvidenceFreshness.support_count=44`
- `liveEvidenceFreshness.wake_allowed_count=0`
- `liveEvidenceFreshness.support_requires_primary_confirmation_count=6`
- `liveEvidenceFreshness.warnings` includes `no_wake_eligible_live_evidence` and `fresh_support_requires_primary_confirmation`.

Current status is still `stale` for the latest event because the latest Hormuz event was already older than the 120-minute freshness window when checked. That is expected and now visible.

## What This Does Not Fix

- Brave is still dry-run / quota-limited and remains a separate P1 activation package.
- Options IV is still proxy-only/stale and remains a separate P2 vendor/surface package.
- Cron still wraps deterministic shell work in LLM agent turns; that remains P4.
- Discord gateway DNS/socket instability remains a parent runtime/network issue.

## Verification

Commands run:

```bash
python3 -m pytest -q tests
python3 -m pytest -q /Users/leofitz/.openclaw/workspace/ops/tests/test_source_promotion_support_only.py /Users/leofitz/.openclaw/workspace/ops/tests/test_gate_evaluator_dispatch.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_semantic_normalizer.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_openclaw_embedded_audit.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_renderer_authority_committed_evidence.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_renderer_authority_post_apply_verify.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_mainline_cutover_status.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_mainline_cutover_review_check.py
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 scripts/source_health_monitor.py
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

- Finance tests: `266 passed`.
- Parent targeted tests: `50 passed`.
- Parent source/gate targeted tests: `17 passed`.
- Product validator: `pass`, `error_count=0`.
- Delivery safety: `pass`, no blocking reasons.
- Reader bundle: latest smoke produced `R7EC6`.
- Parent finance BOOT/cutover scripts: pass.

## Next Package

Proceed to P1: activate Brave live source paths with quota-aware fallback and explicit source-health operator warnings.
