from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
sys.path.insert(0, str(SCRIPTS))

from options_iv_surface_compiler import compile_surface


def _proxy(events: list[dict], generated_at: str = '2026-04-17T14:00:00Z') -> dict:
    return {'generated_at': generated_at, 'status': 'pass', 'top_events': events}


def test_options_iv_surface_marks_missing_iv_as_proxy_penalty() -> None:
    report = compile_surface(_proxy([{
        'symbol': 'RGTI', 'provider': 'nasdaq option-chain', 'call_put': 'call',
        'volume': 1200, 'open_interest': 300, 'volume_oi_ratio': 4.0,
        'option_signal_type': 'options_unusual_activity_proxy', 'score': 5,
    }]), now=datetime(2026, 4, 17, 14, 5, tzinfo=timezone.utc))
    row = report['symbols'][0]
    assert row['iv_observation_count'] == 0
    assert row['proxy_only'] is True
    assert 'missing_iv_surface' in row['confidence_penalties']
    assert row['provider_confidence'] < 0.5


def test_options_iv_surface_marks_stale_chain_as_confidence_penalty() -> None:
    report = compile_surface(_proxy([{
        'symbol': 'MSTR', 'provider': 'yfinance option-chain', 'call_put': 'put',
        'volume': 10, 'open_interest': 100, 'volume_oi_ratio': 0.1,
        'implied_volatility': 0.8, 'score': 1,
    }], generated_at='2026-04-17T12:00:00Z'), now=datetime(2026, 4, 17, 14, 30, tzinfo=timezone.utc))
    row = report['symbols'][0]
    assert row['chain_staleness'] == 'stale'
    assert 'stale_chain_snapshot' in row['confidence_penalties']
    assert row['max_implied_volatility'] == 0.8


def test_options_iv_surface_computes_volume_oi_and_skew_when_available() -> None:
    report = compile_surface(_proxy([
        {'symbol': 'TSLA', 'provider': 'primary iv vendor', 'call_put': 'call', 'volume_oi_ratio': 2.0, 'implied_volatility': 0.7, 'score': 3},
        {'symbol': 'TSLA', 'provider': 'primary iv vendor', 'call_put': 'put', 'volume_oi_ratio': 1.2, 'implied_volatility': 0.5, 'score': 2},
    ]), now=datetime(2026, 4, 17, 14, 10, tzinfo=timezone.utc))
    row = report['symbols'][0]
    assert row['avg_implied_volatility'] == 0.6
    assert row['call_put_skew'] == 0.2
    assert row['max_volume_oi_ratio'] == 2.0
    assert row['provider_confidence'] > 0.6
    assert report['shadow_only'] is True
    assert report['no_execution'] is True


def test_report_job_refreshes_options_iv_surface_shadow_context() -> None:
    text = (ROOT / 'scripts' / 'finance_discord_report_job.py').read_text(encoding='utf-8')
    assert 'options_iv_surface_compiler.py' in text
    assert 'run_optional' in text
