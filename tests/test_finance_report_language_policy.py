from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_decision_report_render import humanize_invalidator_desc


def test_common_invalidator_machine_terms_are_operator_chinese() -> None:
    assert humanize_invalidator_desc('source outage') == '数据源中断'
    assert humanize_invalidator_desc('official correction') == '官方更正'
    assert humanize_invalidator_desc('packet staleness') == '数据包过旧'
