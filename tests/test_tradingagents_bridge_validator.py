from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from tradingagents_bridge_validator import validate_advisory


def test_validate_advisory_allows_machine_only_rating() -> None:
    advisory = {
        'generated_at': '2026-04-23T00:00:00Z',
        'hypothetical_rating': 'OVERWEIGHT',
        'summary_title_safe': 'TradingAgents sidecar | NVDA',
        'why_now_safe': ['Demand remains durable and requires validation.'],
        'why_not_now_safe': ['This sidecar cannot change judgment or execution state.'],
        'invalidators_safe': ['If deterministic sources disagree, deprioritize the sidecar.'],
        'required_confirmations_safe': ['Validate source freshness before any review use.'],
        'source_gaps_safe': ['No deterministic citation promotion exists yet.'],
        'risk_flags_safe': ['Wait for valuation and liquidity confirmation.'],
        'execution_readiness': 'disabled',
        'review_only': True,
        'no_execution': True,
    }
    request = {'source_bindings': {'report_envelope': {'report_hash': 'sha256:report'}, 'context_packet': {'packet_hash': 'sha256:packet'}}, 'surface_policy': {}}
    report = validate_advisory(advisory, request)
    assert report['status'] == 'pass'
    assert report['reader_eligible'] is True
    assert report['context_pack_eligible'] is True


def test_validate_advisory_blocks_execution_language() -> None:
    advisory = {
        'generated_at': '2026-04-23T00:00:00Z',
        'hypothetical_rating': 'BUY',
        'summary_title_safe': 'TradingAgents sidecar | NVDA',
        'why_now_safe': ['Buy immediately on a pullback.'],
        'why_not_now_safe': [],
        'invalidators_safe': [],
        'required_confirmations_safe': [],
        'source_gaps_safe': [],
        'risk_flags_safe': [],
        'execution_readiness': 'disabled',
        'review_only': True,
        'no_execution': True,
    }
    report = validate_advisory(advisory, {'source_bindings': {}, 'surface_policy': {}})
    assert report['status'] == 'fail'
    assert 'execution_language_detected:why_now_safe' in report['errors']


def test_validate_advisory_blocks_chinese_execution_language() -> None:
    advisory = {
        'generated_at': '2026-04-23T00:00:00Z',
        'hypothetical_rating': 'HOLD',
        'summary_title_safe': 'TradingAgents sidecar | NVDA',
        'why_now_safe': ['建议买入并分批加仓。'],
        'why_not_now_safe': [],
        'invalidators_safe': [],
        'required_confirmations_safe': [],
        'source_gaps_safe': [],
        'risk_flags_safe': [],
        'execution_readiness': 'disabled',
        'review_only': True,
        'no_execution': True,
    }
    report = validate_advisory(advisory, {'source_bindings': {}, 'surface_policy': {}})
    assert report['status'] == 'fail'
    assert 'execution_language_detected:why_now_safe' in report['errors']
