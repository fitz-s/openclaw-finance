from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')


def test_thread_lifecycle_gc_prunes_inactive_registry_record(tmp_path) -> None:
    bundle = tmp_path / 'bundle.json'
    bundle.write_text(json.dumps({'report_handle': 'R1'}))
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({
        'threads': {
            'old': {
                'updated_at': '2026-04-13T00:00:00Z',
                'last_activity_at': '2026-04-13T00:00:00Z',
                'followup_bundle_path': str(bundle),
                'account_id': 'default',
            },
            'new': {
                'updated_at': '2026-04-13T00:00:00Z',
                'last_user_message_at': '2026-04-16T23:00:00Z',
                'followup_bundle_path': str(bundle),
                'account_id': 'default',
            },
        }
    }))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / 'finance_thread_lifecycle_gc.py'),
            '--registry', str(registry),
            '--inactive-hours', '72',
            '--ttl-days', '30',
            '--max-records', '10',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(registry.read_text())
    assert list(payload['threads']) == ['new']
    report = json.loads(result.stdout)
    assert report['dropped_inactive_count'] == 1
    assert report['discord_thread_delete_attempted'] is False
