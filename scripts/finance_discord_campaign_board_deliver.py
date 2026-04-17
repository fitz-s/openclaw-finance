#!/usr/bin/env python3
"""Deliver finance campaign boards through the existing OpenClaw message CLI.

This is the Phase 8 cutover adapter that avoids gateway/config changes. It is
idempotent against local state: known board message ids are edited, missing ids
are sent once and recorded. Thread creation is optional and capped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OPENCLAW = Path('/Users/leofitz/.npm-global/bin/openclaw')
PACKAGE = STATE / 'discord-campaign-board-package.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
CAMPAIGN_THREADS = STATE / 'campaign-threads.json'
REPORT_ENVELOPE = STATE / 'finance-decision-report-envelope.json'
FOLLOWUP_THREADS = STATE / 'finance-discord-followup-threads.json'
RUNTIME = STATE / 'discord-campaign-board-runtime.json'
REPORT = STATE / 'discord-campaign-board-delivery-report.json'
DEFAULT_TARGET = 'channel:1479790104490016808'
BOARD_KEYS = (
    ('live', 'live_board_markdown', 'Finance Live Board'),
    ('scout', 'scout_board_markdown', 'Finance Peacetime Board'),
    ('risk', 'risk_board_markdown', 'Finance Risk Board'),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def hash_text(text: str) -> str:
    return 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def default_runtime() -> dict[str, Any]:
    return {
        'generated_at': now_iso(),
        'boards_enabled': False,
        'threads_enabled': False,
        'target': DEFAULT_TARGET,
        'channel': 'discord',
        'max_threads_per_run': 2,
        'boards': {},
        'threads': {},
        'no_execution': True,
    }


def load_runtime(path: Path = RUNTIME) -> dict[str, Any]:
    runtime = load_json_safe(path, {}) or {}
    base = default_runtime()
    base.update(runtime)
    base['boards'] = runtime.get('boards') if isinstance(runtime.get('boards'), dict) else {}
    base['threads'] = runtime.get('threads') if isinstance(runtime.get('threads'), dict) else {}
    return base


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def extract_id(payload: dict[str, Any]) -> str | None:
    for key in ['messageId', 'message_id', 'id', 'threadId', 'thread_id']:
        if payload.get(key):
            return str(payload[key])
    for nested_key in ['payload', 'result', 'thread']:
        nested = payload.get(nested_key) if isinstance(payload.get(nested_key), dict) else {}
        if nested:
            found = extract_id(nested)
            if found:
                return found
    if payload.get('ok') is True and isinstance(payload.get('thread'), dict) and payload['thread'].get('id'):
        return str(payload['thread']['id'])
    return None


def run_openclaw(args: list[str], *, apply: bool) -> dict[str, Any]:
    cmd = [str(OPENCLAW), *args, '--json']
    if not apply:
        cmd.append('--dry-run')
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    parsed: dict[str, Any] = {}
    if stdout:
        try:
            parsed = json.loads(stdout[stdout.find('{'):])
        except Exception:
            parsed = {'stdout': stdout[-1000:]}
    return {
        'returncode': proc.returncode,
        'ok': proc.returncode == 0,
        'stdout': stdout[-1000:],
        'stderr': stderr[-1000:],
        'json': parsed,
        'cmd_preview': ' '.join(cmd[:6]),
    }


def board_operations(package: dict[str, Any], runtime: dict[str, Any]) -> list[dict[str, Any]]:
    target = str(runtime.get('target') or DEFAULT_TARGET)
    boards = runtime.get('boards') if isinstance(runtime.get('boards'), dict) else {}
    ops: list[dict[str, Any]] = []
    for board_key, field, title in BOARD_KEYS:
        content = str(package.get(field) or '').strip()
        if not content:
            continue
        current = boards.get(board_key) if isinstance(boards.get(board_key), dict) else {}
        message_id = current.get('message_id')
        content_hash = hash_text(content)
        if message_id:
            action = 'edit_board'
            args = ['message', 'edit', '--channel', 'discord', '--target', target, '--message-id', str(message_id), '--message', content]
        else:
            action = 'send_board'
            args = ['message', 'send', '--channel', 'discord', '--target', target, '--message', content]
        ops.append({
            'action': action,
            'board_key': board_key,
            'title': title,
            'target': target,
            'message_id': message_id,
            'content_hash': content_hash,
            'args': args,
        })
    return ops


def thread_seed(campaign: dict[str, Any]) -> str:
    lines = [
        f"{campaign.get('human_title') or campaign.get('campaign_id')}｜深挖入口",
        '',
        f"为什么现在：{campaign.get('why_now_delta') or 'n/a'}",
        f"为什么还不是动作：{campaign.get('why_not_now') or 'review-only'}",
        f"确认点：{'; '.join(campaign.get('confirmations_needed', [])[:3]) if isinstance(campaign.get('confirmations_needed'), list) else 'n/a'}",
        '',
        f"可问：why {campaign.get('campaign_id')} / challenge {campaign.get('campaign_id')} / sources {campaign.get('campaign_id')}",
    ]
    return '\n'.join(lines).strip()


def thread_operations(campaign_board: dict[str, Any], runtime: dict[str, Any]) -> list[dict[str, Any]]:
    if not runtime.get('threads_enabled'):
        return []
    target = str(runtime.get('target') or DEFAULT_TARGET)
    existing = runtime.get('threads') if isinstance(runtime.get('threads'), dict) else {}
    max_threads = int(runtime.get('max_threads_per_run', 2))
    campaigns = [c for c in campaign_board.get('campaigns', []) if isinstance(c, dict) and c.get('thread_key')]
    campaigns.sort(key=lambda c: (c.get('board_class') != 'live', -float(c.get('priority_score') or 0)))
    ops: list[dict[str, Any]] = []
    for campaign in campaigns:
        thread_key = str(campaign.get('thread_key'))
        if thread_key in existing and existing.get(thread_key, {}).get('discord_thread_id'):
            continue
        if len(ops) >= max_threads:
            break
        name = str(campaign.get('human_title') or campaign.get('campaign_id') or 'Finance Campaign')[:90]
        ops.append({
            'action': 'create_thread',
            'thread_key': thread_key,
            'campaign_id': campaign.get('campaign_id'),
            'target': target,
            'thread_name': name,
            'seed': thread_seed(campaign),
            'content_hash': hash_text(thread_seed(campaign)),
            'args': ['message', 'thread', 'create', '--channel', 'discord', '--target', target, '--thread-name', name, '--message', thread_seed(campaign)],
        })
    for campaign in campaigns:
        thread_key = str(campaign.get('thread_key'))
        prior = existing.get(thread_key) if isinstance(existing.get(thread_key), dict) else {}
        thread_id = prior.get('discord_thread_id')
        if thread_id and not prior.get('seed_sent'):
            ops.append({
                'action': 'reply_thread_seed',
                'thread_key': thread_key,
                'campaign_id': campaign.get('campaign_id'),
                'target': str(thread_id),
                'seed': thread_seed(campaign),
                'content_hash': hash_text(thread_seed(campaign)),
                'args': ['message', 'thread', 'reply', '--channel', 'discord', '--target', str(thread_id), '--message', thread_seed(campaign)],
            })
            break
    return ops


def apply_operations(package: dict[str, Any], campaign_board: dict[str, Any], runtime: dict[str, Any], *, apply: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    operations = []
    if runtime.get('boards_enabled'):
        operations.extend(board_operations(package, runtime))
    operations.extend(thread_operations(campaign_board, runtime))
    boards = dict(runtime.get('boards') if isinstance(runtime.get('boards'), dict) else {})
    threads = dict(runtime.get('threads') if isinstance(runtime.get('threads'), dict) else {})
    results = []
    for op in operations:
        result = run_openclaw(op['args'], apply=apply)
        record = {k: v for k, v in op.items() if k != 'args'}
        record['result'] = result
        if result['ok']:
            external_id = extract_id(result.get('json', {}))
            if op['action'] in {'send_board', 'edit_board'}:
                board_key = str(op['board_key'])
                boards[board_key] = {
                    'message_id': external_id or op.get('message_id'),
                    'last_hash': op.get('content_hash'),
                    'updated_at': now_iso(),
                    'target': op.get('target'),
                }
            elif op['action'] == 'create_thread':
                thread_key = str(op['thread_key'])
                threads[thread_key] = {
                    'discord_thread_id': external_id,
                    'campaign_id': op.get('campaign_id'),
                    'thread_status': 'active' if external_id else 'unknown',
                    'created_at': now_iso(),
                    'target': op.get('target'),
                    'seed_sent': False,
                }
            elif op['action'] == 'reply_thread_seed':
                thread_key = str(op['thread_key'])
                previous = threads.get(thread_key) if isinstance(threads.get(thread_key), dict) else {}
                threads[thread_key] = {
                    **previous,
                    'discord_thread_id': previous.get('discord_thread_id') or op.get('target'),
                    'campaign_id': op.get('campaign_id'),
                    'thread_status': previous.get('thread_status') or 'active',
                    'seed_sent': True,
                    'seed_sent_at': now_iso(),
                    'target': previous.get('target'),
                }
        results.append(record)
    runtime['boards'] = boards
    runtime['threads'] = threads
    runtime['updated_at'] = now_iso()
    return runtime, results


def build_report(runtime: dict[str, Any], results: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    return {
        'generated_at': now_iso(),
        'status': 'pass' if all(item.get('result', {}).get('ok') for item in results) else 'degraded' if results else 'pass',
        'apply': apply,
        'result_count': len(results),
        'results': results,
        'runtime_path': str(RUNTIME),
        'no_execution': True,
    }


def sync_followup_thread_registry(runtime: dict[str, Any], campaign_board: dict[str, Any], report_envelope: dict[str, Any], *, path: Path = FOLLOWUP_THREADS) -> dict[str, Any]:
    """Register campaign threads with OpenClaw's existing finance follow-up hook."""
    try:
        existing = load_json_safe(path, {}) or {}
    except Exception:
        existing = {}
    threads = existing.get('threads') if isinstance(existing.get('threads'), dict) else {}
    campaigns = {
        str(campaign.get('campaign_id')): campaign
        for campaign in campaign_board.get('campaigns', []) if isinstance(campaign, dict) and campaign.get('campaign_id')
    }
    runtime_threads = runtime.get('threads') if isinstance(runtime.get('threads'), dict) else {}
    synced = 0
    for local_thread_key, record in runtime_threads.items():
        if not isinstance(record, dict) or not record.get('discord_thread_id'):
            continue
        thread_id = str(record['discord_thread_id'])
        campaign = campaigns.get(str(record.get('campaign_id')) or '')
        starter_queries = report_envelope.get('starter_queries') if isinstance(report_envelope.get('starter_queries'), list) else []
        object_alias_map = report_envelope.get('object_alias_map') if isinstance(report_envelope.get('object_alias_map'), dict) else {}
        if campaign:
            starter_queries = [
                f"why {campaign.get('campaign_id')}",
                f"challenge {campaign.get('campaign_id')}",
                f"sources {campaign.get('campaign_id')}",
                f"trace {campaign.get('campaign_id')}",
                *starter_queries,
            ]
        dedup_queries: list[str] = []
        seen: set[str] = set()
        for query in starter_queries:
            key = str(query).strip()
            if key and key not in seen:
                seen.add(key)
                dedup_queries.append(key)
        threads[thread_id] = {
            'updated_at': now_iso(),
            'account_id': 'default',
            'channel_id': str(record.get('target') or DEFAULT_TARGET).replace('channel:', ''),
            'root_message_id': str(record.get('root_message_id') or record.get('discord_thread_id') or ''),
            'campaign_id': record.get('campaign_id'),
            'thread_key': local_thread_key,
            'report_id': report_envelope.get('report_id'),
            'followup_bundle_path': report_envelope.get('followup_bundle_path'),
            'campaign_board_ref': str(CAMPAIGN_BOARD),
            'campaign_cache_ref': str(STATE / 'campaign-cache.json'),
            'starter_queries': dedup_queries[:12],
            'object_alias_map': object_alias_map,
            'rule': 'Thread UI only; rehydrate follow-up from bundle + campaign board/cache + selected handle. Bot messages ignored.',
        }
        synced += 1
    payload = {
        'generated_at': now_iso(),
        'threads': threads,
    }
    atomic_write_json(path, payload)
    return {'status': 'pass', 'synced_count': synced, 'path': str(path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', default=str(PACKAGE))
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--runtime', default=str(RUNTIME))
    parser.add_argument('--report', default=str(REPORT))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    runtime_path = Path(args.runtime)
    report_path = Path(args.report)
    if not safe_state_path(runtime_path) or not safe_state_path(report_path):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    package = load_json_safe(Path(args.package), {}) or {}
    campaign_board = load_json_safe(Path(args.campaign_board), {}) or {}
    runtime = load_runtime(runtime_path)
    runtime, results = apply_operations(package, campaign_board, runtime, apply=args.apply)
    report_envelope = load_json_safe(REPORT_ENVELOPE, {}) or {}
    followup_sync = sync_followup_thread_registry(runtime, campaign_board, report_envelope)
    atomic_write_json(runtime_path, runtime)
    report = build_report(runtime, results, apply=args.apply)
    report['followup_thread_registry_sync'] = followup_sync
    atomic_write_json(report_path, report)
    print(json.dumps({'status': report['status'], 'apply': args.apply, 'result_count': report['result_count'], 'report': str(report_path)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
