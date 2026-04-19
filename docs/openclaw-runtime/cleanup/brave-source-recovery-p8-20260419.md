# Brave Source Recovery P8 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P8 adds a conservative Brave source recovery breaker. When recent Brave Web/News records show quota or rate-limit pressure, live source activation is deferred before budget reservation and before outbound Brave calls.

## Implemented

- Added `scripts/brave_source_recovery_policy.py`.
- Integrated recovery policy into `scripts/brave_source_activation.py`.
- Breaker-open live activations produce `source_recovery_deferred` pack results.
- Deferred packs do not consume `BraveBudgetGuard` search budget.
- Dry-run activation is not blocked by the breaker.
- Snapshot export includes `brave-source-recovery-policy.json`.

## Explicitly Not Changed

- No live retry loop.
- No alternate Brave endpoint bypass after quota pressure.
- No wake/delivery/threshold mutation.
- No broker/execution authority.

## Verification

```bash
python3 -m pytest -q tests/test_brave_source_recovery_policy_p8.py tests/test_brave_source_activation_recovery_p8.py
# 5 passed

python3 scripts/brave_source_recovery_policy.py
# pass

python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 tools/export_openclaw_runtime_snapshot.py
```

## Residual Risks

- This phase preserves source capacity and prevents burn; it does not itself add non-Brave fallback sources.
- Breaker behavior depends on recent fetch records being retained.
