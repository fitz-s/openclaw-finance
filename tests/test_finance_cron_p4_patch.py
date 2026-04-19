from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from patch_finance_cron_p4 import patch_jobs


def test_patch_finance_cron_scanner_uses_single_wrapper() -> None:
    payload = {
        'jobs': [
            {'name': 'finance-subagent-scanner', 'payload': {'message': 'old'}, 'timeout': 180},
            {'name': 'finance-subagent-scanner-offhours', 'payload': {'message': 'old'}, 'timeout': 180},
        ]
    }
    patched, changed = patch_jobs(payload)
    assert set(changed) == {'finance-subagent-scanner', 'finance-subagent-scanner-offhours'}
    for job in patched['jobs']:
        msg = job['payload']['message']
        assert 'finance_scanner_job.py --mode' in msg
        assert 'finance_llm_context_pack.py' in msg
        assert 'query_pack_planner.py' in msg
        assert 'object_links' in msg
        assert 'unknown_discovery_exhausted_reason' in msg
        assert 'unknown_discovery_minimum_attempts' in msg
        assert '不得把已在 watchlist/held 的标的当作 unknown_discovery' in msg
        assert job['payload']['lightContext'] is True
        assert job['payload']['timeoutSeconds'] == 300
        assert job['timeout'] == 300


def test_patch_finance_cron_report_jobs_are_light_context() -> None:
    payload = {'jobs': [
        {'name': 'finance-premarket-brief', 'payload': {'message': 'old'}},
        {'name': 'finance-midday-operator-review', 'payload': {'message': 'old'}},
        {'name': 'finance-premarket-delivery-watchdog', 'payload': {'message': 'old'}},
    ]}
    patched, changed = patch_jobs(payload)
    assert set(changed) == {
        'finance-premarket-brief',
        'finance-midday-operator-review',
        'finance-premarket-delivery-watchdog',
    }
    for job in patched['jobs']:
        msg = job['payload']['message']
        assert 'finance_discord_report_job.py --mode' in msg
        assert 'Return stdout exactly' in msg
        assert 'Do not emit progress text' in msg
        assert job['payload']['lightContext'] is True
        assert job['payload']['timeoutSeconds'] == 420
    by_name = {job['name']: job for job in patched['jobs']}
    assert 'finance_discord_report_job.py --mode marketday-core-review' in by_name['finance-midday-operator-review']['payload']['message']
    assert 'finance_discord_report_job.py --mode marketday-review' in by_name['finance-premarket-brief']['payload']['message']
    assert 'finance_discord_report_job.py --mode morning-watchdog' in by_name['finance-premarket-delivery-watchdog']['payload']['message']
