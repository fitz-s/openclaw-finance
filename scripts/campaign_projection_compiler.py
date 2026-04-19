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
STAGE_HISTORY = STATE / 'campaign-stage-history.jsonl'
CAMPAIGN_THREADS = STATE / 'campaign-threads.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(p or '') for p in parts)
    return f'{prefix}:{hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]}'


def stable_hash(*parts: Any) -> str:
    raw = '|'.join(str(p or '') for p in parts)
    return 'sha256:' + hashlib.sha256(raw.encode('utf-8')).hexdigest()


def short(value: Any, limit: int = 120) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def humanize_raw_title(value: Any) -> str:
    text = str(value or '').strip()
    if text.startswith('invalidator direction conflict:theme:') and ' has hit ' in text:
        left, _, hits = text.partition(' has hit ')
        theme_key = left.replace('invalidator direction conflict:theme:', '').strip()
        return f"{humanize_signal('direction_conflict:theme:' + theme_key)}（{hits.replace(' times', '次')}）"
    if text.startswith('invalidator '):
        return humanize_signal(text.replace('invalidator ', '', 1))
    return text


def claim_subjects(campaign: dict[str, Any]) -> list[str]:
    subjects: list[str] = []
    for value in as_list(campaign.get('linked_opportunities')):
        parts = str(value).replace('opportunity:', '').replace('candidate:', '').split(':')
        if parts and parts[-1]:
            subjects.append(parts[-1].upper())
    for unknown in as_list(campaign.get('known_unknowns')):
        subject = unknown.get('subject') if isinstance(unknown, dict) else None
        if subject:
            subjects.append(str(subject).upper())
    for value in as_list(campaign.get('linked_thesis')):
        if 'TSLA' in str(value).upper():
            subjects.append('TSLA')
    return sorted({item for item in subjects if item and not item.startswith('PACKET')})[:4]


def affected_objects_for_campaign(campaign: dict[str, Any]) -> list[str]:
    title = str(campaign.get('human_title') or '')
    objects = []
    for symbol in ['RGTI', 'BNO', 'SMR', 'XLB', 'TSLA', 'MSTR', 'ORCL', 'NVDA', 'SPX', 'QQQ']:
        if symbol in title.upper():
            objects.append(symbol)
    objects.extend(claim_subjects(campaign))
    return sorted(set(objects), key=objects.index)[:5] if objects else []


def directional_implication(campaign: dict[str, Any]) -> str:
    objects = affected_objects_for_campaign(campaign)
    title = str(campaign.get('human_title') or '').lower()
    if 'unknown' in campaign.get('campaign_type', '') or campaign.get('campaign_type') in {'undercurrent_risk', 'invalidator_cluster'}:
        if objects:
            return f"利好/利空还不能定；当前真正影响的是是否把注意力从现有主轴转向 {'/'.join(objects)}。"
        return '利好/利空还不能定；当前影响的是注意力分配，而不是执行方向。'
    if 'bno' in title or 'oil' in title or '霍尔木兹' in title:
        return '更偏向能源/油价/地缘风险链条的深挖，不是现有持仓替代命令。'
    if 'tsla' in title:
        return '主要影响 TSLA thesis 的继续占用注意力资格。'
    return '影响是候选议程的优先级变化；方向结论需要验证。'


def top_known_unknown(campaign: dict[str, Any]) -> str:
    gaps = as_list(campaign.get('known_unknowns'))
    if not gaps:
        return '暂无明确 context gap；先看价格/量能与来源新鲜度。'
    gap = gaps[0]
    if not isinstance(gap, dict):
        return short(gap, 100)
    lane = str(gap.get('missing_lane') or 'unknown')
    reason = str(gap.get('why_load_bearing') or '')
    labels = {
        'market_structure': '缺价格/量能确认',
        'corporate_filing': '缺官方/issuer 确认',
        'derived_context': '缺二次交叉验证',
    }
    return f"{labels.get(lane, '缺' + lane)}：{short(reason, 90)}"


