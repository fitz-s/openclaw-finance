#!/usr/bin/env python3
"""Compile Calendar-Aware Offhours session aperture state.

Source review: /Users/leofitz/Downloads/review 2026-04-18.md
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json
from exchange_calendar_provider import (
    calendar_confidence,
    early_close_name,
    holiday_name,
    is_trading_day,
    is_weekend,
    rth_close_time as provider_rth_close_time,
)


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'session-aperture-state.json'
CONTRACT = 'offhours-aperture-v1'
ET = ZoneInfo('America/New_York')

RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
HALFDAY_CLOSE = time(13, 0)

def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rth_close_time(day: date) -> time:
    return provider_rth_close_time(day)


def rth_open_dt(day: date) -> datetime:
    return datetime.combine(day, RTH_OPEN, tzinfo=ET)


def rth_close_dt(day: date) -> datetime:
    return datetime.combine(day, rth_close_time(day), tzinfo=ET)


def previous_trading_day(day: date) -> date:
    cur = day - timedelta(days=1)
    for _ in range(14):
        if is_trading_day(cur):
            return cur
        cur -= timedelta(days=1)
    return cur


def next_trading_day(day: date) -> date:
    cur = day + timedelta(days=1)
    for _ in range(14):
        if is_trading_day(cur):
            return cur
        cur += timedelta(days=1)
    return cur


def global_liquidity_band(now_et: datetime) -> str:
    h = now_et.hour + now_et.minute / 60
    if 20 <= h or h < 2:
        return 'asia'
    if 2 <= h < 8:
        return 'europe'
    if 8 <= h < 9.5 or 16 <= h < 20:
        return 'cross_session'
    return 'us_dark'


def class_budget(session_class: str) -> tuple[float, str, float]:
    if session_class in {'weekend_aperture', 'holiday_aperture'}:
        return 1.8, 'high', 0.8
    if session_class == 'halfday_postclose_aperture':
        return 1.5, 'medium', 0.55
    if session_class == 'overnight_session':
        return 1.2, 'low', 0.3
    if session_class in {'post_close_gap', 'pre_open_gap'}:
        return 1.0, 'none', 0.2
    return 0.5, 'none', 0.0


def session_class_for(now_et: datetime) -> tuple[str, datetime, datetime, datetime, str | None, bool]:
    day = now_et.date()
    if is_trading_day(day):
        open_dt = rth_open_dt(day)
        close_dt = rth_close_dt(day)
        if open_dt <= now_et < close_dt:
            prev_close = rth_close_dt(previous_trading_day(day))
            return 'rth', prev_close, open_dt, open_dt, None, early_close_name(day) is not None
        if now_et >= close_dt:
            nxt = next_trading_day(day)
            is_early = early_close_name(day) is not None
            session = 'halfday_postclose_aperture' if is_early else 'post_close_gap' if (now_et - close_dt) <= timedelta(hours=2) else 'overnight_session'
            return session, close_dt, rth_open_dt(nxt), close_dt, None, is_early
        # before open
        prev = previous_trading_day(day)
        session = 'pre_open_gap' if (open_dt - now_et) <= timedelta(hours=3) else 'overnight_session'
        prev_close = rth_close_dt(prev)
        return session, prev_close, open_dt, prev_close, None, False
    prev = previous_trading_day(day)
    nxt = next_trading_day(day)
    holiday = holiday_name(day)
    session = 'weekend_aperture' if is_weekend(day) else 'holiday_aperture'
    prev_close = rth_close_dt(prev)
    return session, prev_close, rth_open_dt(nxt), prev_close, holiday, False


def build_state(now: datetime | None = None) -> dict:
    now_utc = now or datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)
    session, prev_close, next_open, gap_open, holiday, early = session_class_for(now_et)
    gap_hours = 0.0 if session == 'rth' else max(0.0, (now_et - gap_open).total_seconds() / 3600)
    mult, answers_class, monday_risk = class_budget(session)
    return {
        'generated_at': now_utc.isoformat().replace('+00:00', 'Z'),
        'contract': CONTRACT,
        'aperture_id': f"aperture:XNYS:{gap_open.date()}:{session}",
        'market': 'XNYS',
        'session_class': session,
        'global_liquidity_band': global_liquidity_band(now_et),
        'is_offhours': session != 'rth',
        'is_long_gap': session in {'weekend_aperture', 'holiday_aperture', 'halfday_postclose_aperture'} or gap_hours >= 12,
        'previous_rth_close_at': prev_close.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'next_rth_open_at': next_open.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'gap_open_at': gap_open.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'gap_hours': round(gap_hours, 2),
        'holiday_name': holiday,
        'early_close': early,
        'discovery_multiplier': mult,
        'answers_budget_class': answers_class,
        'monday_open_risk': monday_risk,
        'calendar_confidence': calendar_confidence(now_et.date()),
        'review_source': '/Users/leofitz/Downloads/review 2026-04-18.md',
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--now', default=None)
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    state = build_state(parse_now(args.now))
    atomic_write_json(out, state)
    print(json.dumps({'status': 'pass', 'session_class': state['session_class'], 'is_offhours': state['is_offhours'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
