#!/usr/bin/env python3
"""Compile offhours source-router state from session aperture and budget guard.

Source review: /Users/leofitz/Downloads/review 2026-04-18.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from brave_budget_guard import DEFAULT_STATE as BUDGET_STATE, decide, normalize_state
from offhours_session_clock import OUT as APERTURE_STATE, build_state, parse_now


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'offhours-source-router-state.json'
CONTRACT = 'offhours-source-router-v1'
REVIEW_SOURCE = '/Users/leofitz/Downloads/review 2026-04-18.md'

MAX_PACKS_BY_SESSION = {
    'post_close_gap': 2,
    'overnight_session': 3,
    'pre_open_gap': 1,
    'weekend_aperture': 6,
    'holiday_aperture': 6,
    'halfday_postclose_aperture': 4,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def max_packs_for(aperture: dict[str, Any], budget_state: dict[str, Any]) -> int:
    session_class = str(aperture.get('session_class') or '')
    cap = int((budget_state.get('aperture_caps') or {}).get('search') or 0)
    desired = MAX_PACKS_BY_SESSION.get(session_class, 0)
    return max(0, min(cap, desired))


def build_router_state(
    *,
    now: datetime | None = None,
    search_units: int = 1,
    budget_path: Path = BUDGET_STATE,
    dry_run: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    aperture = build_state(now)
    budget = normalize_state(
        load_json_safe(budget_path, {}) or {},
        aperture_id=str(aperture.get('aperture_id') or 'unknown'),
        session_class=str(aperture.get('session_class') or 'unknown'),
        now=parse_now(aperture.get('generated_at')),
    )
    budget, decision = decide(budget, kind='search', units=max(0, search_units), dry_run=dry_run)
    router = {
        'generated_at': now_iso(),
        'contract': CONTRACT,
        'review_source': REVIEW_SOURCE,
        'activation_mode': 'budgeted_offhours_search_news',
        'scanner_mode': 'offhours-scan',
        'session_aperture': aperture,
        'budget_decision': decision,
        'budget_state_path': str(budget_path),
        'max_source_packs': max_packs_for(aperture, budget),
        'should_consider_source_activation': bool(aperture.get('is_offhours')) and bool(decision.get('allowed')),
        'budget_guard_required': True,
        'answers_sidecar_only': True,
        'router_is_not_authority': True,
        'no_wake_mutation': True,
        'no_delivery_mutation': True,
        'no_threshold_mutation': True,
        'no_execution': True,
    }
    return router, budget


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
    parser.add_argument('--now', default=None)
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--aperture-out', default=str(APERTURE_STATE))
    parser.add_argument('--budget-state', default=str(BUDGET_STATE))
    parser.add_argument('--search-units', type=int, default=1)
    args = parser.parse_args(argv)
    out = Path(args.out)
    aperture_out = Path(args.aperture_out)
    budget_path = Path(args.budget_state)
    if not safe_state_path(out) or not safe_state_path(aperture_out) or not safe_state_path(budget_path):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    router, budget = build_router_state(now=parse_now(args.now), search_units=args.search_units, budget_path=budget_path, dry_run=True)
    atomic_write_json(aperture_out, router['session_aperture'])
    atomic_write_json(budget_path, budget)
    atomic_write_json(out, router)
    print(json.dumps({
        'status': 'pass',
        'session_class': router['session_aperture'].get('session_class'),
        'budget_allowed': router['budget_decision'].get('allowed'),
        'max_source_packs': router['max_source_packs'],
        'out': str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