def build_operator_brief(campaign: dict[str, Any]) -> dict[str, Any]:
    objects = affected_objects_for_campaign(campaign)
    why_now = campaign.get('why_now_delta')
    why_now = str(why_now or '').replace(' 持续累积，需要判断是否影响 attention slot', ' 连续命中，正在挑战当前注意力分配')
    if objects:
        why_now = f"{why_now}；涉及 {'/'.join(objects)}"
    if campaign.get('source_diversity'):
        why_now = f"{why_now}；source diversity={campaign.get('source_diversity')}, contradiction_load={campaign.get('contradiction_load', 0)}"
    verify_first = as_list(campaign.get('confirmations_needed'))[:2]
    known = top_known_unknown(campaign)
    if known.startswith('缺价格/量能确认') and objects:
        verify_first = [f"先看 {'/'.join(objects)} 的价格/量能是否二次确认", *verify_first]
    elif known.startswith('缺官方/issuer 确认') and objects:
        verify_first = [f"查 {'/'.join(objects)} 是否有 SEC/issuer/press release 级确认", *verify_first]
    return {
        'title': campaign.get('human_title'),
        'affected_objects': objects,
        'implication': directional_implication(campaign),
        'why_now': why_now,
        'verify_first': verify_first[:3],
        'known_unknown': known,
        'ask': [
            f"why {campaign.get('campaign_id')}",
            f"challenge {campaign.get('campaign_id')}",
            f"sources {campaign.get('campaign_id')}",
            f"trace {campaign.get('campaign_id')}",
        ],
    }


def lane_coverage_summary(campaign: dict[str, Any]) -> dict[str, Any]:
    health = campaign.get('source_health_summary') if isinstance(campaign.get('source_health_summary'), dict) else {}
    return {
        'source_diversity': int(campaign.get('source_diversity') or 0),
        'cross_lane_confirmation': int(campaign.get('cross_lane_confirmation') or 0),
        'cross_lane_confirmation_score': float(campaign.get('cross_lane_confirmation_score') or 0),
        'source_health_degraded_count': int(health.get('degraded_count') or 0),
        'source_health_degraded_sources': as_list(health.get('degraded_sources'))[:5],
    }


def evidence_quality_line(campaign: dict[str, Any]) -> str:
    coverage = campaign.get('lane_coverage_summary') if isinstance(campaign.get('lane_coverage_summary'), dict) else lane_coverage_summary(campaign)
    score = campaign.get('undercurrent_score')
    blockers = as_list(campaign.get('promotion_blockers'))
    blocker = blockers[0] if blockers else 'none'
    parts = [
        f"lanes={coverage.get('cross_lane_confirmation', 0)}",
        f"sources={coverage.get('source_diversity', 0)}",
    ]
    if score is not None:
        parts.append(f"score={score}")
    if coverage.get('source_health_degraded_count'):
        parts.append(f"degraded_sources={coverage.get('source_health_degraded_count')}")
    parts.append(f"blocker={blocker}")
    return '; '.join(parts)


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


