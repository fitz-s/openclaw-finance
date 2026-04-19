from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_brave_source_recovery_policy_and_p8_docs() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/brave-source-recovery-policy.json' in files
    assert 'docs/openclaw-runtime/ralplan/brave-source-recovery-p8-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/brave-source-recovery-p8-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/brave-source-recovery-p8-external-scout.md' in files
    report = _json(RUNTIME / 'brave-source-recovery-policy.json')
    assert report['payload']['contract'] == 'brave-source-recovery-policy-v1'
