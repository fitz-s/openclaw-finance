from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
RUNTIME = ROOT / 'docs' / 'openclaw-runtime'
REVIEW = '/Users/leofitz/Downloads/review 2026-04-18.md'


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_compression_activation_report_and_p2_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])

    assert 'docs/openclaw-runtime/brave-compression-activation-report.json' in files
    assert 'docs/openclaw-runtime/ralplan/offhours-intelligence-p2-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/offhours-intelligence-p2-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/offhours-intelligence-p2-external-scout.md' in files

    report = _json(RUNTIME / 'brave-compression-activation-report.json')
    assert report['state_boundary'] == 'sanitized_runtime_control_state'
    assert report['review_source'] == REVIEW
    assert report['payload']['contract'] == 'brave-compression-activation-v1'
    assert report['payload']['answers_sidecar_only'] is True
    assert report['payload']['compression_records_are_not_authority'] is True
