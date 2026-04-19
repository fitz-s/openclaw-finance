#!/usr/bin/env python3
"""Conservative recovery policy for Brave source activation."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
BRAVE_WEB = STATE / 'brave-web-search-results.jsonl'
BRAVE_NEWS = STATE / 'brave-news-search-results.jsonl'
OUT = STATE / 'brave-source-recovery-policy.json'
CONTRACT = 'brave-source-recovery-policy-v1'
DEFAULT_COOLDOWN_MINUTES = 60


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def retry_after_seconds(record: dict[str, Any]) -> int | None:
    for source in (record.get('quota_state'), record):
        if not isinstance(source, dict):
            continue
        value = source.get('retry_after_sec') or source.get('retry_after_seconds')
        if value is None:
            continue
        try:
            return max(0, int(float(value)))
        except Exception:
            continue
    return None


def is_quota_pressure(record: dict[str, Any]) -> bool:
    return (
        record.get('status') == 'rate_limited'
        or record.get('error_class') == 'throttle_or_quota'
        or record.get('application_error_code') in {'RATE_LIMITED', 'USAGE_LIMIT_EXCEEDED', 'QUOTA_LIMITED'}
        or record.get('error_code') in {'429', '402'}
        or (isinstance(record.get('quota_state'), dict) and record['quota_state'].get('status_code') in {402, 429, '402', '429'})
    )


def build_policy(
    *,
    records: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
) -> dict[str, Any]:
    now_value = now or now_utc()
    rows = records if records is not None else load_jsonl(BRAVE_WEB) + load_jsonl(BRAVE_NEWS)
    pressure_rows = []
    breaker_until: datetime | None = None
    for row in rows:
        if not is_quota_pressure(row):
            continue
        fetched = parse_ts(row.get('fetched_at')) or now_value
        retry_after = retry_after_seconds(row)
        candidate_until = fetched + timedelta(seconds=retry_after) if retry_after is not None else fetched + timedelta(minutes=cooldown_minutes)
        if candidate_until >= now_value:
            pressure_rows.append({
                'endpoint': row.get('endpoint'),
                'status': row.get('status'),
                'error_class': row.get('error_class'),
                'application_error_code': row.get('application_error_code'),
                'fetched_at': row.get('fetched_at'),
                'breaker_until': candidate_until.isoformat().replace('+00:00', 'Z'),
            })
            breaker_until = max(filter(None, [breaker_until, candidate_until])) if breaker_until else candidate_until
    breaker_open = breaker_until is not None and breaker_until >= now_value
    return {
        'generated_at': now_value.isoformat().replace('+00:00', 'Z'),
        'contract': CONTRACT,
        'review_source': '/Users/leofitz/Downloads/review 2026-04-18.md',
        'breaker_open': breaker_open,
        'reason': 'recent_brave_quota_or_rate_limit' if breaker_open else 'clear',
        'breaker_until': breaker_until.isoformat().replace('+00:00', 'Z') if breaker_until else None,
        'cooldown_minutes': cooldown_minutes,
        'pressure_record_count': len(pressure_rows),
        'pressure_records': pressure_rows[-10:],
        'no_execution': True,
        'no_delivery_mutation': True,
        'no_wake_mutation': True,
        'no_threshold_mutation': True,
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
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--cooldown-minutes', type=int, default=DEFAULT_COOLDOWN_MINUTES)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    policy = build_policy(cooldown_minutes=args.cooldown_minutes)
    atomic_write_json(out, policy)
    print(json.dumps({'status': 'pass', 'breaker_open': policy['breaker_open'], 'reason': policy['reason'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
