#!/usr/bin/env python3
"""Render decision-grade finance report from ContextPacket + JudgmentEnvelope."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json, load_json_safe


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
PACKET = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'latest-context-packet.json'
JUDGMENT = FINANCE / 'state' / 'judgment-envelope.json'
VALIDATION = FINANCE / 'state' / 'judgment-validation.json'
OUT = FINANCE / 'state' / 'finance-decision-report-envelope.json'
PRICES = FINANCE / 'state' / 'prices.json'
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
FALLBACK_WATCHLIST = FINANCE / 'watchlists' / 'core.json'
SCAN_STATE = FINANCE / 'state' / 'intraday-open-scan-state.json'
SEC_DISCOVERY = FINANCE / 'state' / 'sec-discovery.json'
SEC_SEMANTICS = FINANCE / 'state' / 'sec-filing-semantics.json'
PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
OPTION_RISK = FINANCE / 'state' / 'portfolio-option-risk.json'
BROAD_MARKET = FINANCE / 'state' / 'broad-market-proxy.json'
OPTIONS_FLOW = FINANCE / 'state' / 'options-flow-proxy.json'
WATCH_INTENT = FINANCE / 'state' / 'watch-intent.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
OPPORTUNITY_QUEUE = FINANCE / 'state' / 'opportunity-queue.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
SHADOW_DELTA_OUT = FINANCE / 'state' / 'finance-thesis-delta-report.shadow.json'
SHADOW_DELTA_MARKDOWN = FINANCE / 'state' / 'finance-thesis-delta-report.shadow.md'
CAPITAL_AGENDA = FINANCE / 'state' / 'capital-agenda.json'
CAPITAL_GRAPH = FINANCE / 'state' / 'capital-graph.json'
DISPLACEMENT_CASES_PATH = FINANCE / 'state' / 'displacement-cases.json'
CAMPAIGN_BOARD = FINANCE / 'state' / 'campaign-board.json'
POLICY_VERSION = 'finance-decision-report-v1'
SYMBOL_STOPWORDS = {
    'AI', 'API', 'CEO', 'CFO', 'CIO', 'COO', 'CPI', 'ETF', 'ET',
    'FEED', 'FOMC', 'GDP', 'GW', 'IV', 'LSEG', 'NAV', 'OI', 'PM',
    'SEC', 'TVA', 'USD', 'VLCC', 'WTI', 'YOY',
}

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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def hash_payload(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop('report_hash', None)
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def hash_text(text: str) -> str:
    return 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def report_short_id(report_hash: Any, judgment_id: Any) -> str:
    value = str(report_hash or '')
    if value.startswith('sha256:'):
        return 'R' + value.replace('sha256:', '')[:4].upper()
    value = str(judgment_id or '')
    if value:
        return 'R' + hashlib.sha1(value.encode('utf-8')).hexdigest()[:4].upper()
    return 'R0000'


def et_time_label(timestamp: Any) -> str:
    text = str(timestamp or '')
    if not text:
        return '00:00 ET'
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return '00:00 ET'
    return dt.astimezone(ZoneInfo('America/New_York')).strftime('%H:%M ET')


def humanize_invalidator_desc(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return '反证'
    if text.startswith('price_vs_negative_upstream:'):
        return f"{text.split(':', 1)[1].upper()} 负面上游反证"
    if text.startswith('direction_conflict:theme:'):
        theme_key = text.split(':')[-1]
        theme = THEME_LABELS.get(theme_key, theme_key.replace('_', ' '))
        return f'{theme}方向冲突'
    if text.startswith('options_flow:'):
        return f"{text.split(':', 1)[1].upper()} 期权流"
    return text.replace('_', ' ')


def humanize_agenda_justification(item: dict[str, Any]) -> str:
    justification = str(item.get('attention_justification') or '').strip()
    if justification.startswith('invalidator ') and ' has hit ' in justification:
        body, _, hits = justification.partition(' has hit ')
        return f"{humanize_invalidator_desc(body.replace('invalidator ', '', 1))}（{hits.replace(' times', '次')}）"
    if ' utilization' in justification:
        return justification.replace('_', ' ').replace(' utilization', ' 利用率')
    if ' hedge coverage' in justification:
        return justification.replace('_', ' ').replace(' hedge coverage', ' 对冲覆盖')
    return short(justification.replace('_', ' '), 80)


def humanize_required_question(value: Any) -> str:
    text = str(value or '').strip()
    hit_match = re.match(r'is thesis (.+) still valid after (\d+) invalidator hits\??', text)
    if hit_match:
        return f'当前 thesis 在 {hit_match.group(2)} 次反证后是否仍成立'
    return short(text.replace('_', ' '), 100)


def evidence_by_id(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get('evidence_id')): record
        for record in packet.get('accepted_evidence_records', [])
        if isinstance(record, dict) and record.get('evidence_id')
    }


def short(text: Any, limit: int = 180) -> str:
    value = ' '.join(str(text or '').split())
    if len(value) <= limit:
        return value
    return value[:limit - 1].rstrip() + '…'


def source_label(record: dict[str, Any]) -> str:
    facts = record.get('structured_facts') if isinstance(record.get('structured_facts'), dict) else {}
    return str(facts.get('source') or record.get('source_kind') or record.get('raw_ref') or 'unknown')


def compact_sources(sources: Any, limit: int = 2) -> str:
    if not isinstance(sources, list) or not sources:
        return 'source unavailable'
    out: list[str] = []
    for src in sources[:limit]:
        value = str(src)
        parsed = urlparse(value)
        if parsed.netloc:
            out.append(parsed.netloc)
        else:
            out.append(short(value, 36))
    return ', '.join(out)


def fmt_pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 'n/a'
    sign = '+' if number > 0 else ''
    return f'{sign}{number:.2f}%'


def fmt_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 'n/a'
    return f'${number:,.2f}'


def evidence_line(record: dict[str, Any]) -> str:
    return (
        f"- `{record.get('evidence_id')}` [{record.get('layer')}] "
        f"{short(record.get('normalized_summary'), 140)} "
        f"(source: {source_label(record)}, disposition: {record.get('quarantine', {}).get('disposition')})"
    )


def strip_bullet(line: str) -> str:
    return line[2:] if line.startswith('- ') else line


def public_text(value: Any) -> str:
    text = str(value)
    return (
        text
        .replace('support-only', '低权限 context')
        .replace('metadata_only', 'metadata context')
        .replace('ordinary_form4_support_only', 'ordinary Form 4 context')
    )


def public_status(value: Any) -> str:
    return {
        'candidate': '候选',
        'promoted': '已晋升',
        'suppressed': '已压制',
        'retired': '已退休',
        'active': '活跃',
        'watch': '观察',
        'seed': '初始',
        'developing': '发展中',
        'validated': '已验证',
        'invalidated': '已失效',
        'open': '开放',
        'hit': '命中',
        'resolved': '已解决',
    }.get(str(value), str(value or 'unknown'))


def public_roles(values: Any) -> str:
    labels = {
        'held_core': '持仓核心',
        'hedge': '对冲',
        'macro_proxy': '宏观代理',
        'event_sensitive': '事件敏感',
        'curiosity': '观察兴趣',
        'unknown_discovery_candidate': '未知探索',
        'do_not_trade': '禁止交易',
    }
    if not isinstance(values, list) or not values:
        return '未标注'
    return '、'.join(labels.get(str(item), str(item)) for item in values[:3])


def public_reason(value: Any) -> str:
    text = str(value or '')
    return {
        'scanner_unknown_discovery': 'scanner 未知探索',
        'compiled_from_watch_intent': '来自 WatchIntent',
    }.get(text, text.replace('_', ' '))


def public_confirmation(value: Any) -> str:
    text = str(value or '')
    return {
        'wake-eligible evidence': '等待可唤醒证据',
        'price/flow continuation': '价格/成交量继续确认',
        'wait for promoted evidence': '等待证据晋升',
    }.get(text, text.replace('_', ' '))


def public_confirmations(values: Any, limit: int = 2) -> str:
    if not isinstance(values, list) or not values:
        return '等待可唤醒证据'
    return '；'.join(public_confirmation(item) for item in values[:limit])


def watchlist_symbols(watchlist: dict[str, Any]) -> list[str]:
    symbols: list[str] = []
    for key in ['tickers', 'indexes', 'crypto']:
        for item in watchlist.get(key, []) if isinstance(watchlist.get(key), list) else []:
            if isinstance(item, dict) and item.get('symbol'):
                symbols.append(str(item['symbol']).replace('/', '-'))
    return sorted(set(symbols))


def watchlist_rows(prices: dict[str, Any], watchlist: dict[str, Any]) -> tuple[list[tuple[float, str, dict[str, Any]]], list[str]]:
    quotes = prices.get('quotes') if isinstance(prices.get('quotes'), dict) else {}
    symbols = set(watchlist_symbols(watchlist))
    rows: list[tuple[float, str, dict[str, Any]]] = []
    for symbol, quote in quotes.items():
        if symbols and str(symbol) not in symbols:
            continue
        if not isinstance(quote, dict) or quote.get('status') != 'ok':
            continue
        pct = quote.get('pct_change') if quote.get('pct_change') is not None else quote.get('change_pct')
        try:
            abs_pct = abs(float(pct))
        except (TypeError, ValueError):
            abs_pct = 0.0
        rows.append((abs_pct, str(symbol), quote))
    rows.sort(reverse=True)
    errors = [
        symbol for symbol, quote in quotes.items()
        if isinstance(quote, dict) and quote.get('status') != 'ok' and (not symbols or symbol in symbols)
    ]
    return rows, sorted(errors)


def watchlist_lines(prices: dict[str, Any], watchlist: dict[str, Any], limit: int = 3) -> list[str]:
    rows, errors = watchlist_rows(prices, watchlist)
    if not rows:
        return ['- Watchlist quote snapshot 不可用；不推断相对强弱。']
    lines = []
    for _, symbol, quote in rows[:limit]:
        pct = quote.get('pct_change') if quote.get('pct_change') is not None else quote.get('change_pct')
        lines.append(
            f"- {symbol}: {fmt_pct(pct)}, price {fmt_money(quote.get('price'))}, volume {quote.get('volume', 'n/a')}"
        )
    if errors:
        lines.append(f"- unavailable: {', '.join(sorted(errors)[:4])}")
    return lines


def flow_proxy_records(packet: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        record for record in packet.get('accepted_evidence_records', [])
        if isinstance(record, dict) and record.get('source_kind') == 'watchlist_volume_pressure_proxy'
    ]
    def score(record: dict[str, Any]) -> float:
        facts = record.get('structured_facts') if isinstance(record.get('structured_facts'), dict) else {}
        try:
            return float(facts.get('pressure_score') or record.get('magnitude') or 0)
        except (TypeError, ValueError):
            return 0.0
    records.sort(key=score, reverse=True)
    return records


def flow_proxy_lines(packet: dict[str, Any], limit: int = 3) -> list[str]:
    records = flow_proxy_records(packet)
    if not records:
        return ['- flow proxy: 暂无成交量/涨跌幅压力代理；不推断资金流。']
    lines = []
    for record in records[:limit]:
        facts = record.get('structured_facts') if isinstance(record.get('structured_facts'), dict) else {}
        symbol = facts.get('symbol') or ','.join(record.get('instrument', []))
        lines.append(
            f"- flow proxy {symbol}: {fmt_pct(facts.get('pct_change'))}, "
            f"volume {facts.get('volume', 'n/a')}, pressure_score {facts.get('pressure_score', 'n/a')}"
        )
    return lines


def broad_market_lines(broad_market: dict[str, Any], limit: int = 2) -> list[str]:
    rows = [item for item in broad_market.get('top_dislocations', []) if isinstance(item, dict)]
    if not rows:
        return ['- broad proxy: 暂无 sector/credit/rates/commodity dislocation。']
    lines = []
    for item in rows[:limit]:
        lines.append(
            f"- broad proxy {item.get('symbol')}: {fmt_pct(item.get('relative_to_spy_pct'))} vs SPY; "
            f"category={item.get('category')}; pressure_score={item.get('pressure_score')}"
        )
    return lines


def _quote_lookup(prices: dict[str, Any], broad_market: dict[str, Any], *symbols: str) -> tuple[str | None, dict[str, Any] | None]:
    price_quotes = prices.get('quotes') if isinstance(prices.get('quotes'), dict) else {}
    broad_quotes = broad_market.get('quotes') if isinstance(broad_market.get('quotes'), dict) else {}
    for symbol in symbols:
        quote = price_quotes.get(symbol) or broad_quotes.get(symbol)
        if isinstance(quote, dict):
            return symbol, quote
    return None, None


def _direction_label(pct: Any) -> str:
    try:
        value = float(pct)
    except (TypeError, ValueError):
        return 'unknown'
    if value >= 0.35:
        return 'risk-on/up'
    if value <= -0.35:
        return 'down/risk-off'
    return 'flat'


def macro_triad_snapshot(prices: dict[str, Any], broad_market: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        ('Gold', ('GLD', 'IAU'), '避险/real-rate proxy'),
        ('Bitcoin', ('BTC-USD', 'BTC/USD', 'BTC'), 'crypto liquidity/risk appetite proxy'),
        ('SPX', ('SPY', '^GSPC'), 'US equity beta proxy via SPY'),
    ]
    out: list[dict[str, Any]] = []
    for label, symbols, role in specs:
        symbol, quote = _quote_lookup(prices, broad_market, *symbols)
        if not quote or quote.get('status') != 'ok':
            out.append({
                'label': label,
                'symbol': symbol or symbols[0],
                'status': 'unavailable',
                'direction': 'unknown',
                'role': role,
            })
            continue
        pct = quote.get('pct_change') if quote.get('pct_change') is not None else quote.get('change_pct')
        out.append({
            'label': label,
            'symbol': symbol or symbols[0],
            'status': 'ok',
            'price': quote.get('price') or quote.get('close'),
            'pct_change': pct,
            'direction': _direction_label(pct),
            'as_of': quote.get('as_of'),
            'role': role,
        })
    return out


def macro_triad_lines(prices: dict[str, Any], broad_market: dict[str, Any]) -> list[str]:
    rows = macro_triad_snapshot(prices, broad_market)
    lines = ['- Core macro triad:']
    for row in rows:
        if row['status'] != 'ok':
            lines.append(f"  - {row['label']} ({row['symbol']}): unavailable; direction unknown; {row['role']}。")
            continue
        lines.append(
            f"  - {row['label']} ({row['symbol']}): {fmt_pct(row.get('pct_change'))}, "
            f"direction={row.get('direction')}, price {fmt_money(row.get('price'))}; {row['role']}。"
        )
    return lines


def macro_triad_operator_line(prices: dict[str, Any], broad_market: dict[str, Any]) -> str:
    parts: list[str] = []
    for row in macro_triad_snapshot(prices, broad_market):
        if row['status'] == 'ok':
            parts.append(f"{row['label']} {fmt_pct(row.get('pct_change'))}({row.get('direction')})")
        else:
            parts.append(f"{row['label']} unavailable")
    return '- Macro triad：' + ' / '.join(parts) + '。'


def append_macro_triad_to_board(board: Any, prices: dict[str, Any], broad_market: dict[str, Any]) -> str:
    text = str(board or '').strip()
    macro = macro_triad_operator_line(prices, broad_market).lstrip('- ').strip()
    if not text:
        return ''
    if 'Macro triad' in text:
        return text + '\n'
    return f'{text}\n\n{macro}\n'


def opportunity_lines(scan: dict[str, Any], watchlist: dict[str, Any] | None = None, portfolio: dict[str, Any] | None = None, limit: int = 1) -> list[str]:
    candidates = [item for item in scan.get('accumulated', []) if isinstance(item, dict)]
    if not candidates:
        return ['- 当前 scanner 没有可展示的机会/风险候选。']
    known = known_symbol_set(watchlist or {}, portfolio)
    filtered = []
    for item in candidates:
        scope = str(item.get('discovery_scope') or item.get('candidate_type') or item.get('exploration_lane') or '')
        text_lower = f"{item.get('theme', '')} {item.get('summary', '')}".lower()
        if scope in {'non_watchlist', 'unknown_discovery', 'discovery', 'non_watchlist_discovery'}:
            continue
        if 'non-watchlist' in text_lower or 'unknown discovery' in text_lower:
            continue
        theme_symbols = candidate_symbols({'theme': item.get('theme', ''), 'summary': '', 'tickers': item.get('tickers', [])})
        if theme_symbols & known:
            continue
        filtered.append(item)
    candidates = filtered
    if not candidates:
        return ['- 暂无非重复的非持仓/非 watchlist 风险候选；避免重复今日看点。']
    def rank(item: dict[str, Any]) -> float:
        return float(item.get('novelty') or 0) * 1.2 + float(item.get('importance') or 0) + float(item.get('urgency') or 0)
    def opportunity_key(item: dict[str, Any]) -> str:
        text = f"{item.get('theme', '')} {item.get('summary', '')}".lower()
        if 'physical forties' in text or 'forties' in text:
            return 'physical_forties'
        if 'hormuz' in text or '霍尔木兹' in text:
            return 'hormuz'
        if 'nuscale' in text or 'smr' in text:
            return 'smr'
        if 'jpmorgan' in text or '原油库存' in text:
            return 'oil_inventory'
        return ''.join(ch for ch in str(item.get('theme', '')).lower() if ch.isalnum())[:48]
    candidates.sort(key=rank, reverse=True)
    deduped = []
    seen = set()
    for item in candidates:
        key = opportunity_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    lines = []
    for item in deduped[:limit]:
        sources = item.get('sources') if isinstance(item.get('sources'), list) else []
        source_text = compact_sources(sources)
        lines.append(
            f"- {short(item.get('theme'), 80)}：novelty {item.get('novelty', 'n/a')}, "
            f"importance {item.get('importance', 'n/a')}, urgency {item.get('urgency', 'n/a')}；"
            f"等待确认：{short(item.get('summary'), 115)} (sources: {source_text})"
        )
    return lines


def known_symbol_set(watchlist: dict[str, Any], portfolio: dict[str, Any] | None = None) -> set[str]:
    known = set(watchlist_symbols(watchlist))
    portfolio = portfolio or {}
    for row in portfolio.get('stocks', []) if isinstance(portfolio.get('stocks'), list) else []:
        if isinstance(row, dict) and row.get('symbol'):
            known.add(str(row['symbol']).replace('/', '-'))
    for row in portfolio.get('options', []) if isinstance(portfolio.get('options'), list) else []:
        if isinstance(row, dict):
            symbol = row.get('underlying') or row.get('symbol')
            if symbol:
                known.add(str(symbol).replace('/', '-'))
    return known


def candidate_symbols(item: dict[str, Any]) -> set[str]:
    import re
    explicit = item.get('tickers') if isinstance(item.get('tickers'), list) else []
    text = f"{item.get('theme', '')} {item.get('summary', '')}"
    symbols = {str(symbol).replace('/', '-') for symbol in explicit if symbol}
    symbols.update(re.findall(r'\b[A-Z]{2,5}(?:-USD)?\b', text))
    return symbols - SYMBOL_STOPWORDS


def unknown_discovery_lines(scan: dict[str, Any], watchlist: dict[str, Any], portfolio: dict[str, Any] | None = None, limit: int = 2) -> list[str]:
    known = known_symbol_set(watchlist, portfolio)
    candidates = [item for item in scan.get('accumulated', []) if isinstance(item, dict)]
    discovery: list[dict[str, Any]] = []
    for item in candidates:
        scope = str(item.get('discovery_scope') or item.get('candidate_type') or item.get('exploration_lane') or '')
        symbols = candidate_symbols(item)
        theme_text = str(item.get('theme') or '')
        theme_symbols = candidate_symbols({'theme': theme_text, 'summary': '', 'tickers': item.get('tickers', [])})
        has_known_theme_symbol = bool(theme_symbols & known)
        has_unknown_symbol = bool(symbols - known)
        explicitly_unknown = scope in {'non_watchlist', 'unknown_discovery', 'discovery', 'non_watchlist_discovery'}
        macro_or_sector = not theme_symbols and any(
            token in f"{item.get('theme', '')} {item.get('summary', '')}".lower()
            for token in ['sector', 'etf', 'commodity', 'credit', 'oil', 'crude', 'physical', 'rates', 'volatility', '原油', '库存', '现货', '板块', '信贷']
        )
        if has_known_theme_symbol:
            continue
        if explicitly_unknown or has_unknown_symbol or macro_or_sector:
            discovery.append(item)
    if not discovery:
        return ['- 未发现合格的非 watchlist/非持仓探索候选；scanner 下一轮必须继续搜索 unknown_discovery。']
    def rank(item: dict[str, Any]) -> float:
        return float(item.get('novelty') or 0) * 1.4 + float(item.get('importance') or 0) + float(item.get('urgency') or 0)
    def discovery_key(item: dict[str, Any]) -> str:
        text = f"{item.get('theme', '')} {item.get('summary', '')}".lower()
        if 'physical forties' in text or 'forties' in text:
            return 'physical_forties'
        if 'jpmorgan' in text or '原油库存' in text:
            return 'oil_inventory'
        if 'iran' in text or '伊朗' in text or 'hormuz' in text or '霍尔木兹' in text:
            return 'iran_hormuz'
        if 'tariff' in text or '关税' in text:
            return 'tariff'
        return ''.join(ch for ch in str(item.get('theme', '')).lower() if ch.isalnum())[:48]
    discovery.sort(key=rank, reverse=True)
    lines = []
    seen = set()
    for item in discovery:
        key = discovery_key(item)
        if key in seen:
            continue
        seen.add(key)
        sources = item.get('sources') if isinstance(item.get('sources'), list) else []
        source_text = compact_sources(sources)
        syms = sorted(candidate_symbols(item) - known)
        symbol_note = f"; unknown symbols: {', '.join(syms[:4])}" if syms else ''
        lines.append(
            f"- {short(item.get('theme'), 85)}：novelty {item.get('novelty', 'n/a')}, "
            f"importance {item.get('importance', 'n/a')}, urgency {item.get('urgency', 'n/a')}{symbol_note}；"
            f"探索理由：{short(item.get('summary'), 120)} (sources: {source_text})"
        )
        if len(lines) >= limit:
            break
    return lines


def sec_discovery_lines(sec_discovery: dict[str, Any], sec_semantics: dict[str, Any], watchlist: dict[str, Any], limit: int = 1) -> list[str]:
    semantics = [
        item for item in sec_semantics.get('semantics', [])
        if isinstance(item, dict)
        and (
            item.get('semantic_wake_candidate') is True
            or item.get('confidence') != 'metadata_only'
            or not str(item.get('filing_semantic_type', '')).endswith('_metadata_only')
        )
    ]
    if semantics:
        lines = []
        for item in semantics[:limit]:
            status = 'wake-candidate' if item.get('semantic_wake_candidate') else 'support-only'
            detail = item.get('filing_semantic_type') or 'sec_filing_metadata'
            issuer = item.get('issuer_name') or 'unknown issuer'
            lines.append(
                f"- SEC {item.get('form_type', 'filing')} / {detail}: {short(issuer, 70)}；"
                f"{status}；confidence={item.get('confidence')}; reasons={item.get('classification_reasons', [])}"
            )
        return lines
    return []


def option_risk_lines(option_risk: dict[str, Any]) -> list[str]:
    if not option_risk:
        return ['- 期权持仓源缺失；不评估持仓 DTE / assignment。']
    status = option_risk.get('data_status') or 'unknown'
    blocking = '; '.join(str(item) for item in option_risk.get('blocking_reasons', [])[:2]) if option_risk.get('blocking_reasons') else 'none'
    assignment = option_risk.get('exercise_assignment') if isinstance(option_risk.get('exercise_assignment'), dict) else {}
    lines = [
        f"- 持仓期权源：`{status}`；option_count={option_risk.get('option_count', 0)}；assignment={assignment.get('status', 'unknown')}。",
    ]
    near = option_risk.get('near_expiry_options') if isinstance(option_risk.get('near_expiry_options'), list) else []
    decay = option_risk.get('large_decay_risk') if isinstance(option_risk.get('large_decay_risk'), list) else []
    def compact_option(item: Any) -> str:
        if not isinstance(item, dict):
            return short(item, 80)
        symbol = item.get('underlying') or item.get('symbol') or 'unknown'
        desc = item.get('description') or item.get('symbol') or symbol
        flags = item.get('risk_flags') if isinstance(item.get('risk_flags'), list) else []
        flag_text = f"; flags={','.join(str(flag) for flag in flags[:2])}" if flags else ''
        return f"{symbol} {desc}; DTE={item.get('dte')}; value={fmt_money(item.get('market_value'))}{flag_text}"
    if near:
        lines.append('- near expiry: ' + '; '.join(compact_option(item) for item in near[:2]))
    if decay:
        lines.append('- large decay risk: ' + '; '.join(compact_option(item) for item in decay[:2]))
    return lines


def options_flow_lines(options_flow: dict[str, Any], limit: int = 1) -> list[str]:
    rows = [item for item in options_flow.get('top_events', []) if isinstance(item, dict)]
    if not rows:
        status = options_flow.get('status', 'missing') if isinstance(options_flow, dict) else 'missing'
        return [f"- options flow proxy: `{status}`；暂无可用 unusual options / IV-OI proxy。"]
    lines = []
    for item in rows[:limit]:
        lines.append(
            f"- options flow {item.get('symbol')} {item.get('call_put')} {item.get('expiry')} {item.get('strike')}: "
            f"vol/OI={item.get('volume_oi_ratio')}; IV={item.get('implied_volatility')}; notional≈{fmt_money(item.get('notional_proxy'))}; score={item.get('score')}"
        )
    return lines


def layer_digest_lines(packet: dict[str, Any], records: dict[str, dict[str, Any]]) -> list[str]:
    lines = []
    digest = packet.get('layer_digest') if isinstance(packet.get('layer_digest'), dict) else {}
    for layer in ['L0', 'L1', 'L2', 'L3', 'L4']:
        refs = digest.get(layer) if isinstance(digest.get(layer), list) else []
        if not refs:
            continue
        def ref_rank(ref: Any) -> float:
            record = records.get(str(ref), {})
            text = str(record.get('normalized_summary') or '')
            import re
            match = re.search(r'([+-]?\d+(?:\.\d+)?)%', text)
            try:
                pct = abs(float(match.group(1))) if match else 0.0
            except ValueError:
                pct = 0.0
            return pct + float(record.get('novelty_score') or 0) / 100
        ranked_refs = sorted(refs, key=ref_rank, reverse=True)
        shown = []
        for ref in ranked_refs[:2]:
            record = records.get(str(ref), {})
            shown.append(f"`{ref}` {short(record.get('normalized_summary'), 70)}")
        suffix = f" (+{len(refs)-2} more)" if len(refs) > 2 else ""
        lines.append(f"- {layer}: " + '; '.join(shown) + suffix)
    return lines


def contradiction_lines(packet: dict[str, Any]) -> list[str]:
    contradictions = [
        item for item in packet.get('contradictions', [])
        if isinstance(item, dict)
        and not str(item.get('contradiction_key', '')).startswith('direction_conflict:theme:broad_market')
        and not str(item.get('contradiction_key', '')).startswith('direction_conflict:theme:sector_rotation_proxy')
        and not str(item.get('contradiction_key', '')).startswith('direction_conflict:theme:commodity_pressure_proxy')
        and not str(item.get('contradiction_key', '')).startswith('direction_conflict:theme:unknown_discovery')
    ]
    if not contradictions:
        return ['- 当前 packet 没有结构化 contradiction；这不代表市场无冲突，只代表本轮 typed evidence 未形成可计算冲突。']
    lines = []
    for item in contradictions[:2]:
        ctype = item.get('type')
        if ctype == 'price_vs_negative_upstream':
            lines.append(
                f"- `{item.get('contradiction_key')}`: 价格/报价偏强，但上游 actor/narrative 证据偏负面；"
                "不要追涨，先等待确认。"
            )
        elif ctype == 'price_vs_positive_upstream':
            lines.append(
                f"- `{item.get('contradiction_key')}`: 上游证据偏正面，但价格行为偏弱；"
                "需要确认是否滞后或 source quality 问题。"
            )
        elif ctype == 'price_before_narrative':
            lines.append(
                f"- `{item.get('contradiction_key')}`: 价格先于叙事变动；不要把滞后新闻当领先 alpha。"
            )
        else:
            lines.append(
                f"- `{item.get('contradiction_key')}`: {item.get('impact')}。"
            )
    return lines


def holding_impact(packet: dict[str, Any], portfolio: dict[str, Any]) -> list[str]:
    position = packet.get('position_state') if isinstance(packet.get('position_state'), dict) else {}
    records = packet.get('accepted_evidence_records', [])
    portfolio_records = [
        record for record in records
        if isinstance(record, dict)
        and (
            'PORTFOLIO' in (record.get('instrument') or [])
            or str(record.get('source_kind', '')).startswith('portfolio')
            or str(record.get('source_kind', '')).startswith('option_risk')
        )
        and 'source status' not in str(record.get('normalized_summary', '')).lower()
        and 'source_status' not in str(record.get('source_kind', '')).lower()
    ]
    lines = []
    if portfolio:
        summary = portfolio.get('summary') if isinstance(portfolio.get('summary'), dict) else {}
        lines.append(
            f"- authority: {position.get('authority', 'review-only')}; exposure: {position.get('exposure', 'unknown')}; portfolio source: `{portfolio.get('data_status', 'unknown')}`; stocks: {summary.get('stock_positions', 0)}; options: {summary.get('option_positions', 0)}"
        )
        if portfolio.get('stale_reason'):
            lines.append(f"- stale/unavailable reason: {portfolio.get('stale_reason')}")
    else:
        lines.append(f"- authority: {position.get('authority', 'review-only')}; exposure: {position.get('exposure', 'unknown')}; portfolio source: unknown")
    portfolio_unavailable = portfolio.get('data_status') in {'unavailable', 'portfolio_unavailable'} if portfolio else False
    if portfolio_records and not portfolio_unavailable:
        lines.extend(evidence_line(record) for record in portfolio_records[:4])
    else:
        lines.append('- 无新鲜持仓/期权 EvidenceRecord；持仓影响不得被推断。')
    return lines


def data_quality_lines(packet: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    summary = packet.get('source_quality_summary') if isinstance(packet.get('source_quality_summary'), dict) else {}
    lines = [
        f"- evidence/support: {summary.get('record_count', len(packet.get('evidence_refs', [])))} total; {summary.get('judgment_support_count', 0)} judgment-support; {summary.get('wake_eligible_count', 0)} wake-eligible",
        f"- validation: {validation.get('outcome')}; errors={validation.get('errors', [])}",
    ]
    return lines


def highlight_lines(packet: dict[str, Any], judgment: dict[str, Any], prices: dict[str, Any], watchlist: dict[str, Any], scan_state: dict[str, Any], sec_semantics: dict[str, Any]) -> list[str]:
    rows, _ = watchlist_rows(prices, watchlist)
    flow = flow_proxy_records(packet)
    highlights = [f"- 当前判断：`{judgment.get('thesis_state')}`；review-only，不下单。"]
    if rows:
        _, symbol, quote = rows[0]
        pct = quote.get('pct_change') if quote.get('pct_change') is not None else quote.get('change_pct')
        flow_note = ''
        if flow:
            facts = flow[0].get('structured_facts', {}) if isinstance(flow[0].get('structured_facts'), dict) else {}
            flow_note = f"；top flow proxy {facts.get('symbol')} score {facts.get('pressure_score')}"
        highlights.append(f"- 市场机会：{symbol} {fmt_pct(pct)}{flow_note}。")
    else:
        highlights.append("- 市场机会：watchlist quote snapshot 不可用。")
    unknown = unknown_discovery_lines(scan_state, watchlist, limit=1)
    sec_rows = [item for item in sec_semantics.get('semantics', []) if isinstance(item, dict)]
    if unknown and '未发现合格' not in unknown[0]:
        highlights.append("- 未知探索：" + unknown[0].removeprefix('- '))
    elif sec_rows:
        highlights.append(f"- 未知探索：SEC {sec_rows[0].get('form_type')} / {sec_rows[0].get('filing_semantic_type')} {short(sec_rows[0].get('issuer_name'), 70)}。")
    else:
        highlights.append("- 未知探索：暂无 fresh non-watchlist candidate。")
    return highlights[:3]


def top_action_lines(
    packet: dict[str, Any],
    judgment: dict[str, Any],
    prices: dict[str, Any],
    watchlist: dict[str, Any],
    scan_state: dict[str, Any],
    options_flow: dict[str, Any],
    portfolio: dict[str, Any],
) -> list[str]:
    unknown = [line for line in unknown_discovery_lines(scan_state, watchlist, portfolio, limit=1) if '未发现合格' not in line]
    watch = watchlist_lines(prices, watchlist, limit=1)
    options = options_flow_lines(options_flow, limit=1)
    lines = []
    if unknown:
        lines.append(f"- 1. 机会拓展：{strip_bullet(unknown[0])}")
    else:
        lines.append("- 1. 机会拓展：暂无合格的非持仓/非 watchlist 候选；不把 watchlist/持仓事件伪装成 unknown。")
    if watch:
        lines.append(f"- 2. 盘面确认：{strip_bullet(watch[0])}")
    if options and (not unknown or strip_bullet(options[0]) not in lines[0]):
        lines.append(f"- 3. 期权异动：{strip_bullet(options[0])}")
    else:
        lines.append("- 3. 期权异动：无新的可用高质量异动。")
    if judgment.get('required_confirmations'):
        lines.append(f"- 下一步：{'; '.join(str(item) for item in judgment.get('required_confirmations', [])[:2])}")
    else:
        lines.append("- 下一步：等待 wake-eligible 证据或价格/成交量二次确认。")
    return lines[:4]


def why_now_lines(packet: dict[str, Any], judgment: dict[str, Any]) -> list[str]:
    summary = packet.get('source_quality_summary') if isinstance(packet.get('source_quality_summary'), dict) else {}
    wake_count = int(summary.get('wake_eligible_count') or 0)
    if wake_count <= 0:
        return ['- 本轮是 context packet 更新，不是 isolated judgment wake；只输出机会雷达、反证和验证清单。']
    lines = [f"- {item}" for item in judgment.get('why_now', [])[:2] if item]
    return lines or ['- 有 wake-eligible 证据进入 JudgmentEnvelope。']


def thesis_delta_summary(thesis_registry: dict[str, Any], opportunity_queue: dict[str, Any], invalidator_ledger: dict[str, Any]) -> str:
    theses = [item for item in thesis_registry.get('theses', []) if isinstance(item, dict)]
    active = [item for item in theses if item.get('status') in {'active', 'watch', 'candidate'}]
    opportunities = [item for item in opportunity_queue.get('candidates', []) if isinstance(item, dict) and item.get('status') in {'candidate', 'promoted'}]
    invalidators = [item for item in invalidator_ledger.get('invalidators', []) if isinstance(item, dict) and item.get('status') in {'open', 'hit'}]
    return (
        f"- 结构变化：活跃/观察 thesis={len(active)}；未知候选={len(opportunities)}；"
        f"开放/命中反证={len(invalidators)}。"
    )


def thesis_focus_lines(thesis_registry: dict[str, Any], watch_intent: dict[str, Any], limit: int = 2) -> list[str]:
    intents = {
        item.get('intent_id'): item
        for item in watch_intent.get('intents', [])
        if isinstance(item, dict) and item.get('intent_id')
    }
    theses = [item for item in thesis_registry.get('theses', []) if isinstance(item, dict)]
    ranked = sorted(
        theses,
        key=lambda item: (
            2 if item.get('status') == 'active' else 1 if item.get('status') == 'watch' else 0,
            str(item.get('instrument') or ''),
        ),
        reverse=True,
    )
    lines = []
    for thesis in ranked[:limit]:
        intent = intents.get(thesis.get('linked_watch_intent'), {})
        lines.append(
            f"- {thesis.get('instrument')}: 状态={public_status(thesis.get('status'))} / 成熟度={public_status(thesis.get('maturity'))}；角色={public_roles(intent.get('roles'))}；"
            f"等待确认：{public_confirmations(thesis.get('required_confirmations'))}"
        )
    return lines or ['- 暂无 active thesis object；本轮只保留 packet/log。']


def opportunity_queue_lines(opportunity_queue: dict[str, Any], limit: int = 2) -> list[str]:
    candidates = [
        item for item in opportunity_queue.get('candidates', [])
        if isinstance(item, dict) and item.get('status') in {'candidate', 'promoted'}
    ]
    candidates.sort(key=lambda item: float(item.get('score') or 0), reverse=True)
    lines = []
    for item in candidates[:limit]:
        instrument = item.get('instrument') or 'macro/theme'
        lines.append(
            f"- {instrument}: {short(item.get('theme'), 90)}；状态={public_status(item.get('status'))}；"
            f"评分={item.get('score')}；依据={short(public_reason(item.get('promotion_reason')), 80)}"
        )
    return lines or ['- OpportunityQueue 暂无候选；scanner 下一轮继续做非持仓/非 watchlist 探索。']


def invalidator_delta_lines(invalidator_ledger: dict[str, Any], limit: int = 2) -> list[str]:
    rows = [
        item for item in invalidator_ledger.get('invalidators', [])
        if isinstance(item, dict) and item.get('status') in {'open', 'hit'}
    ]
    rows.sort(key=lambda item: (int(item.get('hit_count') or 0), str(item.get('last_seen_at') or '')), reverse=True)
    lines = []
    for item in rows[:limit]:
        lines.append(
            f"- {short(item.get('description'), 100)}；状态={public_status(item.get('status'))}；命中次数={item.get('hit_count')}。"
        )
    return lines or ['- InvalidatorLedger 暂无 open/hit 项。']


def render_delta_markdown(
    packet: dict[str, Any],
    judgment: dict[str, Any],
    validation: dict[str, Any],
    *,
    prices: dict[str, Any],
    watchlist: dict[str, Any],
    scan_state: dict[str, Any],
    broad_market: dict[str, Any],
    options_flow: dict[str, Any],
    portfolio: dict[str, Any],
    option_risk: dict[str, Any],
    watch_intent: dict[str, Any],
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    shadow: bool = False,
) -> str:
    digest = packet.get('layer_digest') if isinstance(packet.get('layer_digest'), dict) else {}
    layer_counts = ', '.join(f'{layer}={len(digest.get(layer, []))}' for layer in ['L0', 'L1', 'L2', 'L3', 'L4'])
    portfolio_status = portfolio.get('data_status') if isinstance(portfolio, dict) else None
    confirmations = judgment.get('required_confirmations', []) or ['等待 wake-eligible evidence', '确认 source freshness']
    invalidator_lines = invalidator_delta_lines(invalidator_ledger, limit=2)
    title = 'Finance｜Thesis Delta Shadow' if shadow else 'Finance｜决策报告'
    source_line = (
        '- 完整 packet / JudgmentEnvelope / thesis objects 已写入本地 state；本文件为 shadow，不触发 delivery。'
        if shadow
        else '- 完整 packet / JudgmentEnvelope / thesis objects 已写入 decision log；用户可见输出仍经过 product validation 与 delivery safety。'
    )
    lines = [
        title,
        '',
        '## 结论',
        f"- 当前状态：`{judgment.get('thesis_state')}`；`{judgment.get('actionability')}`；review-only，不下单。",
        '- 报告主轴：先找非持仓/非 watchlist 的机会拓展，其次确认 watchlist/flow，最后才看持仓影响。',
        thesis_delta_summary(thesis_registry, opportunity_queue, invalidator_ledger),
        '',
        '## 今日看点',
        f"- 1. 机会队列：{strip_bullet(opportunity_queue_lines(opportunity_queue, limit=1)[0])}",
        f"- 2. Thesis焦点：{strip_bullet(thesis_focus_lines(thesis_registry, watch_intent, limit=1)[0])}",
        f"- 3. 反证变化：{strip_bullet(invalidator_lines[0])}",
        '',
        '## 为什么现在',
        *why_now_lines(packet, judgment),
        '',
        '## 市场机会雷达（Watchlist / Flow）',
        *watchlist_lines(prices, watchlist, limit=1),
        *flow_proxy_lines(packet, limit=1),
        *broad_market_lines(broad_market, limit=1),
        *macro_triad_lines(prices, broad_market),
        '',
        '## 未知探索（非持仓 / 非Watchlist）',
        *opportunity_queue_lines(opportunity_queue, limit=2),
        '',
        '## 潜在机会 / 风险候选',
        *opportunity_queue_lines(opportunity_queue, limit=1),
        '',
        '## 期权与风险雷达',
        *option_risk_lines(option_risk)[:2],
        *options_flow_lines(options_flow, limit=1),
        '',
        '## 分层证据',
        f"- 证据分布：{layer_counts}；本 shadow report 只渲染 thesis delta，不展开证据流水。",
        '',
        '## 矛盾与裁决',
        *contradiction_lines(packet)[:2],
        '',
        '## 持仓影响',
        f"- portfolio={portfolio_status or 'unknown'}；持仓只作为影响面，不作为本报告主轴。",
        '',
        '## 反证 / Invalidators',
        *invalidator_lines,
        '',
        '## 下一步观察',
        '- ' + public_confirmations(confirmations),
        '',
        '## 数据质量',
        f"- validator={validation.get('outcome')}；thesis_refs={len(packet.get('thesis_refs') or [])}；opportunity_refs={len(packet.get('opportunity_candidate_refs') or [])}；invalidator_refs={len(packet.get('invalidator_refs') or [])}。",
        '',
        '## 来源',
        source_line,
    ]
    return '\n'.join(lines) + '\n'


def capital_agenda_section(capital_agenda: dict[str, Any], limit: int = 5) -> list[str]:
    items = [item for item in capital_agenda.get('agenda_items', []) if isinstance(item, dict)][:limit]
    if not items:
        return ['- 资本议程暂无项目。']
    type_labels = {
        'new_opportunity': '新机会',
        'existing_thesis_review': 'Thesis 审查',
        'hedge_gap_alert': '对冲缺口',
        'invalidator_escalation': '反证升级',
        'exposure_crowding_warning': '暴露拥挤',
    }
    lines = []
    for i, item in enumerate(items, 1):
        atype = type_labels.get(item.get('agenda_type', ''), item.get('agenda_type', 'unknown'))
        justification = short(item.get('attention_justification', ''), 120)
        lines.append(
            f"- {i}. [{atype}] {justification}；"
            f"priority={item.get('priority_score')}；"
            f"thesis_refs={len(item.get('linked_thesis_ids', []))}；"
            f"displacement_refs={len(item.get('displacement_case_refs', []))}"
        )
    return lines


def displacement_section(displacement_cases: dict[str, Any], limit: int = 3) -> list[str]:
    cases = [c for c in displacement_cases.get('cases', []) if isinstance(c, dict)][:limit]
    if not cases:
        return ['- 无候选与现有暴露产生资本竞争；所有候选为增量关注。']
    lines = []
    for c in cases:
        lines.append(
            f"- {c.get('candidate_instrument', 'unknown')} vs "
            f"{c.get('displaced_instrument', 'existing')}："
            f"{c.get('overlap_type', 'unknown')}；{short(c.get('justification', ''), 100)}"
        )
    return lines


def hedge_gap_section(capital_graph: dict[str, Any]) -> list[str]:
    coverage = capital_graph.get('hedge_coverage') if isinstance(capital_graph.get('hedge_coverage'), dict) else {}
    gaps = [(bucket, status) for bucket, status in sorted(coverage.items()) if status in {'uncovered', 'partial'}]
    if not gaps:
        return ['- 所有活跃 bucket 对冲覆盖正常。']
    lines = []
    for bucket, status in gaps:
        util = capital_graph.get('bucket_utilization', {}).get(bucket, 0)
        lines.append(f"- {bucket}：覆盖状态={public_status(status)}；利用率={util:.0%}")
    return lines


def render_capital_delta_markdown(
    packet: dict[str, Any],
    judgment: dict[str, Any],
    validation: dict[str, Any],
    *,
    prices: dict[str, Any],
    watchlist: dict[str, Any],
    scan_state: dict[str, Any],
    broad_market: dict[str, Any],
    options_flow: dict[str, Any],
    portfolio: dict[str, Any],
    option_risk: dict[str, Any],
    watch_intent: dict[str, Any],
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    capital_agenda: dict[str, Any],
    capital_graph: dict[str, Any],
    displacement_cases: dict[str, Any],
) -> str:
    digest = packet.get('layer_digest') if isinstance(packet.get('layer_digest'), dict) else {}
    layer_counts = ', '.join(f'{layer}={len(digest.get(layer, []))}' for layer in ['L0', 'L1', 'L2', 'L3', 'L4'])
    portfolio_status = portfolio.get('data_status') if isinstance(portfolio, dict) else None
    confirmations = judgment.get('required_confirmations', []) or ['等待 wake-eligible evidence', '确认 source freshness']
    graph_hash_short = (capital_graph.get('graph_hash') or 'unavailable')[:20]
    lines = [
        'Finance｜资本议程报告',
        '',
        '## 结论',
        f"- 当前状态：`{judgment.get('thesis_state')}`；`{judgment.get('actionability')}`；review-only，不下单。",
        f'- 报告主轴：资本竞争优先——每个 agenda item 必须回答「为什么它值得占用 attention/capital slot」。',
        thesis_delta_summary(thesis_registry, opportunity_queue, invalidator_ledger),
        f"- 资本图谱：{capital_graph.get('node_count', 0)} nodes / {capital_graph.get('edge_count', 0)} edges / hash={graph_hash_short}…",
        '',
        '## 资本议程',
        *capital_agenda_section(capital_agenda, limit=5),
        '',
        '## 替代分析',
        *displacement_section(displacement_cases, limit=3),
        '',
        '## 护城河缺口',
        *hedge_gap_section(capital_graph),
        '',
        '## Thesis 焦点',
        *thesis_focus_lines(thesis_registry, watch_intent, limit=2),
        '',
        '## 场景敏感面',
        *invalidator_delta_lines(invalidator_ledger, limit=2),
        '',
        '## 市场机会雷达',
        *watchlist_lines(prices, watchlist, limit=1),
        *flow_proxy_lines(packet, limit=1),
        *broad_market_lines(broad_market, limit=1),
        *macro_triad_lines(prices, broad_market),
        '',
        '## 期权与风险雷达',
        *option_risk_lines(option_risk)[:2],
        *options_flow_lines(options_flow, limit=1),
        '',
        '## 分层证据',
        f"- 证据分布：{layer_counts}；本 capital delta report 只渲染资本竞争面，不展开证据流水。",
        '',
        '## 矛盾与裁决',
        *contradiction_lines(packet)[:2],
        '',
        '## 反证 / Invalidators',
        *invalidator_delta_lines(invalidator_ledger, limit=2),
        '',
        '## 下一步观察',
        '- ' + public_confirmations(confirmations),
        '',
        '## 数据质量',
        f"- validator={validation.get('outcome')}；thesis_refs={len(packet.get('thesis_refs') or [])}；"
        f"agenda_items={len(capital_agenda.get('agenda_items', []))}；"
        f"displacement_cases={len(displacement_cases.get('cases', []))}；"
        f"portfolio={portfolio_status or 'unknown'}。",
        '',
        '## 来源',
        '- 完整 packet / JudgmentEnvelope / thesis objects / capital graph 已写入 decision log；用户可见输出仍经过 product validation 与 delivery safety。',
    ]
    return '\n'.join(lines) + '\n'


def render_markdown(
    packet: dict[str, Any],
    judgment: dict[str, Any],
    validation: dict[str, Any],
    *,
    prices: dict[str, Any] | None = None,
    watchlist: dict[str, Any] | None = None,
    scan_state: dict[str, Any] | None = None,
    sec_discovery: dict[str, Any] | None = None,
    sec_semantics: dict[str, Any] | None = None,
    broad_market: dict[str, Any] | None = None,
    options_flow: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
    option_risk: dict[str, Any] | None = None,
) -> str:
    prices = prices or {}
    watchlist = watchlist or {}
    scan_state = scan_state or {}
    sec_discovery = sec_discovery or {}
    sec_semantics = sec_semantics or {}
    broad_market = broad_market or {}
    options_flow = options_flow or {}
    portfolio = portfolio or {}
    option_risk = option_risk or {}
    records = evidence_by_id(packet)
    cited = [records.get(ref) for ref in judgment.get('evidence_refs', []) if records.get(ref)]
    lines = [
        'Finance｜决策报告',
        '',
        '## 结论',
        f"- 当前状态：`{judgment.get('thesis_state')}`；`{judgment.get('actionability')}`；review-only，不下单。",
        '- 报告主轴：先找非持仓/非 watchlist 的机会拓展，其次确认 watchlist/flow，最后才看持仓影响。',
        '',
        '## 今日看点',
        *top_action_lines(packet, judgment, prices, watchlist, scan_state, options_flow, portfolio),
        '',
        '## 为什么现在',
        *why_now_lines(packet, judgment),
    ]
    if cited:
        cited_actionable = [
            record for record in cited
            if 'source status' not in str(record.get('normalized_summary', '')).lower()
            and 'source_status' not in str(record.get('source_kind', '')).lower()
        ]
        if cited_actionable and (packet.get('source_quality_summary') or {}).get('wake_eligible_count', 0):
            for record in cited_actionable[:1]:
                lines.append(evidence_line(record))
    else:
        lines.append('- 没有可作为 judgment support 的 evidence_refs。')
    lines.extend(['', '## 市场机会雷达（Watchlist / Flow）'])
    lines.extend(watchlist_lines(prices, watchlist, limit=2))
    lines.extend(flow_proxy_lines(packet, limit=2))
    lines.extend(broad_market_lines(broad_market, limit=1))
    lines.extend(macro_triad_lines(prices, broad_market))
    lines.extend(['', '## 未知探索（非持仓 / 非Watchlist）'])
    lines.extend(unknown_discovery_lines(scan_state, watchlist, portfolio, limit=1))
    sec_lines = sec_discovery_lines(sec_discovery, sec_semantics, watchlist)
    if sec_lines:
        lines.extend(sec_lines)
    lines.extend(['', '## 潜在机会 / 风险候选'])
    lines.extend(opportunity_lines(scan_state, watchlist, portfolio, limit=1))
    lines.extend(['', '## 期权与风险雷达'])
    lines.extend(option_risk_lines(option_risk))
    lines.extend(options_flow_lines(options_flow))
    lines.extend(['', '## 分层证据'])
    digest = packet.get('layer_digest') if isinstance(packet.get('layer_digest'), dict) else {}
    layer_counts = ', '.join(f'{layer}={len(digest.get(layer, []))}' for layer in ['L0', 'L1', 'L2', 'L3', 'L4'])
    lines.append(f"- 证据分布：{layer_counts}；详单保留在 packet，不在报告里展开。")
    lines.extend(['', '## 矛盾与裁决'])
    lines.extend(contradiction_lines(packet)[:2])
    if judgment.get('why_not'):
        for item in judgment.get('why_not', [])[:1]:
            lines.append(f"- why_not: {public_text(item)}")
    lines.extend(['', '## 持仓影响'])
    portfolio_status = portfolio.get('data_status') if isinstance(portfolio, dict) else None
    if portfolio_status in {'unavailable', 'portfolio_unavailable', 'stale_source', None}:
        lines.append('- 持仓源不可用或不新鲜；本轮不把持仓作为主轴，也不推断仓位收益/风险。')
    else:
        lines.extend(holding_impact(packet, portfolio)[:2])
    lines.extend(['', '## 反证 / Invalidators'])
    invalidators = judgment.get('invalidators', []) or ['source correction', 'packet staleness']
    lines.append('- ' + '; '.join(str(item) for item in invalidators[:4]))
    lines.extend(['', '## 下一步观察'])
    confirmations = judgment.get('required_confirmations', []) or ['wait for promoted evidence']
    lines.append('- ' + '; '.join(str(item) for item in confirmations[:2]))
    lines.extend(['', '## 数据质量'])
    summary = packet.get('source_quality_summary') if isinstance(packet.get('source_quality_summary'), dict) else {}
    lines.append(
        f"- wake-eligible={summary.get('wake_eligible_count', 0)}；judgment-support={summary.get('judgment_support_count', 0)}；"
        f"portfolio={portfolio_status or 'unknown'}；validator={validation.get('outcome')}。"
    )
    lines.extend(['', '## 来源'])
    lines.extend([
        '- 关键外部来源已列在候选行；完整 packet / judgment / evidence_refs 已写入 decision log。',
    ])
    return '\n'.join(lines) + '\n'


def sorted_theses(thesis_registry: dict[str, Any]) -> list[dict[str, Any]]:
    theses = [
        item for item in (thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else [])
        if isinstance(item, dict) and item.get('thesis_id') and item.get('status') in {'active', 'watch', 'candidate'}
    ]
    theses.sort(key=lambda item: (item.get('status') == 'active', str(item.get('instrument') or '')), reverse=True)
    return theses


def sorted_opportunities(opportunity_queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        item for item in (opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else [])
        if isinstance(item, dict) and item.get('candidate_id') and item.get('status') in {'candidate', 'promoted'}
    ]
    rows.sort(key=lambda item: float(item.get('score') or 0), reverse=True)
    return rows


def sorted_invalidators(invalidator_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        item for item in (invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else [])
        if isinstance(item, dict) and item.get('invalidator_id') and item.get('status') in {'open', 'hit'}
    ]
    rows.sort(key=lambda item: (int(item.get('hit_count') or 0), str(item.get('last_seen_at') or '')), reverse=True)
    return rows


def unique_top_opportunities(opportunity_queue: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Return top opportunities with repeated instruments collapsed for operator readability."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted_opportunities(opportunity_queue):
        instrument = str(item.get('instrument') or short(item.get('theme'), 24)).upper()
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
    theme = short(item.get('theme'), 82)
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


def agenda_is_unknown_discovery(item: dict[str, Any]) -> bool:
    text = f"{item.get('attention_justification') or ''} {' '.join(str(q) for q in item.get('required_questions', []) if q)}"
    return 'unknown_discovery' in text


def agenda_operator_label(item: dict[str, Any], opportunity_queue: dict[str, Any]) -> str:
    """Translate agenda internals into an operator-readable object label."""
    if agenda_is_unknown_discovery(item):
        symbols = [str(opp.get('instrument') or '').strip() for opp in unique_top_opportunities(opportunity_queue, limit=3)]
        symbols = [symbol for symbol in symbols if symbol]
        suffix = f"：{'/'.join(symbols)}" if symbols else ""
        return short(f"未知发现改道{suffix}（{humanize_agenda_justification(item)}）", 64)
    return humanize_agenda_justification(item)


def unknown_discovery_focus_line(item: dict[str, Any], opportunity_queue: dict[str, Any]) -> str:
    opps = unique_top_opportunities(opportunity_queue, limit=3)
    if not opps:
        return f"- A1 {agenda_operator_label(item, opportunity_queue)}，先判断值不值得进入深挖；不是下单建议。"
    objects = '；'.join(opportunity_operator_label(opp) for opp in opps)
    return f"- A1 实际指向 {objects}。要决定的是是否把本周注意力从 TSLA 单线挪出一部分；不是下单建议。"


def unknown_discovery_positive_for(opportunity_queue: dict[str, Any]) -> str:
    opps = unique_top_opportunities(opportunity_queue, limit=3)
    if not opps:
        return '未知发现候选'
    labels = []
    for opp in opps:
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
            labels.append(short(theme, 40))
    return '；'.join(labels[:3])


def sorted_agenda(capital_agenda: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        item for item in (capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else [])
        if isinstance(item, dict) and item.get('agenda_id')
    ]
    rows.sort(key=lambda item: float(item.get('priority_score') or 0), reverse=True)
    return rows


def primary_surface_label(capital_agenda: dict[str, Any], opportunity_queue: dict[str, Any], invalidator_ledger: dict[str, Any]) -> str:
    if sorted_agenda(capital_agenda):
        return '资本议程'
    if sorted_opportunities(opportunity_queue):
        return '新机会'
    if sorted_invalidators(invalidator_ledger):
        return '反证'
    return 'Review'


def build_object_surfaces(
    *,
    judgment: dict[str, Any],
    option_risk: dict[str, Any],
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    capital_agenda: dict[str, Any],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Build operator-facing aliases and thread object cards."""
    aliases: dict[str, str] = {}
    cards: list[dict[str, str]] = []
    theses = sorted_theses(thesis_registry)
    opportunities = sorted_opportunities(opportunity_queue)
    invalidators = sorted_invalidators(invalidator_ledger)
    agenda_items = sorted_agenda(capital_agenda)
    thesis_by_id = {str(item.get('thesis_id')): item for item in theses if item.get('thesis_id')}

    if agenda_items:
        item = agenda_items[0]
        linked = [str(thesis_by_id.get(ref, {}).get('instrument') or '') for ref in item.get('linked_thesis_ids', [])[:2]]
        linked = [value for value in linked if value]
        label_detail = ' / '.join(linked) if linked else agenda_operator_label(item, opportunity_queue)
        label = f"{AGENDA_TYPE_LABELS.get(str(item.get('agenda_type') or ''), '议程')}｜{label_detail}"
        aliases['A1'] = short(label, 48)
        cards.append({
            'handle': 'A1',
            'label': aliases['A1'],
            'role': (
                f"判断是否把 attention 分给 {unknown_discovery_positive_for(opportunity_queue)}"
                if agenda_is_unknown_discovery(item)
                else '本周需要判断是否值得占用 attention slot'
            ),
        })

    if theses:
        thesis = theses[0]
        aliases['T1'] = short(f"现有 Thesis｜{thesis.get('instrument')}", 48)
        cards.append({
            'handle': 'T1',
            'label': aliases['T1'],
            'role': f"当前主轴；状态={public_status(thesis.get('status'))}",
        })

    if invalidators:
        inv = invalidators[0]
        aliases['I1'] = short(f"反证｜{humanize_invalidator_desc(inv.get('description'))}", 48)
        cards.append({
            'handle': 'I1',
            'label': aliases['I1'],
            'role': f"削弱当前证据强度；hit_count={inv.get('hit_count')}",
        })

    for idx, opp in enumerate(unique_top_opportunities(opportunity_queue, limit=3), start=1):
        handle = f'O{idx}'
        aliases[handle] = short(f"机会｜{opportunity_operator_label(opp)}", 72)
        cards.append({
            'handle': handle,
            'label': aliases[handle],
            'role': '非持仓候选，用于比较本周 attention allocation',
        })

    if option_risk.get('data_status') in {'stale_source', 'unavailable', 'portfolio_unavailable'}:
        aliases.setdefault('I2', '反证｜期权/持仓数据不新鲜')
        cards.append({
            'handle': 'I2',
            'label': aliases['I2'],
            'role': '限制当前结论置信度',
        })

    return aliases, cards[:4]


