#!/usr/bin/env python3
"""Compile operator-facing CampaignProjection board from canonical finance state."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from undercurrent_compiler import humanize_signal, source_freshness_from_refs

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
CAPITAL_AGENDA = STATE / 'capital-agenda.json'
THESIS_REGISTRY = STATE / 'thesis-registry.json'
OPPORTUNITY_QUEUE = STATE / 'opportunity-queue.json'
INVALIDATOR_LEDGER = STATE / 'invalidator-ledger.json'
SCENARIO_CARDS = STATE / 'scenario-cards.json'
CAPITAL_GRAPH = STATE / 'capital-graph.json'
DISPLACEMENT_CASES = STATE / 'displacement-cases.json'
UNDERCURRENTS = STATE / 'undercurrents.json'
OUT = STATE / 'campaign-board.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(p or '') for p in parts)
    return f'{prefix}:{hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]}'


def short(value: Any, limit: int = 120) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def opportunity_label(item: dict[str, Any]) -> str:
    instrument = str(item.get('instrument') or '').strip()
    theme = str(item.get('theme') or '')
    lower = theme.lower()
    if instrument == 'BNO':
        label = '霍尔木兹/原油供给双向风险'
    elif instrument == 'XLB':
        label = '油价成本压力下材料相对消费走弱'
    elif instrument == 'RGTI' and ('iv' in lower or 'volatility' in lower):
        label = '非 watchlist IV 异动'
    else:
        label = short(theme, 64)
    return f'{instrument}｜{label}' if instrument else label


def top_unique_opportunities(queue: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = [
        row for row in queue.get('candidates', [])
        if isinstance(row, dict) and row.get('candidate_id') and row.get('status') in {'candidate', 'promoted'}
    ]
    rows.sort(key=lambda row: float(row.get('score') or 0), reverse=True)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get('instrument') or row.get('candidate_id'))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def humanize_agenda_delta(value: Any) -> str:
    text = str(value or '').strip()
    if text.startswith('invalidator ') and ' has hit ' in text:
        body, _, hits = text.partition(' has hit ')
        return f"{humanize_signal(body.replace('invalidator ', '', 1))}（{hits.replace(' times', '次')}）"
    return short(text.replace('_', ' '), 140)


def humanize_question(value: Any) -> str:
    text = str(value or '').strip()
    m = re.match(r'is thesis (.+) still valid after (\d+) invalidator hits\??', text)
    if m:
        return f'当前 thesis 在 {m.group(2)} 次反证后是否仍成立'
    return short(text.replace('_', ' '), 120)


def agenda_type_to_campaign_type(item: dict[str, Any]) -> str:
    atype = str(item.get('agenda_type') or '')
    text = f"{item.get('attention_justification') or ''} {' '.join(str(q) for q in item.get('required_questions', []) if q)}"
    if atype == 'new_opportunity':
        return 'live_opportunity' if float(item.get('priority_score') or 0) >= 15 else 'peacetime_scout'
    if atype == 'invalidator_escalation':
        return 'undercurrent_risk' if 'unknown_discovery' in text else 'invalidator_cluster'
    if atype == 'hedge_gap_alert':
        return 'hedge_gap'
    if atype == 'exposure_crowding_warning':
        return 'undercurrent_risk'
    if atype == 'existing_thesis_review':
        return 'existing_thesis_review'
    return 'peacetime_scout'


def campaign_stage(campaign_type: str, score: float) -> str:
    if campaign_type in {'invalidator_cluster', 'undercurrent_risk'} and score >= 20:
        return 'escalation'
    if campaign_type == 'live_opportunity':
        return 'review'
    if score >= 12:
        return 'candidate'
    if score >= 6:
        return 'accumulating'
    return 'scout'


def board_class(campaign_type: str, stage: str) -> str:
    if stage == 'escalation' or campaign_type == 'live_opportunity':
        return 'live'
    if campaign_type in {'undercurrent_risk', 'hedge_gap', 'invalidator_cluster'}:
        return 'risk'
    return 'scout'


def agenda_title(item: dict[str, Any], opportunities: dict[str, Any]) -> str:
    text = f"{item.get('attention_justification') or ''} {' '.join(str(q) for q in item.get('required_questions', []) if q)}"
    if 'unknown_discovery' in text:
        labels = [opportunity_label(row) for row in top_unique_opportunities(opportunities, 3)]
        return '未知发现改道｜' + ' / '.join(labels) if labels else '未知发现改道'
    return humanize_signal(str(item.get('attention_justification') or item.get('agenda_type') or '资本议程'))


def campaign_from_agenda(item: dict[str, Any], opportunity_queue: dict[str, Any]) -> dict[str, Any]:
    ctype = agenda_type_to_campaign_type(item)
    score = float(item.get('priority_score') or 0)
    stage = campaign_stage(ctype, score)
    source_refs: list[str] = []
    linked_opps = []
    if 'unknown_discovery' in f"{item.get('attention_justification') or ''} {' '.join(str(q) for q in item.get('required_questions', []) if q)}":
        for opp in top_unique_opportunities(opportunity_queue, 3):
            linked_opps.append(opp.get('candidate_id'))
            for src in opp.get('source_refs', []) if isinstance(opp.get('source_refs'), list) else []:
                if isinstance(src, str) and src not in source_refs:
                    source_refs.append(src)
    title = agenda_title(item, opportunity_queue)
    return {
        'campaign_id': stable_id('campaign', item.get('agenda_id'), title),
        'campaign_type': ctype,
        'board_class': board_class(ctype, stage),
        'stage': stage,
        'human_title': title,
        'why_now_delta': humanize_agenda_delta(item.get('attention_justification') or '资本议程优先级变化'),
        'why_not_now': 'review-only；还缺确认，不是执行或仓位调整命令',
        'capital_relevance': 'attention/capital slot 竞争；需要比较当前 book 与候选主题的机会成本',
        'confirmations_needed': [humanize_question(q) for q in item.get('required_questions', [])[:4]] or ['价格/量能二次确认', 'source freshness 检查'],
        'kill_switches': ['来源降级或官方修正', '连续两次 watcher update 不再支持', '与现有 book 重叠但无新增边际价值'],
        'linked_thesis': [str(ref) for ref in item.get('linked_thesis_ids', []) if ref],
        'linked_scenarios': [str(ref) for ref in item.get('linked_scenarios', []) if ref],
        'linked_opportunities': [str(ref) for ref in linked_opps if ref],
        'linked_invalidators': [],
        'linked_displacement_cases': [str(ref) for ref in item.get('displacement_case_refs', []) if ref],
        'source_freshness': source_freshness_from_refs(source_refs),
        'thread_key': stable_id('campaign-thread', item.get('agenda_id'), title),
        'priority_score': score,
        'no_execution': True,
    }


def campaign_from_opportunity(item: dict[str, Any]) -> dict[str, Any]:
    score = float(item.get('score') or 0)
    ctype = 'live_opportunity' if score >= 15 else 'peacetime_scout'
    stage = campaign_stage(ctype, score)
    title = opportunity_label(item)
    return {
        'campaign_id': stable_id('campaign', item.get('candidate_id'), title),
        'campaign_type': ctype,
        'board_class': board_class(ctype, stage),
        'stage': stage,
        'human_title': title,
        'why_now_delta': f"候选分数 {score:g}；{short(item.get('theme'), 120)}",
        'why_not_now': '还不是执行；需要确认价格/量能、source freshness、与现有 book 的重叠',
        'capital_relevance': 'peacetime scout；可能成为新 attention lane 或替代/补充现有主题',
        'confirmations_needed': ['价格/量能延续', '来源新鲜度确认', '与现有 bucket 的重叠/冲突检查'],
        'kill_switches': ['候选分数连续下滑', 'source freshness 降级', '价格行为不确认'],
        'linked_thesis': [item.get('linked_thesis_id')] if item.get('linked_thesis_id') else [],
        'linked_scenarios': [],
        'linked_opportunities': [item.get('candidate_id')],
        'linked_invalidators': [],
        'linked_displacement_cases': [item.get('displacement_case_ref')] if item.get('displacement_case_ref') else [],
        'source_freshness': source_freshness_from_refs(item.get('source_refs', []) if isinstance(item.get('source_refs'), list) else []),
        'thread_key': stable_id('campaign-thread', item.get('candidate_id'), title),
        'priority_score': score,
        'no_execution': True,
    }


def campaign_from_undercurrent(card: dict[str, Any]) -> dict[str, Any]:
    source_type = str(card.get('source_type') or '')
    if source_type == 'hedge_gap':
        ctype = 'hedge_gap'
    elif source_type == 'opportunity_accumulation':
        ctype = 'peacetime_scout'
    else:
        ctype = 'undercurrent_risk'
    score = float(card.get('persistence_score') or 0)
    stage = 'accumulating' if score >= 5 else 'scout'
    if ctype in {'undercurrent_risk', 'hedge_gap'} and score >= 8:
        stage = 'review'
    title = str(card.get('human_title') or 'Undercurrent')
    refs = card.get('linked_refs') if isinstance(card.get('linked_refs'), dict) else {}
    return {
        'campaign_id': stable_id('campaign', card.get('undercurrent_id'), title),
        'campaign_type': ctype,
        'board_class': board_class(ctype, stage),
        'stage': stage,
        'human_title': title,
        'why_now_delta': short(card.get('promotion_reason'), 180),
        'why_not_now': '暗流仍在积累；未形成 isolated wake 或执行结论',
        'capital_relevance': 'peacetime/risk board 可见；用于避免暗流完全沉入后台',
        'confirmations_needed': ['下一次 watcher update 是否同向', '相关 scenario/capital edge 是否增强'],
        'kill_switches': [str(item) for item in (card.get('kill_conditions') or [])[:4]],
        'linked_thesis': refs.get('thesis', []),
        'linked_scenarios': refs.get('scenario', []),
        'linked_opportunities': refs.get('opportunity', []),
        'linked_invalidators': refs.get('invalidator', []),
        'linked_displacement_cases': [],
        'source_freshness': card.get('source_freshness') if isinstance(card.get('source_freshness'), dict) else {'status': 'unknown', 'source_refs': []},
        'thread_key': stable_id('campaign-thread', card.get('undercurrent_id'), title),
        'priority_score': score,
        'no_execution': True,
    }


def render_board(title: str, campaigns: list[dict[str, Any]], empty: str) -> str:
    lines = [title]
    if not campaigns:
        lines.extend(['', empty])
        return '\n'.join(lines).strip() + '\n'
    for idx, item in enumerate(campaigns[:5], start=1):
        lines.extend([
            '',
            f"{idx}) {item['human_title']} | {item['stage']}",
            f"为什么现在：{item['why_now_delta']}",
            f"为什么还不是动作：{item['why_not_now']}",
            f"与当前 book：{item['capital_relevance']}",
            f"确认点：{'; '.join(item.get('confirmations_needed', [])[:2])}",
            f"线程：why {item['campaign_id']} / challenge {item['campaign_id']} / sources {item['campaign_id']}",
        ])
    return '\n'.join(lines).strip() + '\n'


def compile_campaign_board(
    capital_agenda: dict[str, Any],
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    scenario_cards: dict[str, Any],
    capital_graph: dict[str, Any],
    displacement_cases: dict[str, Any],
    undercurrents: dict[str, Any],
) -> dict[str, Any]:
    campaigns: list[dict[str, Any]] = []
    for item in capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else []:
        if isinstance(item, dict) and item.get('agenda_id'):
            campaigns.append(campaign_from_agenda(item, opportunity_queue))
    seen = {tuple(c.get('linked_opportunities', [])) for c in campaigns if c.get('linked_opportunities')}
    for item in top_unique_opportunities(opportunity_queue, 8):
        key = tuple([item.get('candidate_id')])
        if key not in seen:
            campaigns.append(campaign_from_opportunity(item))
    for card in undercurrents.get('undercurrents', []) if isinstance(undercurrents.get('undercurrents'), list) else []:
        if isinstance(card, dict):
            campaigns.append(campaign_from_undercurrent(card))
    dedup: dict[str, dict[str, Any]] = {}
    for campaign in campaigns:
        key = campaign['campaign_id']
        if key not in dedup or float(campaign.get('priority_score') or 0) > float(dedup[key].get('priority_score') or 0):
            dedup[key] = campaign
    campaigns = sorted(dedup.values(), key=lambda c: (c.get('board_class') != 'live', -float(c.get('priority_score') or 0), c.get('human_title', '')))
    boards = {
        'live': [c for c in campaigns if c.get('board_class') == 'live'],
        'scout': [c for c in campaigns if c.get('board_class') == 'scout'],
        'risk': [c for c in campaigns if c.get('board_class') == 'risk'],
    }
    return {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': 'campaign-projection-v1',
        'campaigns': campaigns,
        'boards': boards,
        'discord_live_board_markdown': render_board('Finance｜Live Board', boards['live'], '当前没有必须打断你的 live campaign。'),
        'discord_scout_board_markdown': render_board('Finance｜Peacetime Board', boards['scout'], '当前没有 scout campaign。'),
        'discord_risk_board_markdown': render_board('Finance｜Risk / Undercurrent Board', boards['risk'], '当前没有 risk campaign。'),
        'source_refs': {
            'capital_agenda': str(CAPITAL_AGENDA),
            'opportunity_queue': str(OPPORTUNITY_QUEUE),
            'invalidator_ledger': str(INVALIDATOR_LEDGER),
            'undercurrents': str(UNDERCURRENTS),
        },
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile finance campaign projection board.')
    parser.add_argument('--capital-agenda', default=str(CAPITAL_AGENDA))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--opportunities', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--invalidators', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--scenarios', default=str(SCENARIO_CARDS))
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--displacement-cases', default=str(DISPLACEMENT_CASES))
    parser.add_argument('--undercurrents', default=str(UNDERCURRENTS))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)

    payload = compile_campaign_board(
        load_json_safe(Path(args.capital_agenda), {}) or {},
        load_json_safe(Path(args.thesis_registry), {}) or {},
        load_json_safe(Path(args.opportunities), {}) or {},
        load_json_safe(Path(args.invalidators), {}) or {},
        load_json_safe(Path(args.scenarios), {}) or {},
        load_json_safe(Path(args.capital_graph), {}) or {},
        load_json_safe(Path(args.displacement_cases), {}) or {},
        load_json_safe(Path(args.undercurrents), {}) or {},
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'campaign_count': len(payload['campaigns']), 'out': args.out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
