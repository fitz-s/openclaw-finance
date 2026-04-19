from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
RUNTIME = ROOT / 'docs' / 'openclaw-runtime'
REVIEW = '/Users/leofitz/Downloads/review 2026-04-18.md'


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_offhours_router_state_and_p1_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])

    assert 'docs/openclaw-runtime/offhours-source-router-state.json' in files
    assert 'docs/openclaw-runtime/ralplan/offhours-intelligence-p1-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/offhours-intelligence-p1-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/offhours-intelligence-p1-external-scout.md' in files

    router = _json(RUNTIME / 'offhours-source-router-state.json')
    assert router['state_boundary'] == 'sanitized_runtime_control_state'
    assert router['review_source'] == REVIEW
    assert router['payload']['contract'] == 'offhours-source-router-v1'
