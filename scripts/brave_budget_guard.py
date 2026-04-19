#!/usr/bin/env python3
"""Brave Search/Answers budget guard for offhours source routing.

Source review: /Users/leofitz/Downloads/review 2026-04-18.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
DEFAULT_STATE = STATE / 'brave-budget-state.json'
CONTRACT = 'brave-budget-guard-v1'
MONTHLY_CAPS = {'search': 3000, 'answers': 300, 'llm_context': 500}
DEFAULT_DAILY_CAPS = {'search': 100, 'answers': 10, 'llm_context': 20}
LONG_GAP_DAILY_CAPS = {'search': 150, 'answers': 15, 'llm_context': 30}
APERTURE_CAPS = {
    'post_close_gap': {'search': 2, 'answers': 0, 'llm_context': 2},
    'overnight_session': {'search': 3, 'answers': 1, 'llm_context': 2},
    'pre_open_gap': {'search': 1, 'answers': 0, 'llm_context': 2},
    'weekend_aperture': {'search': 6, 'answers': 3, 'llm_context': 4},
    'holiday_aperture': {'search': 6, 'answers': 3, 'llm_context': 4},
    'halfday_postclose_aperture': {'search': 4, 'answers': 2, 'llm_context': 3},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def keys(dt: datetime) -> tuple[str, str]:
    return dt.strftime('%Y-%m'), dt.strftime('%Y-%m-%d')


def zero_usage() -> dict:
    return {f'{kind}_{scope}': 0 for kind in MONTHLY_CAPS for scope in ['month', 'day', 'aperture']}


def normalize_state(state: dict, *, aperture_id: str, session_class: str, now: datetime) -> dict:
    month_key, day_key = keys(now)
    if state.get('month_key') != month_key:
        state['month_key'] = month_key
        for kind in MONTHLY_CAPS:
            state.setdefault('usage', {})[f'{kind}_month'] = 0
    if state.get('day_key') != day_key:
        state['day_key'] = day_key
        for kind in MONTHLY_CAPS:
            state.setdefault('usage', {})[f'{kind}_day'] = 0
    if state.get('aperture_id') != aperture_id:
        state['aperture_id'] = aperture_id
        for kind in MONTHLY_CAPS:
            state.setdefault('usage', {})[f'{kind}_aperture'] = 0
    state.setdefault('usage', zero_usage())
    state['contract'] = CONTRACT
    state['generated_at'] = now.isoformat().replace('+00:00', 'Z')
    state['monthly_caps'] = MONTHLY_CAPS
    state['daily_caps'] = LONG_GAP_DAILY_CAPS if session_class in {'weekend_aperture', 'holiday_aperture', 'halfday_postclose_aperture'} else DEFAULT_DAILY_CAPS
    state['aperture_caps'] = APERTURE_CAPS.get(session_class, {'search': 0, 'answers': 0, 'llm_context': 0})
    state['session_class'] = session_class
    state['review_source'] = '/Users/leofitz/Downloads/review 2026-04-18.md'
    state['no_execution'] = True
    return state


def decide(state: dict, *, kind: str, units: int, dry_run: bool) -> tuple[dict, dict]:
    usage = state['usage']
    monthly = state['monthly_caps'].get(kind, 0)
    daily = state['daily_caps'].get(kind, 0)
    aperture = state['aperture_caps'].get(kind, 0)
    used_month = int(usage.get(f'{kind}_month') or 0)
    used_day = int(usage.get(f'{kind}_day') or 0)
    used_aperture = int(usage.get(f'{kind}_aperture') or 0)
    reason = 'within_budget'
    allowed = True
    if used_month + units > monthly:
        allowed, reason = False, 'monthly_cap_exhausted'
    elif used_day + units > daily:
        allowed, reason = False, 'daily_cap_exhausted'
    elif used_aperture + units > aperture:
        allowed, reason = False, 'aperture_cap_exhausted'
    decision = {
        'allowed': allowed,
        'kind': kind,
        'units': units,
        'reason': reason,
        'remaining': {
            'month': max(0, monthly - used_month - (units if allowed else 0)),
            'day': max(0, daily - used_day - (units if allowed else 0)),
            'aperture': max(0, aperture - used_aperture - (units if allowed else 0)),
        },
        'dry_run': dry_run,
        'no_execution': True,
    }
    if allowed and not dry_run:
        usage[f'{kind}_month'] = used_month + units
        usage[f'{kind}_day'] = used_day + units
        usage[f'{kind}_aperture'] = used_aperture + units
    state['last_decision'] = decision
    return state, decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=['search', 'answers', 'llm_context'], required=True)
    parser.add_argument('--units', type=int, default=1)
    parser.add_argument('--aperture-id', default='manual')
    parser.add_argument('--session-class', default='overnight_session')
    parser.add_argument('--state', default=str(DEFAULT_STATE))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    path = Path(args.state)
    state = normalize_state(load_json_safe(path, {}) or {}, aperture_id=args.aperture_id, session_class=args.session_class, now=now_utc())
    state, decision = decide(state, kind=args.kind, units=max(0, args.units), dry_run=args.dry_run)
    atomic_write_json(path, state)
    print(json.dumps({'status': 'pass', 'decision': decision, 'out': str(path)}, ensure_ascii=False))
    return 0 if decision['allowed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
