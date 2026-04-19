from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import options_iv_provider_fetcher as fetcher


def test_polygon_normalization_writes_derived_only_iv_observation() -> None:
    payload = {
        'results': [{
            'ticker': 'O:TSLA260117C00400000',
            'details': {'expiration_date': '2026-01-17', 'strike_price': 400, 'contract_type': 'call'},
            'greeks': {'delta': 0.45, 'gamma': 0.01, 'theta': -0.02, 'vega': 0.2},
            'implied_volatility': 0.62,
            'open_interest': 1200,
            'day': {'volume': 500},
        }]
    }
    rows = fetcher.normalize_polygon('TSLA', payload, observed_at='2026-04-18T15:00:00Z')
    assert len(rows) == 1
    row = rows[0]
    assert row['symbol'] == 'TSLA'
    assert row['provider'] == 'polygon'
    assert row['implied_volatility'] == 0.62
    assert row['delta'] == 0.45
    assert row['volume_oi_ratio'] == 0.4167
    assert row['derived_only'] is True
    assert row['raw_payload_retained'] is False
    assert row['no_execution'] is True


def test_missing_polygon_credentials_use_failed_fetch_record_status(monkeypatch) -> None:
    monkeypatch.delenv('POLYGON_API_KEY', raising=False)
    rows, record = fetcher.fetch_polygon('TSLA', timeout=1)
    assert rows == []
    assert record['status'] == 'failed'
    assert record['error_class'] == 'missing_credentials'
    assert record['application_error_code'] == 'missing_api_key'
    assert record['source_id'] == 'source:polygon_options_iv'
    assert record['raw_payload_retained'] is False


def test_thetadata_network_error_is_failed_not_custom_status(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise TimeoutError('terminal unavailable')

    monkeypatch.setattr(fetcher, 'get_json', boom)
    rows, record = fetcher.fetch_thetadata('TSLA', timeout=1)
    assert rows == []
    assert record['status'] == 'failed'
    assert record['error_class'] == 'network_error'
    assert record['application_error_code'] == 'TimeoutError'
    assert record['endpoint'] == 'thetadata/option/snapshot/greeks/implied_volatility'


def test_snapshot_no_credentials_degrades_without_raw_payload(monkeypatch) -> None:
    monkeypatch.delenv('POLYGON_API_KEY', raising=False)
    monkeypatch.delenv('TRADIER_ACCESS_TOKEN', raising=False)
    snapshot, records = fetcher.build_snapshot(['TSLA'], ['polygon', 'tradier'], timeout=1)
    assert snapshot['status'] == 'degraded'
    assert snapshot['observation_count'] == 0
    assert snapshot['raw_payload_retained'] is False
    assert snapshot['derived_only'] is True
    assert {record['status'] for record in records} == {'failed'}
    assert {record['error_class'] for record in records} == {'missing_credentials'}


def test_ibkr_disabled_records_broker_session_unavailable(monkeypatch) -> None:
    monkeypatch.delenv('IBKR_OPTIONS_IV_ENABLED', raising=False)
    rows, record = fetcher.fetch_ibkr('TSLA', timeout=1)
    assert rows == []
    assert record['status'] == 'failed'
    assert record['source_id'] == 'source:ibkr_options_iv'
    assert record['error_class'] == 'broker_session_unavailable'
    assert record['application_error_code'] == 'ibkr_options_iv_disabled'


def test_ibkr_normalization_uses_model_option_computation_fields() -> None:
    rows = fetcher.normalize_ibkr('TSLA', [{
        'underlying': 'TSLA',
        'expiration': '20260117',
        'strike': 400,
        'right': 'C',
        'implied_volatility': 0.62,
        'delta': 0.45,
        'gamma': 0.01,
        'vega': 0.2,
        'theta': -0.02,
    }], observed_at='2026-04-18T15:00:00Z')
    assert len(rows) == 1
    row = rows[0]
    assert row['provider'] == 'ibkr'
    assert row['source_id'] == 'source:ibkr_options_iv'
    assert row['implied_volatility'] == 0.62
    assert 'broker_session_required' in row['confidence_penalties']


def test_cli_blocks_unsafe_paths(tmp_path: Path) -> None:
    code = fetcher.main(['--out', str(tmp_path / 'outside.json')])
    assert code == 2