def build_starter_queries(object_alias_map: dict[str, str], report_id: str) -> list[str]:
    queries: list[str] = []
    if 'A1' in object_alias_map:
        queries.extend(['why A1'])
        if 'T1' in object_alias_map:
            queries.append('compare A1 T1')
        queries.extend(['challenge A1', 'sources A1'])
    elif 'O1' in object_alias_map:
        queries.extend(['why O1'])
        if 'T1' in object_alias_map:
            queries.append('compare O1 T1')
        queries.extend(['challenge O1', 'sources O1'])
    elif 'T1' in object_alias_map:
        queries.extend(['why T1', 'challenge T1', 'sources T1'])
    queries.append(f'expand {report_id}')
    return queries[:6]


def build_operator_markdown(
    *,
    report_id: str,
    generated_at: str,
    judgment: dict[str, Any],
    option_risk: dict[str, Any],
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    capital_agenda: dict[str, Any],
    prices: dict[str, Any] | None = None,
    broad_market: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, str], list[str]]:
    """Build Discord primary and thread seed surfaces without polluting artifact markdown."""
    prices = prices or {}
    broad_market = broad_market or {}
    object_alias_map, thread_cards = build_object_surfaces(
        judgment=judgment,
        option_risk=option_risk,
        thesis_registry=thesis_registry,
        opportunity_queue=opportunity_queue,
        invalidator_ledger=invalidator_ledger,
        capital_agenda=capital_agenda,
    )
    starter_queries = build_starter_queries(object_alias_map, report_id)
    surface_label = primary_surface_label(capital_agenda, opportunity_queue, invalidator_ledger)
    agenda_items = sorted_agenda(capital_agenda)
    invalidators = sorted_invalidators(invalidator_ledger)
    theses = sorted_theses(thesis_registry)

    focus_handle = 'A1' if 'A1' in object_alias_map else 'O1' if 'O1' in object_alias_map else 'T1' if 'T1' in object_alias_map else 'I1'
    focus_label = object_alias_map.get(focus_handle, '本轮对象')
    top_agenda = agenda_items[0] if agenda_items else {}
    if focus_handle == 'A1' and agenda_is_unknown_discovery(top_agenda):
        focus_line = unknown_discovery_focus_line(top_agenda, opportunity_queue)
    else:
        focus_line = f'- {focus_handle} {focus_label}，先判断值不值得进入深挖；不是下单建议。'

    fact_lines: list[str] = []
    if agenda_items:
        top = agenda_items[0]
        if agenda_is_unknown_discovery(top):
            fact_lines.append(f"- A1 排第一的真实对象是：{unknown_discovery_positive_for(opportunity_queue)}。")
            fact_lines.append(f"- 触发方式是 {humanize_agenda_justification(top)}；这是 discovery lane 和当前主线打架，不是单票买卖信号。")
        else:
            fact_lines.append(f"- 当前资本议程共有 {len(agenda_items)} 项，A1 优先级最高：{humanize_agenda_justification(top)}。")
    elif opportunity_queue.get('candidates'):
        top_opp = sorted_opportunities(opportunity_queue)[0]
        fact_lines.append(f"- O1 当前是最高分机会候选：{short(top_opp.get('theme'), 90)}。")
    if theses:
        top_thesis = theses[0]
        fact_lines.append(f"- T1 当前仍是 {top_thesis.get('instrument')}；本轮判断仍是 review-only，不触发新动作。")
    if invalidators:
        top_inv = invalidators[0]
        fact_lines.append(f"- I1 {humanize_invalidator_desc(top_inv.get('description'))}；命中 {top_inv.get('hit_count')} 次。")
    macro_line = macro_triad_operator_line(prices, broad_market)
    if macro_line not in fact_lines:
        fact_lines.insert(min(2, len(fact_lines)), macro_line)
    if option_risk.get('data_status') in {'stale_source', 'unavailable', 'portfolio_unavailable'}:
        fact_lines.append(f"- 持仓/期权源当前是 `{option_risk.get('data_status')}`；结论置信度受限。")
    fact_lines = fact_lines[:4] or ['- 当前没有新的强信号；本轮仍是 review-only。']

    interpretation_lines = ['- 这是 attention allocation 问题，不是执行问题。']
    if focus_handle == 'A1':
        if agenda_is_unknown_discovery(top_agenda):
            interpretation_lines.append(f"- 如果要找新机会，优先深挖 {unknown_discovery_positive_for(opportunity_queue)}；如果只维护现有 book，它是在质疑 TSLA 是否仍应独占注意力。")
        else:
            interpretation_lines.append('- 更像“本周该不该占用注意力”，不是“现有 book 该不该立刻替代”。')
    elif focus_handle == 'O1':
        interpretation_lines.append('- 这是新机会候选，不是现有持仓的强制替代。')
    else:
        interpretation_lines.append('- 当前更像结构复核，而不是新判断或执行动作。')

    verify_lines = []
    if agenda_items and agenda_is_unknown_discovery(agenda_items[0]):
        verify_lines.extend([
            '- BNO：油价/霍尔木兹供给风险是否有价格、量能或 headline 二次确认',
            '- XLB/RGTI：板块 dislocation 或 IV 异动是否仍在延续，而不是一次性噪音',
        ])
    elif agenda_items and agenda_items[0].get('required_questions'):
        verify_lines.extend(f"- {humanize_required_question(item)}" for item in agenda_items[0].get('required_questions', [])[:2])
    else:
        verify_lines.extend(f"- {humanize_required_question(item)}" for item in (judgment.get('required_confirmations') or [])[:2])
    if not verify_lines:
        verify_lines = ['- 等待价格 / 流量二次确认', '- 确认当前 source freshness']

    object_lines = [f"- {handle} {label}" for handle, label in object_alias_map.items()]
    title = f'Finance｜{surface_label} | {et_time_label(generated_at)} | {report_id}'
    primary_lines = [
        title,
        '',
        '这次只看 1 件事：',
        focus_line,
        '',
        'Fact',
        *fact_lines,
        '',
        'Interpretation',
        *interpretation_lines,
        '',
        'To Verify',
        *verify_lines[:2],
        '',
        '对象',
        *object_lines,
        '',
        '追问：' + ' / '.join(starter_queries),
    ]
    primary_markdown = '\n'.join(primary_lines).strip() + '\n'

    thread_lines = [
        f'{report_id}｜深挖入口',
        '',
        '对象卡',
    ]
    for card in thread_cards:
        thread_lines.append(f"- {card['handle']} {card['label']}")
        thread_lines.append(f"  作用：{card['role']}")
    thread_lines.extend([
        '',
        '可直接追问',
        *[f'- {query}' for query in starter_queries],
    ])
    thread_seed_markdown = '\n'.join(thread_lines).strip() + '\n'
    return primary_markdown, thread_seed_markdown, object_alias_map, starter_queries


