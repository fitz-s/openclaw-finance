#!/usr/bin/env python3
"""NYSE/XNYS calendar provider for finance session classification.

Sources:
- https://www.nyse.com/markets/hours-calendars
- https://www.businesswire.com/news/home/20241108580933/en/NYSE-Group-Announces-2025-2026-and-2027-Holiday-and-Early-Closings-Calendar
- https://www.morningstar.com/news/business-wire/20251223981478/nyse-group-announces-2026-2027-and-2028-holiday-and-early-closings-calendar
"""
from __future__ import annotations

import argparse
import json
from datetime import date, time
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'exchange-calendar-provider-report.json'
CONTRACT = 'exchange-calendar-provider-v1'
RTH_CLOSE = time(16, 0)
HALFDAY_CLOSE = time(13, 0)

HOLIDAYS_BY_YEAR: dict[int, dict[date, str]] = {
    2026: {
        date(2026, 1, 1): 'New Years Day',
        date(2026, 1, 19): 'Martin Luther King Jr. Day',
        date(2026, 2, 16): 'Washingtons Birthday',
        date(2026, 4, 3): 'Good Friday',
        date(2026, 5, 25): 'Memorial Day',
        date(2026, 6, 19): 'Juneteenth National Independence Day',
        date(2026, 7, 3): 'Independence Day Observed',
        date(2026, 9, 7): 'Labor Day',
        date(2026, 11, 26): 'Thanksgiving Day',
        date(2026, 12, 25): 'Christmas Day',
    },
    2027: {
        date(2027, 1, 1): 'New Years Day',
        date(2027, 1, 18): 'Martin Luther King Jr. Day',
        date(2027, 2, 15): 'Washingtons Birthday',
        date(2027, 3, 26): 'Good Friday',
        date(2027, 5, 31): 'Memorial Day',
        date(2027, 6, 18): 'Juneteenth National Independence Day Observed',
        date(2027, 7, 5): 'Independence Day Observed',
        date(2027, 9, 6): 'Labor Day',
        date(2027, 11, 25): 'Thanksgiving Day',
        date(2027, 12, 24): 'Christmas Day Observed',
    },
    2028: {
        date(2028, 1, 17): 'Martin Luther King Jr. Day',
        date(2028, 2, 21): 'Washingtons Birthday',
        date(2028, 4, 14): 'Good Friday',
        date(2028, 5, 29): 'Memorial Day',
        date(2028, 6, 19): 'Juneteenth National Independence Day',
        date(2028, 7, 4): 'Independence Day',
        date(2028, 9, 4): 'Labor Day',
        date(2028, 11, 23): 'Thanksgiving Day',
        date(2028, 12, 25): 'Christmas Day',
    },
}

EARLY_CLOSES_BY_YEAR: dict[int, dict[date, str]] = {
    2026: {
        date(2026, 11, 27): 'Day After Thanksgiving',
        date(2026, 12, 24): 'Christmas Eve',
    },
    2027: {
        date(2027, 11, 26): 'Day After Thanksgiving',
    },
    2028: {
        date(2028, 7, 3): 'Day Before Independence Day',
        date(2028, 11, 24): 'Day After Thanksgiving',
    },
}

SOURCE_URLS = [
    'https://www.nyse.com/markets/hours-calendars',
    'https://www.businesswire.com/news/home/20241108580933/en/NYSE-Group-Announces-2025-2026-and-2027-Holiday-and-Early-Closings-Calendar',
    'https://www.morningstar.com/news/business-wire/20251223981478/nyse-group-announces-2026-2027-and-2028-holiday-and-early-closings-calendar',
]


def supported_years() -> list[int]:
    return sorted(set(HOLIDAYS_BY_YEAR) | set(EARLY_CLOSES_BY_YEAR))


def calendar_confidence(day: date) -> str:
    return 'ok' if day.year in supported_years() else 'degraded'


def holiday_name(day: date) -> str | None:
    return HOLIDAYS_BY_YEAR.get(day.year, {}).get(day)


def early_close_name(day: date) -> str | None:
    return EARLY_CLOSES_BY_YEAR.get(day.year, {}).get(day)


def rth_close_time(day: date) -> time:
    return HALFDAY_CLOSE if early_close_name(day) else RTH_CLOSE


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def is_trading_day(day: date) -> bool:
    return not is_weekend(day) and holiday_name(day) is None


def report() -> dict[str, Any]:
    return {
        'contract': CONTRACT,
        'supported_years': supported_years(),
        'source_urls': SOURCE_URLS,
        'holiday_counts': {str(year): len(days) for year, days in HOLIDAYS_BY_YEAR.items()},
        'early_close_counts': {str(year): len(days) for year, days in EARLY_CLOSES_BY_YEAR.items()},
        'holidays': {
            str(year): {day.isoformat(): name for day, name in sorted(days.items())}
            for year, days in HOLIDAYS_BY_YEAR.items()
        },
        'early_closes': {
            str(year): {day.isoformat(): name for day, name in sorted(days.items())}
            for year, days in EARLY_CLOSES_BY_YEAR.items()
        },
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    atomic_write_json(Path(args.out), report())
    print(json.dumps({'status': 'pass', 'out': str(args.out), 'supported_years': supported_years()}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
