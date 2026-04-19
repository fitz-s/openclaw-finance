#!/usr/bin/env python3
"""Audit observed parent delivery success for finance report jobs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json

ROOT = Path('/Users/leofitz/.openclaw')
FINANCE = ROOT / 'workspace' / 'finance'
RUNS_DIR = ROOT / 'cron' / 'runs'
STATE = FINANCE / 'state'
OUT = STATE / 'finance-delivery-observed-audit.json'
CT = ZoneInfo('America/Chicago')
CONTRACT = 'finance-delivery-observed-audit-v1'
REPORT_JOBS = {
    'finance-premarket-brief': 'b2c3d4e5-f6a7-8901-bcde-f01234567890',
    'finance-premarket-delivery-watchdog': 'finance-premarket-delivery-watchdog-v1',
    'finance-midday-operator-review': 'finance-midday-operator-review-v1',
}


def now_ct() -> datetime:
    return datetime.now(timezone.utc).astimezone(CT)


def parse_ms(value: Any) -> datetime | None:
    try:
        ms = int(value)
    except Exception:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(CT)


def row_time(row: dict[str, Any]) -> datetime | None:
    for key in ('ts', 'finishedAtMs', 'runAtMs', 'startedAtMs'):
        parsed = parse_ms(row.get(key))
        if parsed:
            return parsed
    value = row.get('finishedAt') or row.get('startedAt')
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(CT)
        except Exception:
            return None
    return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    ts = row_time(row)
    return {
        'ts': ts.isoformat() if ts else None,
        'jobId': row.get('jobId'),
        'action': row.get('action'),
        'status': row.get('status'),
        'delivered': row.get('delivered'),
        'deliveryStatus': row.get('deliveryStatus'),
        'durationMs': row.get('durationMs'),
        'sessionKey': row.get('sessionKey'),
        'error': row.get('error'),
    }


def is_delivered(row: dict[str, Any]) -> bool:
    return row.get('delivered') is True or row.get('deliveryStatus') == 'delivered'


def build_audit(*, runs_dir: Path = RUNS_DIR, now: datetime | None = None, lookback_rows: int = 50) -> dict[str, Any]:
    now_value = now or now_ct()
    jobs: dict[str, Any] = {}
    delivered_rows: list[dict[str, Any]] = []
    for name, job_id in REPORT_JOBS.items():
        rows = load_jsonl(runs_dir / f'{job_id}.jsonl')[-lookback_rows:]
        finished = [row for row in rows if row.get('action') in {None, 'finished'}]
        compact = [compact_row(row) for row in finished]
        delivered = [row for row in finished if is_delivered(row)]
        delivered_rows.extend(delivered)
        latest = compact[-1] if compact else None
        jobs[name] = {
            'job_id': job_id,
            'run_file': str(runs_dir / f'{job_id}.jsonl'),
            'row_count': len(finished),
            'delivered_count': len(delivered),
            'latest': latest,
            'recent': compact[-5:],
        }
    delivered_compact = [compact_row(row) for row in delivered_rows]
    return {
        'generated_at': now_value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'contract': CONTRACT,
        'review_source': '/Users/leofitz/Downloads/review 2026-04-18.md',
        'jobs': jobs,
        'delivered_count': len(delivered_rows),
        'delivered_recent': delivered_compact[-10:],
        'observed_delivery_boundary': 'parent_cron_run_history',
        'no_direct_discord_send': True,
        'no_delivery_mutation': True,
        'no_wake_mutation': True,
        'no_execution': True,
    }


def observed_delivered_since(audit: dict[str, Any], *, hour: int, minute: int, now: datetime | None = None) -> bool:
    now_value = now or now_ct()
    cutoff = datetime.combine(now_value.date(), time(hour, minute), tzinfo=CT)
    for row in audit.get('delivered_recent', []) if isinstance(audit.get('delivered_recent'), list) else []:
        value = row.get('ts') if isinstance(row, dict) else None
        if not isinstance(value, str):
            continue
        try:
            ts = datetime.fromisoformat(value).astimezone(CT)
        except Exception:
            continue
        if ts >= cutoff:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs-dir', default=str(RUNS_DIR))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    audit = build_audit(runs_dir=Path(args.runs_dir))
    atomic_write_json(Path(args.out), audit)
    print(json.dumps({'status': 'pass', 'delivered_count': audit['delivered_count'], 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
