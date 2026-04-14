#!/usr/bin/env python3
"""Portfolio intelligence — generates actionable alerts based on real positions.
Checks: option expiry proximity, loss thresholds, concentration risk, daily P&L delta.
Outputs alerts to state/portfolio-alerts.json for renderer consumption.
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
DEFAULT_PORTFOLIO = FINANCE / 'state' / 'portfolio.json'
PORTFOLIO = DEFAULT_PORTFOLIO
RESOLVED_PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
PRICES = FINANCE / 'state' / 'prices.json'
DEFAULT_HELD_TICKERS = FINANCE / 'state' / 'held-tickers.json'
HELD_TICKERS = DEFAULT_HELD_TICKERS
RESOLVED_HELD_TICKERS = FINANCE / 'state' / 'held-tickers-resolved.json'
ALERTS_OUT = FINANCE / 'state' / 'portfolio-alerts.json'
SEEN_OUT = FINANCE / 'state' / 'portfolio-alerts-seen.json'
TZ_CHI = ZoneInfo('America/Chicago')

# Thresholds
EXPIRY_WARN_DAYS = 14       # Warn when option expires within N days
LOSS_WARN_PCT = -30         # Warn when position loss exceeds N%
LOSS_CRITICAL_PCT = -50     # Critical when position loss exceeds N%
CONCENTRATION_WARN = 0.30   # Warn when single stock > 30% of portfolio
DAILY_MOVE_ALERT = 3.0      # Alert when a held stock moves > N% in a day
PORTFOLIO_STALE_HOURS = 24


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def portfolio_freshness(portfolio: dict, now: datetime) -> tuple[bool, float | None]:
    fetched_at = parse_iso_datetime(portfolio.get('fetched_at')) if isinstance(portfolio, dict) else None
    if fetched_at is None:
        return False, None
    age_hours = (now - fetched_at).total_seconds() / 3600
    return age_hours <= PORTFOLIO_STALE_HOURS, age_hours


def portfolio_invalidated_by_failed_refresh(portfolio: dict, held_tickers: dict) -> bool:
    """Treat last-good portfolio as unavailable if a newer IBKR refresh failed closed."""
    if not isinstance(portfolio, dict) or not isinstance(held_tickers, dict):
        return False
    if held_tickers.get('data_status') != 'ibkr_unavailable':
        return False
    failed_at = parse_iso_datetime(held_tickers.get('updated_at'))
    fetched_at = parse_iso_datetime(portfolio.get('fetched_at'))
    if failed_at is None:
        return False
    if fetched_at is None:
        return True
    return failed_at >= fetched_at


def alert_signature(alert: dict) -> str:
    """Stable identity for duplicate suppression.

    The goal is to emit a critical/expiry/daily alert once per position unless
    the position itself materially changes (size/contract/identity changes).
    """
    level = alert.get('level', 'info')
    kind = alert.get('type', 'unknown')
    if kind == 'loss':
        return alert.get('position_key') or f"{level}|loss|{alert.get('symbol', 'unknown')}"
    if kind == 'expiry':
        return alert.get('position_key') or f"{level}|expiry|{alert.get('description', 'unknown')}"
    if kind == 'daily_move':
        return alert.get('position_key') or f"{level}|daily_move|{alert.get('symbol', 'unknown')}"
    return alert.get('position_key') or f"{level}|{kind}|{alert.get('symbol', alert.get('message', 'unknown'))}"


def build_position_key(pos: dict) -> str:
    """Build a stable key that changes when the actual position changes."""
    asset_class = str(pos.get('asset_class', 'UNK'))
    symbol = str(pos.get('symbol', 'UNK'))
    direction = str(pos.get('direction', 'UNK'))
    qty = pos.get('quantity', 0)
    description = str(pos.get('description', ''))
    strike = pos.get('strike')
    expiry = pos.get('expiry')
    if asset_class == 'OPT':
        return f"{asset_class}|{symbol}|{direction}|{description}|{strike}|{expiry}|{qty}"
    return f"{asset_class}|{symbol}|{direction}|{qty}"


def parse_expiry(desc: str) -> datetime | None:
    """Extract expiry date from option description like 'TSLA DEC2026 600 C'."""
    months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
              'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
    parts = desc.split()
    for i, p in enumerate(parts):
        for m, num in months.items():
            if p.startswith(m) and len(p) == 7:  # e.g., "DEC2026"
                try:
                    year = int(p[3:])
                    # Default to 3rd Friday (approx) — good enough for alerts
                    return datetime(year, num, 15, tzinfo=timezone.utc)
                except ValueError:
                    pass
    return None


def check_expiry_alerts(options: list, now: datetime) -> list:
    alerts = []
    for opt in options:
        expiry = parse_expiry(opt['description'])
        if not expiry:
            continue
        days_to_expiry = (expiry - now).days
        if days_to_expiry <= 0:
            alerts.append({
                'level': 'critical',
                'type': 'expiry',
                'position_key': build_position_key(opt),
                'message': f"⚠️ {opt['description'][:40]} 已过期或今日到期！市值=${opt['mkt_value']:,.2f} 盈亏=${opt['unrealized_pnl']:+,.2f}",
                'days_remaining': days_to_expiry,
            })
        elif days_to_expiry <= EXPIRY_WARN_DAYS:
            alerts.append({
                'level': 'warning',
                'type': 'expiry',
                'position_key': build_position_key(opt),
                'message': f"📅 {opt['description'][:40]} 距到期还有 {days_to_expiry} 天，市值=${opt['mkt_value']:,.2f} 盈亏=${opt['unrealized_pnl']:+,.2f}",
                'days_remaining': days_to_expiry,
            })
    return sorted(alerts, key=lambda a: a.get('days_remaining', 999))


def check_loss_alerts(positions: list) -> list:
    alerts = []
    for pos in positions:
        pnl_pct = pos.get('pnl_pct', 0)
        if pnl_pct <= LOSS_CRITICAL_PCT:
            alerts.append({
                'level': 'critical',
                'type': 'loss',
                'position_key': build_position_key(pos),
                'message': f"🔴 {pos['symbol']} 亏损 {pnl_pct:+.1f}%（${pos['unrealized_pnl']:+,.2f}），已超过 {LOSS_CRITICAL_PCT}% 止损线",
            })
        elif pnl_pct <= LOSS_WARN_PCT:
            alerts.append({
                'level': 'warning',
                'type': 'loss',
                'position_key': build_position_key(pos),
                'message': f"🟡 {pos['symbol']} 亏损 {pnl_pct:+.1f}%（${pos['unrealized_pnl']:+,.2f}），接近止损线",
            })
    return alerts


def check_concentration(stocks: list, total_value: float) -> list:
    alerts = []
    if total_value <= 0:
        return alerts
    for s in stocks:
        weight = abs(s['mkt_value']) / total_value
        if weight > CONCENTRATION_WARN:
            alerts.append({
                'level': 'info',
                'type': 'concentration',
                'position_key': build_position_key(s),
                'message': f"📊 {s['symbol']} 占组合 {weight:.0%}（${s['mkt_value']:,.2f} / ${total_value:,.2f}），集中度偏高",
            })
    return alerts


def check_daily_moves(stocks: list, prices: dict) -> list:
    """Cross-reference held positions with today's price moves."""
    alerts = []
    if not prices or 'quotes' not in prices:
        return alerts

    held_symbols = {s['symbol'] for s in stocks}
    for symbol, quote in prices['quotes'].items():
        clean_sym = symbol.replace('-', '/')
        # Match held symbol
        match = None
        for held in held_symbols:
            if held == symbol or held == clean_sym or symbol.startswith(held):
                match = held
                break
        if not match:
            continue

        pct = quote.get('pct_change', 0)
        if abs(pct) >= DAILY_MOVE_ALERT:
            emoji = '📈' if pct > 0 else '📉'
            position = next((s for s in stocks if s['symbol'] == match), None)
            qty = position['quantity'] if position else 0
            day_pnl = round(qty * quote.get('change', 0), 2) if qty else 0
            alerts.append({
                'level': 'warning' if abs(pct) >= 5 else 'info',
                'type': 'daily_move',
                'position_key': build_position_key(position) if position else f"daily_move|{match}",
                'message': f"{emoji} {match} 今日 {pct:+.2f}%，持仓 {qty} 股，日内盈亏约 ${day_pnl:+,.2f}",
            })
    return alerts


