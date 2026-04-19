# RALPLAN P9: SEC Fallback Activation Lane

Status: approved_for_p9_implementation
Mode: consensus_planning
Scope: zero-credential SEC filing fallback activation

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/sec-fallback-activation-p9-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/sec-fallback-activation-p9-external-scout.md`

## Task Statement

When Brave source activation is deferred or quota-limited, provide a bounded non-Brave fallback lane using SEC current filings. The lane must be metadata-only, review-only, and explicitly degraded when SEC fetch is blocked.

## RALPLAN-DR

### Principles

1. Fallback does not mean authority escalation.
2. SEC fetch failure must be explicit degradation, not stale reuse.
3. No credentials required.
4. No wake/delivery/threshold mutation.
5. Metadata-only by default.

### ADR

Decision: Add `sec_fallback_activation.py` that runs SEC discovery and filing semantics when Brave recovery breaker is open or when forced. It writes a report and optional compatibility observations but does not promote to wake/judgment authority.

Rejected: Make SEC fallback always authoritative | filings require semantic review and can be noisy.
Rejected: Hide SEC 403 as empty results | this masks source unavailability.

## Test Plan

- Forced fallback runs discovery/semantics using fixture and writes report.
- Brave breaker closed skips fallback unless `--force`.
- Brave breaker open runs fallback.
- SEC fetch degradation is explicit and no execution authority exists.
- Snapshot exports fallback report.

## No-Go Items

- No Discord delivery mutation.
- No wake threshold mutation.
- No broker/execution authority.
