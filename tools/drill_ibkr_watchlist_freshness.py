#!/usr/bin/env python3
"""Export a drill report for IBKR Client Portal watchlist freshness."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
STATE = FINANCE / 'state'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'ibkr-watchlist-freshness-drill.json'


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def main() -> int:
    ibkr = load_json(STATE / 'ibkr-watchlists.json', {}) or {}
    resolved = load_json(STATE / 'watchlist-resolved.json', {}) or {}
    fresh = resolved.get('ibkr_watchlist_fresh') is True and ibkr.get('data_status') == 'fresh'
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass' if fresh else 'needs_login_or_cached_fallback',
        'ibkr_watchlist_data_status': ibkr.get('data_status'),
        'ibkr_watchlist_fresh': resolved.get('ibkr_watchlist_fresh'),
        'resolved_data_status': resolved.get('data_status'),
        'portfolio_fresh': resolved.get('portfolio_fresh'),
        'resolved_symbol_count': resolved.get('symbol_count'),
        'blocking_reasons': resolved.get('blocking_reasons', []),
        'operator_drill': [
            'Log into IBKR Client Portal / local gateway.',
            'Run: cd /Users/leofitz/.openclaw/workspace/finance/scripts && /opt/homebrew/bin/python3 watchlist_sync.py',
            'Confirm ibkr_watchlist_fresh=true in state/watchlist-resolved.json.',
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'ibkr_watchlist_fresh': report['ibkr_watchlist_fresh'], 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
