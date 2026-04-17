from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_discord_campaign_board_deliver import board_operations, build_report, default_runtime, thread_operations


def _package() -> dict:
    return {
        'live_board_markdown': 'Finance｜Live Board\n1) A',
        'scout_board_markdown': 'Finance｜Peacetime Board\n1) B',
        'risk_board_markdown': 'Finance｜Risk Board\n1) C',
    }


def _campaign_board() -> dict:
    return {'campaigns': [{
        'campaign_id': 'campaign:a',
        'thread_key': 'thread:a',
        'human_title': 'Campaign A',
        'board_class': 'live',
        'priority_score': 10,
        'why_now_delta': 'changed',
        'why_not_now': 'review only',
        'confirmations_needed': ['x'],
    }]}


def test_board_operations_send_when_message_ids_missing() -> None:
    runtime = default_runtime()
    runtime['boards_enabled'] = True
    ops = board_operations(_package(), runtime)
    assert [op['action'] for op in ops] == ['send_board', 'send_board', 'send_board']
    assert all('--dry-run' not in op['args'] for op in ops)


def test_board_operations_edit_when_message_ids_exist() -> None:
    runtime = default_runtime()
    runtime['boards_enabled'] = True
    runtime['boards'] = {'live': {'message_id': '123'}}
    ops = board_operations(_package(), runtime)
    live = next(op for op in ops if op['board_key'] == 'live')
    assert live['action'] == 'edit_board'
    assert '--message-id' in live['args']
    assert '123' in live['args']


def test_thread_operations_create_only_when_enabled_and_unbound() -> None:
    runtime = default_runtime()
    assert thread_operations(_campaign_board(), runtime) == []
    runtime['threads_enabled'] = True
    ops = thread_operations(_campaign_board(), runtime)
    assert len(ops) == 1
    assert ops[0]['action'] == 'create_thread'
    assert ops[0]['thread_key'] == 'thread:a'


def test_thread_operations_respect_zero_auto_create_cap() -> None:
    runtime = default_runtime()
    runtime['threads_enabled'] = True
    runtime['max_threads_per_run'] = 0
    assert thread_operations(_campaign_board(), runtime) == []


def test_delivery_report_is_degraded_only_on_failed_results() -> None:
    report = build_report(default_runtime(), [{'result': {'ok': True}}], apply=False)
    assert report['status'] == 'pass'
    report = build_report(default_runtime(), [{'result': {'ok': False}}], apply=True)
    assert report['status'] == 'degraded'
    assert report['no_execution'] is True
