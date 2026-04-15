#!/usr/bin/env python3
"""Render a deterministic Finance ReportEnvelope from report-input-packet.json."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
INPUT_PACKET = FINANCE / 'state' / 'report-input-packet.json'
ENVELOPE_OUT = FINANCE / 'state' / 'finance-report-envelope.json'


def envelope_hash(envelope: dict[str, Any]) -> str:
    clone = dict(envelope)
    clone.pop('envelope_hash', None)
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return 'n/a'
    sign = '-' if value < 0 else ''
    return f'{sign}${abs(value):,.2f}'


def signed_money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return 'n/a'
    sign = '+' if value >= 0 else '-'
    return f'{sign}${abs(value):,.2f}'


def pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return 'n/a'
    return f'{value:+.2f}%'


def score(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return 'n/a'
    return f'{value:.2f}'


def ratio(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return 'n/a'
    return f'{value:.2f}x'


def source_refs(packet: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for name, ref in packet.get('source_refs', {}).items():
        if not isinstance(ref, dict):
            continue
        refs.append({'name': name, 'path': ref.get('path'), 'sha256': ref.get('sha256')})
    refs.sort(key=lambda item: item['name'])
    return refs


def fact(label: str, value: Any, source_ref: str | None) -> dict[str, Any]:
    return {'label': label, 'value': value, 'source_ref': source_ref}


def report_headline(packet: dict[str, Any]) -> str:
    gate = packet.get('gate_snapshot', {})
    report_type = gate.get('recommended_report_type') if isinstance(gate, dict) else None
    window = gate.get('window') if isinstance(gate, dict) else None
    if report_type == 'immediate_alert':
        return '🚨 Finance｜紧急报告'
    if report_type == 'core':
        return 'Finance｜核心报告'
    if report_type == 'short':
        return 'Finance｜盘后短报' if window == 'post' else 'Finance｜盘中短报'
    return 'Finance｜观察简报'


def top_observations(packet: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    observations = [item for item in packet.get('scanner_observations', []) if isinstance(item, dict)]
    observations.sort(
        key=lambda item: (
            float(item.get('importance') or 0) + float(item.get('urgency') or 0) + float(item.get('cumulative_value') or 0),
            float(item.get('novelty') or 0),
        ),
        reverse=True,
    )
    return observations[:limit]


def brief(text: Any, max_chars: int = 230) -> str:
    value = ' '.join(str(text or '').split())
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + '…'


def market_facts(packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for quote in packet.get('market_snapshot', {}).get('core_quotes', []):
        if not isinstance(quote, dict):
            continue
        facts.append(fact(str(quote.get('symbol')), pct(quote.get('change_pct')), 'prices'))
    return facts


def watchlist_facts(packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for quote in packet.get('market_snapshot', {}).get('top_watchlist_moves', [])[:5]:
        if not isinstance(quote, dict):
            continue
        facts.append(fact(str(quote.get('symbol')), pct(quote.get('change_pct')), 'prices'))
    return facts


def risk_facts(packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    option_risk = packet.get('option_risk_snapshot', {})
    for item in option_risk.get('near_expiry_options', [])[:3] if isinstance(option_risk, dict) else []:
        facts.append(fact(
            f"{item.get('underlying')} 近到期",
            f"{item.get('description')} / DTE {item.get('dte')} / {money(item.get('market_value'))}",
            'option_risk',
        ))
    for item in option_risk.get('large_decay_risk', [])[:3] if isinstance(option_risk, dict) else []:
        label = f"{item.get('underlying')} 时间价值风险"
        if not any(existing['label'] == label for existing in facts):
            facts.append(fact(label, f"{item.get('description')} / DTE {item.get('dte')}", 'option_risk'))
    for obs in top_observations(packet, 3):
        if isinstance(obs, dict):
            facts.append(fact(str(obs.get('theme')), brief(obs.get('summary'), 160), obs.get('source_ref') or 'scan_state'))
    return facts


def data_quality_facts(packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    seen: set[str] = set()
    for item in packet.get('data_quality', []):
        if not isinstance(item, dict):
            continue
        label = str(item.get('key'))
        seen.add(label)
        facts.append(fact(label, item.get('status'), item.get('key') if item.get('key') in packet.get('source_refs', {}) else None))
    for unavailable in packet.get('unavailable_facts', []):
        label = str(unavailable)
        if label in seen:
            continue
        facts.append(fact(label, 'unavailable', None))
    return facts


def why_no_alert(packet: dict[str, Any]) -> str:
    gate = packet.get('gate_snapshot', {})
    reason = gate.get('decision_reason') if isinstance(gate, dict) else None
    recommendation = gate.get('recommended_report_type') if isinstance(gate, dict) else None
    if recommendation and recommendation != 'hold':
        obs = top_observations(packet, 1)
        lead = f"；核心证据是 {obs[0].get('theme')}" if obs else ''
        return f"系统 gate 建议 {recommendation} 级别{lead}。本报告只给出 context/watch 判断，不代表执行指令。"
    if reason == 'no_candidate_met_report_threshold':
        return '没有新事件达到升级阈值；当前只保留 context/watch 信息，不生成交易型告警。'
    if reason in {'core_report_gate_recommended', 'short_report_gate_recommended'}:
        return 'Gate 有升级建议；本报告只输出已验证事实、风险和下一步观察条件。'
    return '当前没有足够的新证据升级为交易型告警。'


def next_watch_conditions(packet: dict[str, Any]) -> list[str]:
    conditions: list[str] = []
    for obs in top_observations(packet, 2):
        theme = obs.get('theme')
        if theme:
            conditions.append(f"{theme}: 等待新的独立来源、价格延续或反向证据确认。")
    for item in packet.get('option_risk_snapshot', {}).get('near_expiry_options', [])[:2]:
        if isinstance(item, dict):
            conditions.append(f"{item.get('underlying')} 到期前价格、流动性或 moneyness 明显变化时升级。")
    for quote in packet.get('market_snapshot', {}).get('top_watchlist_moves', [])[:2]:
        if isinstance(quote, dict) and isinstance(quote.get('change_pct'), (int, float)) and abs(quote['change_pct']) >= 3:
            conditions.append(f"{quote.get('symbol')} 异动继续扩大并出现新事件来源时升级。")
    if not conditions:
        conditions.append('等待下一轮扫描出现新事件、持仓风险变化或 watchlist 异动扩大。')
    return conditions


def markdown(envelope: dict[str, Any], packet: dict[str, Any]) -> str:
    portfolio = packet.get('portfolio_snapshot', {})
    summary = portfolio.get('summary', {}) if isinstance(portfolio, dict) else {}
    perf = packet.get('performance_snapshot', {})
    cash = packet.get('cash_nav_snapshot', {})
    option = packet.get('option_risk_snapshot', {})
    gate = packet.get('gate_snapshot', {})
    observations = top_observations(packet, 5)
    lines = [
        envelope['headline'],
        '',
        '## 结论',
        envelope['why_no_alert'],
        f"- gate: {gate.get('recommended_report_type')} / candidates {gate.get('candidate_count')} / CV {score(gate.get('total_cumulative_value'))} / importance {score(gate.get('total_importance'))}",
        "- 当前动作: review-only；不下单；等待触发条件或人工判断。",
        '',
        '## 为什么现在',
    ]
    if observations:
        for obs in observations[:3]:
            lines.append(
                f"- {obs.get('theme')}: {brief(obs.get('summary'), 180)} "
                f"(U {score(obs.get('urgency'))}, I {score(obs.get('importance'))}, N {score(obs.get('novelty'))}, CV {score(obs.get('cumulative_value'))})"
            )
    else:
        lines.append('- 没有可用 scanner evidence；报告只能降级为价格/持仓状态检查。')
    lines.extend([
        '',
        '## 市场快照',
    ]
    )
    for item in envelope['market_snapshot'] or [fact('market', '报价源暂无可引用核心快照', 'prices')]:
        lines.append(f"- {item['label']}: {item['value']}")
    lines.extend(['', '## Watchlist 动态'])
    for item in envelope['watchlist_moves'] or [fact('watchlist', '暂无足够新鲜异动', 'prices')]:
        lines.append(f"- {item['label']}: {item['value']}")
    lines.extend(['', '## 持仓影响'])
    if portfolio.get('data_status') == 'fresh':
        lines.append(
            f"- 组合市值 {money(summary.get('total_portfolio_value'))}；股票 {money(summary.get('total_stock_value'))}，期权 {money(summary.get('total_option_value'))}。"
        )
        lines.append(f"- 组合 MTM {signed_money(perf.get('total_mtm'))}，不使用 Flex OpenPosition 的未实现盈亏字段。")
        lines.append(f"- NAV {money(cash.get('nav_total'))}；现金 {money(cash.get('ending_cash'))}；总敞口倍数 {ratio(cash.get('gross_exposure_ratio'))}。")
    else:
        lines.append('- [持仓数据不可用] 持仓相关判断已 fail-closed 抑制，避免基于旧仓位误报。')
    lines.extend(['', '## 核心证据'])
    evidence_items = [
        item for item in envelope['risk_flags']
        if item.get('source_ref') in {'scan_state', 'scanner_output'}
    ]
    for item in evidence_items or [fact('evidence', '暂无新的 scanner evidence', 'scan_state')]:
        lines.append(f"- {item['label']}: {item['value']}")
    lines.extend(['', '## 持仓风险'])
    holding_risks = [
        item for item in envelope['risk_flags']
        if item.get('source_ref') == 'option_risk'
    ]
    for item in holding_risks or [fact('holding_risk', '暂无新的持仓风险观察', 'option_risk')]:
        lines.append(f"- {item['label']}: {item['value']}")
    lines.extend(['', '## 反证与无动作理由'])
    lines.append('- 当前输出是 review/context，不是交易执行指令；任何动作仍需通过单独 risk/execution gate。')
    if 'open_position_unrealized_pnl' in packet.get('unavailable_facts', []):
        lines.append('- Flex OpenPosition 未实现盈亏字段不可用；报告使用 performance MTM，不把 0 当作真实 P&L。')
    if not observations:
        lines.append('- scanner evidence 缺失时，不根据价格表单独形成交易判断。')
    lines.extend(['', '## 数据质量'])
    for item in envelope['data_quality']:
        display_value = {'available': '可用', 'missing': '缺失', 'unavailable': '不可用'}.get(item['value'], item['value'])
        lines.append(f"- {item['label']}: {display_value}")
    lines.extend(['', '## 下一步关注'])
    for item in envelope['next_watch_conditions']:
        lines.append(f"- {item}")
    lines.extend(['', '## 来源'])
    for ref in envelope['source_refs'][:8]:
        digest = (ref.get('sha256') or 'missing')[:18]
        lines.append(f"- {ref.get('name')}: {digest}")
    return '\n'.join(lines) + '\n'


def build_envelope(packet: dict[str, Any]) -> dict[str, Any]:
    envelope = {
        'report_policy_version': packet.get('report_policy_version', 'finance-report-input-v1'),
        'prompt_version': 'none',
        'renderer_id': 'deterministic-v1',
        'model_id': 'deterministic',
        'input_packet_hash': packet.get('packet_hash'),
        'envelope_hash': '',
        'headline': report_headline(packet),
        'market_snapshot': market_facts(packet),
        'portfolio_snapshot': packet.get('portfolio_snapshot', {}),
        'risk_flags': risk_facts(packet),
        'watchlist_moves': watchlist_facts(packet),
        'data_quality': data_quality_facts(packet),
        'why_no_alert': why_no_alert(packet),
        'next_watch_conditions': next_watch_conditions(packet),
        'source_refs': source_refs(packet),
        'markdown': '',
    }
    envelope['markdown'] = markdown(envelope, packet)
    envelope['envelope_hash'] = envelope_hash(envelope)
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Render deterministic finance report envelope.')
    parser.add_argument('--input-packet', default=str(INPUT_PACKET))
    parser.add_argument('--out', default=str(ENVELOPE_OUT))
    args = parser.parse_args(argv)
    packet = load_json_safe(Path(args.input_packet), {}) or {}
    envelope = build_envelope(packet)
    atomic_write_json(Path(args.out), envelope)
    print(json.dumps({
        'status': 'pass',
        'renderer_id': envelope['renderer_id'],
        'input_packet_hash': envelope['input_packet_hash'],
        'envelope_hash': envelope['envelope_hash'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
