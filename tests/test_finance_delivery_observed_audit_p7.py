from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_delivery_observed_audit import build_audit, observed_delivered_since

CT = ZoneInfo('America/Chicago')


def _write_run(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def test_audit_detects_observed_delivery_after_cutoff(tmp_path: Path) -> None:
    runs = tmp_path / 'runs'
    _write_run(runs / 'b2c3d4e5-f6a7-8901-bcde-f01234567890.jsonl', [
        {'ts': _ms(datetime(2026, 4, 20, 8, 10, tzinfo=CT)), 'jobId': 'b2c3', 'action': 'finished', 'status': 'ok', 'delivered': True, 'deliveryStatus': 'delivered'},
    ])
    audit = build_audit(runs_dir=runs, now=datetime(2026, 4, 20, 8, 30, tzinfo=CT))
    assert audit['delivered_count'] == 1
    assert observed_delivered_since(audit, hour=7, minute=30, now=datetime(2026, 4, 20, 8, 30, tzinfo=CT)) is True


def test_audit_does_not_treat_ok_not_delivered_as_observed(tmp_path: Path) -> None:
    runs = tmp_path / 'runs'
    _write_run(runs / 'b2c3d4e5-f6a7-8901-bcde-f01234567890.jsonl', [
        {'ts': _ms(datetime(2026, 4, 20, 8, 10, tzinfo=CT)), 'jobId': 'b2c3', 'action': 'finished', 'status': 'ok', 'delivered': False, 'deliveryStatus': 'not-delivered'},
    ])
    audit = build_audit(runs_dir=runs, now=datetime(2026, 4, 20, 8, 30, tzinfo=CT))
    assert audit['delivered_count'] == 0
    assert observed_delivered_since(audit, hour=7, minute=30, now=datetime(2026, 4, 20, 8, 30, tzinfo=CT)) is False
    latest = audit['jobs']['finance-premarket-brief']['latest']
    assert latest['status'] == 'ok'
    assert latest['deliveryStatus'] == 'not-delivered'
