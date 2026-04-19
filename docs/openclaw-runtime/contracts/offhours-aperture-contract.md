# Offhours Aperture Contract

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

`SessionApertureState` is the deterministic clock surface for Calendar-Aware Offhours Intelligence Fabric.

It does not wake the user, mutate thresholds, deliver Discord messages, make judgments, or execute trades. It tells downstream jobs which intelligence aperture they are in.

## Shape

```json
{
  "generated_at": "...",
  "contract": "offhours-aperture-v1",
  "aperture_id": "aperture:XNYS:2026-04-18:weekend_aperture",
  "market": "XNYS",
  "session_class": "rth|post_close_gap|overnight_session|pre_open_gap|weekend_aperture|holiday_aperture|halfday_postclose_aperture",
  "global_liquidity_band": "us_dark|asia|europe|cross_session|shock",
  "is_offhours": true,
  "is_long_gap": true,
  "previous_rth_close_at": "...",
  "next_rth_open_at": "...",
  "gap_open_at": "...",
  "gap_hours": 0.0,
  "holiday_name": null,
  "early_close": false,
  "discovery_multiplier": 1.0,
  "answers_budget_class": "none|low|medium|high",
  "monday_open_risk": 0.0,
  "calendar_confidence": "ok|degraded",
  "no_execution": true
}
```

## Required Semantics

- `offhours` means any time outside XNYS regular cash session.
- Weekends, market holidays, and half-day post-close periods are offhours.
- Weekday offhours must be split into post-close, overnight, and pre-open apertures.
- Existing manual windows may be compatibility views only; they are not calendar authority.
- Long-gap apertures should receive larger discovery and Answers budget classes, but this contract itself does not execute source calls.

## Forbidden

- No wake mutation.
- No report delivery mutation.
- No threshold mutation.
- No execution or broker authority.
