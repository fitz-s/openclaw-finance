from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from brave_source_recovery_policy import build_policy


def test_recent_rate_limited_record_opens_breaker() -> None:
    now = datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc)
    record = {'status': 'rate_limited', 'endpoint': 'brave/news/search', 'fetched_at': (now - timedelta(minutes=5)).isoformat().replace('+00:00', 'Z'), 'quota_state': {'retry_after_sec': '600'}}
    policy = build_policy(records=[record], now=now)
    assert policy['breaker_open'] is True
    assert policy['reason'] == 'recent_brave_quota_or_rate_limit'
    assert policy['pressure_record_count'] == 1


def test_old_rate_limited_record_does_not_open_breaker() -> None:
    now = datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc)
    record = {'status': 'rate_limited', 'endpoint': 'brave/news/search', 'fetched_at': (now - timedelta(hours=3)).isoformat().replace('+00:00', 'Z')}
    policy = build_policy(records=[record], now=now, cooldown_minutes=60)
    assert policy['breaker_open'] is False
    assert policy['reason'] == 'clear'


def test_non_quota_record_keeps_breaker_closed() -> None:
    now = datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc)
    record = {'status': 'ok', 'endpoint': 'brave/news/search', 'fetched_at': now.isoformat().replace('+00:00', 'Z')}
    policy = build_policy(records=[record], now=now)
    assert policy['breaker_open'] is False
