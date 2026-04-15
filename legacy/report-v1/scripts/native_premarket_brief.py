#!/usr/bin/env python3
"""Deterministic native premarket brief generator (shadow/no-delivery)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json

TZ_CHI = ZoneInfo('America/Chicago')
TZ_ET = ZoneInfo('America/New_York')

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
OPS_STATE = WORKSPACE / 'ops' / 'state'

TEMPLATE = FINANCE / 'REPORT_TEMPLATE.md'
SCAN_STATE = FINANCE / 'state' / 'intraday-open-scan-state.json'
GATE_STATE = FINANCE / 'state' / 'report-gate-state.json'
PRICES = FINANCE / 'state' / 'prices.json'
PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
PORTFOLIO_ALERTS = FINANCE / 'state' / 'portfolio-alerts.json'
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
FRESHNESS = OPS_STATE / 'finance-state-freshness-report.json'
BLOCKERS = OPS_STATE / 'finance-runtime-blocker-report.json'

REPORT_JSON = OPS_STATE / 'finance-native-premarket-brief-report.json'
REPORT_MD = OPS_STATE / 'finance-native-premarket-brief.md'


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(content, encoding='utf-8')
    tmp.replace(path)


def quote_for_symbol(quotes: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    quote = quotes.get(symbol) or quotes.get(symbol.replace('/', '-')) or quotes.get(symbol.replace('-', '/'))
    return quote if isinstance(quote, dict) else None


def valid_quote(quote: dict[str, Any] | None) -> bool:
    if not isinstance(quote, dict):
        return False
    price = quote.get('price', quote.get('close'))
    return quote.get('status') == 'ok' and isinstance(price, (int, float)) and price > 0


def quote_pct(quote: dict[str, Any]) -> float | None:
    pct = quote.get('change_pct', quote.get('pct_change'))
    return float(pct) if isinstance(pct, (int, float)) else None


def fmt_price(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def fmt_quote_line(symbol: str, quote: dict[str, Any]) -> str:
    pct = quote_pct(quote)
    price = quote.get('price', quote.get('close'))
    pct_text = f"{pct:+.2f}%" if pct is not None else "n/a"
    return f"- {symbol}: {fmt_price(price)} ({pct_text})"


def quote_quality_notes(prices: dict[str, Any], watchlist: dict[str, Any]) -> list[str]:
    quotes = prices.get('quotes', {}) if isinstance(prices, dict) else {}
    symbols = []
    for key in ['indexes', 'tickers', 'crypto']:
        for item in watchlist.get(key, []) if isinstance(watchlist, dict) else []:
            if isinstance(item, dict) and item.get('symbol'):
                symbols.append(str(item['symbol']))
    bad = []
    for symbol in symbols:
        quote = quote_for_symbol(quotes, symbol)
        if quote is None:
            bad.append(f"{symbol}: missing")
            continue
        if not valid_quote(quote):
            bad.append(f"{symbol}: quote invalid/stale")
    return bad[:6]


def top_watchlist_moves(prices: dict[str, Any], watchlist: dict[str, Any]) -> list[tuple[str, dict[str, Any], float]]:
    symbols = []
    for key in ['tickers', 'indexes', 'crypto']:
        for item in watchlist.get(key, []) if isinstance(watchlist, dict) else []:
            if isinstance(item, dict) and item.get('symbol'):
                symbols.append(str(item['symbol']))
    quotes = prices.get('quotes', {}) if isinstance(prices, dict) else {}
    moves = []
    for symbol in symbols:
        quote = quote_for_symbol(quotes, symbol)
        if not valid_quote(quote):
            continue
        pct = quote_pct(quote)
        if pct is not None:
            moves.append((symbol, quote, pct))
    moves.sort(key=lambda item: abs(item[2]), reverse=True)
    return moves[:4]


def market_snapshot_lines(prices: dict[str, Any]) -> list[str]:
    quotes = prices.get('quotes', {}) if isinstance(prices, dict) else {}
    lines = []
    for symbol in ['SPY', 'QQQ', 'BTC/USD', 'IAU']:
        quote = quote_for_symbol(quotes, symbol)
        if valid_quote(quote):
            lines.append(fmt_quote_line(symbol, quote))
    return lines or ["- 报价源当前不可用，暂不引用价格。"]


def market_summary(gate_state: dict[str, Any], top_moves: list[tuple[str, dict[str, Any], float]]) -> str:
    candidate_count = gate_state.get('candidateCount', 0)
    recommendation = gate_state.get('recommendedReportType')
    if candidate_count == 0 and recommendation == 'hold':
        lead = "开盘后价格源正常，但本轮没有进入 gate 的新事件；系统维持观察，不触发交易型告警。"
    elif recommendation == 'hold':
        lead = f"已有 {candidate_count} 条候选信号，但综合强度尚未达到报告阈值；暂不升级为 short/core 报告。"
    else:
        lead = f"Gate 当前建议：{recommendation}。"
    if top_moves:
        leader = top_moves[0]
        lead += f" Watchlist 最大异动是 {leader[0]} {leader[2]:+.2f}%。"
    return lead


def human_gate_reason(reason: Any) -> str:
    if not isinstance(reason, str) or not reason.strip():
        return "等待下一轮扫描确认。"
    normalized = reason.strip().lower()
    if normalized == 'thresholds not met':
        return "没有新事件达到报告阈值。"
    if normalized.startswith('data stale'):
        return "数据曾经陈旧；已等待新扫描刷新。"
    return reason.strip()


def portfolio_fresh(portfolio: dict[str, Any], freshness: dict[str, Any]) -> bool:
    if portfolio.get('data_status') not in {None, 'fresh'}:
        return False
    fetched_at = portfolio.get('fetched_at')
    if isinstance(fetched_at, str):
        try:
            fetched = datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
            return age_hours <= 36
        except Exception:
            pass
    entry = freshness.get('entries', {}).get('portfolio', {}) if isinstance(freshness, dict) else {}
    age = entry.get('age_hours')
    return isinstance(age, (int, float)) and age <= 36 and portfolio.get('fetched_at')


def build_markdown(
    scan_state: dict[str, Any],
    gate_state: dict[str, Any],
    prices: dict[str, Any],
    portfolio: dict[str, Any],
    alerts: dict[str, Any],
    watchlist: dict[str, Any],
    freshness: dict[str, Any],
    blockers: dict[str, Any],
    now: datetime,
) -> tuple[str, dict[str, Any]]:
    time_line = f"时间：{now.astimezone(TZ_CHI).strftime('%H:%M %Z')} / {now.astimezone(TZ_ET).strftime('%H:%M %Z')}"
    runtime_blockers = blockers.get('blockers', []) if isinstance(blockers, dict) else []
    blocker_line = (
        f"[运行时阻塞] {'；'.join(runtime_blockers)}"
        if runtime_blockers
        else "运行时状态：green"
    )

    top_moves = top_watchlist_moves(prices, watchlist)
    move_lines = [
        fmt_quote_line(symbol, quote)
        for symbol, quote, _pct in top_moves
    ] or ["- 暂无足够的新鲜报价"]
    snapshot_lines = market_snapshot_lines(prices)
    quality_notes = quote_quality_notes(prices, watchlist)
    quality_lines = [
        f"- {item}"
        for item in quality_notes
    ] or ["- 价格源可用；IBKR 持仓链路若不可用，会在持仓部分显式降级。"]

    portfolio_line = "[持仓数据不可用]"
    if portfolio_fresh(portfolio, freshness):
        summary = portfolio.get('summary', {})
        portfolio_line = (
            f"组合总市值 ${summary.get('total_portfolio_value', 0):,.2f} / "
            f"未实现盈亏 ${summary.get('total_unrealized_pnl', 0):+,.2f}"
        )

    alert_lines = [
        f"- {alert.get('message')}"
        for alert in alerts.get('alerts', []) if isinstance(alert, dict)
    ] or ["- 无新持仓告警；若 IBKR 当前不可用，这表示告警被 fail-closed 抑制，不代表真实持仓无风险。"]

    if alerts.get('data_status') in {'ibkr_unavailable', 'portfolio_unavailable', 'unavailable'}:
        portfolio_line = "[持仓数据不可用] 当前没有 fresh resolved portfolio，持仓告警已被抑制，避免基于旧仓位误报。"
    elif alerts.get('data_status') == 'stale_portfolio':
        portfolio_line = "[持仓数据过期] 等待 portfolio_fetcher 恢复后再恢复持仓判断。"

    next_focus = []
    for symbol, _quote, pct in top_moves[:3]:
        if abs(pct) >= 3:
            next_focus.append(f"- 观察 {symbol} 的 {pct:+.2f}% 异动是否扩散成板块/主题信号。")
    if not next_focus:
        next_focus.append("- 当前没有单一 watchlist 异动超过 3% 后仍需要升级；继续等待下一轮 20 分钟扫描。")
    if gate_state.get('candidateCount', 0) == 0:
        next_focus.append("- 当前 gate 候选为 0；下一条消息应来自新事件、持仓告警或阈值被触发，而不是机械报流水。")

    lines = [
        "Finance｜开盘后补发简报",
        "",
        time_line,
        blocker_line,
        "",
        "## 结论",
        market_summary(gate_state, top_moves),
        "",
        "## 市场快照",
        *snapshot_lines,
        "",
        "## Watchlist 动态",
        *move_lines,
        "",
        "## 持仓概览",
        portfolio_line,
        *alert_lines,
        "",
        "## 数据质量",
        *quality_lines,
        "",
        "## 下一步关注",
        *next_focus,
        "",
        "## 扫描状态",
        f"- 最近扫描时间: {scan_state.get('last_scan_time')}",
        f"- 候选累计数: {len(scan_state.get('accumulated', []))}",
        f"- Gate 建议: {gate_state.get('recommendedReportType')}；原因: {human_gate_reason(gate_state.get('decisionReason'))}",
    ]

    return '\n'.join(lines) + '\n', {
        'top_watchlist_moves': top_moves,
        'runtime_blockers': runtime_blockers,
        'portfolio_fresh': portfolio_fresh(portfolio, freshness),
        'alert_count': len(alerts.get('alerts', [])),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', default=str(TEMPLATE))
    parser.add_argument('--scan-state', default=str(SCAN_STATE))
    parser.add_argument('--gate-state', default=str(GATE_STATE))
    parser.add_argument('--prices', default=str(PRICES))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--portfolio-alerts', default=str(PORTFOLIO_ALERTS))
    parser.add_argument('--watchlist', default=str(WATCHLIST))
    parser.add_argument('--freshness-report', default=str(FRESHNESS))
    parser.add_argument('--blocker-report', default=str(BLOCKERS))
    parser.add_argument('--markdown-out', default=str(REPORT_MD))
    parser.add_argument('--json-out', default=str(REPORT_JSON))
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    markdown, summary = build_markdown(
        scan_state=load_json(Path(args.scan_state), {}),
        gate_state=load_json(Path(args.gate_state), {}),
        prices=load_json(Path(args.prices), {}),
        portfolio=load_json(Path(args.portfolio), {}),
        alerts=load_json(Path(args.portfolio_alerts), {}),
        watchlist=load_json(Path(args.watchlist), {}),
        freshness=load_json(Path(args.freshness_report), {}),
        blockers=load_json(Path(args.blocker_report), {}),
        now=now,
    )
    write_markdown(Path(args.markdown_out), markdown)
    payload = {
        'generated_at': now.isoformat(),
        'status': 'pass',
        'markdown_path': str(args.markdown_out),
        'summary': summary,
    }
    atomic_write_json(Path(args.json_out), payload)
    print(json.dumps({
        'status': payload['status'],
        'markdown_path': payload['markdown_path'],
        'json_path': str(args.json_out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
