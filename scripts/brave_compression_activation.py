#!/usr/bin/env python3
"""Budgeted Brave LLM Context / Answers compression activation.

Source review: /Users/leofitz/Downloads/review 2026-04-18.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from brave_answers_sidecar import OUT as ANSWERS_OUT, run_sidecar
from brave_budget_guard import DEFAULT_STATE as BUDGET_STATE, decide as budget_decide, normalize_state as normalize_budget_state
from brave_llm_context_fetcher import OUT as CONTEXT_OUT, fetch_context
from brave_search_fetcher_common import write_jsonl

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
QUERY_PACKS = STATE / 'query-packs' / 'scanner-planned.jsonl'
BRAVE_WEB = STATE / 'brave-web-search-results.jsonl'
BRAVE_NEWS = STATE / 'brave-news-search-results.jsonl'
ROUTER_STATE = STATE / 'offhours-source-router-state.json'
REPORT = STATE / 'brave-compression-activation-report.json'
CONTRACT = 'brave-compression-activation-v1'
REVIEW_SOURCE = '/Users/leofitz/Downloads/review 2026-04-18.md'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]], *, keep: int = 200) -> None:
    existing = load_jsonl(path)
    write_jsonl(path, (existing + rows)[-keep:])


def urls_from_record(record: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in ('result_urls', 'urls'):
        values = record.get(key)
        if isinstance(values, list):
            urls.extend(str(value) for value in values if isinstance(value, str) and value.startswith(('http://', 'https://')))
    results = record.get('results')
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and isinstance(item.get('url'), str):
                urls.append(item['url'])
    context_refs = record.get('context_refs')
    if isinstance(context_refs, list):
        for item in context_refs:
            if isinstance(item, dict) and isinstance(item.get('url'), str):
                urls.append(item['url'])
    seen = set()
    out = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def seed_urls(fetch_records: list[dict[str, Any]], *, limit: int = 4) -> list[str]:
    urls: list[str] = []
    for record in reversed(fetch_records):
        if record.get('status') not in {'ok', 'partial', 'dry_run'}:
            continue
        urls.extend(urls_from_record(record))
        if len(urls) >= limit:
            break
    dedup = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        dedup.append(url)
    return dedup[:limit]


def selected_packs(packs: list[dict[str, Any]], *, max_packs: int) -> list[dict[str, Any]]:
    valid = [
        pack for pack in packs
        if isinstance(pack, dict)
        and pack.get('query')
        and pack.get('no_execution') is True
        and pack.get('pack_is_not_authority') is True
    ]
    return valid[:max(0, max_packs)]


def aperture_from_router(router: dict[str, Any]) -> dict[str, Any] | None:
    aperture = router.get('session_aperture') if isinstance(router.get('session_aperture'), dict) else None
    if not aperture:
        return None
    keys = ['generated_at', 'aperture_id', 'session_class', 'is_offhours', 'is_long_gap', 'answers_budget_class', 'calendar_confidence']
    return {key: aperture.get(key) for key in keys if key in aperture}


def budget_check(kind: str, *, aperture: dict[str, Any] | None, budget_state_path: Path, dry_run: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    aperture_id = str((aperture or {}).get('aperture_id') or 'compression:manual')
    session_class = str((aperture or {}).get('session_class') or 'overnight_session')
    state = normalize_budget_state(
        load_json_safe(budget_state_path, {}) or {},
        aperture_id=aperture_id,
        session_class=session_class,
        now=datetime.now(timezone.utc),
    )
    state, decision = budget_decide(state, kind=kind, units=1, dry_run=dry_run)
    atomic_write_json(budget_state_path, state)
    decision['budget_guard_contract'] = 'brave-budget-guard-v1'
    decision['budget_state_path'] = str(budget_state_path)
    decision['aperture_id'] = aperture_id
    decision['session_class'] = session_class
    return decision, state


def context_pack_from(pack: dict[str, Any], urls: list[str], aperture: dict[str, Any] | None) -> dict[str, Any]:
    return {
        'pack_id': f"{pack.get('pack_id')}:llm-context",
        'lane': pack.get('lane') or 'news_policy_narrative',
        'purpose': 'source_reading',
        'query': pack.get('query'),
        'freshness': pack.get('freshness') or 'day',
        'selected_urls': urls[:4],
        'allowed_domains': pack.get('allowed_domains') if isinstance(pack.get('allowed_domains'), list) else [],
        'max_results': min(int(pack.get('max_results') or 5), 10),
        'authority_level': 'canonical_candidate',
        'session_aperture': aperture,
        'budget_request': {'requires_budget_guard': True, 'llm_context_units': 1, 'answers_units': 0, 'search_units': 0},
        'pack_is_not_authority': True,
        'compression_pack_not_authority': True,
        'no_execution': True,
    }


def answers_pack_from(pack: dict[str, Any], urls: list[str], aperture: dict[str, Any] | None) -> dict[str, Any]:
    prompt = (
        'Summarize only what these seed sources can support. '
        'Do not recommend trades. Cite every source-dependent claim.\n'
        f"Question: {pack.get('query')}\n"
        f"Seed URLs: {', '.join(urls[:4])}"
    )
    return {
        'pack_id': f"{pack.get('pack_id')}:answers-sidecar",
        'lane': pack.get('lane') or 'news_policy_narrative',
        'purpose': 'sidecar_synthesis',
        'authority_level': 'sidecar_only',
        'prompt': prompt,
        'query': pack.get('query'),
        'selected_urls': urls[:4],
        'session_aperture': aperture,
        'budget_request': {'requires_budget_guard': True, 'answers_units': 1, 'llm_context_units': 0, 'search_units': 0},
        'pack_is_not_authority': True,
        'compression_pack_not_authority': True,
        'no_execution': True,
    }


def blocked_result(pack: dict[str, Any] | None, *, kind: str, reason: str, budget_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'pack_id': pack.get('pack_id') if isinstance(pack, dict) else None,
        'kind': kind,
        'status': 'blocked',
        'reason': reason,
        'budget_decision': budget_decision,
        'records': [],
        'no_execution': True,
    }


def run_activation(
    *,
    query_packs_path: Path = QUERY_PACKS,
    web_records_path: Path = BRAVE_WEB,
    news_records_path: Path = BRAVE_NEWS,
    router_state_path: Path = ROUTER_STATE,
    budget_state_path: Path = BUDGET_STATE,
    report_path: Path = REPORT,
    context_out: Path = CONTEXT_OUT,
    answers_out: Path = ANSWERS_OUT,
    max_packs: int = 2,
    dry_run: bool = True,
    timeout: int = 30,
) -> dict[str, Any]:
    paths = [query_packs_path, web_records_path, news_records_path, router_state_path, budget_state_path, report_path, context_out, answers_out]
    if any(not safe_state_path(path) for path in paths):
        return {'status': 'blocked', 'blocking_reasons': ['unsafe_state_path'], 'no_execution': True}
    packs = load_jsonl(query_packs_path)
    fetch_records = load_jsonl(web_records_path) + load_jsonl(news_records_path)
    urls = seed_urls(fetch_records)
    router = load_json_safe(router_state_path, {}) or {}
    aperture = aperture_from_router(router)
    selected = selected_packs(packs, max_packs=max_packs)
    results: list[dict[str, Any]] = []
    context_records: list[dict[str, Any]] = []
    answer_records: list[dict[str, Any]] = []

    if not urls:
        for pack in selected or [None]:
            results.append(blocked_result(pack, kind='compression', reason='missing_seed_urls'))
    for pack in selected if urls else []:
        ctx_pack = context_pack_from(pack, urls, aperture)
        ctx_decision, _ = budget_check('llm_context', aperture=aperture, budget_state_path=budget_state_path, dry_run=dry_run)
        if ctx_decision.get('allowed') is True:
            record = fetch_context(ctx_pack, dry_run=dry_run, timeout=timeout)
            record['budget_decision'] = ctx_decision
            record['session_aperture'] = aperture
            record['compression_activation_runner'] = CONTRACT
            context_records.append(record)
            results.append({'pack_id': pack.get('pack_id'), 'kind': 'llm_context', 'status': record.get('status'), 'budget_decision': ctx_decision, 'records': [record], 'no_execution': True})
        else:
            results.append(blocked_result(pack, kind='llm_context', reason='budget_guard_denied', budget_decision=ctx_decision))

        ans_pack = answers_pack_from(pack, urls, aperture)
        ans_decision, _ = budget_check('answers', aperture=aperture, budget_state_path=budget_state_path, dry_run=dry_run)
        if ans_decision.get('allowed') is True:
            record = run_sidecar(ans_pack, dry_run=dry_run, timeout=timeout)
            record['budget_decision'] = ans_decision
            record['session_aperture'] = aperture
            record['compression_activation_runner'] = CONTRACT
            answer_records.append(record)
            results.append({'pack_id': pack.get('pack_id'), 'kind': 'answers', 'status': record.get('status'), 'budget_decision': ans_decision, 'records': [record], 'no_execution': True})
        else:
            results.append(blocked_result(pack, kind='answers', reason='budget_guard_denied', budget_decision=ans_decision))

    if context_records:
        append_jsonl(context_out, context_records)
    if answer_records:
        append_jsonl(answers_out, answer_records)

    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get('status') or 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    report = {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': CONTRACT,
        'review_source': REVIEW_SOURCE,
        'dry_run': dry_run,
        'input_pack_count': len(packs),
        'selected_pack_count': len(selected),
        'seed_url_count': len(urls),
        'context_record_count': len(context_records),
        'answer_record_count': len(answer_records),
        'budget_checked_count': sum(1 for result in results if isinstance(result.get('budget_decision'), dict)),
        'budget_blocked_count': sum(1 for result in results if result.get('reason') == 'budget_guard_denied'),
        'status_counts': status_counts,
        'results': [
            {
                'pack_id': result.get('pack_id'),
                'kind': result.get('kind'),
                'status': result.get('status'),
                'reason': result.get('reason'),
                'budget_decision': result.get('budget_decision'),
            }
            for result in results
        ],
        'answers_sidecar_only': True,
        'compression_records_are_not_authority': True,
        'no_wake_mutation': True,
        'no_delivery_mutation': True,
        'no_threshold_mutation': True,
        'no_execution': True,
    }
    atomic_write_json(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--query-packs', default=str(QUERY_PACKS))
    parser.add_argument('--web-records', default=str(BRAVE_WEB))
    parser.add_argument('--news-records', default=str(BRAVE_NEWS))
    parser.add_argument('--router-state', default=str(ROUTER_STATE))
    parser.add_argument('--budget-state', default=str(BUDGET_STATE))
    parser.add_argument('--report', default=str(REPORT))
    parser.add_argument('--context-out', default=str(CONTEXT_OUT))
    parser.add_argument('--answers-out', default=str(ANSWERS_OUT))
    parser.add_argument('--max-packs', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args(argv)
    report = run_activation(
        query_packs_path=Path(args.query_packs),
        web_records_path=Path(args.web_records),
        news_records_path=Path(args.news_records),
        router_state_path=Path(args.router_state),
        budget_state_path=Path(args.budget_state),
        report_path=Path(args.report),
        context_out=Path(args.context_out),
        answers_out=Path(args.answers_out),
        max_packs=args.max_packs,
        dry_run=not args.live,
        timeout=args.timeout,
    )
    print(json.dumps({
        'status': report.get('status'),
        'dry_run': report.get('dry_run'),
        'selected_pack_count': report.get('selected_pack_count'),
        'seed_url_count': report.get('seed_url_count'),
        'budget_checked_count': report.get('budget_checked_count'),
        'budget_blocked_count': report.get('budget_blocked_count'),
        'out': str(args.report),
    }, ensure_ascii=False))
    return 0 if report.get('status') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
