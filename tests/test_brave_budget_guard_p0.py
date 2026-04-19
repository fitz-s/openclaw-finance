from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from brave_budget_guard import decide, normalize_state


def _state(session_class: str = 'weekend_aperture') -> dict:
    return normalize_state({}, aperture_id='aperture:test', session_class=session_class, now=datetime(2026, 4, 18, tzinfo=timezone.utc))


def test_brave_budget_guard_separates_search_and_answers() -> None:
    state = _state()
    state, decision = decide(state, kind='search', units=3, dry_run=False)
    assert decision['allowed'] is True
    assert state['usage']['search_month'] == 3
    assert state['usage']['answers_month'] == 0


def test_brave_budget_guard_blocks_monthly_exhaustion() -> None:
    state = _state()
    state['usage']['search_month'] = 3000
    _state2, decision = decide(state, kind='search', units=1, dry_run=False)
    assert decision['allowed'] is False
    assert decision['reason'] == 'monthly_cap_exhausted'


def test_weekend_budget_is_higher_than_postclose() -> None:
    weekend = _state('weekend_aperture')
    post = _state('post_close_gap')
    assert weekend['daily_caps']['search'] > post['daily_caps']['search']
    assert weekend['aperture_caps']['answers'] > post['aperture_caps']['answers']


def test_dry_run_does_not_consume_budget() -> None:
    state = _state()
    state, decision = decide(state, kind='answers', units=2, dry_run=True)
    assert decision['allowed'] is True
    assert state['usage']['answers_month'] == 0
