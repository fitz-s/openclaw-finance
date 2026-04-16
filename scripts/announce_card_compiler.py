#!/usr/bin/env python3
"""Compile deterministic announce card from completed report envelope + decision log."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
REPORT_ENVELOPE = FINANCE / 'state' / 'finance-decision-report-envelope.json'
DECISION_LOG = FINANCE / 'state' / 'finance-decision-log-report.json'
CAPITAL_AGENDA = FINANCE / 'state' / 'capital-agenda.json'
OPPORTUNITY_QUEUE = FINANCE / 'state' / 'opportunity-queue.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
WATCH_INTENT = FINANCE / 'state' / 'watch-intent.json'
PREV_CARD = FINANCE / 'state' / 'announce-card-prev.json'
OUT = FINANCE / 'state' / 'announce-card.json'

# report-posting-contract.json blockIfContains — card must NOT contain these
BLOCKED_PATTERNS = [
    'Silently ended', 'Silent exit', 'continue_observing',
    'shouldSend=false', 'recommendedReportType=hold',
    'Read: from ', 'SKILL.md failed', 'code review',
    'technical review', 'UTC', 'NO_REPLY', 'HEARTBEAT_OK',
]

ATTENTION_LABELS = {
    'deep_dive': '深度分析',
    'review': 'Review',
    'skim': '概览',
    'ops': '系统状态',
    'ignore': '无变化',
}

AGENDA_TYPE_LABELS = {
    'invalidator_escalation': '反证升级',
    'exposure_crowding_warning': '拥挤预警',
    'hedge_gap_alert': '对冲缺口',
    'new_opportunity': '新机会',
    'existing_thesis_review': '旧 thesis 复核',
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def decision_id_short(decision_id: str | None) -> str:
    """Short hash from decision_id for card_id and handle."""
    if not decision_id:
        return 'R0'
    short = decision_id.replace('sha256:', '')[:6]
    return f'R{short}'


def short_text(value: Any, limit: int) -> str:
    text = ' '.join(str(value or '').split())
    if len(text) <= limit:
        return text
    clipped = text[:limit].rstrip()
    if ' ' in clipped and text[limit:limit + 1] not in {'', ' '}:
        clipped = clipped.rsplit(' ', 1)[0]
    return clipped


def humanize_descriptor(raw: Any) -> str:
    """Convert internal descriptor text into something Discord can show directly."""
    text = ' '.join(str(raw or '').replace('_', ' ').split())
    if not text:
        return '待确认'

    price_match = re.match(r'price vs negative upstream:(.+)', text, flags=re.IGNORECASE)
    if price_match:
        ticker = price_match.group(1).strip().upper()
        return f'{ticker} 负面上游反证'

    direction_match = re.match(r'direction conflict:theme:(.+)', text, flags=re.IGNORECASE)
    if direction_match:
        theme_key = direction_match.group(1).strip().split(':')[-1].replace(' ', '_')
        theme = THEME_LABELS.get(theme_key, theme_key.replace('_', ' '))
        return f'{theme} 方向冲突'

    options_flow_match = re.match(r'options flow:(.+)', text, flags=re.IGNORECASE)
    if options_flow_match:
        ticker = options_flow_match.group(1).strip().upper()
        return f'{ticker} 期权流'

    return text.replace(':', ' ')


def summarize_agenda_item(item: dict[str, Any]) -> str:
    """Human-friendly summary for agenda items on Discord."""
    agenda_type = str(item.get('agenda_type') or 'agenda')
    justification = str(item.get('attention_justification') or '').strip()

    invalidator_match = re.match(r'invalidator (.+) has hit (\d+) times', justification, flags=re.IGNORECASE)
    if invalidator_match:
        desc = humanize_descriptor(invalidator_match.group(1))
        hits = invalidator_match.group(2)
        return short_text(f'{desc} 命中 {hits} 次', 44)

    utilization_match = re.match(r'(.+) at ([0-9]+%) utilization', justification, flags=re.IGNORECASE)
    if utilization_match:
        bucket = utilization_match.group(1).replace('_', ' ')
        util = utilization_match.group(2)
        return short_text(f'{bucket} bucket 利用率 {util}', 44)

    hedge_match = re.match(r'(.+) bucket has (.+) hedge coverage', justification, flags=re.IGNORECASE)
    if hedge_match:
        bucket = hedge_match.group(1).replace('_', ' ')
        coverage = hedge_match.group(2)
        return short_text(f'{bucket} bucket 对冲 {coverage}', 44)

    prefix = AGENDA_TYPE_LABELS.get(agenda_type, agenda_type.replace('_', ' '))
    if justification:
        return short_text(f'{prefix} {humanize_descriptor(justification)}', 44)
    return short_text(prefix, 44)


def summarize_invalidator_handle(inv: dict[str, Any]) -> str:
    desc = str(inv.get('description') or '').strip()
    price_match = re.match(r'price_vs_negative_upstream:(.+)', desc)
    if price_match:
        return f'{price_match.group(1).strip().upper()}反证'
    direction_match = re.match(r'direction_conflict:theme:(.+)', desc)
    if direction_match:
        theme_key = direction_match.group(1).strip().split(':')[-1]
        theme = THEME_LABELS.get(theme_key, theme_key.replace('_', ' '))
        return short_text(f'{theme}冲突', 10)
    return short_text(humanize_descriptor(desc), 12)


def classify_attention(
    report: dict[str, Any],
    decision_log_entry: dict[str, Any],
    capital_agenda: dict[str, Any],
    invalidator_ledger: dict[str, Any],
) -> str:
    """Deterministic attention class from pipeline state."""
    # ops: pipeline failure
    renderer_id = str(report.get('renderer_id') or '')
    if not report.get('markdown') or not renderer_id:
        return 'ops'

    # Check if wake dispatch was active
    wake_attr = decision_log_entry.get('wake_threshold_attribution', {})
    is_wake_dispatch = wake_attr.get('attribution') == 'canonical_wake_dispatch'

    # Check for high-severity invalidators
    max_hit = 0
    for inv in invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []:
        if isinstance(inv, dict) and inv.get('status') in {'open', 'hit'}:
            max_hit = max(max_hit, int(inv.get('hit_count') or 0))

    # deep_dive: active wake + invalidator severity
    if is_wake_dispatch and max_hit >= 3:
        return 'deep_dive'

    # review: thesis/capital changes present
    agenda_items = capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else []
    thesis_state = report.get('thesis_state')
    if thesis_state not in {'no_trade', None} or agenda_items:
        return 'review'

    # skim: fallback no_trade, nothing actionable
    return 'skim'


def find_dominant_object(
    capital_agenda: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    thesis_registry: dict[str, Any],
) -> dict[str, Any]:
    """Pick the single most attention-worthy object. Priority: agenda > opp > inv > thesis."""
    # 1. Capital agenda top item
    for item in capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else []:
        if isinstance(item, dict) and item.get('agenda_id'):
            return {
                'type': 'agenda',
                'id': item['agenda_id'],
                'instrument': item.get('instrument') or '',
                'label': summarize_agenda_item(item),
            }

    # 2. Top opportunity
    for opp in sorted(
        (o for o in (opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else []) if isinstance(o, dict) and o.get('status') in {'candidate', 'promoted'}),
        key=lambda o: float(o.get('score') or 0), reverse=True,
    )[:1]:
        return {
            'type': 'opportunity',
            'id': opp.get('candidate_id', ''),
            'instrument': opp.get('instrument', ''),
            'label': short_text(f"{opp.get('instrument', '')} {opp.get('theme', '')}", 44),
        }

    # 3. Top invalidator
    for inv in sorted(
        (i for i in (invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []) if isinstance(i, dict) and i.get('status') in {'open', 'hit'}),
        key=lambda i: int(i.get('hit_count') or 0), reverse=True,
    )[:1]:
        return {
            'type': 'invalidator',
            'id': inv.get('invalidator_id', ''),
            'instrument': '',
            'label': short_text(humanize_descriptor(inv.get('description', '')), 44),
        }

    # 4. Active thesis
    for thesis in thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []:
        if isinstance(thesis, dict) and thesis.get('status') == 'active':
            return {
                'type': 'thesis',
                'id': thesis.get('thesis_id', ''),
                'instrument': thesis.get('instrument', ''),
                'label': short_text(f"{thesis.get('instrument', '')} thesis {thesis.get('status', '')}", 44),
            }

    return {'type': 'system_steady_state', 'id': '', 'instrument': '', 'label': '系统稳定，无变化'}


def build_handles(
    decision_id: str | None,
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
) -> list[str]:
    """Compact list of navigable handles for the announce card."""
    handles = [decision_id_short(decision_id)]

    theses = [t for t in (thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []) if isinstance(t, dict) and t.get('status') in {'active', 'watch'}]
    theses.sort(key=lambda t: (t.get('status') == 'active', str(t.get('instrument') or '')), reverse=True)
    for i, t in enumerate(theses[:2]):
        handles.append(f'T{i + 1}')

    opps = [o for o in (opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else []) if isinstance(o, dict) and o.get('status') in {'candidate', 'promoted'}]
    opps.sort(key=lambda o: float(o.get('score') or 0), reverse=True)
    for i, o in enumerate(opps[:2]):
        handles.append(f'O{i + 1}')

    invs = [i for i in (invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []) if isinstance(i, dict) and i.get('status') in {'open', 'hit'}]
    invs.sort(key=lambda i: int(i.get('hit_count') or 0), reverse=True)
    for i, inv in enumerate(invs[:1]):
        handles.append(f'I{i + 1}')

    return handles


def build_display_handles(
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
) -> list[str]:
    """User-facing handle map for Discord."""
    display_handles: list[str] = []

    theses = [t for t in (thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []) if isinstance(t, dict) and t.get('status') in {'active', 'watch'}]
    theses.sort(key=lambda t: (t.get('status') == 'active', str(t.get('instrument') or '')), reverse=True)
    for i, thesis in enumerate(theses[:2]):
        instrument = short_text(thesis.get('instrument', ''), 10) or f'T{i + 1}'
        display_handles.append(f'T{i + 1}={instrument}')

    opps = [o for o in (opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else []) if isinstance(o, dict) and o.get('status') in {'candidate', 'promoted'}]
    opps.sort(key=lambda o: float(o.get('score') or 0), reverse=True)
    for i, opp in enumerate(opps[:2]):
        instrument = short_text(opp.get('instrument', ''), 10) or f'O{i + 1}'
        display_handles.append(f'O{i + 1}={instrument}')

    invs = [i for i in (invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []) if isinstance(i, dict) and i.get('status') in {'open', 'hit'}]
    invs.sort(key=lambda i: int(i.get('hit_count') or 0), reverse=True)
    for i, inv in enumerate(invs[:1]):
        display_handles.append(f'I{i + 1}={summarize_invalidator_handle(inv)}')

    return display_handles


def build_why_now(report: dict[str, Any], dominant: dict[str, Any]) -> str:
    """One-liner why-now, ≤80 chars."""
    thesis_state = report.get('thesis_state') or 'no_trade'
    if thesis_state not in {'no_trade', 'watch'}:
        return f'thesis 状态变化: {thesis_state}，需要关注'
    if dominant.get('type') == 'invalidator':
        return '反证命中，需确认是否影响现有 thesis'
    if dominant.get('type') == 'opportunity':
        return f"{dominant.get('instrument', '')} 候选得分上升，待确认值得深挖否"
    if dominant.get('type') == 'agenda':
        return '资本议程有新增项，检查 attention slot 竞争'
    return '等待 wake-eligible 证据或人工确认'


def build_next_decision(dominant: dict[str, Any]) -> str:
    """What the user should decide now, ≤80 chars."""
    dtype = dominant.get('type', '')
    instrument = dominant.get('instrument', '')
    if dtype == 'opportunity':
        return f'{instrument} 值不值得本周深挖'
    if dtype == 'invalidator':
        return '反证是否已实质性削弱当前 thesis'
    if dtype == 'agenda':
        return '这条议程值不值得占用 attention slot'
    if dtype == 'thesis':
        return f'{instrument} thesis 主轴是否变了'
    return '无需决定，保持观察'


def render_announce_markdown(
    attention_class: str,
    dominant: dict[str, Any],
    why_now: str,
    next_decision: str,
    display_handles: list[str],
) -> str:
    """Compact announce markdown for Discord delivery."""
    label = ATTENTION_LABELS.get(attention_class, attention_class)
    dominant_label = short_text(dominant.get('label', ''), 44)
    why_now_text = short_text(why_now, 32)
    next_decision_text = short_text(next_decision, 32)
    visible_handles = display_handles[:5] or ['待展开']

    while True:
        handle_str = ' / '.join(visible_handles)
        lines = [
            f'Finance｜{label}',
            f'值得看：{dominant_label}',
            f'为什么现在：{why_now_text}',
            f'你只要决定：{next_decision_text}',
            f'对象：{handle_str}',
        ]
        markdown = '\n'.join(lines)
        if len(markdown) <= 200 or len(visible_handles) <= 1:
            return markdown
        visible_handles = visible_handles[:-1]


def validate_posting_contract(markdown: str) -> list[str]:
    """Check announce markdown against report-posting-contract blockIfContains."""
    violations = []
    for pattern in BLOCKED_PATTERNS:
        if pattern in markdown:
            violations.append(f'blocked_pattern:{pattern}')
    return violations


def compile_card(
    report: dict[str, Any],
    decision_log_entry: dict[str, Any],
    capital_agenda: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    thesis_registry: dict[str, Any],
    prev_card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile deterministic announce card from pipeline state."""
    decision_id = decision_log_entry.get('decision_id') or report.get('report_hash')
    attention_class = classify_attention(report, decision_log_entry, capital_agenda, invalidator_ledger)
    dominant = find_dominant_object(capital_agenda, opportunity_queue, invalidator_ledger, thesis_registry)
    handles = build_handles(decision_id, thesis_registry, opportunity_queue, invalidator_ledger)
    display_handles = build_display_handles(thesis_registry, opportunity_queue, invalidator_ledger)
    why_now = build_why_now(report, dominant)
    next_decision = build_next_decision(dominant)

    # Detect no-change from previous card
    if prev_card and isinstance(prev_card, dict):
        if (prev_card.get('attention_class') == attention_class
                and prev_card.get('dominant_object', {}).get('id') == dominant.get('id')
                and attention_class in {'skim'}):
            attention_class = 'ignore'

    announce_md = render_announce_markdown(attention_class, dominant, why_now, next_decision, display_handles)
    if str(report.get('discord_thread_seed_markdown') or '').strip():
        announce_md = str(report.get('discord_thread_seed_markdown')).strip()
    violations = validate_posting_contract(announce_md)

    return {
        'card_id': f'announce:{decision_id_short(decision_id)}',
        'generated_at': now_iso(),
        'report_ref': decision_id,
        'reader_bundle_ref': f'state/report-reader/{decision_id_short(decision_id)}.json',
        'core_report_path': str(REPORT_ENVELOPE),
        'attention_class': attention_class,
        'dominant_object': dominant,
        'why_now': why_now,
        'next_decision': next_decision,
        'handles': handles,
        'display_handles': display_handles,
        'announce_markdown': announce_md,
        'surface_role': 'thread_router_compatibility',
        'posting_contract_violations': violations,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile announce card from report envelope.')
    parser.add_argument('--report', default=str(REPORT_ENVELOPE))
    parser.add_argument('--decision-log', default=str(DECISION_LOG))
    parser.add_argument('--capital-agenda', default=str(CAPITAL_AGENDA))
    parser.add_argument('--opportunity-queue', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--prev-card', default=str(PREV_CARD))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    report = load_json_safe(Path(args.report), {}) or {}
    decision_log_data = load_json_safe(Path(args.decision_log), {}) or {}
    decision_log_entry = decision_log_data.get('entry', {}) if isinstance(decision_log_data.get('entry'), dict) else {}
    capital_agenda = load_json_safe(Path(args.capital_agenda), {}) or {}
    opportunity_queue = load_json_safe(Path(args.opportunity_queue), {}) or {}
    invalidator_ledger = load_json_safe(Path(args.invalidator_ledger), {}) or {}
    thesis_registry = load_json_safe(Path(args.thesis_registry), {}) or {}
    prev_card = load_json_safe(Path(args.prev_card), None)
    card = compile_card(
        report, decision_log_entry, capital_agenda,
        opportunity_queue, invalidator_ledger, thesis_registry,
        prev_card=prev_card,
    )
    # Save current as prev for next cycle
    atomic_write_json(Path(args.out), card)
    atomic_write_json(Path(args.prev_card), card)
    violations = card.get('posting_contract_violations', [])
    print(json.dumps({
        'status': 'pass' if not violations else 'warn',
        'attention_class': card['attention_class'],
        'dominant_object': card['dominant_object']['type'],
        'handles': card['handles'],
        'violations': violations,
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
