from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_decision_report_render import build_report
from finance_report_product_validator import validate


def test_shadow_delta_report_passes_product_validator() -> None:
    packet = {
        'packet_id': 'packet:test',
        'packet_hash': 'sha256:test',
        'instrument': 'SPY',
        'layer_digest': {'L0': ['ev:1'], 'L1': [], 'L2': [], 'L3': [], 'L4': []},
        'contradictions': [],
        'evidence_refs': ['ev:1'],
        'thesis_refs': ['thesis:abc'],
        'scenario_refs': [],
        'opportunity_candidate_refs': ['opportunity:abc'],
        'invalidator_refs': ['invalidator:abc'],
        'source_quality_summary': {'wake_eligible_count': 0, 'judgment_support_count': 1, 'record_count': 1},
    }
    judgment = {
        'judgment_id': 'judgment:test',
        'packet_id': 'packet:test',
        'packet_hash': 'sha256:test',
        'thesis_state': 'no_trade',
        'actionability': 'none',
        'confidence': 0,
        'evidence_refs': ['ev:1'],
        'why_now': ['context packet updated'],
        'why_not': ['no wake eligible evidence'],
        'invalidators': ['packet staleness'],
        'required_confirmations': ['source-backed confirmation'],
        'thesis_refs': ['thesis:abc'],
        'scenario_refs': [],
        'opportunity_candidate_refs': ['opportunity:abc'],
        'invalidator_refs': ['invalidator:abc'],
        'policy_version': 'test',
        'model_id': 'test-model',
    }
    validation = {'outcome': 'accepted_for_log', 'errors': []}
    report = build_report(
        packet,
        judgment,
        validation,
        prices={'quotes': {'ABC': {'status': 'ok', 'pct_change': 4.2, 'price': 12.3, 'volume': 1000}}},
        watchlist={'tickers': []},
        scan_state={'accumulated': []},
        broad_market={},
        options_flow={},
        portfolio={'data_status': 'fresh'},
        option_risk={'data_status': 'fresh', 'option_count': 0, 'exercise_assignment': {'status': 'none'}},
        watch_intent={'intents': [{'intent_id': 'watch-intent:abc', 'symbol': 'ABC', 'roles': ['curiosity']}]},
        thesis_registry={
            'theses': [
                {
                    'thesis_id': 'thesis:abc',
                    'instrument': 'ABC',
                    'linked_watch_intent': 'watch-intent:abc',
                    'status': 'watch',
                    'maturity': 'seed',
                    'required_confirmations': ['source-backed confirmation'],
                }
            ]
        },
        opportunity_queue={
            'candidates': [
                {
                    'candidate_id': 'opportunity:abc',
                    'instrument': 'ABC',
                    'theme': 'new demand inflection',
                    'status': 'candidate',
                    'score': 8.1,
                    'promotion_reason': 'scanner_unknown_discovery',
                }
            ]
        },
        invalidator_ledger={
            'invalidators': [
                {
                    'invalidator_id': 'invalidator:abc',
                    'description': 'packet staleness',
                    'status': 'open',
                    'hit_count': 1,
                }
            ]
        },
        campaign_board={
            'status': 'pass',
            'discord_live_board_markdown': 'Finance｜Live Board\n1) Campaign ABC',
            'campaigns': [{
                'campaign_id': 'campaign:abc',
                'human_title': 'ABC campaign',
            }],
        },
        shadow_delta=True,
    )

    errors, warnings = validate(report, packet, judgment, validation)

    assert report['renderer_id'] == 'thesis-delta-shadow-deterministic-v1'
    assert 'ABC: new demand inflection' in report['markdown']
    assert 'shadow' in report['markdown'].lower()
    assert 'discord_primary_markdown' in report
    assert 'discord_thread_seed_markdown' in report
    assert report['object_alias_map']['T1'].startswith('现有 Thesis')
    assert report['object_alias_map']['campaign:abc'] == 'ABC campaign'
    assert report['starter_queries']
    assert 'why campaign:abc' in report['starter_queries']
    assert report['followup_bundle_path'].endswith('.json')
    assert report['options_iv_surface_summary']['authority'] == 'source_context_only_not_judgment_wake_threshold_or_execution'
    assert report['options_iv_authority'] == 'source_context_only_not_judgment_wake_threshold_or_execution'
    assert not errors
    assert not warnings
