#!/usr/bin/env python3
"""Signal learner — fully automated, zero LLM, zero human-in-the-loop.

Reads ALL historical scan data from buffer/archive/ + prices.json.
Computes: which themes/keywords actually correlated with market moves.
Outputs: signal-weights.json that scanner can read to adjust importance.

Run weekly via cron, or manually: python3 signal_learner.py

Data sources (all already exist, all JSON, all local):
- finance/buffer/archive/*.json — 200+ historical scans with observations
- finance/state/prices.json — latest price snapshot
- finance/state/calibration-history.jsonl — historical price anchors

Design from Mars's original spec:
- 5D Value: Novelty × Impact × Actionability × Persistence × Confidence
- Auto-clustering: repeated themes merge
- Auto-weighting: themes that correlate with moves get boosted
- Auto-pruning: noise themes get suppressed
- No human feedback needed. Market IS the feedback.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

FINANCE = Path("/Users/leofitz/.openclaw/workspace/finance")
ARCHIVE_DIR = FINANCE / "buffer" / "archive"
ACTIVE_BUFFER = FINANCE / "buffer"
PRICES_PATH = FINANCE / "state" / "prices.json"
SCAN_STATE = FINANCE / "state" / "intraday-open-scan-state.json"
CALIBRATION_PATH = FINANCE / "state" / "calibration-history.jsonl"
WEIGHTS_PATH = FINANCE / "state" / "signal-weights.json"
WATCHLIST_PATH = FINANCE / "watchlists" / "core.json"

# Well-known tickers to track
CORE_TICKERS = {"SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "GOOG", "AMZN",
                "META", "NFLX", "AMD", "ORCL", "SMR", "HIMS", "BTC"}
MOVE_THRESHOLD_PCT = 2.0


def load_json(p: Path) -> dict | list:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_json(p: Path, d: dict) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(p)


def load_all_observations() -> list[dict]:
    """Load ALL historical observations from archive + active buffer."""
    obs = []
    for scan_dir in [ARCHIVE_DIR, ACTIVE_BUFFER]:
        if not scan_dir.exists():
            continue
        for f in sorted(scan_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                scan_time = d.get("scan_time", "")
                for o in d.get("observations", []):
                    o["_scan_file"] = f.name
                    o["_scan_time"] = scan_time or o.get("ts", "")
                    obs.append(o)
            except Exception:
                continue
    return obs


def extract_tickers(text: str) -> set[str]:
    """Extract ticker mentions from text."""
    words = set(re.findall(r'\b[A-Z]{2,5}\b', text))
    return words & CORE_TICKERS


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from theme/summary."""
    # Simple keyword extraction: lowercase, split, filter stopwords
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                 "and", "or", "but", "in", "on", "at", "to", "for", "of",
                 "with", "from", "by", "as", "its", "that", "this", "not",
                 "all", "new", "now", "may", "also", "per", "via"}
    words = re.findall(r'[a-z]{3,}', text.lower())
    return [w for w in words if w not in stopwords]


def load_price_history() -> dict[str, list[dict]]:
    """Load calibration history as time series per observation."""
    history: dict[str, list] = defaultdict(list)
    if not CALIBRATION_PATH.exists():
        return history
    for line in CALIBRATION_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", entry.get("ts", ""))
            for ticker, data in entry.get("anchors", entry.get("prices", {})).items():
                if isinstance(data, dict):
                    history[ticker].append({"ts": ts, **data})
        except Exception:
            continue
    return history


def cluster_themes(observations: list[dict]) -> dict[str, list[dict]]:
    """Group observations by normalized theme keywords."""
    clusters: dict[str, list[dict]] = defaultdict(list)
    for obs in observations:
        theme = obs.get("theme", "unknown")
        # Normalize: extract tickers + top keywords
        tickers = extract_tickers(theme + " " + obs.get("summary", obs.get("description", "")))
        keywords = extract_keywords(theme)

        # Cluster key: tickers + top 2 keywords
        ticker_part = "_".join(sorted(tickers)[:2]) if tickers else "macro"
        kw_part = "_".join(sorted(keywords[:2])) if keywords else "general"
        cluster_key = f"{ticker_part}:{kw_part}"
        clusters[cluster_key].append(obs)

    return clusters


def compute_persistence(cluster: list[dict]) -> float:
    """How many distinct days does this theme appear?"""
    dates = set()
    for obs in cluster:
        ts = obs.get("_scan_time", "")
        if ts and len(ts) >= 10:
            dates.add(ts[:10])
    return len(dates)


