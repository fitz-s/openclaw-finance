from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from offhours_session_clock import build_state


def _state(iso: str) -> dict:
    return build_state(datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(timezone.utc))


def test_offhours_includes_weekend_holiday_halfday_not_just_weekday_non_rth() -> None:
    assert _state('2026-04-18T16:00:00Z')['session_class'] == 'weekend_aperture'
    holiday = _state('2026-11-26T16:00:00Z')
    assert holiday['session_class'] == 'holiday_aperture'
    assert holiday['holiday_name'] == 'Thanksgiving Day'
    halfday = _state('2026-11-27T19:00:00Z')
    assert halfday['session_class'] == 'halfday_postclose_aperture'
    assert halfday['early_close'] is True


def test_session_clock_uses_exchange_calendar_not_manual_weekday_clock() -> None:
    rth = _state('2026-04-20T15:00:00Z')
    assert rth['session_class'] == 'rth'
    assert rth['is_offhours'] is False
    assert rth['gap_hours'] == 0.0
    assert rth['next_rth_open_at'] == '2026-04-20T13:30:00Z'
    post = _state('2026-04-20T21:00:00Z')
    assert post['session_class'] == 'post_close_gap'
    pre = _state('2026-04-20T13:00:00Z')
    assert pre['session_class'] == 'pre_open_gap'
    overnight = _state('2026-04-21T04:00:00Z')
    assert overnight['session_class'] == 'overnight_session'


def test_weekend_aperture_receives_higher_discovery_and_answers_budget() -> None:
    weekend = _state('2026-04-18T16:00:00Z')
    post = _state('2026-04-20T21:00:00Z')
    assert weekend['is_long_gap'] is True
    assert weekend['discovery_multiplier'] > post['discovery_multiplier']
    assert weekend['answers_budget_class'] == 'high'


def test_postclose_gap_does_not_run_broad_macro_discovery() -> None:
    post = _state('2026-04-20T21:00:00Z')
    assert post['answers_budget_class'] == 'none'
    assert post['is_long_gap'] is False
