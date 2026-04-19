# Marketday Core Review P4 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P4 adds a fixed second marketday core review attempt to prevent a trading day from depending only on threshold wakes or a heavy premarket-equivalent report path.

## Implemented

- Added `marketday-core-review` mode to `scripts/finance_discord_report_job.py`.
- The mode uses `fast_core=True` and skips live parent ingest/source activation for timeliness.
- It still uses existing price/macro/options refresh, JudgmentEnvelope fallback, renderer, product validator, decision log, delivery safety, reader bundle, campaign cache, board package, archive, and cutover gate.
- Added `state/marketday-core-review-policy.json` runtime policy record for reviewer visibility.
- Added `tools/patch_marketday_core_review_p4.py`.
- Patched active `finance-midday-operator-review` cron:
  - schedule: `15 13 * * 1-5`
  - mode: `finance_discord_report_job.py --mode marketday-core-review`
  - delivery remains `announce` to the existing finance Discord channel.
- Refreshed parent runtime mirror and finance runtime snapshot.

## Explicitly Not Changed

- No Discord channel/thread topology changes.
- No delivery safety bypass.
- No wake threshold mutation.
- No broker/execution authority.
- Existing `marketday-review` full path remains available for premarket/threshold-style report jobs.

## Verification

```bash
python3 -m pytest -q tests/test_finance_discord_report_job_p4_core.py tests/test_patch_marketday_core_review_p4.py tests/test_marketday_core_review_snapshot_p4.py tests/test_finance_job_prompt_contract.py tests/test_finance_cron_p4_patch.py
# 10 passed

python3 scripts/finance_discord_report_job.py --mode marketday-core-review
# NO_REPLY on Sunday 2026-04-19, expected weekend behavior

python3 -m pytest -q tests
# 333 passed

python3 -m compileall -q scripts tools tests
# pass

python3 tools/audit_operating_model.py
# pass, error_count=0

python3 tools/audit_benchmark_boundary.py
# pass, blocking_reasons=[]

python3 tools/export_parent_runtime_mirror.py
# pass

python3 tools/export_openclaw_runtime_snapshot.py
# pass
```

## Residual Risks

- The fixed second report is a scheduled attempt. Actual Discord delivery still depends on parent OpenClaw delivery health.
- The fast path intentionally avoids live source acquisition; report quality depends on scanner/source state freshness plus price/macro/options refresh.
- Holiday awareness for report cron still uses weekday schedule; a future phase should align report cron with the exchange calendar governor.