def quality_adjusted_stage(campaign_type: str, score: float, *, source_diversity: int = 0, cross_lane_confirmation: int = 0, contradiction_load: int = 0) -> str:
    quality_score = score + source_diversity + cross_lane_confirmation + min(contradiction_load, 3)
    if campaign_type in {'undercurrent_risk', 'invalidator_cluster'} and (quality_score >= 12 or contradiction_load >= 2):
        return 'review'
    if campaign_type == 'peacetime_scout' and quality_score >= 10:
        return 'candidate'
    return campaign_stage(campaign_type, score)


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
    campaign = {
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
    return finalize_campaign(campaign, stage_reason='agenda priority and canonical capital agenda score')


def campaign_from_opportunity(item: dict[str, Any]) -> dict[str, Any]:
    score = float(item.get('score') or 0)
    ctype = 'live_opportunity' if score >= 15 else 'peacetime_scout'
    stage = campaign_stage(ctype, score)
    title = opportunity_label(item)
    campaign = {
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
    return finalize_campaign(campaign, stage_reason='opportunity score and peacetime scout status')


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
    source_diversity = int(card.get('source_diversity') or 0)
    cross_lane = int(card.get('cross_lane_confirmation') or 0)
    contradiction_load = int(card.get('contradiction_load') or 0)
    stage = quality_adjusted_stage(ctype, score, source_diversity=source_diversity, cross_lane_confirmation=cross_lane, contradiction_load=contradiction_load)
    campaign = {
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
        'linked_atoms': refs.get('atom', []),
        'linked_claims': refs.get('claim', []),
        'linked_context_gaps': refs.get('context_gap', []),
        'source_freshness': card.get('source_freshness') if isinstance(card.get('source_freshness'), dict) else {'status': 'unknown', 'source_refs': []},
        'source_diversity': source_diversity,
        'cross_lane_confirmation': cross_lane,
        'contradiction_load': contradiction_load,
        'cross_lane_confirmation_score': card.get('cross_lane_confirmation_score'),
        'contradiction_load_score': card.get('contradiction_load_score'),
        'capital_relevance_score': card.get('capital_relevance_score'),
        'freshness_penalty': card.get('freshness_penalty'),
        'undercurrent_score': card.get('undercurrent_score'),
        'promotion_candidate': bool(card.get('promotion_candidate')),
        'promotion_blockers': as_list(card.get('promotion_blockers')),
        'peacetime_update_eligible': bool(card.get('peacetime_update_eligible')),
        'packet_update_visibility': card.get('packet_update_visibility') or 'none',
        'wake_impact': card.get('wake_impact') or 'none',
        'known_unknowns': as_list(card.get('known_unknowns'))[:5],
        'source_health_summary': card.get('source_health_summary') if isinstance(card.get('source_health_summary'), dict) else {'degraded_count': 0, 'degraded_sources': []},
        'thread_key': stable_id('campaign-thread', card.get('undercurrent_id'), title),
        'priority_score': score,
        'no_execution': True,
    }
    return finalize_campaign(
        campaign,
        stage_reason=f'undercurrent score={score:g}, source_diversity={source_diversity}, cross_lane={cross_lane}, contradiction_load={contradiction_load}',
    )


def finalize_campaign(campaign: dict[str, Any], *, stage_reason: str) -> dict[str, Any]:
    out = dict(campaign)
    out['human_title'] = short(humanize_raw_title(out.get('human_title')), 110)
    out.setdefault('linked_atoms', [])
    out.setdefault('linked_claims', [])
    out.setdefault('linked_context_gaps', [])
    out.setdefault('known_unknowns', [])
    out.setdefault('source_diversity', 0)
    out.setdefault('cross_lane_confirmation', 0)
    out.setdefault('contradiction_load', 0)
    out.setdefault('undercurrent_score', None)
    out.setdefault('promotion_candidate', False)
    out.setdefault('promotion_blockers', [])
    out.setdefault('peacetime_update_eligible', False)
    out.setdefault('packet_update_visibility', 'none')
    out.setdefault('wake_impact', 'none')
    out.setdefault('source_health_summary', {'degraded_count': 0, 'degraded_sources': []})
    out['lane_coverage_summary'] = lane_coverage_summary(out)
    out['stage_reason'] = stage_reason
    out['last_stage_hash'] = stable_hash(out.get('campaign_id'), out.get('stage'), stage_reason, out.get('board_class'))
    out['thread_status'] = out.get('thread_status') or 'unbound'
    out['operator_brief'] = build_operator_brief(out)
    out['affected_objects'] = out['operator_brief']['affected_objects']
    out['directional_implication'] = out['operator_brief']['implication']
    if out['affected_objects'] and str(out.get('human_title', '')).startswith('未知发现方向冲突'):
        count = re.search(r'（(\\d+)次）', str(out.get('human_title')))
        suffix = f"（{count.group(1)}次冲突）" if count else ''
        out['human_title'] = short(f"未知发现｜{'/'.join(out['affected_objects'])}{suffix}", 110)
        out['operator_brief']['title'] = out['human_title']
    out['no_execution'] = True
    return out


def render_board(title: str, campaigns: list[dict[str, Any]], empty: str) -> str:
    lines = [title]
    if not campaigns:
        lines.extend(['', empty])
        return '\n'.join(lines).strip() + '\n'
    for idx, item in enumerate(campaigns[:3], start=1):
        brief = item.get('operator_brief') if isinstance(item.get('operator_brief'), dict) else {}
        verify = brief.get('verify_first') if isinstance(brief.get('verify_first'), list) else item.get('confirmations_needed', [])[:2]
        lines.extend([
            '',
            f"{idx}) {short(item['human_title'], 72)} | {item['stage']}",
            f"Implication：{short(brief.get('implication') or directional_implication(item), 105)}",
            f"Why：{short(brief.get('why_now') or item['why_now_delta'], 115)}",
            f"Evidence：{short(evidence_quality_line(item), 115)}",
            f"Verify：{short('; '.join(str(v) for v in verify[:2]) if verify else '价格/量能与来源新鲜度', 105)}",
            f"Unknown：{short(brief.get('known_unknown') or top_known_unknown(item), 105)}",
            f"Ask：why {item['campaign_id']} / challenge / sources",
        ])
    if len(campaigns) > 3:
        lines.append(f"\n还有 {len(campaigns) - 3} 个 campaign；在线程问 expand board。")
    return '\n'.join(lines).strip() + '\n'


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


def build_stage_transitions(campaigns: list[dict[str, Any]], existing_rows: list[dict[str, Any]] | None = None, *, generated_at: str | None = None) -> list[dict[str, Any]]:
    existing_rows = existing_rows or []
    generated = generated_at or now_iso()
    latest_hash: dict[str, str] = {}
    for row in existing_rows:
        if isinstance(row, dict) and row.get('campaign_id') and row.get('last_stage_hash'):
            latest_hash[str(row['campaign_id'])] = str(row['last_stage_hash'])
    transitions: list[dict[str, Any]] = []
    for campaign in campaigns:
        cid = str(campaign.get('campaign_id') or '')
        stage_hash = str(campaign.get('last_stage_hash') or '')
        if not cid or not stage_hash or latest_hash.get(cid) == stage_hash:
            continue
        transitions.append({
            'transition_id': stable_id('campaign-stage-transition', cid, stage_hash),
            'campaign_id': cid,
            'created_at': generated,
            'stage': campaign.get('stage'),
            'board_class': campaign.get('board_class'),
            'stage_reason': campaign.get('stage_reason'),
            'last_stage_hash': stage_hash,
            'source_refs': {
                'atoms': as_list(campaign.get('linked_atoms'))[:8],
                'claims': as_list(campaign.get('linked_claims'))[:8],
                'context_gaps': as_list(campaign.get('linked_context_gaps'))[:8],
            },
            'no_execution': True,
        })
    return transitions


def append_stage_transitions(path: Path, transitions: list[dict[str, Any]]) -> None:
    if not transitions:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        for transition in transitions:
            fh.write(json.dumps(transition, ensure_ascii=False, sort_keys=True) + '\n')


def build_thread_registry(campaigns: list[dict[str, Any]], existing_registry: dict[str, Any] | None = None, *, generated_at: str | None = None) -> dict[str, Any]:
    existing = existing_registry if isinstance(existing_registry, dict) else {}
    existing_threads = existing.get('threads') if isinstance(existing.get('threads'), dict) else {}
    generated = generated_at or now_iso()
    threads: dict[str, dict[str, Any]] = {}
    for campaign in campaigns:
        thread_key = str(campaign.get('thread_key') or '')
        if not thread_key:
            continue
        previous = existing_threads.get(thread_key) if isinstance(existing_threads.get(thread_key), dict) else {}
        thread_status = str(previous.get('thread_status') or previous.get('status') or campaign.get('thread_status') or 'unbound')
        threads[thread_key] = {
            'thread_key': thread_key,
            'campaign_id': campaign.get('campaign_id'),
            'thread_status': thread_status,
            'discord_thread_id': previous.get('discord_thread_id'),
            'created_at': previous.get('created_at') or generated,
            'updated_at': generated,
            'human_title': campaign.get('human_title'),
            'board_class': campaign.get('board_class'),
            'stage': campaign.get('stage'),
            'bundle_ref': previous.get('bundle_ref'),
            'no_execution': True,
        }
        campaign['thread_status'] = thread_status
    return {
        'generated_at': generated,
        'status': 'pass',
        'contract': 'campaign-threads-v1-local',
        'threads': threads,
        'thread_count': len(threads),
        'thread_is_ui_not_memory': True,
        'no_execution': True,
    }


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
    thread_registry = build_thread_registry(campaigns, {}, generated_at=now_iso())
    stage_transitions = build_stage_transitions(campaigns, [], generated_at=thread_registry['generated_at'])
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
        'stage_transitions': stage_transitions,
        'thread_registry': thread_registry,
        'discord_live_board_markdown': render_board('Finance｜Live Board', boards['live'], '当前没有必须打断你的 live campaign。'),
        'discord_scout_board_markdown': render_board('Finance｜Peacetime Board', boards['scout'], '当前没有 scout campaign。'),
        'discord_risk_board_markdown': render_board('Finance｜Risk / Undercurrent Board', boards['risk'], '当前没有 risk campaign。'),
        'source_refs': {
            'capital_agenda': str(CAPITAL_AGENDA),
            'opportunity_queue': str(OPPORTUNITY_QUEUE),
            'invalidator_ledger': str(INVALIDATOR_LEDGER),
            'undercurrents': str(UNDERCURRENTS),
            'stage_history': str(STAGE_HISTORY),
            'campaign_threads': str(CAMPAIGN_THREADS),
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
    parser.add_argument('--stage-history', default=str(STAGE_HISTORY))
    parser.add_argument('--campaign-threads', default=str(CAMPAIGN_THREADS))
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
    existing_history = load_jsonl(Path(args.stage_history))
    transitions = build_stage_transitions(payload['campaigns'], existing_history, generated_at=payload['generated_at'])
    payload['stage_transitions'] = transitions
    thread_registry = build_thread_registry(payload['campaigns'], load_json_safe(Path(args.campaign_threads), {}) or {}, generated_at=payload['generated_at'])
    payload['thread_registry'] = thread_registry
    atomic_write_json(Path(args.out), payload)
    append_stage_transitions(Path(args.stage_history), transitions)
    atomic_write_json(Path(args.campaign_threads), thread_registry)
    print(json.dumps({'status': payload['status'], 'campaign_count': len(payload['campaigns']), 'out': args.out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
