from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from offhours_session_clock import build_state


def _state(iso: str) -> dict:
    return build_state(datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(timezone.utc))


def test_2027_weekday_holiday_is_holiday_aperture() -> None:
    state = _state('2027-01-01T16:00:00Z')
    assert state['session_class'] == 'holiday_aperture'
    assert state['holiday_name'] == 'New Years Day'
    assert state['calendar_confidence'] == 'ok'
    assert state['next_rth_open_at'] == '2027-01-04T14:30:00Z'


def test_2027_halfday_postclose_is_classified_after_early_close() -> None:
    rth = _state('2027-11-26T17:00:00Z')
    assert rth['session_class'] == 'rth'
    assert rth['early_close'] is True
    post = _state('2027-11-26T19:00:00Z')
    assert post['session_class'] == 'halfday_postclose_aperture'
    assert post['early_close'] is True


def test_2028_jan_3_is_normal_rth() -> None:
    state = _state('2028-01-03T16:00:00Z')
    assert state['session_class'] == 'rth'
    assert state['calendar_confidence'] == 'ok'
