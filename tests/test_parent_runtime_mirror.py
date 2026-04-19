from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from export_parent_runtime_mirror import finance_cron_slice

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
MIRROR = ROOT / 'docs' / 'openclaw-runtime' / 'parent-runtime'


def test_parent_runtime_mirror_contains_cutover_source_files() -> None:
    expected = [
        MIRROR / 'services' / 'market-ingest' / 'adapters' / 'live_finance_adapter.py',
        MIRROR / 'services' / 'market-ingest' / 'normalizer' / 'source_promotion.py',
        MIRROR / 'services' / 'market-ingest' / 'normalizer' / 'semantic_normalizer.py',
        MIRROR / 'services' / 'market-ingest' / 'source_health' / 'compiler.py',
        MIRROR / 'services' / 'market-ingest' / 'packet_compiler' / 'compiler.py',
        MIRROR / 'services' / 'market-ingest' / 'wake_policy' / 'policy.py',
    ]
    for path in expected:
        assert path.exists(), path


def test_parent_runtime_mirror_manifest_and_cron_slice() -> None:
    manifest = json.loads((MIRROR / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['contract'] == 'parent-runtime-mirror-v1'
    assert manifest['status'] == 'pass'
    cron = json.loads((MIRROR / 'cron' / 'finance-jobs-slice.json').read_text(encoding='utf-8'))
    names = {job['name'] for job in cron['jobs']}
    assert 'finance-premarket-brief' in names
    assert 'finance-subagent-scanner' in names
    assert 'finance_parent_market_ingest_cutover.py' in json.dumps(cron, ensure_ascii=False)


def test_finance_cron_slice_is_sanitized_to_finance_jobs() -> None:
    payload = finance_cron_slice()
    assert payload['jobs']
    assert all(str(job['name']).startswith('finance-') for job in payload['jobs'])
    assert payload['no_execution'] is True
