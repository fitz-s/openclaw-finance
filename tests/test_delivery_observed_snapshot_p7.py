from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_delivery_observed_audit_and_p7_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/finance-delivery-observed-audit.json' in files
    assert 'docs/openclaw-runtime/ralplan/delivery-observed-audit-p7-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/delivery-observed-audit-p7-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/delivery-observed-audit-p7-external-scout.md' in files
    report = _json(RUNTIME / 'finance-delivery-observed-audit.json')
    assert report['payload']['contract'] == 'finance-delivery-observed-audit-v1'
    assert report['payload']['observed_delivery_boundary'] == 'parent_cron_run_history'
