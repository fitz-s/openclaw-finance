from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_marketday_report_calendar_guard_and_p5_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/marketday-report-calendar-guard.json' in files
    assert 'docs/openclaw-runtime/ralplan/marketday-report-calendar-p5-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/marketday-report-calendar-p5-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/marketday-report-calendar-p5-external-scout.md' in files
