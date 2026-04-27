from __future__ import annotations

import json
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
    assert request['model_resolution']['role_name'] == 'finance-tradingagents'
    assert request['config']['llm_provider'] == 'google'
    assert request['config']['quick_think_llm'] == 'gemini-3-flash-preview'
    assert request['config']['deep_think_llm'] == 'gemini-3.1-pro-preview'
    assert request['config']['google_use_application_default_credentials'] is True
    assert request['config']['google_vertexai'] is True
    assert request['config']['google_location'] == 'global'


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
    assert request['model_resolution']['auth_source'] == 'GOOGLE_API_KEY'


def test_build_request_raises_when_no_target_exists() -> None:
    try:
        build_request(
            mode='manual',
            research_packet={'selected_opportunities': [], 'selected_theses': []},
            report_envelope={},
            decision_log={},
            packet={},
            thesis_registry={'theses': []},
            capital_agenda={'agenda_items': []},
        )
    except ValueError as exc:
        assert 'no TradingAgents target instrument available' in str(exc)
    else:
        raise AssertionError('expected ValueError')


def test_build_request_falls_back_to_thesis_registry(monkeypatch) -> None:
    monkeypatch.setattr('tradingagents_request_packet.load_json', lambda path, default=None: {
        '/Users/leofitz/.openclaw/workspace/finance/state/thesis-research-packet.json': {'selected_opportunities': [], 'selected_theses': []},
        '/Users/leofitz/.openclaw/workspace/finance/state/finance-decision-report-envelope.json': {'report_hash': 'sha256:report'},
        '/Users/leofitz/.openclaw/workspace/finance/state/finance-decision-log-report.json': {'entry': {'decision_id': 'decision:123'}},
        '/Users/leofitz/.openclaw/workspace/services/market-ingest/state/latest-context-packet.json': {'packet_id': 'packet:1', 'packet_hash': 'sha256:packet', 'instrument': 'SPY'},
        '/Users/leofitz/.openclaw/workspace/finance/state/capital-agenda.json': {'agenda_items': []},
        '/Users/leofitz/.openclaw/workspace/finance/state/thesis-registry.json': {
            'theses': [{'thesis_id': 'thesis:nvda', 'instrument': 'NVDA', 'status': 'active'}]
        },
    }.get(str(path), default))
    request = build_request(mode='scheduled')
    assert request['instrument'] == 'NVDA'
    assert request['request_source'] == 'thesis_registry'
    assert request['request_source_meta']['selected_thesis_id'] == 'thesis:nvda'


def test_build_request_prefers_capital_agenda_linked_thesis(monkeypatch) -> None:
    monkeypatch.setattr('tradingagents_request_packet.load_json', lambda path, default=None: {
        '/Users/leofitz/.openclaw/workspace/finance/state/thesis-research-packet.json': {'selected_opportunities': [], 'selected_theses': []},
        '/Users/leofitz/.openclaw/workspace/finance/state/finance-decision-report-envelope.json': {'report_hash': 'sha256:report'},
        '/Users/leofitz/.openclaw/workspace/finance/state/finance-decision-log-report.json': {'entry': {'decision_id': 'decision:123'}},
        '/Users/leofitz/.openclaw/workspace/services/market-ingest/state/latest-context-packet.json': {'packet_id': 'packet:1', 'packet_hash': 'sha256:packet', 'instrument': 'SPY'},
        '/Users/leofitz/.openclaw/workspace/finance/state/capital-agenda.json': {
            'agenda_items': [{'agenda_id': 'agenda:1', 'agenda_type': 'existing_thesis_review', 'linked_thesis_ids': ['thesis:tsla']}]
        },
        '/Users/leofitz/.openclaw/workspace/finance/state/thesis-registry.json': {
            'theses': [
                {'thesis_id': 'thesis:aapl', 'instrument': 'AAPL', 'status': 'active'},
                {'thesis_id': 'thesis:tsla', 'instrument': 'TSLA', 'status': 'watch'},
            ]
        },
    }.get(str(path), default))
    request = build_request(mode='scheduled')
    assert request['instrument'] == 'TSLA'
    assert request['request_source'] == 'capital_agenda'
    assert request['request_source_meta']['agenda_id'] == 'agenda:1'


def test_request_example_tracks_google_preview_resolution_contract() -> None:
    example = json.loads(
        (ROOT / 'docs' / 'openclaw-runtime' / 'examples' / 'tradingagents-run-request.example.json').read_text(encoding='utf-8')
    )
    assert example['config']['llm_provider'] == 'google'
    assert example['config']['quick_think_llm'] == 'gemini-3-flash-preview'
    assert example['config']['deep_think_llm'] == 'gemini-3.1-pro-preview'
    assert example['config']['backend_url'] is None
    assert example['config']['google_use_application_default_credentials'] is True
    assert example['config']['google_vertexai'] is True
    assert example['config']['google_location'] == 'global'
    assert example['model_resolution']['openclaw_runtime_alias'] == 'google-gemini-cli/gemini-3-flash-preview'
    assert example['model_resolution']['quick_model'] == 'gemini-3-flash-preview'
    assert example['model_resolution']['deep_model'] == 'gemini-3.1-pro-preview'
