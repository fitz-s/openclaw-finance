from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from patch_marketday_core_review_p4 import SCHEDULE, patch_jobs


def test_patch_midday_job_to_fixed_marketday_core_review() -> None:
    payload = {'jobs': [{'name': 'finance-midday-operator-review', 'enabled': True, 'schedule': {'kind': 'cron', 'expr': '30 11 * * 1-5', 'tz': 'America/Chicago'}, 'delivery': {'mode': 'announce'}, 'payload': {'message': 'old', 'timeoutSeconds': 420}}]}
    patched, changed = patch_jobs(payload)
    job = patched['jobs'][0]
    assert 'schedule_1315_ct' in changed
    assert job['schedule']['expr'] == SCHEDULE
    assert job['delivery']['mode'] == 'announce'
    assert 'finance_discord_report_job.py --mode marketday-core-review' in job['payload']['message']
    assert 'fixed second marketday core review attempt' in job['payload']['message']
    assert job['payload']['timeoutSeconds'] == 420