def main():
    now = datetime.now(timezone.utc)
    portfolio_path = RESOLVED_PORTFOLIO if PORTFOLIO == DEFAULT_PORTFOLIO and RESOLVED_PORTFOLIO.exists() else PORTFOLIO
    held_path = RESOLVED_HELD_TICKERS if HELD_TICKERS == DEFAULT_HELD_TICKERS and RESOLVED_HELD_TICKERS.exists() else HELD_TICKERS
    portfolio = load_json_safe(portfolio_path, {})
    prices = load_json_safe(PRICES, {})
    held_tickers = load_json_safe(held_path, {})
    seen_state = load_json_safe(SEEN_OUT, {
        'seen_signatures': []
    })
    seen_signatures = set(seen_state.get('seen_signatures', []))

    if not portfolio or 'stocks' not in portfolio or portfolio.get('data_status') in {'unavailable', 'flex_unavailable'}:
        state = {
            'generated_at': now.isoformat(),
            'generated_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
            'data_status': portfolio.get('data_status') or 'portfolio_unavailable',
            'portfolio_fetched_at': portfolio.get('fetched_at'),
            'portfolio_age_hours': None,
            'alert_count': 0,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'alerts': [],
            'note': 'No fresh resolved portfolio source; alerts suppressed.',
        }
        atomic_write_json(ALERTS_OUT, state)
        atomic_write_json(SEEN_OUT, {
            'last_generated_at': now.isoformat(),
            'seen_signatures': sorted(seen_signatures),
        })
        print("⚠️ resolved portfolio unavailable; suppressing portfolio alerts")
        return

    portfolio_is_fresh, portfolio_age_hours = portfolio_freshness(portfolio, now)
    failed_refresh_invalidates_portfolio = portfolio_invalidated_by_failed_refresh(portfolio, held_tickers)
    if failed_refresh_invalidates_portfolio:
        state = {
            'generated_at': now.isoformat(),
            'generated_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
            'data_status': 'ibkr_unavailable',
            'portfolio_fetched_at': portfolio.get('fetched_at'),
            'ibkr_unavailable_at': held_tickers.get('updated_at'),
            'portfolio_age_hours': round(portfolio_age_hours, 2) if isinstance(portfolio_age_hours, (int, float)) else None,
            'alert_count': 0,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'alerts': [],
            'note': 'Latest IBKR refresh failed after the last portfolio snapshot; alerts suppressed to avoid acting on stale holdings.',
        }
        atomic_write_json(ALERTS_OUT, state)
        atomic_write_json(SEEN_OUT, {
            'last_generated_at': now.isoformat(),
            'seen_signatures': sorted(seen_signatures),
        })
        print("⚠️ latest IBKR refresh failed; suppressing portfolio alerts")
        return

    if not portfolio_is_fresh:
        state = {
            'generated_at': now.isoformat(),
            'generated_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
            'data_status': 'stale_portfolio',
            'portfolio_fetched_at': portfolio.get('fetched_at'),
            'portfolio_age_hours': round(portfolio_age_hours, 2) if isinstance(portfolio_age_hours, (int, float)) else None,
            'alert_count': 0,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'alerts': [],
            'note': f'portfolio.json is stale (> {PORTFOLIO_STALE_HOURS}h); alerts suppressed until portfolio_fetcher refreshes state.',
        }
        atomic_write_json(ALERTS_OUT, state)
        atomic_write_json(SEEN_OUT, {
            'last_generated_at': now.isoformat(),
            'seen_signatures': sorted(seen_signatures),
        })
        print(f"⚠️ portfolio.json stale ({state['portfolio_age_hours']}h); suppressing alerts")
        return

    stocks = portfolio.get('stocks', [])
    options = portfolio.get('options', [])
    total_value = portfolio.get('summary', {}).get('total_portfolio_value', 0)

    all_alerts = []
    all_alerts.extend(check_expiry_alerts(options, now))
    all_alerts.extend(check_loss_alerts(stocks + options))
    all_alerts.extend(check_concentration(stocks, total_value))
    all_alerts.extend(check_daily_moves(stocks, prices))

    # Suppress alerts already emitted for the same underlying position.
    new_alerts = []
    new_signatures = []
    for alert in all_alerts:
        sig = alert_signature(alert)
        if sig in seen_signatures:
            continue
        new_alerts.append(alert)
        new_signatures.append(sig)
        seen_signatures.add(sig)

    # Sort: critical first, then warning, then info
    priority = {'critical': 0, 'warning': 1, 'info': 2}
    new_alerts.sort(key=lambda a: priority.get(a.get('level', 'info'), 3))

    state = {
        'generated_at': now.isoformat(),
        'generated_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'alert_count': len(new_alerts),
        'critical': sum(1 for a in new_alerts if a['level'] == 'critical'),
        'warning': sum(1 for a in new_alerts if a['level'] == 'warning'),
        'info': sum(1 for a in new_alerts if a['level'] == 'info'),
        'alerts': new_alerts,
    }

    atomic_write_json(ALERTS_OUT, state)
    atomic_write_json(SEEN_OUT, {
        'last_generated_at': now.isoformat(),
        'seen_signatures': sorted(seen_signatures),
    })

    if not new_alerts:
        print("✅ 无告警")
    else:
        print(f"📋 生成 {len(new_alerts)} 条新告警 (critical={state['critical']} warning={state['warning']} info={state['info']})")
        print()
        for a in new_alerts:
            print(f"  {a['message']}")


if __name__ == '__main__':
    main()
