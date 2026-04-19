#!/usr/bin/env python3
"""Compile self-contained reader bundle for deep-dive exploration."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
REPORT_ENVELOPE = STATE / 'finance-decision-report-envelope.json'
DECISION_LOG = STATE / 'finance-decision-log-report.json'
THESIS_REGISTRY = STATE / 'thesis-registry.json'
WATCH_INTENT = STATE / 'watch-intent.json'
SCENARIO_CARDS = STATE / 'scenario-cards.json'
OPPORTUNITY_QUEUE = STATE / 'opportunity-queue.json'
INVALIDATOR_LEDGER = STATE / 'invalidator-ledger.json'
CAPITAL_AGENDA = STATE / 'capital-agenda.json'
CAPITAL_GRAPH = STATE / 'capital-graph.json'
DISPLACEMENT_CASES = STATE / 'displacement-cases.json'
PRICES = STATE / 'prices.json'
PORTFOLIO = STATE / 'portfolio-resolved.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
CAMPAIGN_CACHE = STATE / 'campaign-cache.json'
SOURCE_ATOMS = STATE / 'source-atoms' / 'latest.jsonl'
CLAIM_GRAPH = STATE / 'claim-graph.json'
CONTEXT_GAPS = STATE / 'context-gaps.json'
SOURCE_HEALTH = STATE / 'source-health.json'
OPTIONS_IV_SURFACE = STATE / 'options-iv-surface.json'
DOSSIER_DIR = STATE / 'thesis-dossiers'
CUSTOM_METRICS_DIR = STATE / 'custom-metrics'
OUT_DIR = STATE / 'report-reader'

AGENDA_TYPE_LABELS = {
    'new_opportunity': '新机会',
    'existing_thesis_review': '现有 Thesis',
    'hedge_gap_alert': '对冲缺口',
    'invalidator_escalation': '反证升级',
    'exposure_crowding_warning': '拥挤预警',
}

THEME_LABELS = {
    'unknown_discovery': '未知发现',
    'broad_market': '大盘',
    'sector': '板块',
    'commodity': '商品',
    'commodity_pressure_proxy': '商品压力',
    'options_unusual_activity_proxy': '期权异动',
    'options_chain_context': '期权链',
    'sector_rotation_proxy': '板块轮动',
}

DETAIL_LABELS = {
    'source outage': '源中断',
    'official correction': '官方修正',
    'uncovered': '未覆盖',
    'partial': '部分覆盖',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def short_text(value: Any, limit: int = 80) -> str:
    text = ' '.join(str(value or '').split())
    return text[:limit]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def decision_id_short(decision_id: str | None) -> str:
    if not decision_id:
        return 'R0'
    return 'R' + str(decision_id).replace('sha256:', '')[:6]


def report_short_id(report: dict[str, Any], decision_log_entry: dict[str, Any]) -> str:
    packet_hash = str(report.get('packet_hash') or '')
    if packet_hash.startswith('sha256:'):
        return 'R' + packet_hash.replace('sha256:', '')[:4].upper()
    report_hash = str(report.get('report_hash') or '')
    if report_hash.startswith('sha256:'):
        return 'R' + report_hash.replace('sha256:', '')[:4].upper()
    decision_id = str(decision_log_entry.get('decision_id') or '')
    if decision_id.startswith('decision:'):
        return 'R' + decision_id.split(':', 1)[1][:4].upper()
    if decision_id.startswith('sha256:'):
        return 'R' + decision_id.replace('sha256:', '')[:4].upper()
    if decision_id:
        return 'R' + decision_id[:4].upper()
    return 'R0'


def agenda_display_label(item: dict[str, Any], linked_instruments: list[str]) -> str:
    agenda_type = AGENDA_TYPE_LABELS.get(str(item.get('agenda_type') or ''), str(item.get('agenda_type') or '议程'))
    targets = ' / '.join(linked_instruments[:2])
    justification = str(item.get('attention_justification') or '').strip()
    detail = justification or str((item.get('required_questions') or [''])[0])
    if detail.startswith('invalidator ') and ' has hit ' in detail:
        body, _, hits = detail.partition(' has hit ')
        body = body.replace('invalidator ', '', 1)
        if body.startswith('direction_conflict:theme:'):
            theme_key = body.split(':')[-1]
            body = THEME_LABELS.get(theme_key, theme_key.replace('_', ' ')) + '方向冲突'
        elif body.startswith('price_vs_negative_upstream:'):
            body = body.split(':', 1)[1].upper() + '负面上游反证'
        else:
            body = DETAIL_LABELS.get(body, body)
        detail = f'{body}（{hits.replace(" times", "次")}）'
    elif ' hedge coverage' in detail:
        bucket, _, rest = detail.partition(' bucket has ')
        coverage = rest.replace(' hedge coverage', '')
        detail = f"{bucket.replace('_', ' ')} bucket 对冲{DETAIL_LABELS.get(coverage, coverage)}"
    elif ' utilization' in detail:
        detail = detail.replace('_', ' ').replace(' utilization', ' 利用率')
    if targets:
        return short_text(f'{agenda_type}｜{targets}', 60)
    if detail:
        return short_text(f'{agenda_type}｜{detail}', 60)
    return short_text(agenda_type, 60)


def agenda_role_text(item: dict[str, Any]) -> str:
    agenda_type = str(item.get('agenda_type') or '')
    if agenda_type == 'new_opportunity':
        return '本周候选，不是持仓替代命令'
    if agenda_type == 'invalidator_escalation':
        return '需要判断是否值得占用本周注意力'
    if agenda_type == 'exposure_crowding_warning':
        return '提示现有 attention slot 可能过度拥挤'
    if agenda_type == 'hedge_gap_alert':
        return '提示保护层缺口，不是执行指令'
    return '用于 attention 分配，不是执行命令'


def agenda_is_unknown_discovery(item: dict[str, Any]) -> bool:
    text = f"{item.get('attention_justification') or ''} {' '.join(str(q) for q in item.get('required_questions', []) if q)}"
    return 'unknown_discovery' in text


def unique_top_opportunities(opportunity_queue: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    candidates = [
        o for o in (opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else [])
        if isinstance(o, dict) and o.get('candidate_id') and o.get('status') in {'candidate', 'promoted'}
    ]
    candidates.sort(key=lambda o: float(o.get('score') or 0), reverse=True)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        instrument = str(item.get('instrument') or short_text(item.get('theme'), 24)).upper()
        key = instrument or str(item.get('candidate_id') or '')
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def opportunity_operator_label(item: dict[str, Any]) -> str:
    instrument = str(item.get('instrument') or '').strip()
    theme = short_text(item.get('theme'), 82)
    score = item.get('score')
    score_text = f"score {score}" if score is not None else "score n/a"
    raw_theme = str(item.get('theme') or '').lower()
    if instrument == 'BNO':
        theme = '霍尔木兹/原油供给双向风险'
    elif instrument == 'XLB':
        theme = '油价成本压力下材料相对消费走弱'
    elif instrument == 'RGTI' and ('iv' in raw_theme or 'volatility' in raw_theme):
        theme = '非 watchlist IV 异动'
    return f"{instrument}｜{theme}（{score_text}）" if instrument else f"{theme}（{score_text}）"


def unknown_discovery_positive_for(opportunity_queue: dict[str, Any]) -> str:
    labels: list[str] = []
    for opp in unique_top_opportunities(opportunity_queue, limit=3):
        instrument = str(opp.get('instrument') or '').strip()
        theme = str(opp.get('theme') or '')
        if instrument == 'BNO':
            labels.append('BNO/油价/霍尔木兹供给风险')
        elif instrument == 'XLB':
            labels.append('XLB/材料板块相对消费的成本压力观察')
        elif instrument == 'RGTI':
            labels.append('RGTI/非 watchlist IV 异动观察')
        elif instrument:
            labels.append(f'{instrument} 深挖')
        elif theme:
            labels.append(short_text(theme, 40))
    return '；'.join(labels) if labels else '未知发现候选'


def agenda_operator_label(item: dict[str, Any], opportunity_queue: dict[str, Any]) -> str:
    if agenda_is_unknown_discovery(item):
        symbols = [str(opp.get('instrument') or '').strip() for opp in unique_top_opportunities(opportunity_queue, limit=3)]
        symbols = [symbol for symbol in symbols if symbol]
        suffix = f"：{'/'.join(symbols)}" if symbols else ""
        return short_text(f"未知发现改道{suffix}（{agenda_display_label(item, [])}）", 72)
    return agenda_display_label(item, [])


def resolved_instrument(thesis: dict[str, Any] | None) -> str:
    if not isinstance(thesis, dict):
        return ''
    instrument = str(thesis.get('instrument') or '').strip()
    return instrument if instrument and not instrument.startswith('packet:') else ''


def build_thesis_cards(
    thesis_registry: dict[str, Any],
    watch_intent: dict[str, Any],
    prices: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build stable T<n> handles and object cards for theses."""
    intents_by_id = {
        i.get('intent_id'): i
        for i in watch_intent.get('intents', [])
        if isinstance(i, dict) and i.get('intent_id')
    }
    quotes = {}
    for key in ['stocks', 'indexes', 'crypto']:
        for q in prices.get(key, []) if isinstance(prices.get(key), list) else []:
            if isinstance(q, dict) and q.get('symbol'):
                quotes[str(q['symbol']).upper()] = q

    theses = [
        t for t in (thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else [])
        if isinstance(t, dict) and t.get('thesis_id') and t.get('status') in {'active', 'watch', 'candidate'}
    ]
    # Stable sort: active first, then instrument alphabetical
    theses.sort(key=lambda t: (t.get('status') == 'active', str(t.get('instrument') or '')), reverse=True)

    handles: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    for idx, thesis in enumerate(theses):
        handle = f'T{idx + 1}'
        instrument = str(thesis.get('instrument') or '')
        intent = intents_by_id.get(thesis.get('linked_watch_intent'), {})
        quote = quotes.get(instrument.replace('/', '-').upper(), {})
        price_str = f"${quote.get('price', '')}" if quote.get('price') else 'N/A'
        change = quote.get('change_pct') or quote.get('pct_change')
        change_str = f"{'+' if isinstance(change, (int, float)) and change > 0 else ''}{change}%" if change else 'N/A'

        handles[handle] = {
            'type': 'thesis',
            'ref': thesis.get('thesis_id', ''),
            'instrument': instrument,
        }
        cards.append({
            'handle': handle,
            'type': 'thesis',
            'instrument': instrument,
            'status': thesis.get('status'),
            'maturity': thesis.get('maturity'),
            'roles': intent.get('roles', []),
            'bucket_ref': intent.get('capital_bucket_hint'),
            'why_now': ', '.join(str(c) for c in thesis.get('evidence_refs', [])[:3]),
            'required_confirmations': thesis.get('required_confirmations', [])[:3],
            'invalidators': [inv_id for inv_id in (thesis.get('invalidators') or [])[:3]],
            'evidence_snapshot': thesis.get('evidence_refs', [])[:5],
            'price': price_str,
            'change_pct': change_str,
        })
    return handles, cards


