from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from tradingagents_request_packet import build_request


def test_build_request_prefers_manual_instrument() -> None:
    request = build_request(
        mode='manual',
        instrument='nvda',
        analysis_date='2026-04-23',
        research_packet={'selected_opportunities': [{'candidate_id': 'opp:abc', 'instrument': 'ABC'}]},
        report_envelope={'report_hash': 'sha256:report', 'packet_hash': 'sha256:packet'},
        decision_log={'entry': {'decision_id': 'decision:123'}},
        packet={'packet_id': 'packet:1', 'packet_hash': 'sha256:packet'},
    )

    assert request['instrument'] == 'NVDA'
    assert request['request_source'] == 'manual_instrument'
    assert request['analysis_date'] == '2026-04-23'
    assert request['review_only'] is True
    assert request['no_execution'] is True
    assert 'no_execution' in request['forbidden_actions']


def test_build_request_falls_back_to_selected_opportunity() -> None:
    request = build_request(
        mode='manual',
        research_packet={
            'selected_opportunities': [
                {'candidate_id': 'opp:high', 'instrument': 'smr', 'theme': 'Nuclear buildout'},
            ],
            'selected_theses': [{'thesis_id': 'thesis:tsla', 'instrument': 'TSLA'}],
        },
        report_envelope={'report_hash': 'sha256:report'},
        decision_log={'entry': {'decision_id': 'decision:123'}},
        packet={'packet_id': 'packet:1', 'packet_hash': 'sha256:packet'},
    )

    assert request['instrument'] == 'SMR'
    assert request['request_source'] == 'selected_opportunity'
    assert request['request_source_meta']['selected_opportunity_id'] == 'opp:high'
    assert request['source_bindings']['report_envelope']['report_hash'] == 'sha256:report'


def test_build_request_raises_when_no_target_exists() -> None:
    try:
        build_request(
            mode='manual',
            research_packet={'selected_opportunities': [], 'selected_theses': []},
            report_envelope={},
            decision_log={},
            packet={},
        )
    except ValueError as exc:
        assert 'no TradingAgents target instrument available' in str(exc)
    else:
        raise AssertionError('expected ValueError')
