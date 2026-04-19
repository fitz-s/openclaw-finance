from __future__ import annotations

import json
from pathlib import Path


ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
RUNTIME = ROOT / 'docs' / 'openclaw-runtime'
REVIEW = '/Users/leofitz/Downloads/review 2026-04-18.md'


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_aperture_and_budget_state() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])

    assert 'docs/openclaw-runtime/session-aperture-state.json' in files
    assert 'docs/openclaw-runtime/brave-budget-state.json' in files
    assert 'docs/openclaw-runtime/ralplan/offhours-intelligence-p0-ralplan.md' in files
    assert 'docs/openclaw-runtime/contracts/offhours-aperture-contract.md' in files
    assert 'docs/openclaw-runtime/contracts/brave-budget-guard-contract.md' in files

    aperture = _json(RUNTIME / 'session-aperture-state.json')
    budget = _json(RUNTIME / 'brave-budget-state.json')

    assert aperture['state_boundary'] == 'sanitized_runtime_control_state'
    assert budget['state_boundary'] == 'sanitized_runtime_control_state'
    assert aperture['review_source'] == REVIEW
    assert budget['review_source'] == REVIEW
    assert aperture['payload']['contract'] == 'offhours-aperture-v1'
    assert budget['payload']['contract'] == 'brave-budget-guard-v1'
