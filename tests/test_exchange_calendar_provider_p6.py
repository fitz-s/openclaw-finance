from __future__ import annotations

from datetime import date, time
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from exchange_calendar_provider import calendar_confidence, early_close_name, holiday_name, is_trading_day, rth_close_time, supported_years


def test_provider_supports_2026_2028_without_runtime_lookup() -> None:
    assert supported_years() == [2026, 2027, 2028]
    assert calendar_confidence(date(2027, 1, 1)) == 'ok'
    assert calendar_confidence(date(2029, 1, 1)) == 'degraded'


def test_provider_marks_2027_holidays_and_early_closes() -> None:
    assert holiday_name(date(2027, 1, 1)) == 'New Years Day'
    assert holiday_name(date(2027, 12, 24)) == 'Christmas Day Observed'
    assert is_trading_day(date(2027, 1, 1)) is False
    assert early_close_name(date(2027, 11, 26)) == 'Day After Thanksgiving'
    assert rth_close_time(date(2027, 11, 26)) == time(13, 0)


def test_provider_preserves_2026_july_2_as_regular_close() -> None:
    assert early_close_name(date(2026, 7, 2)) is None
    assert is_trading_day(date(2026, 7, 2)) is True
    assert rth_close_time(date(2026, 7, 2)) == time(16, 0)


def test_provider_2028_new_year_saturday_has_no_monday_observed_close() -> None:
    assert holiday_name(date(2028, 1, 3)) is None
    assert is_trading_day(date(2028, 1, 3)) is True
