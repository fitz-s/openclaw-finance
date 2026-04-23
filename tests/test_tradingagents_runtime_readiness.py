from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import tradingagents_runtime_readiness as readiness


def test_runtime_readiness_fails_without_auth(monkeypatch) -> None:
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.setattr(readiness, 'detect_google_adc', lambda: {
        'available': False,
        'project': None,
        'credential_type': None,
        'error_class': 'DefaultCredentialsError',
        'error_message': 'missing',
    })
    report = readiness.evaluate_runtime_readiness()
    assert report['status'] == 'fail'
    assert report['provider'] == 'google'
    assert report['auth_source'] == 'GOOGLE_API_KEY'
    assert report['auth_present'] is False
    assert any(err.startswith('missing_auth_source:GOOGLE_API_KEY') for err in report['errors'])
    assert 'google_adc_unavailable' in report['errors']


def test_runtime_readiness_passes_with_auth(monkeypatch) -> None:
    monkeypatch.setenv('GOOGLE_API_KEY', 'test-key')
    monkeypatch.setattr(readiness, 'detect_google_adc', lambda: {
        'available': False,
        'project': None,
        'credential_type': None,
        'error_class': None,
        'error_message': None,
    })
    report = readiness.evaluate_runtime_readiness()
    assert report['provider'] == 'google'
    assert report['auth_source'] == 'GOOGLE_API_KEY'
    assert report['auth_present'] is True
    assert report['auth_via_api_key'] is True
    assert not any(err.startswith('missing_auth_source:') for err in report['errors'])


def test_runtime_readiness_passes_with_google_adc(monkeypatch) -> None:
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.setattr(readiness, 'detect_google_adc', lambda: {
        'available': True,
        'project': 'snappy-frame-468105-h0',
        'credential_type': 'Credentials',
        'error_class': None,
        'error_message': None,
    })
    report = readiness.evaluate_runtime_readiness()
    assert report['provider'] == 'google'
    assert report['auth_present'] is True
    assert report['auth_via_api_key'] is False
    assert report['google_adc']['available'] is True
    assert not any(err.startswith('missing_auth_source:') for err in report['errors'])
