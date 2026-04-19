from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_sec_fallback_report_and_p9_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/sec-fallback-activation-report.json' in files
    assert 'docs/openclaw-runtime/ralplan/sec-fallback-activation-p9-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/sec-fallback-activation-p9-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/sec-fallback-activation-p9-external-scout.md' in files
    report = _json(RUNTIME / 'sec-fallback-activation-report.json')
    assert report['payload']['contract'] == 'sec-fallback-activation-v1'
    assert report['payload']['records_are_not_evidence'] is True
