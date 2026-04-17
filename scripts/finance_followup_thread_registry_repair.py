#!/usr/bin/env python3
"""Repair OpenClaw finance Discord follow-up thread registry records.

The parent Discord delivery runtime owns thread creation, but the finance repo
owns the canonical rehydration artifacts. This tool upgrades old parent-created
records so follow-up threads point at the full operator bundle and campaign
cache, not just a bare report-reader JSON path.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
REGISTRY = STATE / 'finance-discord-followup-threads.json'
ENVELOPE = STATE / 'finance-decision-report-envelope.json'
LATEST_BUNDLE = STATE / 'report-reader' / 'latest.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
CAMPAIGN_CACHE = STATE / 'campaign-cache.json'
FOLLOWUP_ROUTER = FINANCE / 'scripts' / 'finance_followup_context_router.py'
ANSWER_GUARD = FINANCE / 'scripts' / 'finance_followup_answer_guard.py'
ALLOWED_VERBS = ['why', 'challenge', 'compare', 'scenario', 'sources', 'trace', 'expand']


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def load_bundle(path_value: Any) -> dict[str, Any]:
    path = Path(str(path_value or ''))
    if not path.is_absolute():
        path = FINANCE / path
    bundle = load_json_safe(path, None)
    if isinstance(bundle, dict):
        return bundle
    latest = load_json_safe(LATEST_BUNDLE, {})
    return latest if isinstance(latest, dict) else {}


def merge_aliases(*maps: Any) -> dict[str, str]:
    merged: dict[str, str] = {}
    for value in maps:
        if not isinstance(value, dict):
            continue
        for handle, label in value.items():
            handle_text = str(handle).strip()
            label_text = str(label).strip()
            if handle_text and label_text and handle_text not in merged:
                merged[handle_text] = label_text
    return merged


def strip_campaign_aliases(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        str(handle): label
        for handle, label in value.items()
        if not str(handle).startswith('campaign:')
    }


def campaign_alias_queries(campaign_alias_map: dict[str, Any], *, limit: int = 4) -> list[str]:
    queries: list[str] = []
    for campaign_id in list(campaign_alias_map)[:limit]:
        campaign = str(campaign_id).strip()
        if not campaign:
            continue
        queries.extend([
            f'why {campaign}',
            f'challenge {campaign}',
            f'sources {campaign}',
            f'trace {campaign}',
        ])
    return queries


def dedup(values: list[str], *, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def upgrade_record(record: dict[str, Any], *, envelope: dict[str, Any] | None = None) -> tuple[dict[str, Any], bool]:
    envelope = envelope or {}
    before = json.dumps(record, sort_keys=True, ensure_ascii=False)
    bundle_path = record.get('followup_bundle_path') or envelope.get('followup_bundle_path') or str(LATEST_BUNDLE)
    bundle = load_bundle(bundle_path)
    campaign_alias_map = bundle.get('campaign_alias_map') if isinstance(bundle.get('campaign_alias_map'), dict) else {}
    top_campaign_aliases = dict(list(campaign_alias_map.items())[:4])
    aliases = merge_aliases(
        top_campaign_aliases,
        strip_campaign_aliases(record.get('object_alias_map')),
        strip_campaign_aliases(envelope.get('object_alias_map')),
        strip_campaign_aliases(bundle.get('object_alias_map')),
    )
    starter_queries = dedup([
        *as_str_list(record.get('starter_queries')),
        *as_str_list(envelope.get('starter_queries')),
        *as_str_list(bundle.get('starter_queries')),
        *campaign_alias_queries(campaign_alias_map),
    ])
    upgraded = dict(record)
    upgraded['updated_at'] = now_iso()
    upgraded['account_id'] = str(upgraded.get('account_id') or 'default')
    upgraded['root_message_id'] = str(upgraded.get('root_message_id') or upgraded.get('thread_id') or '')
    upgraded['report_id'] = upgraded.get('report_id') or envelope.get('report_id') or bundle.get('report_handle')
    upgraded['followup_bundle_path'] = str(bundle_path)
    upgraded['campaign_board_ref'] = str(upgraded.get('campaign_board_ref') or bundle.get('campaign_board_ref') or envelope.get('campaign_board_ref') or CAMPAIGN_BOARD)
    upgraded['campaign_cache_ref'] = str(upgraded.get('campaign_cache_ref') or bundle.get('campaign_cache_ref') or CAMPAIGN_CACHE)
    upgraded['followup_context_router_path'] = str(upgraded.get('followup_context_router_path') or FOLLOWUP_ROUTER)
    upgraded['answer_guard_path'] = str(upgraded.get('answer_guard_path') or ANSWER_GUARD)
    upgraded['allowed_verbs'] = dedup([
        *as_str_list(upgraded.get('allowed_verbs')),
        *ALLOWED_VERBS,
    ], limit=len(ALLOWED_VERBS))
    upgraded['starter_queries'] = starter_queries
    upgraded['object_alias_map'] = aliases
    upgraded['rule'] = (
        'Thread UI only; rehydrate follow-up from followup_bundle_path + campaign board/cache '
        '+ selected handle. Use finance_followup_context_router.py; bot messages ignored.'
    )
    after = json.dumps(upgraded, sort_keys=True, ensure_ascii=False)
    return upgraded, before != after


def repair_registry(path: Path = REGISTRY, *, envelope_path: Path = ENVELOPE) -> dict[str, Any]:
    payload = load_json_safe(path, {}) or {}
    threads = payload.get('threads') if isinstance(payload.get('threads'), dict) else {}
    envelope = load_json_safe(envelope_path, {}) or {}
    repaired: dict[str, Any] = {}
    changed = 0
    for thread_id, record in threads.items():
        if not isinstance(record, dict):
            continue
        upgraded, did_change = upgrade_record(record, envelope=envelope if isinstance(envelope, dict) else {})
        repaired[str(thread_id)] = upgraded
        if did_change:
            changed += 1
    result = {
        'generated_at': now_iso(),
        'threads': repaired,
    }
    atomic_write_json(path, result)
    return {
        'status': 'pass',
        'path': str(path),
        'thread_count': len(repaired),
        'changed_count': changed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Repair finance Discord follow-up thread registry records.')
    parser.add_argument('--registry', default=str(REGISTRY))
    parser.add_argument('--envelope', default=str(ENVELOPE))
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)
    report = repair_registry(Path(args.registry), envelope_path=Path(args.envelope))
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
