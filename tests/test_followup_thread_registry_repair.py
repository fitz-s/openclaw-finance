from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_followup_thread_registry_repair import repair_registry, upgrade_record


def test_upgrade_record_adds_campaign_rehydration_fields(tmp_path) -> None:
    bundle = tmp_path / 'R1.json'
    bundle.write_text(json.dumps({
        'report_handle': 'R1',
        'campaign_board_ref': str(tmp_path / 'campaign-board.json'),
        'campaign_cache_ref': str(tmp_path / 'campaign-cache.json'),
        'campaign_alias_map': {'campaign:abc': 'Energy scout'},
        'object_alias_map': {'A1': 'Agenda item'},
        'starter_queries': ['why A1'],
    }))
    upgraded, changed = upgrade_record({
        'account_id': 'default',
        'channel_id': '1479790104490016808',
        'root_message_id': '149',
        'report_id': 'R1',
        'followup_bundle_path': str(bundle),
        'starter_queries': ['why A1'],
        'rule': 'Thread UI only; rehydrate follow-up from bundle, not raw thread history.',
    })
    assert changed is True
    assert upgraded['campaign_board_ref'].endswith('campaign-board.json')
    assert upgraded['campaign_cache_ref'].endswith('campaign-cache.json')
    assert upgraded['followup_context_router_path'].endswith('finance_followup_context_router.py')
    assert 'trace' in upgraded['allowed_verbs']
    assert 'why campaign:abc' in upgraded['starter_queries']
    assert upgraded['object_alias_map']['campaign:abc'] == 'Energy scout'
    assert 'campaign board/cache' in upgraded['rule']


def test_repair_registry_updates_old_parent_created_thread(tmp_path) -> None:
    bundle = tmp_path / 'R1.json'
    bundle.write_text(json.dumps({
        'report_handle': 'R1',
        'campaign_alias_map': {'campaign:abc': 'Energy scout'},
        'starter_queries': ['why A1'],
    }))
    registry = tmp_path / 'finance-discord-followup-threads.json'
    registry.write_text(json.dumps({
        'threads': {
            '149': {
                'updated_at': '2026-04-17T13:13:07.434Z',
                'account_id': 'default',
                'channel_id': '1479790104490016808',
                'root_message_id': '149',
                'report_id': 'R1',
                'followup_bundle_path': str(bundle),
                'starter_queries': ['why A1'],
                'rule': 'Thread UI only; rehydrate follow-up from bundle, not raw thread history.',
            }
        }
    }))
    envelope = tmp_path / 'envelope.json'
    envelope.write_text(json.dumps({'report_id': 'R1'}))
    report = repair_registry(registry, envelope_path=envelope)
    payload = json.loads(registry.read_text())
    assert report['changed_count'] == 1
    assert payload['threads']['149']['campaign_cache_ref'].endswith('campaign-cache.json')
    assert 'sources campaign:abc' in payload['threads']['149']['starter_queries']
