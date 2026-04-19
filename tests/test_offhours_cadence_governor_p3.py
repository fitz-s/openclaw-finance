from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from brave_budget_guard import normalize_state
from offhours_cadence_governor import build_governor_state


def test_governor_skips_rth() -> None:
    state = build_governor_state(now=datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc), budget_state={})
    assert state['should_run'] is False
    assert state['skip_reason'] == 'rth_session'


def test_governor_allows_weekend_under_budget() -> None:
    now = datetime(2026, 4, 18, 16, 0, tzinfo=timezone.utc)
    budget = normalize_state({}, aperture_id='aperture:XNYS:2026-04-17:weekend_aperture', session_class='weekend_aperture', now=now)
    state = build_governor_state(now=now, budget_state=budget, previous_state={})
    assert state['should_run'] is True
    assert state['session_class'] == 'weekend_aperture'


def test_governor_blocks_budget_exhausted() -> None:
    now = datetime(2026, 4, 18, 16, 0, tzinfo=timezone.utc)
    budget = normalize_state({}, aperture_id='aperture:XNYS:2026-04-17:weekend_aperture', session_class='weekend_aperture', now=now)
    budget['usage']['search_aperture'] = 6
    state = build_governor_state(now=now, budget_state=budget, previous_state={})
    assert state['should_run'] is False
    assert state['skip_reason'] == 'aperture_cap_exhausted'


def test_governor_uses_session_class_min_spacing() -> None:
    now = datetime(2026, 4, 18, 16, 0, tzinfo=timezone.utc)
    budget = normalize_state({}, aperture_id='aperture:XNYS:2026-04-17:weekend_aperture', session_class='weekend_aperture', now=now)
    previous = {'last_allowed_run_at': '2026-04-18T15:00:00Z'}
    state = build_governor_state(now=now, budget_state=budget, previous_state=previous)
    assert state['should_run'] is False
    assert state['skip_reason'] == 'min_spacing_not_met'
