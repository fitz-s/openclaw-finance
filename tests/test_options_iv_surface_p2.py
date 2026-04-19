from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from options_iv_surface_compiler import compile_surface


def test_provider_snapshot_takes_precedence_over_proxy_for_same_symbol() -> None:
    provider = {
        'generated_at': '2026-04-18T15:00:00Z',
        'status': 'pass',
        'observation_count': 1,
        'observations': [{
            'symbol': 'TSLA',
            'provider': 'polygon',
            'source_id': 'source:polygon_options_iv',
            'expiration': '2026-06-19',
            'strike': 300,
            'call_put': 'call',
            'implied_volatility': 0.64,
            'delta': 0.4,
            'volume': 500,
            'open_interest': 1000,
            'volume_oi_ratio': 0.5,
            'rights_policy': 'derived_only',
            'point_in_time_replay_supported': False,
            'provider_confidence_base': 0.72,
            'confidence_penalties': [],
        }],
    }
    proxy = {
        'generated_at': '2026-04-18T15:00:00Z',
        'status': 'pass',
        'top_events': [{'symbol': 'TSLA', 'provider': 'nasdaq option-chain', 'call_put': 'put', 'volume_oi_ratio': 10, 'score': 10}],
    }
    report = compile_surface(proxy, provider_snapshot=provider, now=datetime(2026, 4, 18, 15, 10, tzinfo=timezone.utc))
    row = report['symbols'][0]
    assert report['primary_source_status'] == 'ok'
    assert report['summary']['provider_backed_count'] == 1
    assert row['symbol'] == 'TSLA'
    assert row['proxy_only'] is False
    assert row['provider_set'] == ['polygon']
    assert row['iv_observation_count'] == 1
    assert row['max_implied_volatility'] == 0.64
    assert row['provider_confidence'] > 0.6


def test_proxy_fallback_has_missing_primary_penalty() -> None:
    proxy = {
        'generated_at': '2026-04-18T15:00:00Z',
        'status': 'pass',
        'top_events': [{'symbol': 'AAPL', 'provider': 'nasdaq option-chain', 'call_put': 'call', 'volume_oi_ratio': 3, 'score': 5}],
    }
    report = compile_surface(proxy, provider_snapshot={}, now=datetime(2026, 4, 18, 15, 10, tzinfo=timezone.utc))
    row = report['symbols'][0]
    assert report['status'] == 'degraded'
    assert report['primary_source_status'] == 'missing'
    assert row['proxy_only'] is True
    assert 'missing_primary_options_iv_source' in row['confidence_penalties']
    assert row['source_health_refs'] == ['source:nasdaq_options_flow_proxy', 'source:yfinance_options_proxy']


def test_provider_term_structure_and_skew_are_derived() -> None:
    provider = {
        'generated_at': '2026-04-18T15:00:00Z',
        'status': 'pass',
        'observations': [
            {'symbol': 'MSTR', 'provider': 'thetadata', 'source_id': 'source:thetadata_options_iv', 'expiration': '2026-05-15', 'call_put': 'call', 'implied_volatility': 0.9, 'provider_confidence_base': 0.82, 'point_in_time_replay_supported': True},
            {'symbol': 'MSTR', 'provider': 'thetadata', 'source_id': 'source:thetadata_options_iv', 'expiration': '2026-06-19', 'call_put': 'put', 'implied_volatility': 0.7, 'provider_confidence_base': 0.82, 'point_in_time_replay_supported': True},
        ],
    }
    report = compile_surface({}, provider_snapshot=provider, now=datetime(2026, 4, 18, 15, 10, tzinfo=timezone.utc))
    row = report['symbols'][0]
    assert row['call_put_skew'] == 0.2
    assert row['term_structure']['slope'] == -0.2
    assert row['point_in_time_replay_supported'] is True
    assert report['point_in_time_replay_supported'] is True
