from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))

from export_reviewer_report_packets import export_packets


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_export_reviewer_packets_sanitizes_runtime_state(tmp_path) -> None:
    state = tmp_path / 'state'
    reader = state / 'report-reader'
    for idx, report_id in enumerate(['R1', 'R2', 'R3']):
        path = reader / f'{report_id}.json'
        _write_json(path, {
            'bundle_id': f'rb:{report_id}',
            'report_handle': report_id,
            'generated_at': f'2026-04-17T13:0{idx}:00Z',
            'report_hash': 'sha256:x',
            'starter_queries': ['why A1'],
            'followup_digest': [f'{report_id}: digest'],
            'object_alias_map': {'A1': 'Agenda'},
            'object_cards': [{
                'handle': 'A1',
                'type': 'agenda',
                'label': 'Agenda',
                'attention_justification': 'check attention slot',
                'required_questions': ['what changed?'],
            }],
            'campaigns': [{
                'campaign_id': 'campaign:1',
                'human_title': 'Energy scout',
                'why_now_delta': 'changed',
            }],
        })
        path.touch()
    _write_json(state / 'finance-decision-report-envelope.json', {
        'report_id': 'R3',
        'discord_primary_markdown': 'Finance｜Report\nFact\n- x',
        'discord_thread_seed_markdown': 'R3｜深挖入口',
    })
    _write_json(state / 'source-atoms' / 'latest-report.json', {
        'status': 'pass',
        'atom_count': 1,
        'atoms': [{
            'atom_id': 'atom:1',
            'source_id': 'source:reuters',
            'source_lane': 'news_policy_narrative',
            'candidate_type': 'unknown_discovery',
            'compliance_class': 'licensed',
            'raw_ref': 'raw:1',
            'raw_snippet': 'must not be exported',
        }],
    })
    _write_json(state / 'claim-graph.json', {
        'status': 'pass',
        'claim_count': 1,
        'claims': [{
            'claim_id': 'claim:1',
            'atom_id': 'atom:1',
            'subject': 'BNO',
            'predicate': 'mentions',
            'object': 'derived claim summary',
            'direction': 'bullish',
            'source_lane': 'news_policy_narrative',
        }],
    })
    _write_json(state / 'context-gaps.json', {
        'status': 'pass',
        'gap_count': 1,
        'gaps': [{
            'gap_id': 'gap:1',
            'subject': 'BNO',
            'missing_lane': 'corporate_filing',
            'why_load_bearing': 'needs issuer confirmation',
        }],
    })
    archive = state / 'report-archive' / 'R3'
    _write_json(archive / 'envelope.json', {
        'report_id': 'R3',
        'discord_primary_markdown': 'Finance｜Archived Report\nFact\n- archived',
        'discord_thread_seed_markdown': 'R3｜archive',
    })
    _write_json(archive / 'reader-bundle.json', {
        'bundle_id': 'rb:R3',
        'report_handle': 'R3',
        'object_cards': [],
        'campaigns': [],
    })
    _write_json(archive / 'source-atoms.json', {
        'status': 'pass',
        'atom_count': 1,
        'atoms': [{
            'atom_id': 'atom:archived',
            'source_id': 'source:sec_edgar',
            'source_lane': 'corp_filing_ir',
            'compliance_class': 'public',
            'raw_snippet': 'archived raw must not export',
        }],
    })
    _write_json(archive / 'claim-graph.json', {'status': 'pass', 'claim_count': 1, 'claims': [{'claim_id': 'claim:archived', 'atom_id': 'atom:archived', 'subject': 'R3'}]})
    _write_json(archive / 'context-gaps.json', {'status': 'pass', 'gap_count': 0, 'gaps': []})
    _write_json(archive / 'source-health.json', {'status': 'pass', 'source_count': 1, 'sources': [{'source_id': 'source:sec_edgar', 'freshness_status': 'fresh'}]})
    _write_json(archive / 'options-iv-surface.json', {'status': 'empty', 'summary': {'symbol_count': 0}})
    _write_json(archive / 'line-to-claim-refs.json', {'line_count': 2, 'matched_line_count': 1})
    _write_json(archive / 'manifest.json', {
        'contract': 'report-time-archive-v1',
        'report_id': 'R3',
        'exact_replay_available': True,
        'missing_required_artifacts': [],
        'artifacts': {
            'envelope': {'available': True, 'path': str(archive / 'envelope.json')},
            'reader_bundle': {'available': True, 'path': str(archive / 'reader-bundle.json')},
            'source_atoms': {'available': True, 'path': str(archive / 'source-atoms.json')},
            'claim_graph': {'available': True, 'path': str(archive / 'claim-graph.json')},
            'context_gaps': {'available': True, 'path': str(archive / 'context-gaps.json')},
            'source_health': {'available': True, 'path': str(archive / 'source-health.json')},
            'options_iv_surface': {'available': True, 'path': str(archive / 'options-iv-surface.json')},
            'line_to_claim_refs': {'available': True, 'path': str(archive / 'line-to-claim-refs.json')},
        },
    })
    source_health = tmp_path / 'source-health.json'
    _write_json(source_health, {
        'status': 'degraded',
        'source_count': 1,
        'summary': {'freshness': {'unknown': 1}},
        'sources': [{
            'source_id': 'source:reuters',
            'freshness_status': 'unknown',
            'rights_status': 'restricted',
            'breach_reasons': ['rights:restricted'],
        }],
    })

    out = tmp_path / 'out'
    result = export_packets(state_dir=state, out_dir=out, source_health_path=source_health, limit=2)
    index = json.loads((out / 'index.json').read_text())
    packets = [json.loads((out / item['file']).read_text()) for item in index['reports']]
    serialized = json.dumps(packets, ensure_ascii=False)

    assert result['packet_count'] == 2
    assert index['sanitization']['discord_conversation_included'] is False
    assert index['sanitization']['raw_licensed_snippets_included'] is False
    assert 'must not be exported' not in serialized
    assert 'raw_snippet' not in serialized or 'raw_snippet_included' in serialized
    assert all(packet['sanitization']['account_ids_included'] is False for packet in packets)
    assert any(packet['operator_surface']['operator_surface_available'] for packet in packets)
    archived = next(packet for packet in packets if packet['report_id'] == 'R3')
    assert archived['report_time_replay']['exact_replay_available'] is True
    assert archived['information_acquisition_snapshot']['scope'] == 'exact report-time archive snapshot'
    assert 'Archived Report' in archived['operator_surface']['discord_primary_markdown']
    assert 'archived raw must not export' not in json.dumps(archived, ensure_ascii=False)
