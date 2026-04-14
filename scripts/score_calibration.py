#!/usr/bin/env python3
"""Score calibration analysis — evaluates LLM scanner scoring quality.

Reads accumulated signals from scan state and archived buffers,
cross-references with actual price movements from prices.json,
and produces a calibration report showing:
- Score distribution (are most signals clustered at 5-6 or spread out?)
- Top-scored signals vs actual market impact
- Duplicate/near-duplicate detection rate
- Decay survivor analysis (what survives vs what gets pruned)

Usage:
  python3 score_calibration.py              # analyze current state
  python3 score_calibration.py --full       # analyze current + archived buffers
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
SCAN_STATE = FINANCE / 'state' / 'intraday-open-scan-state.json'
PRICES = FINANCE / 'state' / 'prices.json'
ARCHIVE = FINANCE / 'buffer' / 'archive'


def load(path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def analyze_score_distribution(signals: list) -> dict:
    """Analyze how scores are distributed across signals."""
    dims = ['urgency', 'importance', 'novelty', 'cumulative_value']
    dist = {}
    for dim in dims:
        values = [s.get(dim, 0) for s in signals]
        if not values:
            continue
        # Bucket into ranges
        buckets = Counter()
        for v in values:
            if v < 1.5:
                buckets['< 1.5 (会被衰减淘汰)'] += 1
            elif v < 3:
                buckets['1.5-3 (低)'] += 1
            elif v < 5:
                buckets['3-5 (中)'] += 1
            elif v < 7:
                buckets['5-7 (高)'] += 1
            elif v < 9:
                buckets['7-9 (很高)'] += 1
            else:
                buckets['9+ (危机级)'] += 1
        dist[dim] = {
            '平均': round(sum(values) / len(values), 2),
            '最高': round(max(values), 2),
            '最低': round(min(values), 2),
            '分布': dict(sorted(buckets.items())),
        }
    return dist


def analyze_top_signals(signals: list, n: int = 5) -> list:
    """Extract the top-N signals by importance and check their themes."""
    sorted_by_imp = sorted(signals, key=lambda s: s.get('importance', 0), reverse=True)
    top = []
    for s in sorted_by_imp[:n]:
        top.append({
            '主题': s.get('theme', '?')[:80],
            'importance': s.get('importance', 0),
            'urgency': s.get('urgency', 0),
            'cv': s.get('cumulative_value', 0),
            '来源': (s.get('sources', ['?']) or ['?'])[0][:40],
        })
    return top


def detect_near_duplicates(signals: list) -> list:
    """Find signals with very similar themes."""
    dupes = []
    themes = [(i, s.get('theme', '').lower().strip()) for i, s in enumerate(signals)]
    for i, (idx_a, theme_a) in enumerate(themes):
        for idx_b, theme_b in themes[i + 1:]:
            if not theme_a or not theme_b:
                continue
            # Check substring overlap
            shorter, longer = sorted([theme_a, theme_b], key=len)
            if len(shorter) > 15 and shorter in longer:
                dupes.append({
                    'a': theme_a[:60],
                    'b': theme_b[:60],
                    '类型': '子串包含',
                })
            # Check high word overlap
            words_a = set(theme_a.split())
            words_b = set(theme_b.split())
            if len(words_a) > 3 and len(words_b) > 3:
                overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
                if overlap > 0.7:
                    dupes.append({
                        'a': theme_a[:60],
                        'b': theme_b[:60],
                        '类型': f'词重叠 {overlap:.0%}',
                    })
    return dupes


def cross_reference_prices(signals: list, prices: dict) -> list:
    """Check if high-importance signals about specific tickers correlate with price moves."""
    if not prices or 'quotes' not in prices:
        return [{'提示': 'prices.json 不可用，无法交叉验证'}]

    ticker_signals = defaultdict(list)
    known_tickers = {'AAPL', 'MSFT', 'NVDA', 'TSLA', 'SPY', 'QQQ', 'BTC'}

    for s in signals:
        theme = s.get('theme', '').upper()
        summary = s.get('summary', '').upper()
        text = theme + ' ' + summary
        for ticker in known_tickers:
            if ticker in text:
                ticker_signals[ticker].append(s)

    results = []
    for ticker, sigs in ticker_signals.items():
        price_key = ticker if ticker != 'BTC' else 'BTC-USD'
        quote = prices['quotes'].get(price_key, {})
        if quote.get('status') != 'ok':
            continue
        avg_importance = sum(s.get('importance', 0) for s in sigs) / len(sigs)
        pct = quote.get('pct_change', 0)
        results.append({
            'ticker': ticker,
            '信号数': len(sigs),
            '平均 importance': round(avg_importance, 2),
            '实际涨跌%': round(pct, 2),
            '绝对波动': round(abs(pct), 2),
            '判断': '合理' if (avg_importance >= 5 and abs(pct) >= 1) or (avg_importance < 5 and abs(pct) < 1) else '待校准',
        })
    return results


def load_archived_signals(limit: int = 100) -> list:
    """Load signals from archived buffer files."""
    if not ARCHIVE.exists():
        return []
    all_signals = []
    files = sorted(ARCHIVE.glob('*.json'), reverse=True)[:limit]
    for f in files:
        data = load(f, {})
        for obs in data.get('observations', []):
            obs['_source_file'] = f.name
            all_signals.append(obs)
    return all_signals


def main():
    full_mode = '--full' in sys.argv

    scan = load(SCAN_STATE, {})
    current_signals = scan.get('accumulated', [])
    prices = load(PRICES, {})

    print("=" * 60)
    print("  Finance Scanner 打分校准分析")
    print("=" * 60)
    print()

    # 1. Current state overview
    print(f"📊 当前累积信号数: {len(current_signals)}")
    print(f"📅 最后扫描: {scan.get('last_scan_time', '?')}")
    print(f"📅 最后衰减: {scan.get('last_decay_time', '?')}")
    print()

    # 2. Score distribution
    print("── 评分分布 ──")
    dist = analyze_score_distribution(current_signals)
    for dim, info in dist.items():
        print(f"\n  {dim}: 平均={info['平均']} 最高={info['最高']} 最低={info['最低']}")
        for bucket, count in info['分布'].items():
            bar = '█' * count
            print(f"    {bucket}: {count} {bar}")

    # 3. Top signals
    print("\n── Top 5 高 importance 信号 ──")
    for i, s in enumerate(analyze_top_signals(current_signals), 1):
        print(f"\n  #{i} importance={s['importance']} urgency={s['urgency']} cv={s['cv']}")
        print(f"     主题: {s['主题']}")
        print(f"     来源: {s['来源']}")

    # 4. Duplicate detection
    dupes = detect_near_duplicates(current_signals)
    print(f"\n── 近似重复检测 ({len(dupes)} 对) ──")
    for d in dupes[:5]:
        print(f"  [{d['类型']}]")
        print(f"    A: {d['a']}")
        print(f"    B: {d['b']}")

    # 5. Price cross-reference
    print("\n── 价格交叉验证 ──")
    xref = cross_reference_prices(current_signals, prices)
    for r in xref:
        if '提示' in r:
            print(f"  {r['提示']}")
        else:
            emoji = '✅' if r['判断'] == '合理' else '⚠️'
            print(f"  {emoji} {r['ticker']}: {r['信号数']}条信号 平均importance={r['平均 importance']} → 实际涨跌={r['实际涨跌%']}% [{r['判断']}]")

    # 6. Decay survivor analysis
    print("\n── 衰减生存分析 ──")
    survivors = [s for s in current_signals if max(s.get('urgency', 0), s.get('importance', 0), s.get('cumulative_value', 0)) >= 1.5]
    zombies = [s for s in current_signals if max(s.get('urgency', 0), s.get('importance', 0), s.get('cumulative_value', 0)) < 1.5]
    print(f"  存活 (≥1.5): {len(survivors)} 条")
    print(f"  僵尸 (<1.5, 应被下轮清除): {len(zombies)} 条")
    if zombies:
        for z in zombies[:3]:
            print(f"    → {z.get('theme', '?')[:50]} (imp={z.get('importance', 0)} urg={z.get('urgency', 0)})")

    # 7. Archive analysis (if --full)
    if full_mode:
        print("\n── 归档信号统计 (--full) ──")
        archived = load_archived_signals(50)
        print(f"  已分析 {len(archived)} 条归档信号")
        if archived:
            arch_dist = analyze_score_distribution(archived)
            for dim, info in arch_dist.items():
                print(f"  {dim}: 平均={info['平均']}")

    print("\n" + "=" * 60)
    print("  校准建议")
    print("=" * 60)

    # Generate calibration suggestions
    if dist.get('importance', {}).get('平均', 0) > 6:
        print("  ⚠️ importance 平均值偏高 (>6)：scanner 可能打分过于慷慨")
        print("     建议：在 scanner prompt 中增加锚点示例（importance 8 = Fed 降息；4 = analyst downgrade）")
    if dist.get('importance', {}).get('平均', 0) < 3:
        print("  ⚠️ importance 平均值偏低 (<3)：信号可能在衰减后全部低于门槛")
    if dupes:
        print(f"  ⚠️ 发现 {len(dupes)} 对近似重复：finance_worker.py 的去重可能需要加强")
    if any(r.get('判断') == '待校准' for r in xref if isinstance(r, dict)):
        print("  ⚠️ 部分 ticker 的 importance 评分与实际波动不匹配")
    if not dupes and dist.get('importance', {}).get('平均', 5) <= 6:
        print("  ✅ 当前评分分布看起来合理")


if __name__ == '__main__':
    main()
