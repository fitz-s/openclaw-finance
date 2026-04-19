#!/usr/bin/env python3
"""Deterministic offhours cadence governor.

Source review: /Users/leofitz/Downloads/review 2026-04-18.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from brave_budget_guard import DEFAULT_STATE as BUDGET_STATE, decide as budget_decide, normalize_state as normalize_budget_state
from offhours_session_clock import build_state, parse_now

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'offhours-cadence-governor-state.json'
CONTRACT = 'offhours-cadence-governor-v1'
REVIEW_SOURCE = '/Users/leofitz/Downloads/review 2026-04-18.md'
MIN_SPACING_MINUTES = {
    'pre_open_gap': 60,
    'post_close_gap': 120,
    'overnight_session': 180,
    'weekend_aperture': 240,
    'holiday_aperture': 240,
    'halfday_postclose_aperture': 180,
}


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def minutes_since(value: Any, now: datetime) -> float | None:
    parsed = parse_ts(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 60)


def build_governor_state(
    *,
    now: datetime | None = None,
    budget_state: dict[str, Any] | None = None,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now_dt = now or datetime.now(timezone.utc)
    aperture = build_state(now_dt)
    session_class = str(aperture.get('session_class') or 'unknown')
    budget = normalize_budget_state(
        budget_state or {},
        aperture_id=str(aperture.get('aperture_id') or 'unknown'),
        session_class=session_class,
        now=now_dt,
    )
    _budget, decision = budget_decide(budget, kind='search', units=1, dry_run=True)
    min_spacing = int(MIN_SPACING_MINUTES.get(session_class, 120))
    prior_run_minutes = minutes_since((previous_state or {}).get('last_allowed_run_at'), now_dt)
    should_run = True
    skip_reason = None
    if aperture.get('is_offhours') is not True:
        should_run = False
        skip_reason = 'rth_session'
    elif decision.get('allowed') is not True:
        should_run = False
        skip_reason = str(decision.get('reason') or 'budget_guard_denied')
    elif prior_run_minutes is not None and prior_run_minutes < min_spacing:
        should_run = False
        skip_reason = 'min_spacing_not_met'
    last_allowed = now_dt.isoformat().replace('+00:00', 'Z') if should_run else (previous_state or {}).get('last_allowed_run_at')
    return {
        'generated_at': now_dt.isoformat().replace('+00:00', 'Z'),
        'contract': CONTRACT,
        'review_source': REVIEW_SOURCE,
        'should_run': should_run,
        'skip_reason': skip_reason,
        'session_class': session_class,
        'session_aperture': aperture,
        'budget_decision': decision,
        'min_spacing_minutes': min_spacing,
        'minutes_since_last_allowed_run': prior_run_minutes,
        'last_allowed_run_at': last_allowed,
        'no_delivery_mutation': True,
        'no_wake_mutation': True,
        'no_threshold_mutation': True,
        'no_execution': True,
    }


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--now')
    parser.add_argument('--budget-state', default=str(BUDGET_STATE))
    parser.add_argument('--previous-state', default=str(OUT))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    budget = Path(args.budget_state)
    previous = Path(args.previous_state)
    if not safe_state_path(out) or not safe_state_path(budget) or not safe_state_path(previous):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    state = build_governor_state(
        now=parse_now(args.now),
        budget_state=load_json_safe(budget, {}) or {},
        previous_state=load_json_safe(previous, {}) or {},
    )
    atomic_write_json(out, state)
    print(json.dumps({'status': 'pass', 'should_run': state['should_run'], 'skip_reason': state['skip_reason'], 'session_class': state['session_class'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
