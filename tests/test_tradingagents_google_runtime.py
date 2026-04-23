from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from tradingagents_google_runtime import patch_yfinance_dataflow


def test_patch_yfinance_dataflow_injects_pandas_alias() -> None:
    module = SimpleNamespace()
    patch_yfinance_dataflow(module)
    assert getattr(module, '_finance_dataflow_patch_applied') is True
    assert module.pd.__name__ == 'pandas'
