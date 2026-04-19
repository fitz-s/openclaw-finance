from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_followup_thread_registry_repair import prune_threads, repair_registry, upgrade_record


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
        'updated_at': '2026-04-17T13:13:07.434Z',
        'account_id': 'default',
        'channel_id': '1479790104490016808',
        'root_message_id': '149',
        'report_id': 'R1',
        'followup_bundle_path': str(bundle),
        'starter_queries': ['why A1'],
        'rule': 'Thread UI only; rehydrate follow-up from bundle, not raw thread history.',
    })
    assert changed is True
    assert upgraded['account_id'] == 'default'
    assert upgraded['allowed_reply_account_ids'] == ['default']
    assert upgraded['allowed_reply_agent'] == 'Mars'
    assert upgraded['updated_at'] != upgraded['last_repaired_at']
    assert upgraded['created_at'] == '2026-04-17T13:13:07.434Z'
    assert upgraded['last_activity_at'].startswith('2026-04-17T13:13:07.434')
    assert upgraded['inactive_after_hours'] == 72
    assert upgraded['lifecycle_status'] == 'active'
    assert upgraded['campaign_board_ref'].endswith('campaign-board.json')
    assert upgraded['campaign_cache_ref'].endswith('campaign-cache.json')
    assert upgraded['followup_context_router_path'].endswith('finance_followup_context_router.py')
    assert 'trace' in upgraded['allowed_verbs']
    assert 'why campaign:abc' in upgraded['starter_queries']
    assert upgraded['object_alias_map']['campaign:abc'] == 'Energy scout'
    assert 'Only Mars/default may reply' in upgraded['rule']


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
    assert payload['owner_account_id'] == 'default'
    assert payload['owner_agent_label'] == 'Mars'
    assert payload['max_records'] == 100
    assert payload['threads']['149']['campaign_cache_ref'].endswith('campaign-cache.json')
    assert 'sources campaign:abc' in payload['threads']['149']['starter_queries']


def test_prune_threads_drops_expired_missing_bundle_and_over_cap(tmp_path) -> None:
    bundle = tmp_path / 'live.json'
    bundle.write_text('{}')
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    kept, stats = prune_threads(
        {
            'newer': {'updated_at': '2026-04-16T00:00:00Z', 'followup_bundle_path': str(bundle)},
            'older': {'updated_at': '2026-03-01T00:00:00Z', 'followup_bundle_path': str(bundle)},
            'missing': {'updated_at': '2026-04-16T00:00:00Z', 'followup_bundle_path': str(tmp_path / 'missing.json')},
            'also_new': {'updated_at': '2026-04-15T00:00:00Z', 'followup_bundle_path': str(bundle)},
        },
        ttl_days=30,
        max_records=1,
        inactive_after_hours=72,
        prune_missing_bundle=True,
        now=now,
    )
    assert list(kept) == ['newer']
    assert stats['dropped_expired_count'] == 1
    assert stats['dropped_missing_bundle_count'] == 1
    assert stats['dropped_over_cap_count'] == 1


def test_prune_threads_drops_inactive_after_72h(tmp_path) -> None:
    bundle = tmp_path / 'live.json'
    bundle.write_text('{}')
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    kept, stats = prune_threads(
        {
            'inactive': {'updated_at': '2026-04-13T00:00:00Z', 'last_activity_at': '2026-04-13T00:00:00Z', 'followup_bundle_path': str(bundle)},
            'active': {'updated_at': '2026-04-13T00:00:00Z', 'last_user_message_at': '2026-04-16T23:00:00Z', 'followup_bundle_path': str(bundle)},
        },
        ttl_days=30,
        max_records=10,
        inactive_after_hours=72,
        prune_missing_bundle=True,
        now=now,
    )
    assert list(kept) == ['active']
    assert stats['dropped_inactive_count'] == 1
