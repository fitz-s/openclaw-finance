#!/usr/bin/env python3
"""Scoring calibration loop — compares historical signal scores vs actual price moves.
Runs weekly, reads archived buffers + prices, outputs calibration adjustments.
Writes updated anchor examples to state/calibration-anchors.json for scanner consumption.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
ARCHIVE = FINANCE / 'buffer' / 'archive'
PRICES = FINANCE / 'state' / 'prices.json'
CALIBRATION_OUT = FINANCE / 'state' / 'calibration-anchors.json'
CALIBRATION_HISTORY = FINANCE / 'state' / 'calibration-history.jsonl'

KNOWN_TICKERS = {'AAPL', 'MSFT', 'NVDA', 'TSLA', 'SPY', 'QQQ', 'BTC', 'GOOG',
                 'HIMS', 'IAU', 'MSTR', 'NFLX', 'ORCL', 'SMR', 'VOO', 'RGTI', 'LUMN'}


def load_archived_signals(days: int = 7) -> list:
    if not ARCHIVE.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    signals = []
    for f in sorted(ARCHIVE.glob('*.json')):
        # Parse date from filename like "2026-03-26-scan-1520.json"
        try:
            date_part = '-'.join(f.stem.split('-')[:3])
            fdate = datetime.strptime(date_part, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            if fdate < cutoff:
                continue
        except ValueError:
            continue
        data = load_json_safe(f, {})
        for obs in data.get('observations', []):
            obs['_file'] = f.name
            obs['_date'] = date_part
            signals.append(obs)
    return signals


def extract_mentioned_tickers(signal: dict) -> set:
    text = (signal.get('theme', '') + ' ' + signal.get('description', '') +
            ' ' + signal.get('summary', '')).upper()
    return {t for t in KNOWN_TICKERS if t in text}


def build_score_vs_move_table(signals: list, prices: dict) -> list:
    """For each ticker mentioned in signals, compare avg importance vs actual price move."""
    if not prices or 'quotes' not in prices:
        return []

    ticker_scores = defaultdict(list)
    for s in signals:
        tickers = extract_mentioned_tickers(s)
        imp = s.get('importance', 0)
        if isinstance(imp, (int, float)):
            for t in tickers:
                ticker_scores[t].append(imp)

    results = []
    for ticker, scores in ticker_scores.items():
        price_key = ticker if ticker != 'BTC' else 'BTC-USD'
        quote = prices.get('quotes', {}).get(price_key, {})
        if quote.get('status') != 'ok':
            continue
        avg_imp = sum(scores) / len(scores)
        pct_move = abs(quote.get('pct_change', 0))
        # Calibration: high importance should correlate with high absolute move
        expected_imp = _move_to_expected_importance(pct_move)
        drift = avg_imp - expected_imp
        results.append({
            'ticker': ticker,
            'signal_count': len(scores),
            'avg_importance': round(avg_imp, 2),
            'actual_abs_move_pct': round(pct_move, 2),
            'expected_importance': expected_imp,
            'drift': round(drift, 2),  # positive = over-scored, negative = under-scored
        })
    return sorted(results, key=lambda r: abs(r['drift']), reverse=True)


def _move_to_expected_importance(abs_pct: float) -> float:
    """Map absolute price move to expected importance score."""
    if abs_pct >= 10:
        return 9.0
    elif abs_pct >= 5:
        return 7.5
    elif abs_pct >= 3:
        return 6.0
    elif abs_pct >= 1.5:
        return 5.0
    elif abs_pct >= 0.5:
        return 3.5
    else:
        return 2.0


def generate_calibrated_anchors(table: list) -> dict:
    """Generate updated anchor examples based on calibration data."""
    under_scored = [r for r in table if r['drift'] < -1.5]
    over_scored = [r for r in table if r['drift'] > 1.5]
    well_calibrated = [r for r in table if abs(r['drift']) <= 1.5]

    anchors = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'calibration_summary': {
            'total_tickers_analyzed': len(table),
            'under_scored': len(under_scored),
            'over_scored': len(over_scored),
            'well_calibrated': len(well_calibrated),
        },
        'adjustments': [],
        'anchor_examples': _build_anchor_text(table),
    }

    for r in under_scored:
        anchors['adjustments'].append({
            'ticker': r['ticker'],
            'direction': 'increase',
            'reason': f"实际波动 {r['actual_abs_move_pct']}% 但平均评分仅 {r['avg_importance']}（期望 {r['expected_importance']}）",
        })
    for r in over_scored:
        anchors['adjustments'].append({
            'ticker': r['ticker'],
            'direction': 'decrease',
            'reason': f"实际波动仅 {r['actual_abs_move_pct']}% 但平均评分 {r['avg_importance']}（期望 {r['expected_importance']}）",
        })

    return anchors


def _build_anchor_text(table: list) -> str:
    """Build human-readable anchor text that scanner can consume."""
    lines = ["根据最近校准数据的评分参考："]
    for r in table[:8]:
        move_desc = f"{r['ticker']} 波动 {r['actual_abs_move_pct']}%"
        if r['drift'] < -1:
            lines.append(f"- {move_desc} → 建议 importance≈{r['expected_importance']}（之前偏低，给了 {r['avg_importance']}）")
        elif r['drift'] > 1:
            lines.append(f"- {move_desc} → 建议 importance≈{r['expected_importance']}（之前偏高，给了 {r['avg_importance']}）")
        else:
            lines.append(f"- {move_desc} → importance≈{r['avg_importance']} ✓ 合理")
    return '\n'.join(lines)


def main():
    print("=" * 50)
    print("  打分校准循环")
    print("=" * 50)

    signals = load_archived_signals(days=7)
    prices = load_json_safe(PRICES, {})

    print(f"\n分析 {len(signals)} 条近 7 天信号...")

    table = build_score_vs_move_table(signals, prices)
    if not table:
        print("⚠️ 无法生成校准表（缺少价格数据或归档信号）")
        return

    print("\n── 校准对照表 ──")
    for r in table:
        emoji = '✅' if abs(r['drift']) <= 1.5 else ('⬆️' if r['drift'] < 0 else '⬇️')
        print(f"  {emoji} {r['ticker']:6s} 信号{r['signal_count']:>3d}条 "
              f"平均imp={r['avg_importance']:>5.2f} 实际波动={r['actual_abs_move_pct']:>5.2f}% "
              f"期望imp={r['expected_importance']:>4.1f} 偏差={r['drift']:>+5.2f}")

    anchors = generate_calibrated_anchors(table)
    atomic_write_json(CALIBRATION_OUT, anchors)

    # Append to history
    CALIBRATION_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_HISTORY, 'a') as f:
        f.write(json.dumps({
            'at': datetime.now(timezone.utc).isoformat(),
            'table': table,
        }, ensure_ascii=False) + '\n')

    print(f"\n── 校准结果 ──")
    s = anchors['calibration_summary']
    print(f"  评分偏低（需提高）: {s['under_scored']} 个 ticker")
    print(f"  评分偏高（需降低）: {s['over_scored']} 个 ticker")
    print(f"  校准良好: {s['well_calibrated']} 个 ticker")
    print(f"\n已写入 {CALIBRATION_OUT}")
    print(f"Scanner 下次运行时可读取此文件作为动态锚点补充")


if __name__ == '__main__':
    main()