def build_report(
    packet: dict[str, Any],
    judgment: dict[str, Any],
    validation: dict[str, Any],
    *,
    prices: dict[str, Any] | None = None,
    watchlist: dict[str, Any] | None = None,
    scan_state: dict[str, Any] | None = None,
    sec_discovery: dict[str, Any] | None = None,
    sec_semantics: dict[str, Any] | None = None,
    broad_market: dict[str, Any] | None = None,
    options_flow: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
    option_risk: dict[str, Any] | None = None,
    watch_intent: dict[str, Any] | None = None,
    thesis_registry: dict[str, Any] | None = None,
    opportunity_queue: dict[str, Any] | None = None,
    invalidator_ledger: dict[str, Any] | None = None,
    shadow_delta: bool = False,
    report_mode: str = 'packet_first',
    capital_agenda: dict[str, Any] | None = None,
    capital_graph: dict[str, Any] | None = None,
    displacement_cases: dict[str, Any] | None = None,
    campaign_board: dict[str, Any] | None = None,
) -> dict[str, Any]:
    has_valid_capital_graph = bool(capital_graph and capital_graph.get('graph_hash'))
    if report_mode == 'capital_delta' and has_valid_capital_graph:
        effective_mode = 'capital_delta'
    elif report_mode == 'capital_delta':
        effective_mode = 'thesis_delta'  # deterministic fallback
    elif shadow_delta:
        effective_mode = 'thesis_delta_shadow'
    else:
        effective_mode = report_mode
    envelope = {
        'report_policy_version': POLICY_VERSION,
        'renderer_id': 'decision-report-deterministic-v1',
        'model_id': 'deterministic',
        'generated_at': now_iso(),
        'packet_id': packet.get('packet_id'),
        'packet_hash': packet.get('packet_hash'),
        'judgment_id': judgment.get('judgment_id'),
        'judgment_model_id': judgment.get('model_id'),
        'judgment_policy_version': judgment.get('policy_version'),
        'judgment_validation_outcome': validation.get('outcome'),
        'thesis_state': judgment.get('thesis_state'),
        'actionability': judgment.get('actionability'),
        'confidence': judgment.get('confidence'),
        'evidence_refs': judgment.get('evidence_refs', []),
        'thesis_refs': judgment.get('thesis_refs') or packet.get('thesis_refs', []),
        'scenario_refs': judgment.get('scenario_refs') or packet.get('scenario_refs', []),
        'opportunity_candidate_refs': judgment.get('opportunity_candidate_refs') or packet.get('opportunity_candidate_refs', []),
        'invalidator_refs': judgment.get('invalidator_refs') or packet.get('invalidator_refs', []),
        'source_quality_summary': packet.get('source_quality_summary', {}),
        'markdown': '',
        'report_hash': '',
    }
    if effective_mode == 'capital_delta':
        envelope['renderer_id'] = 'capital-delta-deterministic-v1'
        envelope['capital_agenda_refs'] = [item.get('agenda_id') for item in (capital_agenda or {}).get('agenda_items', [])[:5] if isinstance(item, dict)]
        envelope['displacement_case_refs'] = [c.get('case_id') for c in (displacement_cases or {}).get('cases', [])[:5] if isinstance(c, dict)]
        envelope['capital_graph_hash'] = (capital_graph or {}).get('graph_hash')
        envelope['markdown'] = render_capital_delta_markdown(
            packet,
            judgment,
            validation,
            prices=prices or {},
            watchlist=watchlist or {},
            scan_state=scan_state or {},
            broad_market=broad_market or {},
            options_flow=options_flow or {},
            portfolio=portfolio or {},
            option_risk=option_risk or {},
            watch_intent=watch_intent or {},
            thesis_registry=thesis_registry or {},
            opportunity_queue=opportunity_queue or {},
            invalidator_ledger=invalidator_ledger or {},
            capital_agenda=capital_agenda or {},
            capital_graph=capital_graph or {},
            displacement_cases=displacement_cases or {},
        )
    elif effective_mode in {'thesis_delta', 'thesis_delta_shadow'}:
        envelope['renderer_id'] = 'thesis-delta-shadow-deterministic-v1' if effective_mode == 'thesis_delta_shadow' else 'thesis-delta-deterministic-v1'
        envelope['markdown'] = render_delta_markdown(
            packet,
            judgment,
            validation,
            prices=prices or {},
            watchlist=watchlist or {},
            scan_state=scan_state or {},
            broad_market=broad_market or {},
            options_flow=options_flow or {},
            portfolio=portfolio or {},
            option_risk=option_risk or {},
            watch_intent=watch_intent or {},
            thesis_registry=thesis_registry or {},
            opportunity_queue=opportunity_queue or {},
            invalidator_ledger=invalidator_ledger or {},
            shadow=effective_mode == 'thesis_delta_shadow',
        )
    else:
        envelope['markdown'] = render_markdown(
            packet,
            judgment,
            validation,
            prices=prices,
            watchlist=watchlist,
            scan_state=scan_state,
            sec_discovery=sec_discovery,
            sec_semantics=sec_semantics,
            broad_market=broad_market,
            options_flow=options_flow,
            portfolio=portfolio,
            option_risk=option_risk,
        )
    report_id = report_short_id(envelope.get('packet_hash'), envelope.get('judgment_id'))
    primary_markdown, thread_seed_markdown, object_alias_map, starter_queries = build_operator_markdown(
        report_id=report_id,
        generated_at=envelope['generated_at'],
        judgment=judgment,
        option_risk=option_risk or {},
        thesis_registry=thesis_registry or {},
        opportunity_queue=opportunity_queue or {},
        invalidator_ledger=invalidator_ledger or {},
        capital_agenda=capital_agenda or {},
        prices=prices or {},
        broad_market=broad_market or {},
    )
    envelope['report_id'] = report_id
    envelope['discord_primary_markdown'] = primary_markdown
    if isinstance(campaign_board, dict) and campaign_board.get('status') == 'pass':
        envelope['discord_live_board_markdown'] = append_macro_triad_to_board(campaign_board.get('discord_live_board_markdown'), prices or {}, broad_market or {})
        envelope['discord_scout_board_markdown'] = append_macro_triad_to_board(campaign_board.get('discord_scout_board_markdown'), prices or {}, broad_market or {})
        envelope['discord_risk_board_markdown'] = append_macro_triad_to_board(campaign_board.get('discord_risk_board_markdown'), prices or {}, broad_market or {})
        envelope['campaign_board_ref'] = str(CAMPAIGN_BOARD)
        envelope['campaign_count'] = len(campaign_board.get('campaigns', []) if isinstance(campaign_board.get('campaigns'), list) else [])
    envelope['discord_thread_seed_markdown'] = thread_seed_markdown
    envelope['object_alias_map'] = object_alias_map
    envelope['starter_queries'] = starter_queries
    envelope['followup_bundle_path'] = str(FINANCE / 'state' / 'report-reader' / f'{report_id}.json')
    envelope['report_hash'] = hash_payload(envelope)
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', default=str(PACKET))
    parser.add_argument('--judgment', default=str(JUDGMENT))
    parser.add_argument('--judgment-validation', default=str(VALIDATION))
    parser.add_argument('--prices', default=str(PRICES))
    parser.add_argument('--watchlist', default=str(WATCHLIST))
    parser.add_argument('--scan-state', default=str(SCAN_STATE))
    parser.add_argument('--sec-discovery', default=str(SEC_DISCOVERY))
    parser.add_argument('--sec-semantics', default=str(SEC_SEMANTICS))
    parser.add_argument('--broad-market', default=str(BROAD_MARKET))
    parser.add_argument('--options-flow', default=str(OPTIONS_FLOW))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--option-risk', default=str(OPTION_RISK))
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--shadow-thesis-delta', action='store_true')
    parser.add_argument('--report-mode', choices=['thesis_delta', 'packet_first', 'capital_delta'], default='thesis_delta')
    parser.add_argument('--watch-intent', default=str(WATCH_INTENT))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--opportunity-queue', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--markdown-out', default=None)
    args = parser.parse_args(argv)
    out_path = Path(args.out)
    markdown_out = Path(args.markdown_out) if args.markdown_out else None
    if args.shadow_thesis_delta and args.out == str(OUT):
        out_path = SHADOW_DELTA_OUT
        markdown_out = markdown_out or SHADOW_DELTA_MARKDOWN
    packet = load_json_safe(Path(args.packet), {}) or {}
    judgment = load_json_safe(Path(args.judgment), {}) or {}
    validation = load_json_safe(Path(args.judgment_validation), {}) or {}
    report = build_report(
        packet,
        judgment,
        validation,
        prices=load_json_safe(Path(args.prices), {}) or {},
        watchlist=load_json_safe(Path(args.watchlist), {}) or load_json_safe(FALLBACK_WATCHLIST, {}) or {},
        scan_state=load_json_safe(Path(args.scan_state), {}) or {},
        sec_discovery=load_json_safe(Path(args.sec_discovery), {}) or {},
        sec_semantics=load_json_safe(Path(args.sec_semantics), {}) or {},
        broad_market=load_json_safe(Path(args.broad_market), {}) or {},
        options_flow=load_json_safe(Path(args.options_flow), {}) or {},
        portfolio=load_json_safe(Path(args.portfolio), {}) or {},
        option_risk=load_json_safe(Path(args.option_risk), {}) or {},
        watch_intent=load_json_safe(Path(args.watch_intent), {}) or {},
        thesis_registry=load_json_safe(Path(args.thesis_registry), {}) or {},
        opportunity_queue=load_json_safe(Path(args.opportunity_queue), {}) or {},
        invalidator_ledger=load_json_safe(Path(args.invalidator_ledger), {}) or {},
        shadow_delta=args.shadow_thesis_delta,
        report_mode=args.report_mode,
        capital_agenda=load_json_safe(CAPITAL_AGENDA, {}) or {},
        capital_graph=load_json_safe(CAPITAL_GRAPH, {}) or {},
        displacement_cases=load_json_safe(DISPLACEMENT_CASES_PATH, {}) or {},
        campaign_board=load_json_safe(Path(args.campaign_board), {}) or {},
    )
    atomic_write_json(out_path, report)
    if markdown_out:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(report['markdown'], encoding='utf-8')
    print(json.dumps({'status': 'pass', 'report_hash': report['report_hash'], 'out': str(out_path), 'markdown_out': str(markdown_out) if markdown_out else None}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
