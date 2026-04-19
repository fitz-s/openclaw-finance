# RALPLAN Source-to-Campaign Phase 03: Options And IV Sensitivity

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Make options volatility / IV a first-class deterministic surface over existing proxy data, so the system can see when it is relying on stale or weak options-chain evidence.

This phase does not add a new vendor and does not fetch network data. It compiles and scores the existing `options-flow-proxy.json` into a structured `options-iv-surface.json` with explicit confidence penalties.

## Principles

1. Do not treat proxy options chain data as primary options truth.
2. IV availability, staleness, skew, OI, and volume/OI must be explicit.
3. Missing IV metrics should become confidence penalties, not silent ambiguity.
4. Non-watchlist IV anomalies need later cross-lane confirmation before campaign promotion.
5. Review-only; no execution language or threshold mutation.

## Decision Drivers

1. The user observed the current system is insensitive to options volatility and IV.
2. `options_flow_proxy_fetcher.py` is explicitly conservative/proxy-only.
3. Later undercurrent/campaign/follow-up phases need an IV surface artifact before using IV evidence.

## Selected Plan

Add `scripts/options_iv_surface_compiler.py` that reads `state/options-flow-proxy.json` and writes `state/options-iv-surface.json`.

The compiler will expose:
- chain snapshot age and stale flag
- provider confidence
- proxy-only reason
- IV observation count
- average/max IV where present
- call/put skew when possible
- volume/OI max and unusual contract count
- stale/missing-IV confidence penalties
- no-execution boundary

## Rejected Options

Rejected: Integrate ORATS/ThetaData now | requires rights/cost/API review and later RALPLAN.
Rejected: Treat Nasdaq/yfinance proxy as primary IV surface | current source cannot guarantee IV completeness or point-in-time replay.
Rejected: Wait for full source activation | a deterministic proxy surface still improves visibility and reviewer evidence immediately.

## Acceptance Criteria

- Compiler outputs symbol-level IV/flow summaries with staleness and confidence.
- Missing IV data creates explicit penalties.
- Stale chain creates explicit penalties.
- Output is review-only and never eligible for execution.
- Tests cover fresh, stale, and missing-IV cases.

## Test Plan

- `test_options_iv_surface_marks_missing_iv_as_proxy_penalty`
- `test_options_iv_surface_marks_stale_chain_as_confidence_penalty`
- `test_options_iv_surface_computes_volume_oi_and_skew_when_available`

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-03-implementation-critic.md` after implementation.
