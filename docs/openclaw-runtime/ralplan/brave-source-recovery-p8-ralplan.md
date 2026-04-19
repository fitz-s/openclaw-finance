# RALPLAN P8: Brave Source Recovery Breaker

Status: approved_for_p8_implementation
Mode: consensus_planning
Scope: conservative Brave source recovery / quota breaker

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/brave-source-recovery-p8-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/brave-source-recovery-p8-external-scout.md`

## Task Statement

Stop repeatedly spending source budget on live Brave Web/News calls when recent records already show quota/rate-limit pressure. Add a deterministic recovery policy that defers live activation before budget checks and fetch attempts, while keeping dry-run and reviewer visibility intact.

## RALPLAN-DR

### Principles

1. Do not recover from quota pressure by making more quota-consuming calls.
2. Defer before budget reservation.
3. Keep query-registry exact-query cooldown and add global Brave-source breaker.
4. Surface explicit recovery/defer reasons for operators and reviewers.
5. No wake/delivery/threshold mutation.

### ADR

Decision: Add `brave_source_recovery_policy.py` and integrate it into `brave_source_activation.py`. When the breaker is open, selected packs are skipped as `source_recovery_deferred` without consuming budget or calling Brave.

Rejected: Try alternate Brave endpoint after rate-limit | likely same quota pressure and can worsen burn.
Rejected: Suppress only exact query via query registry | misses cross-query quota exhaustion.

## Test Plan

- recent rate-limited record opens breaker.
- non-rate-limited old records keep breaker closed.
- activation with breaker open skips before budget and fetch.
- dry-run activation is not blocked by breaker.
- snapshot exports recovery policy state.

## No-Go Items

- No live retry loop.
- No wake/delivery mutation.
- No broker/execution authority.
