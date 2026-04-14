#!/usr/bin/env python3
"""IBKR portfolio fetcher — reads real positions via Client Portal API.
Writes structured portfolio state to state/portfolio.json.
Options are parsed into structured fields (symbol, strike, expiry, put/call, DTE).
Also writes state/held-tickers.json for scanner boost consumption.

Default mode is phone/TWS-priority snapshot-only: it reads an already active
brokerage session but will not claim/compete for one. Use
`--claim-brokerage-session` only during an explicit short API snapshot window.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path('/Users/leofitz/.openclaw/workspace/ops/scripts')))
from atomic_io import atomic_write_json

TZ_CHI = ZoneInfo('America/Chicago')
TZ_ET = ZoneInfo('America/New_York')
FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
PORTFOLIO_STATE = FINANCE / 'state' / 'portfolio.json'
HELD_TICKERS = FINANCE / 'state' / 'held-tickers.json'
TARGET_ACCOUNT = 'U18011257'

MONTHS = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
          'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}


def write_unavailable_held_tickers(now: datetime, reason: str, mode: str = 'snapshot-only') -> None:
    held = {
        'updated_at': now.isoformat(),
        'data_status': 'ibkr_unavailable',
        'ibkr_session_mode': mode,
        'tickers': {},
        'scanner_boost_note': 'IBKR unavailable; held-ticker boost disabled until portfolio_fetcher refresh succeeds.',
        'stale_reason': reason,
    }
    atomic_write_json(HELD_TICKERS, held)


def fetch_positions(allow_brokerage_claim: bool = False):
    import ibkr_reader
    try:
        raw = ibkr_reader.request(
            f'portfolio/{TARGET_ACCOUNT}/positions',
            allow_brokerage_claim=allow_brokerage_claim,
        )
    except Exception as exc:
        return None, str(exc)
    if not isinstance(raw, list):
        return None, f"Unexpected response: {type(raw)}"
    return raw, None


def parse_option_desc(desc: str, now: datetime) -> dict:
    """Parse 'TSLA DEC2026 600 C [TSLA 261218C00600000 100]' into structured fields."""
    parts = desc.split()
    underlying = parts[0] if parts else '?'
    put_or_call = None
    strike = None
    expiry_date = None
    dte = None

    for p in parts:
        if p in ('C', 'P'):
            put_or_call = 'call' if p == 'C' else 'put'
        # Match "DEC2026" pattern
        for m, num in MONTHS.items():
            if p.startswith(m) and len(p) == 7:
                try:
                    year = int(p[3:])
                    # Parse exact date from OCC symbol if available
                    expiry_date = datetime(year, num, 15, tzinfo=timezone.utc)
                except ValueError:
                    pass
        # Match strike price
        try:
            val = float(p)
            if 0.5 < val < 10000:
                strike = val
        except ValueError:
            pass

    # Try to parse exact date from OCC symbol in brackets [TSLA 261218C00600000 100]
    bracket = re.search(r'\[(\w+)\s+(\d{6})([CP])(\d+)\s+(\d+)\]', desc)
    if bracket:
        occ_date = bracket.group(2)  # "261218"
        try:
            y = 2000 + int(occ_date[:2])
            m = int(occ_date[2:4])
            d = int(occ_date[4:6])
            expiry_date = datetime(y, m, d, 16, 0, tzinfo=TZ_ET)
        except ValueError:
            pass
        occ_strike = int(bracket.group(4)) / 1000
        if occ_strike > 0:
            strike = occ_strike
        put_or_call = 'call' if bracket.group(3) == 'C' else 'put'

    if expiry_date:
        dte = (expiry_date - now).days

    return {
        'underlying': underlying,
        'strike': strike,
        'expiry': expiry_date.strftime('%Y-%m-%d') if expiry_date else None,
        'dte': dte,
        'put_or_call': put_or_call,
    }


def classify_position(pos: dict, now: datetime) -> dict:
    asset_class = pos.get('assetClass', 'STK')
    desc = pos.get('contractDesc', '')
    symbol = desc.split()[0] if desc else '?'
    qty = pos.get('position', 0)
    mkt_value = pos.get('mktValue', 0)
    mkt_price = pos.get('mktPrice', 0)
    avg_cost = pos.get('avgCost', 0)
    avg_price = pos.get('avgPrice', 0)
    unrealized_pnl = pos.get('unrealizedPnl', 0)
    realized_pnl = pos.get('realizedPnl', 0)

    cost_basis = avg_cost * abs(qty) if asset_class == 'STK' else avg_cost
    pnl_pct = round((unrealized_pnl / cost_basis) * 100, 2) if cost_basis else 0

    result = {
        'symbol': symbol,
        'description': desc,
        'asset_class': asset_class,
        'quantity': qty,
        'direction': 'long' if qty > 0 else 'short',
        'mkt_price': round(mkt_price, 2),
        'mkt_value': round(mkt_value, 2),
        'avg_price': round(avg_price, 2),
        'cost_basis': round(cost_basis, 2),
        'unrealized_pnl': round(unrealized_pnl, 2),
        'pnl_pct': pnl_pct,
    }

    if asset_class == 'OPT':
        opt_info = parse_option_desc(desc, now)
        result.update({
            'underlying': opt_info['underlying'],
            'strike': opt_info['strike'],
            'expiry': opt_info['expiry'],
            'dte': opt_info['dte'],
            'put_or_call': opt_info['put_or_call'],
            'multiplier': 100,
        })

    return result


def build_held_tickers(stocks: list, options: list) -> dict:
    """Build a ticker->exposure map for scanner boost.
    This tells the scanner: these tickers matter MORE because we hold them."""
    exposure = {}
    for s in stocks:
        sym = s['symbol']
        exposure.setdefault(sym, {'stock_qty': 0, 'stock_value': 0, 'options': [],
                                   'total_exposure': 0, 'direction': 'long'})
        exposure[sym]['stock_qty'] = s['quantity']
        exposure[sym]['stock_value'] = s['mkt_value']
        exposure[sym]['total_exposure'] += abs(s['mkt_value'])
        if s['quantity'] < 0:
            exposure[sym]['direction'] = 'short'

    for o in options:
        und = o.get('underlying', o['symbol'])
        exposure.setdefault(und, {'stock_qty': 0, 'stock_value': 0, 'options': [],
                                   'total_exposure': 0, 'direction': 'long'})
        exposure[und]['options'].append({
            'type': o.get('put_or_call', '?'),
            'strike': o.get('strike'),
            'expiry': o.get('expiry'),
            'dte': o.get('dte'),
            'qty': o['quantity'],
            'value': o['mkt_value'],
            'pnl': o['unrealized_pnl'],
        })
        exposure[und]['total_exposure'] += abs(o['mkt_value'])

    return exposure


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='Fetch IBKR portfolio snapshot.')
    parser.add_argument(
        '--claim-brokerage-session',
        action='store_true',
        help='Explicitly compete for/claim the IBKR brokerage session for this snapshot window.',
    )
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    session_mode = 'brokerage-claim' if args.claim_brokerage_session else 'snapshot-only'

    positions_raw, err = fetch_positions(allow_brokerage_claim=args.claim_brokerage_session)
    if err:
        write_unavailable_held_tickers(now, err, mode=session_mode)
        print(f"❌ IBKR fetch failed: {err}", file=sys.stderr)
        sys.exit(1)

    stocks = []
    options = []
    for p in positions_raw:
        if p.get('position', 0) == 0:
            continue
        classified = classify_position(p, now)
        if classified['asset_class'] == 'STK':
            stocks.append(classified)
        elif classified['asset_class'] == 'OPT':
            options.append(classified)

    total_stock_value = sum(s['mkt_value'] for s in stocks)
    total_option_value = sum(o['mkt_value'] for o in options)
    total_unrealized = sum(s['unrealized_pnl'] for s in stocks) + sum(o['unrealized_pnl'] for o in options)

    # Options summary by expiry
    expiry_buckets = {}
    for o in options:
        exp = o.get('expiry', 'unknown')
        expiry_buckets.setdefault(exp, []).append(o)

    state = {
        'fetched_at': now.isoformat(),
        'fetched_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'account_id': TARGET_ACCOUNT,
        'source': 'IBKR Client Portal API',
        'ibkr_session_mode': session_mode,
        'summary': {
            'stock_positions': len(stocks),
            'option_positions': len(options),
            'total_stock_value': round(total_stock_value, 2),
            'total_option_value': round(total_option_value, 2),
            'total_portfolio_value': round(total_stock_value + total_option_value, 2),
            'total_unrealized_pnl': round(total_unrealized, 2),
            'options_by_expiry': {k: len(v) for k, v in sorted(expiry_buckets.items())},
        },
        'stocks': sorted(stocks, key=lambda s: abs(s['mkt_value']), reverse=True),
        'options': sorted(options, key=lambda o: o.get('dte') or 9999),  # Sort by nearest expiry
    }

    atomic_write_json(PORTFOLIO_STATE, state)

    # Build held-tickers for scanner boost
    exposure = build_held_tickers(stocks, options)
    held = {
        'updated_at': now.isoformat(),
        'ibkr_session_mode': session_mode,
        'tickers': exposure,
        'scanner_boost_note': '持有的标的在 scanner 评分中 importance 自动 +2，持有期权的标的 +3',
    }
    atomic_write_json(HELD_TICKERS, held)

    # Output
    print(f"✅ Portfolio: {len(stocks)} stocks + {len(options)} options")
    print(f"   总市值: ${state['summary']['total_portfolio_value']:,.2f}")
    print(f"   未实现盈亏: ${total_unrealized:,.2f}")

    print("\n── 股票 ──")
    for s in stocks:
        emoji = '🟢' if s['unrealized_pnl'] >= 0 else '🔴'
        d = '空' if s['direction'] == 'short' else '多'
        print(f"  {emoji} {s['symbol']:6s} {d} {abs(s['quantity']):>5.0f}股 "
              f"${s['mkt_price']:>8.2f} 市值${s['mkt_value']:>10,.2f} "
              f"盈亏${s['unrealized_pnl']:>+9,.2f} ({s['pnl_pct']:>+.1f}%)")

    print("\n── 期权（按到期日排序）──")
    for o in options:
        emoji = '🟢' if o['unrealized_pnl'] >= 0 else '🔴'
        pc = o.get('put_or_call', '?')[0].upper() if o.get('put_or_call') else '?'
        dte_str = f"{o['dte']}天" if o.get('dte') is not None else '?天'
        d = '空' if o['direction'] == 'short' else '多'
        print(f"  {emoji} {o.get('underlying', '?'):5s} {o.get('expiry', '?'):10s} "
              f"${o.get('strike', 0):>7.0f}{pc} {d}{abs(o['quantity']):>2.0f}张 "
              f"DTE={dte_str:>5s} 市值${o['mkt_value']:>8,.2f} 盈亏${o['unrealized_pnl']:>+9,.2f}")

    print(f"\n📊 持仓标的已写入 held-tickers.json（{len(exposure)} 个 ticker）供 scanner 增权")


if __name__ == '__main__':
    main()
