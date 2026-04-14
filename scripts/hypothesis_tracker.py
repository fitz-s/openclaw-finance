#!/usr/bin/env python3
"""Hypothesis tracker — turns report 'To Verify' into a live tracking system.

Two modes:
  python hypothesis_tracker.py extract  — scan recent reports, extract new hypotheses
  python hypothesis_tracker.py verify   — check open hypotheses against current data

Designed to run as cron:
  extract: daily after reports (e.g. 16:00 Chicago)
  verify: daily morning (e.g. 07:00 Chicago, before premarket brief)

When verify finds a resolved hypothesis, it writes the result to
hypothesis-tracker.json. The premarket-brief renderer can then open with:
  "昨日追踪更新: 我们周一预测 X, 实际结果是 Y"

This is what turns reports from "单次输出" into "连续追踪".
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

FINANCE = Path("/Users/leofitz/.openclaw/workspace/finance")
TRACKER_PATH = FINANCE / "state" / "hypothesis-tracker.json"
PRICES_PATH = FINANCE / "state" / "prices.json"
SCAN_STATE = FINANCE / "state" / "intraday-open-scan-state.json"
BUFFER_ARCHIVE = FINANCE / "buffer" / "archive"
BRIEF_OUTPUT = FINANCE / "brief-output"

# Where reports land (Discord delivery, but summaries in cron runs)
CRON_RUNS = Path("/Users/leofitz/.openclaw/cron/runs")


def load_json(p: Path) -> dict:
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


def extract_hypotheses_from_text(text: str, source_date: str) -> list[dict]:
    """Extract 'To Verify' items from report text."""
    hypotheses = []

    # Find "To Verify" or "待验证" sections
    patterns = [
        r'(?:To Verify|待验证|需要验证|待确认)[：:]\s*\n((?:[-•*]\s*.+\n?)+)',
        r'(?:To Verify|待验证|需要验证|待确认)\n((?:[-•*]\s*.+\n?)+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            items = re.findall(r'[-•*]\s*(.+)', match)
            for item in items:
                item = item.strip()
                if len(item) < 10:
                    continue

                # Try to extract ticker mentions
                tickers = set(re.findall(r'\b[A-Z]{2,5}\b', item)) & {
                    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "GOOG",
                    "AMZN", "META", "NFLX", "AMD", "ORCL", "BTC", "SMR"
                }

                # Try to detect direction prediction
                bullish_words = {"rise", "rally", "up", "涨", "反弹", "突破", "强"}
                bearish_words = {"fall", "drop", "down", "跌", "回调", "下行", "弱"}
                direction = "neutral"
                item_lower = item.lower()
                if any(w in item_lower for w in bullish_words):
                    direction = "bullish"
                elif any(w in item_lower for w in bearish_words):
                    direction = "bearish"

                hypotheses.append({
                    "text": item,
                    "tickers": sorted(tickers),
                    "direction": direction,
                    "sourceDate": source_date,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "status": "open",
                    "resolvedAt": None,
                    "resolution": None,
                    "expiresAt": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                })

    return hypotheses


def extract_from_cron_runs() -> list[dict]:
    """Scan recent cron run summaries for To Verify items."""
    all_hypotheses = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    for run_file in CRON_RUNS.glob("*.jsonl"):
        try:
            for line in run_file.read_text().splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("action") != "finished":
                    continue
                summary = entry.get("summary", "")
                ts = entry.get("ts", 0)
                if ts:
                    run_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                else:
                    run_date = "unknown"

                hypotheses = extract_hypotheses_from_text(summary, run_date)
                all_hypotheses.extend(hypotheses)
        except Exception:
            continue

    return all_hypotheses


def verify_hypotheses(tracker: dict, prices: dict) -> int:
    """Check open hypotheses against current data. Returns count resolved."""
    resolved = 0
    now = datetime.now(timezone.utc)
    quotes = prices.get("quotes") if isinstance(prices, dict) else {}
    if not isinstance(quotes, dict):
        quotes = prices if isinstance(prices, dict) else {}

    for h in tracker.get("hypotheses", []):
        if h["status"] != "open":
            continue

        # Check expiry
        expires = h.get("expiresAt", "")
        if expires and expires < now.isoformat():
            h["status"] = "expired"
            h["resolvedAt"] = now.isoformat()
            h["resolution"] = "expired without clear resolution"
            resolved += 1
            continue

        # Check if related tickers moved significantly
        if h.get("tickers") and h.get("direction") != "neutral":
            for ticker in h["tickers"]:
                price_data = quotes.get(ticker, {})
                change_pct = price_data.get("change_pct")
                if change_pct is None:
                    continue
                try:
                    pct = float(change_pct)
                except (TypeError, ValueError):
                    continue

                # Did reality match prediction?
                if abs(pct) >= 2.0:  # significant move
                    if h["direction"] == "bullish" and pct > 2.0:
                        h["status"] = "confirmed"
                        h["resolution"] = f"{ticker} moved +{pct:.1f}%, confirming bullish hypothesis"
                    elif h["direction"] == "bearish" and pct < -2.0:
                        h["status"] = "confirmed"
                        h["resolution"] = f"{ticker} moved {pct:.1f}%, confirming bearish hypothesis"
                    elif h["direction"] == "bullish" and pct < -2.0:
                        h["status"] = "denied"
                        h["resolution"] = f"{ticker} moved {pct:.1f}%, denying bullish hypothesis"
                    elif h["direction"] == "bearish" and pct > 2.0:
                        h["status"] = "denied"
                        h["resolution"] = f"{ticker} moved +{pct:.1f}%, denying bearish hypothesis"

                    if h["status"] in ("confirmed", "denied"):
                        h["resolvedAt"] = now.isoformat()
                        resolved += 1
                        break

    return resolved


def get_open_summary(tracker: dict) -> dict:
    """Summary for premarket-brief to reference."""
    hypotheses = tracker.get("hypotheses", [])
    open_h = [h for h in hypotheses if h["status"] == "open"]
    recently_resolved = [
        h for h in hypotheses
        if h["status"] in ("confirmed", "denied")
        and h.get("resolvedAt", "") >= (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    ]
    return {
        "openCount": len(open_h),
        "recentlyResolved": [
            {"text": h["text"], "status": h["status"], "resolution": h["resolution"]}
            for h in recently_resolved
        ],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: hypothesis_tracker.py [extract|verify|summary]")
        sys.exit(1)

    cmd = sys.argv[1]
    tracker = load_json(TRACKER_PATH)
    if "hypotheses" not in tracker:
        tracker["hypotheses"] = []

    if cmd == "extract":
        new = extract_from_cron_runs()
        # Dedupe by text
        existing_texts = {h["text"] for h in tracker["hypotheses"]}
        added = [h for h in new if h["text"] not in existing_texts]
        tracker["hypotheses"].extend(added)
        save_json(TRACKER_PATH, tracker)
        print(json.dumps({"status": "ok", "scanned": len(new), "added": len(added), "total": len(tracker["hypotheses"])}))

    elif cmd == "verify":
        prices = load_json(PRICES_PATH)
        resolved = verify_hypotheses(tracker, prices)
        save_json(TRACKER_PATH, tracker)
        summary = get_open_summary(tracker)
        print(json.dumps({"status": "ok", "resolved": resolved, **summary}))

    elif cmd == "summary":
        summary = get_open_summary(tracker)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