def build_opportunity_cards(
    opportunity_queue: dict[str, Any],
    prices: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build stable O<n> handles for opportunities."""
    quotes = {}
    for key in ['stocks', 'indexes', 'crypto']:
        for q in prices.get(key, []) if isinstance(prices.get(key), list) else []:
            if isinstance(q, dict) and q.get('symbol'):
                quotes[str(q['symbol']).upper()] = q

    opps = [
        o for o in (opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else [])
        if isinstance(o, dict) and o.get('candidate_id') and o.get('status') in {'candidate', 'promoted'}
    ]
    opps.sort(key=lambda o: float(o.get('score') or 0), reverse=True)

    handles: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    for idx, opp in enumerate(opps):
        handle = f'O{idx + 1}'
        instrument = str(opp.get('instrument') or '')
        quote = quotes.get(instrument.replace('/', '-').upper(), {})
        price_str = f"${quote.get('price', '')}" if quote.get('price') else 'N/A'

        handles[handle] = {
            'type': 'opportunity',
            'ref': opp.get('candidate_id', ''),
            'instrument': instrument,
        }
        cards.append({
            'handle': handle,
            'type': 'opportunity',
            'instrument': instrument,
            'status': opp.get('status'),
            'theme': str(opp.get('theme') or '')[:100],
            'score': opp.get('score'),
            'source_refs': opp.get('source_refs', [])[:4],
            'displacement_case_ref': opp.get('displacement_case_ref'),
            'price': price_str,
        })
    return handles, cards


def build_invalidator_cards(
    invalidator_ledger: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build stable I<n> handles for invalidators."""
    invs = [
        i for i in (invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else [])
        if isinstance(i, dict) and i.get('invalidator_id') and i.get('status') in {'open', 'hit'}
    ]
    invs.sort(key=lambda i: int(i.get('hit_count') or 0), reverse=True)

    handles: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    for idx, inv in enumerate(invs):
        handle = f'I{idx + 1}'
        handles[handle] = {
            'type': 'invalidator',
            'ref': inv.get('invalidator_id', ''),
            'description': str(inv.get('description') or '')[:80],
        }
        cards.append({
            'handle': handle,
            'type': 'invalidator',
            'target_type': inv.get('target_type'),
            'target_id': inv.get('target_id'),
            'status': inv.get('status'),
            'description': str(inv.get('description') or '')[:120],
            'hit_count': inv.get('hit_count'),
            'evidence_refs': inv.get('evidence_refs', [])[:5],
        })
    return handles, cards


def build_scenario_cards(
    scenario_cards: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build stable S<n> handles for scenarios."""
    scenarios = [
        s for s in (scenario_cards.get('scenarios', []) if isinstance(scenario_cards.get('scenarios'), list) else [])
        if isinstance(s, dict) and s.get('scenario_id')
    ]
    scenarios.sort(key=lambda s: str(s.get('title') or s.get('scenario_id') or ''))

    handles: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    for idx, sc in enumerate(scenarios):
        handle = f'S{idx + 1}'
        handles[handle] = {
            'type': 'scenario',
            'ref': sc.get('scenario_id', ''),
            'title': str(sc.get('title') or '')[:60],
        }
        cards.append({
            'handle': handle,
            'type': 'scenario',
            'scenario_id': sc.get('scenario_id'),
            'title': str(sc.get('title') or '')[:80],
            'thesis_refs': sc.get('thesis_refs', [])[:5],
            'exposure_refs': sc.get('exposure_refs', [])[:5],
            'crowding_risk': sc.get('crowding_risk'),
        })
    return handles, cards


def build_agenda_cards(
    capital_agenda: dict[str, Any],
    thesis_registry: dict[str, Any],
    thesis_handles: dict[str, dict[str, Any]],
    opportunity_queue: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build stable A<n> handles for agenda items."""
    opportunity_queue = opportunity_queue or {}
    theses_by_id = {
        str(item.get('thesis_id')): item
        for item in capital_agenda.get('linked_theses', [])
        if isinstance(item, dict) and item.get('thesis_id')
    }
    for item in thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []:
        if isinstance(item, dict) and item.get('thesis_id'):
            theses_by_id[str(item['thesis_id'])] = item

    thesis_handle_by_ref = {
        str(payload.get('ref')): handle
        for handle, payload in thesis_handles.items()
        if isinstance(payload, dict) and payload.get('ref')
    }

    agenda_items = [
        item for item in (capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else [])
        if isinstance(item, dict) and item.get('agenda_id')
    ]
    agenda_items.sort(key=lambda item: float(item.get('priority_score') or 0), reverse=True)

    handles: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    for idx, item in enumerate(agenda_items):
        handle = f'A{idx + 1}'
        linked_thesis_ids = [str(ref) for ref in item.get('linked_thesis_ids', [])[:3]]
        linked_instruments = [
            resolved_instrument(theses_by_id.get(ref))
            for ref in linked_thesis_ids
        ]
        linked_instruments = [value for value in linked_instruments if value]
        linked_handles = [thesis_handle_by_ref.get(ref) for ref in linked_thesis_ids if thesis_handle_by_ref.get(ref)]
        label = agenda_display_label(item, linked_instruments)
        if not linked_instruments and agenda_is_unknown_discovery(item):
            label = f"反证升级｜{agenda_operator_label(item, opportunity_queue)}"
        related_opps = unique_top_opportunities(opportunity_queue, limit=3) if agenda_is_unknown_discovery(item) else []
        related_objects = [opportunity_operator_label(opp) for opp in related_opps]
        related_sources: list[str] = []
        for opp in related_opps:
            for src in opp.get('source_refs', []) if isinstance(opp.get('source_refs'), list) else []:
                if isinstance(src, str) and src not in related_sources:
                    related_sources.append(src)

        handles[handle] = {
            'type': 'agenda',
            'ref': item.get('agenda_id', ''),
            'label': label,
        }
        cards.append({
            'handle': handle,
            'type': 'agenda',
            'agenda_id': item.get('agenda_id'),
            'agenda_type': item.get('agenda_type'),
            'label': label,
            'priority_score': item.get('priority_score'),
            'linked_thesis_ids': linked_thesis_ids,
            'linked_thesis_handles': linked_handles,
            'linked_instruments': linked_instruments,
            'attention_justification': short_text(item.get('attention_justification'), 140),
            'required_questions': item.get('required_questions', [])[:3],
            'role_text': (
                f"判断是否把 attention 分给 {unknown_discovery_positive_for(opportunity_queue)}"
                if agenda_is_unknown_discovery(item)
                else agenda_role_text(item)
            ),
            'operator_summary': (
                f"A1 实际对象：{unknown_discovery_positive_for(opportunity_queue)}。这是是否切换注意力方向的问题，不是下单信号。"
                if agenda_is_unknown_discovery(item)
                else ''
            ),
            'positive_for': unknown_discovery_positive_for(opportunity_queue) if agenda_is_unknown_discovery(item) else '',
            'not_positive_for': '不是 TSLA 加码信号；也不是立即替代现有 book 的命令' if agenda_is_unknown_discovery(item) else '',
            'related_opportunities': related_objects,
            'source_refs': related_sources[:8],
        })
    return handles, cards


def build_starter_questions(
    object_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate starter questions from object cards, one per verb per dominant card."""
    starters: list[dict[str, Any]] = []
    if not object_cards:
        return starters

    # Pick first few cards for starters
    for card in object_cards[:3]:
        handle = card.get('handle', '')
        ctype = card.get('type', '')
        instrument = card.get('instrument') or handle

        if ctype == 'agenda':
            starters.append({'verb': 'why', 'handle': handle, 'question': f'为什么现在要看 {handle}？'})
            starters.append({'verb': 'challenge', 'handle': handle, 'question': f'{handle} 最大的反证或错配点是什么？'})
            starters.append({'verb': 'sources', 'handle': handle, 'question': f'{handle} 依赖的证据源有哪些？'})
            linked = card.get('linked_thesis_handles', []) if isinstance(card.get('linked_thesis_handles'), list) else []
            if linked:
                starters.append({'verb': 'compare', 'handle': handle, 'other_handle': linked[0], 'question': f'{handle} 和 {linked[0]} 谁更该占用本周 attention slot？'})
        elif ctype == 'thesis':
            starters.append({'verb': 'why', 'handle': handle, 'question': f'{instrument} 的 why-now 证据链是什么？'})
            starters.append({'verb': 'challenge', 'handle': handle, 'question': f'{instrument} 最大的反证和缺失确认是什么？'})
            starters.append({'verb': 'sources', 'handle': handle, 'question': f'{instrument} 当前依赖哪些 source？'})
        elif ctype == 'opportunity':
            starters.append({'verb': 'why', 'handle': handle, 'question': f'{instrument} 为什么值得进入深挖？'})
            starters.append({'verb': 'compare', 'handle': handle, 'question': f'{instrument} 候选与现有暴露有什么资本竞争？'})
            starters.append({'verb': 'sources', 'handle': handle, 'question': f'{instrument} 当前证据源有哪些？'})
        elif ctype == 'invalidator':
            starters.append({'verb': 'challenge', 'handle': handle, 'question': f'这个反证是否已实质性削弱它指向的 thesis？'})
            starters.append({'verb': 'sources', 'handle': handle, 'question': f'{handle} 反证来自哪些 source？'})
        elif ctype == 'scenario':
            starters.append({'verb': 'scenario', 'handle': handle, 'question': f'{card.get("title", "")} 场景下哪些 thesis 最受影响？'})

    return starters[:8]


def build_starter_queries(starter_questions: list[dict[str, Any]], report_handle: str) -> list[str]:
    queries: list[str] = []
    for item in starter_questions:
        verb = str(item.get('verb') or '')
        handle = str(item.get('handle') or '')
        other = str(item.get('other_handle') or '')
        if not verb or not handle:
            continue
        query = f'{verb} {handle} {other}'.strip() if verb == 'compare' and other else f'{verb} {handle}'
        if query not in queries:
            queries.append(query)
    expand_query = f'expand {report_handle}'
    if expand_query not in queries:
        queries.append(expand_query)
    return queries[:6]


def build_portfolio_attachment(
    watch_intent: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, list[str]]:
    """Group held/hedge/event symbols from watch intent roles."""
    roles: dict[str, list[str]] = {
        'held_core': [],
        'hedge': [],
        'event_sensitive': [],
        'macro_proxy': [],
    }
    for intent in watch_intent.get('intents', []) if isinstance(watch_intent.get('intents'), list) else []:
        if not isinstance(intent, dict):
            continue
        symbol = str(intent.get('symbol') or '')
        for role in intent.get('roles', []):
            if role in roles:
                roles[role].append(symbol)
    return {k: sorted(set(v)) for k, v in roles.items() if v}


def build_capital_summary(
    capital_graph: dict[str, Any],
    capital_agenda: dict[str, Any],
    displacement_cases: dict[str, Any],
) -> dict[str, Any]:
    """Compact capital competition summary."""
    utilization: dict[str, str] = {}
    for node in capital_graph.get('nodes', []) if isinstance(capital_graph.get('nodes'), list) else []:
        if isinstance(node, dict) and node.get('type') == 'bucket':
            bucket_id = str(node.get('id') or '')
            util = node.get('utilization_pct')
            if bucket_id and util is not None:
                utilization[bucket_id] = f'{util}%'

    return {
        'graph_hash': capital_graph.get('graph_hash'),
        'agenda_items_count': len(capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else []),
        'displacement_cases_count': len(displacement_cases.get('cases', []) if isinstance(displacement_cases.get('cases'), list) else []),
        'bucket_utilization': utilization,
    }


def build_evidence_index(
    atoms: list[dict[str, Any]],
    claim_graph: dict[str, Any],
    context_gaps: dict[str, Any],
    source_health: dict[str, Any],
) -> dict[str, Any]:
    claims = [claim for claim in as_list(claim_graph.get('claims')) if isinstance(claim, dict) and claim.get('claim_id')]
    gaps = [gap for gap in as_list(context_gaps.get('gaps')) if isinstance(gap, dict) and gap.get('gap_id')]
    health_rows = [row for row in as_list(source_health.get('sources')) if isinstance(row, dict) and row.get('source_id')]
    atom_by_id = {str(atom.get('atom_id')): atom for atom in atoms if isinstance(atom, dict) and atom.get('atom_id')}
    gaps_by_claim: dict[str, list[dict[str, Any]]] = {}
    for gap in gaps:
        claim_ids = as_list(gap.get('weak_claim_ids')) or [gap.get('claim_id')]
        for claim_id in claim_ids:
            if claim_id:
                gaps_by_claim.setdefault(str(claim_id), []).append(gap)
    return {
        'atoms': atoms,
        'claims': claims,
        'gaps': gaps,
        'health_rows': health_rows,
        'atom_by_id': atom_by_id,
        'gaps_by_claim': gaps_by_claim,
        'health_by_source': {str(row.get('source_id')): row for row in health_rows},
    }


def card_matches_claim(card: dict[str, Any], claim: dict[str, Any]) -> bool:
    text = ' '.join(str(card.get(key) or '') for key in ['handle', 'label', 'instrument', 'description', 'theme', 'agenda_id', 'thesis_id', 'candidate_id'])
    text += ' ' + ' '.join(str(v) for v in as_list(card.get('linked_instruments')))
    haystack = ' '.join(str(claim.get(key) or '') for key in ['subject', 'predicate', 'object', 'event_class'])
    tokens = {token.lower() for token in text.replace('/', ' ').replace('|', ' ').split() if len(token) >= 3}
    haystack_l = haystack.lower()
    return bool(tokens and any(token in haystack_l for token in tokens))


def evidence_for_card(card: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    claims = [claim for claim in index.get('claims', []) if card_matches_claim(card, claim)]
    if not claims and card.get('handle') == 'A1':
        claims = index.get('claims', [])[:5]
    claim_ids = [str(claim.get('claim_id')) for claim in claims if claim.get('claim_id')]
    atom_ids = sorted({str(claim.get('atom_id')) for claim in claims if claim.get('atom_id')})
    atoms = [index.get('atom_by_id', {}).get(atom_id) for atom_id in atom_ids]
    atoms = [atom for atom in atoms if isinstance(atom, dict)]
    gap_rows: list[dict[str, Any]] = []
    for claim_id in claim_ids:
        gap_rows.extend(index.get('gaps_by_claim', {}).get(claim_id, []))
    source_ids = sorted({str(atom.get('source_id')) for atom in atoms if atom.get('source_id')})
    lanes = sorted({str(atom.get('source_lane')) for atom in atoms if atom.get('source_lane')})
    health_rows = [index.get('health_by_source', {}).get(source_id) for source_id in source_ids]
    health_rows = [row for row in health_rows if isinstance(row, dict)]
    degraded = [
        row for row in health_rows
        if row.get('freshness_status') in {'stale', 'unknown'}
        or row.get('rights_status') in {'restricted', 'unknown'}
        or row.get('quota_status') == 'degraded'
        or row.get('coverage_status') == 'unavailable'
    ]
    return {
        'linked_claims': claim_ids[:12],
        'linked_atoms': atom_ids[:12],
        'linked_context_gaps': [str(gap.get('gap_id')) for gap in gap_rows if gap.get('gap_id')][:12],
        'lane_coverage': {
            'lanes': lanes,
            'source_ids': source_ids,
            'claim_count': len(claim_ids),
            'atom_count': len(atom_ids),
            'context_gap_count': len(gap_rows),
        },
        'source_health_summary': {
            'degraded_count': len(degraded),
            'degraded_sources': [str(row.get('source_id')) for row in degraded[:8]],
            'degraded_reasons': sorted({str(reason) for row in degraded for reason in as_list(row.get('breach_reasons'))})[:8],
        },
    }


def enrich_object_cards_with_evidence(cards: list[dict[str, Any]], index: dict[str, Any]) -> list[dict[str, Any]]:
    enriched = []
    for card in cards:
        next_card = dict(card)
        next_card.update(evidence_for_card(card, index))
        enriched.append(next_card)
    return enriched


def build_followup_slice_index(object_cards: list[dict[str, Any]], bundle_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for card in object_cards:
        handle = str(card.get('handle') or '')
        if not handle:
            continue
        base = {
            'handle': handle,
            'card_type': card.get('type'),
            'source_id': f"reader-bundle:{bundle_id}:{handle}",
            'source_name': 'finance_report_reader_bundle',
            'version': 'followup-slice-v1',
            'permission_metadata': {
                'review_only': True,
                'raw_thread_history_allowed': False,
                'raw_source_dump_allowed': False,
            },
            'linked_claims': card.get('linked_claims', []),
            'linked_atoms': card.get('linked_atoms', []),
            'linked_context_gaps': card.get('linked_context_gaps', []),
            'lane_coverage': card.get('lane_coverage', {}),
            'source_health_summary': card.get('source_health_summary', {}),
            'retrieval_score': 1.0 if card.get('linked_claims') or card.get('linked_atoms') else 0.0,
            'no_execution': True,
        }
        base['content_hash'] = canonical_hash({
            'handle': handle,
            'linked_claims': base['linked_claims'],
            'linked_atoms': base['linked_atoms'],
            'linked_context_gaps': base['linked_context_gaps'],
            'lane_coverage': base['lane_coverage'],
            'source_health_summary': base['source_health_summary'],
        })
        out[handle] = {
            verb: dict(base, evidence_slice_id=f"slice:{bundle_id}:{handle}:{verb}", verb=verb)
            for verb in ['why', 'challenge', 'sources', 'trace', 'expand']
        }
    return out


def options_iv_source_card(surface: dict[str, Any]) -> dict[str, Any] | None:
    if not surface:
        return None
    summary = surface.get('summary') if isinstance(surface.get('summary'), dict) else {}
    return {
        'handle': 'SIV1',
        'type': 'source_context',
        'label': 'Options IV surface｜source context only',
        'ref': str(OPTIONS_IV_SURFACE),
        'status': surface.get('status'),
        'surface_policy_version': surface.get('surface_policy_version') or surface.get('contract'),
        'primary_source_status': surface.get('primary_source_status'),
        'provider_set': surface.get('provider_set', [])[:8] if isinstance(surface.get('provider_set'), list) else [],
        'primary_provider_set': surface.get('primary_provider_set', [])[:8] if isinstance(surface.get('primary_provider_set'), list) else [],
        'summary': {
            'symbol_count': surface.get('symbol_count') or summary.get('symbol_count') or 0,
            'provider_backed_count': summary.get('provider_backed_count'),
            'proxy_only_count': summary.get('proxy_only_count'),
            'missing_iv_count': summary.get('missing_iv_count'),
            'stale_or_unknown_chain_count': summary.get('stale_or_unknown_chain_count'),
            'provider_confidence': {
                'min': summary.get('min_provider_confidence'),
                'max': summary.get('max_provider_confidence'),
            },
        },
        'source_health_refs': surface.get('source_health_refs', [])[:12] if isinstance(surface.get('source_health_refs'), list) else [],
        'rights_policy': surface.get('rights_policy') or 'unknown',
        'derived_only': surface.get('derived_only') is True,
        'raw_payload_retained': surface.get('raw_payload_retained') is True,
        'authority': 'source_context_only_not_judgment_wake_threshold_or_execution',
        'no_execution': True,
    }


def build_followup_digest(object_cards: list[dict[str, Any]], report_handle: str) -> list[str]:
    """Precompute compact answer material for Discord follow-up rehydration."""
    digest: list[str] = [f'{report_handle}: review-only; explain/compare/challenge/source trace only; no execution.']
    agenda = next((card for card in object_cards if card.get('handle') == 'A1'), None)
    if agenda:
        summary = str(agenda.get('operator_summary') or agenda.get('label') or '').strip()
        if summary:
            digest.append(f"A1: {summary}")
        if agenda.get('positive_for'):
            digest.append(f"利好/应深挖: {agenda.get('positive_for')}")
        if agenda.get('not_positive_for'):
            digest.append(f"不代表: {agenda.get('not_positive_for')}")
        related = agenda.get('related_opportunities') if isinstance(agenda.get('related_opportunities'), list) else []
        if related:
            digest.append('A1 相关候选: ' + '；'.join(str(item) for item in related[:4]))
        sources = agenda.get('source_refs') if isinstance(agenda.get('source_refs'), list) else []
        if sources:
            digest.append('A1 主要来源: ' + '；'.join(str(item) for item in sources[:5]))
    top_opps = [
        card for card in object_cards
        if isinstance(card, dict) and card.get('type') == 'opportunity'
    ][:5]
    if top_opps:
        digest.append('Top opportunities: ' + '；'.join(
            f"{card.get('handle')} {card.get('instrument')}: {short_text(card.get('theme'), 70)}"
            for card in top_opps
        ))
    top_invalidators = [
        card for card in object_cards
        if isinstance(card, dict) and card.get('type') == 'invalidator'
    ][:5]
    if top_invalidators:
        digest.append('Main invalidators: ' + '；'.join(
            f"{card.get('handle')} {card.get('description')} hit_count={card.get('hit_count')}"
            for card in top_invalidators
        ))
    return digest[:8]


def compile_bundle(
    report: dict[str, Any],
    decision_log_entry: dict[str, Any],
    thesis_registry: dict[str, Any],
    watch_intent: dict[str, Any],
    scenario_cards_data: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    capital_agenda: dict[str, Any],
    capital_graph: dict[str, Any],
    displacement_cases: dict[str, Any],
    prices: dict[str, Any],
    portfolio: dict[str, Any],
    campaign_board: dict[str, Any] | None = None,
    campaign_cache: dict[str, Any] | None = None,
    source_atoms: list[dict[str, Any]] | None = None,
    claim_graph: dict[str, Any] | None = None,
    context_gaps: dict[str, Any] | None = None,
    source_health: dict[str, Any] | None = None,
    options_iv_surface: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile self-contained reader bundle."""
    decision_id = decision_log_entry.get('decision_id') or report.get('report_hash')
    report_handle = report_short_id(report, decision_log_entry)

    handles: dict[str, dict[str, Any]] = {
        report_handle: {'type': 'report', 'ref': str(REPORT_ENVELOPE)},
    }
    all_cards: list[dict[str, Any]] = []

    t_handles, t_cards = build_thesis_cards(thesis_registry, watch_intent, prices)
    handles.update(t_handles)
    a_handles, a_cards = build_agenda_cards(capital_agenda, thesis_registry, t_handles, opportunity_queue)
    handles.update(a_handles)
    all_cards.extend(a_cards)
    all_cards.extend(t_cards)

    o_handles, o_cards = build_opportunity_cards(opportunity_queue, prices)
    handles.update(o_handles)
    all_cards.extend(o_cards)

    i_handles, i_cards = build_invalidator_cards(invalidator_ledger)
    handles.update(i_handles)
    all_cards.extend(i_cards)

    s_handles, s_cards = build_scenario_cards(scenario_cards_data)
    handles.update(s_handles)
    all_cards.extend(s_cards)
    iv_card = options_iv_source_card(options_iv_surface or {})
    if iv_card:
        handles['SIV1'] = {'type': 'source_context', 'ref': str(OPTIONS_IV_SURFACE)}
        all_cards.append(iv_card)
    bundle_id = f'rb:{report_handle}'
    evidence_index = build_evidence_index(source_atoms or [], claim_graph or {}, context_gaps or {}, source_health or {})
    all_cards = enrich_object_cards_with_evidence(all_cards, evidence_index)

    starter_questions = build_starter_questions(all_cards)
    starter_queries = build_starter_queries(starter_questions, report_handle)
    object_alias_map = {
        card['handle']: str(card.get('label') or card.get('instrument') or card.get('title') or card.get('description') or card['handle'])
        for card in all_cards
        if isinstance(card, dict) and card.get('handle')
    }

    return {
        'bundle_id': bundle_id,
        'decision_id': decision_id,
        'report_hash': report.get('report_hash'),
        'report_handle': report_handle,
        'generated_at': now_iso(),
        'handles': handles,
        'object_cards': all_cards,
        'starter_questions': starter_questions,
        'starter_queries': starter_queries,
        'object_alias_map': object_alias_map,
        'campaign_board_ref': str(CAMPAIGN_BOARD),
        'campaign_cache_ref': str(CAMPAIGN_CACHE),
        'campaigns': (campaign_board or {}).get('campaigns', []) if isinstance((campaign_board or {}).get('campaigns', []), list) else [],
        'campaign_alias_map': {c.get('campaign_id'): c.get('human_title') for c in ((campaign_board or {}).get('campaigns', []) if isinstance((campaign_board or {}).get('campaigns', []), list) else []) if isinstance(c, dict) and c.get('campaign_id')},
        'followup_digest': build_followup_digest(all_cards, report_handle),
        'followup_slice_index': build_followup_slice_index(all_cards, bundle_id),
        'evidence_index_summary': {
            'claim_count': len(evidence_index.get('claims', [])),
            'atom_count': len(evidence_index.get('atoms', [])),
            'context_gap_count': len(evidence_index.get('gaps', [])),
            'source_health_count': len(evidence_index.get('health_rows', [])),
        },
        'portfolio_attachment': build_portfolio_attachment(watch_intent, portfolio),
        'capital_summary': build_capital_summary(capital_graph, capital_agenda, displacement_cases),
        'options_iv_surface_summary': iv_card,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile reader bundle for deep-dive exploration.')
    parser.add_argument('--out-dir', default=str(OUT_DIR))
    args = parser.parse_args(argv)

    report = load_json_safe(REPORT_ENVELOPE, {}) or {}
    decision_log_data = load_json_safe(DECISION_LOG, {}) or {}
    entry = decision_log_data.get('entry', {}) if isinstance(decision_log_data.get('entry'), dict) else {}
    thesis_registry = load_json_safe(THESIS_REGISTRY, {}) or {}
    watch_intent = load_json_safe(WATCH_INTENT, {}) or {}
    scenario_cards_data = load_json_safe(SCENARIO_CARDS, {}) or {}
    opportunity_queue = load_json_safe(OPPORTUNITY_QUEUE, {}) or {}
    invalidator_ledger = load_json_safe(INVALIDATOR_LEDGER, {}) or {}
    capital_agenda = load_json_safe(CAPITAL_AGENDA, {}) or {}
    capital_graph = load_json_safe(CAPITAL_GRAPH, {}) or {}
    displacement_cases = load_json_safe(DISPLACEMENT_CASES, {}) or {}
    prices = load_json_safe(PRICES, {}) or {}
    portfolio = load_json_safe(PORTFOLIO, {}) or {}
    campaign_board = load_json_safe(CAMPAIGN_BOARD, {}) or {}
    campaign_cache = load_json_safe(CAMPAIGN_CACHE, {}) or {}
    source_atoms = load_jsonl(SOURCE_ATOMS)
    claim_graph = load_json_safe(CLAIM_GRAPH, {}) or {}
    context_gaps = load_json_safe(CONTEXT_GAPS, {}) or {}
    source_health = load_json_safe(SOURCE_HEALTH, {}) or {}
    options_iv_surface = load_json_safe(OPTIONS_IV_SURFACE, {}) or {}

    bundle = compile_bundle(
        report, entry, thesis_registry, watch_intent, scenario_cards_data,
        opportunity_queue, invalidator_ledger, capital_agenda, capital_graph,
        displacement_cases, prices, portfolio, campaign_board, campaign_cache,
        source_atoms=source_atoms,
        claim_graph=claim_graph,
        context_gaps=context_gaps,
        source_health=source_health,
        options_iv_surface=options_iv_surface,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_handle = report_short_id(report, entry)
    out_path = out_dir / f'{report_handle}.json'
    atomic_write_json(out_path, bundle)
    atomic_write_json(out_dir / 'latest.json', bundle)
    print(json.dumps({
        'status': 'pass',
        'bundle_id': bundle['bundle_id'],
        'handles_count': len(bundle['handles']),
        'object_cards_count': len(bundle['object_cards']),
        'starter_questions_count': len(bundle['starter_questions']),
        'out': str(out_path),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
