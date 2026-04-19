from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
RUNTIME = ROOT / 'docs' / 'openclaw-runtime'
REVIEW = '/Users/leofitz/Downloads/review 2026-04-18.md'


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_offhours_cadence_governor_and_all_days_cron() -> None:
    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/offhours-cadence-governor-state.json' in files
    assert 'docs/openclaw-runtime/ralplan/offhours-intelligence-p3-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/offhours-intelligence-p3-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/offhours-intelligence-p3-external-scout.md' in files

    governor = _json(RUNTIME / 'offhours-cadence-governor-state.json')
    assert governor['review_source'] == REVIEW
    assert governor['payload']['contract'] == 'offhours-cadence-governor-v1'

    jobs = _json(RUNTIME / 'finance-cron-jobs.json')['jobs']
    offhours = next(job for job in jobs if job['name'] == 'finance-subagent-scanner-offhours')
    assert offhours['schedule']['expr'] == '0 0,4,7,17,20 * * *'
    assert offhours['delivery']['mode'] == 'none'