def compute_cluster_weight(cluster_key: str, cluster: list[dict], prices: dict, calibration_entries: list[dict] = None) -> dict:
    if calibration_entries is None:
        calibration_entries = []
    """Compute weight for a theme cluster based on market correlation."""
    total = len(cluster)
    avg_importance = sum(o.get("importance", 0) for o in cluster) / max(total, 1)
    avg_urgency = sum(o.get("urgency", 0) for o in cluster) / max(total, 1)
    persistence = compute_persistence(cluster)

    # Check if related tickers moved
    tickers_mentioned = set()
    for obs in cluster:
        tickers_mentioned |= extract_tickers(
            f"{obs.get('theme', '')} {obs.get('summary', obs.get('description', ''))}"
        )

    # Market correlation: check calibration-history for actual moves
    market_moved = False
    max_move = 0.0
    for ticker in tickers_mentioned:
        # Check current prices
        ticker_price = prices.get(ticker, {})
        change = ticker_price.get("change_pct", 0)
        if change is not None:
            try:
                pct = abs(float(change))
                max_move = max(max_move, pct)
                if pct >= MOVE_THRESHOLD_PCT:
                    market_moved = True
            except (TypeError, ValueError):
                pass
        # Check calibration history for actual moves
        for entry in calibration_entries:
            for row in entry.get("table", []):
                if row.get("ticker") in tickers_mentioned:
                    actual = row.get("actual_abs_move_pct", 0)
                    if actual and abs(actual) >= MOVE_THRESHOLD_PCT:
                        market_moved = True
                        max_move = max(max_move, abs(actual))

    # Weight formula (Mars 5D simplified):
    # Impact (importance) × Persistence (days) × market_signal
    # Phase 1: persistence + importance are primary
    # Phase 2 (when calibration-history has 30+ entries): market_correlation becomes primary
    impact = avg_importance / 10.0
    persist = min(persistence / 7.0, 1.0)
    market_factor = 1.5 if market_moved else 0.8  # softer penalty when no price data

    weight = round((impact * persist * market_factor) - 0.3, 2)

    return {
        "weight": weight,
        "total": total,
        "persistence_days": persistence,
        "avgImportance": round(avg_importance, 1),
        "avgUrgency": round(avg_urgency, 1),
        "tickersMentioned": sorted(tickers_mentioned),
        "marketMoved": market_moved,
        "maxMovePct": round(max_move, 1),
    }


def generate_keyword_weights(clusters: dict, cluster_weights: dict) -> dict[str, float]:
    """Extract individual keyword weights from cluster data."""
    kw_scores: dict[str, list[float]] = defaultdict(list)
    for key, cluster in clusters.items():
        w = cluster_weights.get(key, {}).get("weight", 0)
        for obs in cluster:
            for kw in extract_keywords(obs.get("theme", "")):
                kw_scores[kw].append(w)

    return {
        kw: round(sum(scores) / len(scores), 2)
        for kw, scores in kw_scores.items()
        if len(scores) >= 3  # need enough data
    }


def main() -> None:
    observations = load_all_observations()
    prices = load_json(PRICES_PATH)

    # Load calibration history for market verification
    calibration_entries = []
    if CALIBRATION_PATH.exists():
        for line in CALIBRATION_PATH.read_text().splitlines():
            if line.strip():
                try:
                    calibration_entries.append(json.loads(line))
                except Exception:
                    pass

    # Cluster
    clusters = cluster_themes(observations)

    # Compute per-cluster weights
    cluster_weights = {}
    for key, cluster in clusters.items():
        cluster_weights[key] = compute_cluster_weight(key, cluster, prices, calibration_entries)

    # Separate into boost vs suppress
    boost = {k: v for k, v in cluster_weights.items() if v["weight"] > 0.2}
    suppress = {k: v for k, v in cluster_weights.items() if v["weight"] < -0.1}
    neutral = {k: v for k, v in cluster_weights.items() if -0.1 <= v["weight"] <= 0.2}

    # Keyword-level weights
    keyword_weights = generate_keyword_weights(clusters, cluster_weights)

    output = {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "computedAt": datetime.now(timezone.utc).isoformat(),
        "totalObservations": len(observations),
        "totalClusters": len(clusters),
        "boostedThemes": len(boost),
        "suppressedThemes": len(suppress),
        "neutralThemes": len(neutral),
        "clusterWeights": cluster_weights,
        "keywordWeights": keyword_weights,
        "topBoosted": dict(sorted(boost.items(), key=lambda x: -x[1]["weight"])[:10]),
        "topSuppressed": dict(sorted(suppress.items(), key=lambda x: x[1]["weight"])[:10]),
        "note": "Scanner can add clusterWeights[theme].weight to observation importance. keywordWeights gives per-keyword adjustment.",
    }

    save_json(WEIGHTS_PATH, output)

    print(json.dumps({
        "status": "ok",
        "observations": len(observations),
        "clusters": len(clusters),
        "boosted": len(boost),
        "suppressed": len(suppress),
        "topBoosted": list(boost.keys())[:5],
        "topSuppressed": list(suppress.keys())[:5],
    }, indent=2))


if __name__ == "__main__":
    main()
