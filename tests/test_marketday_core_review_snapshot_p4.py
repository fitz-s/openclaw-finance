from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_snapshot_exports_marketday_core_review_schedule_and_prompt() -> None:
    jobs = _json(RUNTIME / 'finance-cron-jobs.json')['jobs']
    midday = next(job for job in jobs if job['name'] == 'finance-midday-operator-review')
    assert midday['schedule']['expr'] == '15 13 * * 1-5'
    assert midday['delivery']['mode'] == 'announce'
    assert 'marketday-core-review' in midday['payload']['message']

    manifest = _json(RUNTIME / 'snapshot-manifest.json')
    files = set(manifest['snapshot_files'])
    assert 'docs/openclaw-runtime/ralplan/marketday-core-review-p4-ralplan.md' in files
    assert 'docs/openclaw-runtime/scouts/marketday-core-review-p4-internal-explorer.md' in files
    assert 'docs/openclaw-runtime/scouts/marketday-core-review-p4-external-scout.md' in files
