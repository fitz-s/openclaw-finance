# SEC Fallback Activation P9 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P9 adds a zero-credential SEC current-filings fallback lane that can run when Brave source activation is deferred or explicitly forced. It is metadata-only and review-only.

## Implemented

- Added `scripts/sec_fallback_activation.py`.
- The runner checks `brave-source-recovery-policy.json` and runs only when the Brave breaker is open or `--force` is passed.
- It invokes `sec_discovery_fetcher.py` and `sec_filing_semantics.py`.
- It writes `state/sec-fallback-activation-report.json`.
- Parent market-ingest cutover now includes optional `sec_fallback_activation` after Brave activation.
- Snapshot export includes the fallback report and P9 docs.

## Explicitly Not Changed

- No SEC filing is promoted directly into wake/judgment authority.
- No Discord delivery mutation.
- No wake threshold mutation.
- No broker/execution authority.

## Verification

```bash
python3 -m pytest -q tests/test_sec_fallback_activation_p9.py tests/test_parent_cutover_sec_fallback_p9.py
python3 scripts/sec_fallback_activation.py --force --fixture-xml tests/fixtures/sec-current-sample.atom
python3 -m pytest -q tests/test_sec_fallback_snapshot_p9.py tests/test_snapshot_manifest_integrity.py
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

## Residual Risks

- Live SEC endpoints can return 403 from this environment; that is represented as degraded source availability.
- SEC current-filings Atom is broad and noisy; semantics remain conservative and support-only by default.
