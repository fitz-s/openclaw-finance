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
from datetime import datetime, timedelta, timezone
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
OWNER_ACCOUNT_ID = 'default'
OWNER_AGENT_LABEL = 'Mars'
DEFAULT_TTL_DAYS = 30
DEFAULT_MAX_RECORDS = 100
DEFAULT_INACTIVE_HOURS = 72


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


def parse_iso(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None


def bundle_path_exists(value: Any) -> bool:
    text = str(value or '').strip()
    if not text:
        return False
    path = Path(text)
    if not path.is_absolute():
        path = FINANCE / path
    return path.exists()


def latest_activity_time(record: dict[str, Any]) -> datetime | None:
    candidates = [
        parse_iso(record.get('last_activity_at')),
        parse_iso(record.get('last_user_message_at')),
        parse_iso(record.get('last_bot_reply_at')),
        parse_iso(record.get('updated_at')),
        parse_iso(record.get('created_at')),
    ]
    candidates = [item for item in candidates if item is not None]
    return max(candidates) if candidates else None


def lifecycle_fields(record: dict[str, Any], *, default_time: str) -> dict[str, Any]:
    created_at = str(record.get('created_at') or record.get('updated_at') or default_time)
    activity = latest_activity_time(record)
    last_activity_at = activity.isoformat().replace('+00:00', 'Z') if activity else created_at
    return {
        'created_at': created_at,
        'last_user_message_at': record.get('last_user_message_at'),
        'last_bot_reply_at': record.get('last_bot_reply_at'),
        'last_activity_at': str(record.get('last_activity_at') or last_activity_at),
        'inactive_after_hours': int(record.get('inactive_after_hours') or DEFAULT_INACTIVE_HOURS),
        'lifecycle_status': str(record.get('lifecycle_status') or 'active'),
    }


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
    upgraded['updated_at'] = str(upgraded.get('updated_at') or now_iso())
    upgraded['last_repaired_at'] = now_iso()
    upgraded.update(lifecycle_fields(upgraded, default_time=upgraded['updated_at']))
    upgraded['account_id'] = OWNER_ACCOUNT_ID
    upgraded['allowed_reply_account_ids'] = [OWNER_ACCOUNT_ID]
    upgraded['allowed_reply_agent'] = OWNER_AGENT_LABEL
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
        '+ selected handle. Only Mars/default may reply. Use finance_followup_context_router.py; '
        'bot messages ignored.'
    )
    after = json.dumps(upgraded, sort_keys=True, ensure_ascii=False)
    return upgraded, before != after


def prune_threads(
    threads: dict[str, dict[str, Any]],
    *,
    ttl_days: int = DEFAULT_TTL_DAYS,
    max_records: int = DEFAULT_MAX_RECORDS,
    inactive_after_hours: int = DEFAULT_INACTIVE_HOURS,
    prune_missing_bundle: bool = True,
    now: datetime | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(ttl_days, 0))
    kept: dict[str, dict[str, Any]] = {}
    stats = {
        'dropped_expired_count': 0,
        'dropped_missing_bundle_count': 0,
        'dropped_over_cap_count': 0,
        'dropped_inactive_count': 0,
    }
    for thread_id, record in threads.items():
        updated = parse_iso(record.get('updated_at')) or parse_iso(record.get('last_repaired_at')) or now
        activity = latest_activity_time(record) or updated
        if ttl_days >= 0 and updated < cutoff:
            stats['dropped_expired_count'] += 1
            continue
        if inactive_after_hours >= 0 and activity < now - timedelta(hours=inactive_after_hours):
            stats['dropped_inactive_count'] += 1
            continue
        if prune_missing_bundle and not bundle_path_exists(record.get('followup_bundle_path')):
            stats['dropped_missing_bundle_count'] += 1
            continue
        kept[str(thread_id)] = record
    ordered = sorted(
        kept.items(),
        key=lambda item: parse_iso(item[1].get('updated_at')) or parse_iso(item[1].get('last_repaired_at')) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    if max_records >= 0 and len(ordered) > max_records:
        stats['dropped_over_cap_count'] = len(ordered) - max_records
        ordered = ordered[:max_records]
    return dict(ordered), stats


def repair_registry(
    path: Path = REGISTRY,
    *,
    envelope_path: Path = ENVELOPE,
    ttl_days: int = DEFAULT_TTL_DAYS,
    max_records: int = DEFAULT_MAX_RECORDS,
    inactive_after_hours: int = DEFAULT_INACTIVE_HOURS,
    prune_missing_bundle: bool = True,
) -> dict[str, Any]:
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
    pruned, prune_stats = prune_threads(
        repaired,
        ttl_days=ttl_days,
        max_records=max_records,
        inactive_after_hours=inactive_after_hours,
        prune_missing_bundle=prune_missing_bundle,
    )
    result = {
        'generated_at': now_iso(),
        'ttl_days': ttl_days,
        'max_records': max_records,
        'owner_account_id': OWNER_ACCOUNT_ID,
        'owner_agent_label': OWNER_AGENT_LABEL,
        'inactive_after_hours': inactive_after_hours,
        'threads': pruned,
    }
    atomic_write_json(path, result)
    return {
        'status': 'pass',
        'path': str(path),
        'thread_count': len(pruned),
        'changed_count': changed,
        **prune_stats,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Repair finance Discord follow-up thread registry records.')
    parser.add_argument('--registry', default=str(REGISTRY))
    parser.add_argument('--envelope', default=str(ENVELOPE))
    parser.add_argument('--ttl-days', type=int, default=DEFAULT_TTL_DAYS)
    parser.add_argument('--max-records', type=int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument('--inactive-hours', type=int, default=DEFAULT_INACTIVE_HOURS)
    parser.add_argument('--keep-missing-bundles', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)
    report = repair_registry(
        Path(args.registry),
        envelope_path=Path(args.envelope),
        ttl_days=args.ttl_days,
        max_records=args.max_records,
        inactive_after_hours=args.inactive_hours,
        prune_missing_bundle=not args.keep_missing_bundles,
    )
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
