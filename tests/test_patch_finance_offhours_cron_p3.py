from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from patch_finance_offhours_cron_p3 import ALL_DAYS_EXPR, patch_jobs


def test_patch_finance_offhours_cron_p3_all_days_no_delivery() -> None:
    payload = {'jobs': [{'name': 'finance-subagent-scanner-offhours', 'enabled': True, 'schedule': {'kind': 'cron', 'expr': '0 0,4,7,17,20 * * 1-5', 'tz': 'America/Chicago'}, 'delivery': {'mode': 'none'}, 'payload': {'message': 'Run scanner', 'timeoutSeconds': 300}}]}
    patched, changed = patch_jobs(json.loads(json.dumps(payload)))
    job = patched['jobs'][0]
    assert 'schedule_expr_all_days' in changed
    assert job['schedule']['expr'] == ALL_DAYS_EXPR
    assert job['delivery']['mode'] == 'none'
    assert job['payload']['message'] == 'Run scanner'
    assert job['payload']['timeoutSeconds'] == 300
