from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_exchange_calendar_provider_report_and_p6_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/exchange-calendar-provider-report.json' in files
    assert 'docs/openclaw-runtime/ralplan/exchange-calendar-provider-p6-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/exchange-calendar-provider-p6-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/exchange-calendar-provider-p6-external-scout.md' in files

    report = _json(RUNTIME / 'exchange-calendar-provider-report.json')
    assert report['payload']['contract'] == 'exchange-calendar-provider-v1'
    assert report['payload']['supported_years'] == [2026, 2027, 2028]
