# Brave Budget Guard Contract

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

`BraveBudgetGuard` tracks Search/Web/News/LLM Context and Answers usage before offhours source routing expands. It is a budget and observability surface, not source evidence.

## State Shape

```json
{
  "generated_at": "...",
  "contract": "brave-budget-guard-v1",
  "month_key": "2026-04",
  "day_key": "2026-04-18",
  "monthly_caps": {"search": 3000, "answers": 300},
  "daily_caps": {"search": 100, "answers": 10},
  "aperture_caps": {"search": 6, "answers": 3},
  "usage": {
    "search_month": 0,
    "answers_month": 0,
    "search_day": 0,
    "answers_day": 0,
    "search_aperture": 0,
    "answers_aperture": 0
  },
  "last_decision": {},
  "no_execution": true
}
```

## Decision Shape

```json
{
  "allowed": true,
  "kind": "search|answers|llm_context",
  "units": 1,
  "reason": "within_budget|monthly_cap_exhausted|daily_cap_exhausted|aperture_cap_exhausted",
  "remaining": {"month": 1, "day": 1, "aperture": 1},
  "dry_run": true,
  "no_execution": true
}
```

## Required Semantics

- Search and Answers budgets are separate.
- Answers is sidecar-only and never evidence authority.
- Budget exhaustion must be explicit and must not silently fall back to stale narratives.
- P0 does not call Brave. It only checks/reserves budget state.

## Default P0 Caps

- Search monthly cap: 3000
- Answers monthly cap: 300
- Search daily cap: 100
- Weekend/holiday search daily cap: 150
- Answers daily cap: 10

## Forbidden

- No credentials.
- No Brave API calls.
- No wake/report/threshold mutation.
