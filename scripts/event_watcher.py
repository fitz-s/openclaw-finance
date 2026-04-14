#!/usr/bin/env python3
"""Event watcher manager — the deterministic backbone of the event-driven forecast system.

Three modes:
  python event_watcher.py create --theme "..." --tickers "ORCL,NVDA" --trigger "..." --ttl 7
  python event_watcher.py tick    (check all active watchers, decide which need LLM update)
  python event_watcher.py close --id <watcher_id>

Lifecycle:
  1. Scanner detects high-value event (importance >= 7, or urgency >= 8)
  2. gate_evaluator calls: event_watcher.py create --theme ... --tickers ... --trigger ...
  3. Every hour, cron runs: event_watcher.py tick
     - For each active watcher, checks if new data appeared (price moves, new observations)
     - If yes → marks watcher as "needs_update" → triggers Mars LLM session for analysis
     - If no → silent, zero tokens
  4. After TTL expires or event resolves → auto-close with final summary

Design:
  - Deterministic (Python) decides WHEN to wake Mars
  - Mars (LLM) decides WHAT the update means
  - Human sees only meaningful updates, never "nothing changed"
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

FINANCE = Path("/Users/leofitz/.openclaw/workspace/finance")
WATCHERS_PATH = FINANCE / "state" / "event-watchers.json"
PRICES_PATH = FINANCE / "state" / "prices.json"
SCAN_STATE = FINANCE / "state" / "intraday-open-scan-state.json"
WEIGHTS_PATH = FINANCE / "state" / "signal-weights.json"
OPENCLAW = "/Users/leofitz/.npm-global/bin/openclaw"

# Watcher LLM renderer job — only triggered when watcher needs update
WATCHER_RENDERER_ID = "c4d5e6f7-a8b9-0123-cdef-watcher-renderer"

MOVE_THRESHOLD_PCT = 1.5  # lower than signal_learner — watchers are more sensitive


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


def price_quotes(prices: dict) -> dict:
    quotes = prices.get("quotes")
    if isinstance(quotes, dict):
        return quotes
    return prices if isinstance(prices, dict) else {}


def normalized_pct_change(quote: dict) -> float | None:
    if not isinstance(quote, dict):
        return None
    change = quote.get("change_pct")
    if change is None:
        change = quote.get("pct_change")
    if change is None:
        return None
    try:
        return float(change)
    except (TypeError, ValueError):
        return None


def quote_price_value(quote: dict) -> float | None:
    if not isinstance(quote, dict):
        return None
    for key in ("price", "mkt_price", "close"):
        value = quote.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def canonical_wake_key(watcher: dict) -> str:
    source_id = watcher.get("id", "unknown")
    created_at = watcher.get("createdAt", "unknown")
    return f"watcher:{source_id}:{created_at}"


def ensure_watcher_identity(watcher: dict) -> bool:
    changed = False
    key = canonical_wake_key(watcher)
    if watcher.get("source_uid") != key:
        watcher["source_uid"] = key
        changed = True
    if watcher.get("canonical_wake_key") != key:
        watcher["canonical_wake_key"] = key
        changed = True
    return changed


def normalize_watchers_payload(payload: dict) -> bool:
    changed = False
    watchers = payload.get("watchers", [])
    if not isinstance(watchers, list):
        return False
    for watcher in watchers:
        if isinstance(watcher, dict):
            changed = ensure_watcher_identity(watcher) or changed
    return changed


def watcher_matches_id(watcher: dict, identifier: str) -> bool:
    return identifier in {
        watcher.get("source_uid"),
        watcher.get("canonical_wake_key"),
        watcher.get("id"),
    }


def create_watcher(theme: str, tickers: list[str], trigger: str, ttl_days: int = 7) -> dict:
    """Create a new event watcher."""
    watchers = load_json(WATCHERS_PATH)
    if "watchers" not in watchers:
        watchers["watchers"] = []
    normalize_watchers_payload(watchers)

    now = datetime.now(timezone.utc)
    watcher = {
        "id": f"ew-{int(now.timestamp() * 1_000_000)}",
        "theme": theme,
        "tickers": tickers,
        "trigger": trigger,
        "status": "active",
        "createdAt": now.isoformat(),
        "expiresAt": (now + timedelta(days=ttl_days)).isoformat(),
        "lastCheckedAt": now.isoformat(),
        "lastUpdatedAt": None,
        "updateCount": 0,
        "priceAtCreation": {},
        "timeline": [
            {
                "ts": now.isoformat(),
                "type": "created",
                "note": trigger,
            }
        ],
        "hypothesis": None,
        "resolution": None,
    }
    ensure_watcher_identity(watcher)

    # Capture current prices for tickers
    prices = price_quotes(load_json(PRICES_PATH))
    for ticker in tickers:
        p = prices.get(ticker, {})
        if p:
            pct = normalized_pct_change(p)
            watcher["priceAtCreation"][ticker] = {
                "price": quote_price_value(p),
                "change_pct": pct,
                "pct_change": pct,
            }

    watchers["watchers"].append(watcher)
    save_json(WATCHERS_PATH, watchers)
    return watcher


def tick() -> dict:
    """Check all active watchers. Returns which ones need LLM update."""
    watchers_data = load_json(WATCHERS_PATH)
    normalize_watchers_payload(watchers_data)
    watchers = watchers_data.get("watchers", [])
    prices = price_quotes(load_json(PRICES_PATH))
    scan = load_json(SCAN_STATE)
    accumulated = scan.get("accumulated", [])
    now = datetime.now(timezone.utc)

    needs_update = []
    expired = []

    for w in watchers:
        if w["status"] != "active":
            continue

        # Check expiry
        if w.get("expiresAt", "") < now.isoformat():
            w["status"] = "expired"
            w["timeline"].append({
                "ts": now.isoformat(),
                "type": "expired",
                "note": f"TTL expired after {w['updateCount']} updates",
            })
            expired.append(w["id"])
            continue

        # Check if tickers moved significantly since last check
        price_moved = False
        move_details = []
        for ticker in w.get("tickers", []):
            p = prices.get(ticker, {})
            pct = normalized_pct_change(p)
            if pct is not None and abs(pct) >= MOVE_THRESHOLD_PCT:
                price_moved = True
                move_details.append(f"{ticker} {pct:+.1f}%")

        # Check if new observations mention this watcher's theme
        new_signal = False
        theme_lower = w.get("theme", "").lower()
        theme_words = set(theme_lower.split()[:3])  # first 3 words as matcher
        for obs in accumulated:
            obs_theme = obs.get("theme", "").lower()
            if theme_words and len(theme_words & set(obs_theme.split())) >= 2:
                new_signal = True
                break

        # Decide: does this watcher need an LLM update?
        needs_llm = price_moved or new_signal

        # Rate limit: don't update same watcher more than once per 4 hours
        last_updated = w.get("lastUpdatedAt")
        if last_updated:
            hours_since = (now - datetime.fromisoformat(last_updated.replace("Z", "+00:00"))).total_seconds() / 3600
            if hours_since < 4:
                needs_llm = False

        if needs_llm:
            w["lastCheckedAt"] = now.isoformat()
            reason = []
            if price_moved:
                reason.append(f"price: {', '.join(move_details)}")
            if new_signal:
                reason.append("new observation matches theme")
            needs_update.append({
                "watcherId": w.get("source_uid", w["id"]),
                "theme": w["theme"],
                "tickers": w["tickers"],
                "reason": "; ".join(reason),
                "updateCount": w["updateCount"],
            })
        else:
            w["lastCheckedAt"] = now.isoformat()

    save_json(WATCHERS_PATH, watchers_data)

    return {
        "status": "ok",
        "activeWatchers": len([w for w in watchers if w["status"] == "active"]),
        "needsUpdate": needs_update,
        "expired": expired,
    }


def record_update(watcher_id: str, note: str) -> None:
    """Record an LLM-generated update for a watcher."""
    watchers_data = load_json(WATCHERS_PATH)
    normalize_watchers_payload(watchers_data)
    now = datetime.now(timezone.utc)
    for w in watchers_data.get("watchers", []):
        if watcher_matches_id(w, watcher_id):
            w["lastUpdatedAt"] = now.isoformat()
            w["updateCount"] += 1
            w["timeline"].append({
                "ts": now.isoformat(),
                "type": "update",
                "note": note[:500],
            })
            break
    save_json(WATCHERS_PATH, watchers_data)


def close_watcher(watcher_id: str, resolution: str = "manual close") -> None:
    """Close a watcher with final resolution."""
    watchers_data = load_json(WATCHERS_PATH)
    normalize_watchers_payload(watchers_data)
    now = datetime.now(timezone.utc)
    for w in watchers_data.get("watchers", []):
        if watcher_matches_id(w, watcher_id):
            w["status"] = "closed"
            w["resolution"] = resolution
            w["timeline"].append({
                "ts": now.isoformat(),
                "type": "closed",
                "note": resolution[:500],
            })
            break
    save_json(WATCHERS_PATH, watchers_data)


def list_active() -> list[dict]:
    watchers_data = load_json(WATCHERS_PATH)
    if normalize_watchers_payload(watchers_data):
        save_json(WATCHERS_PATH, watchers_data)
    return [
        {
            "id": w["id"],
            "source_uid": w.get("source_uid"),
            "theme": w["theme"],
            "tickers": w["tickers"],
            "updateCount": w["updateCount"],
            "age_hours": round(
                (datetime.now(timezone.utc) - datetime.fromisoformat(
                    w["createdAt"].replace("Z", "+00:00")
                )).total_seconds() / 3600, 1
            ),
        }
        for w in watchers_data.get("watchers", [])
        if w["status"] == "active"
    ]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: event_watcher.py [create|tick|close|list|record-update]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("cmd")
        parser.add_argument("--theme", required=True)
        parser.add_argument("--tickers", default="")
        parser.add_argument("--trigger", required=True)
        parser.add_argument("--ttl", type=int, default=7)
        args = parser.parse_args()
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
        w = create_watcher(args.theme, tickers, args.trigger, args.ttl)
        print(json.dumps({"status": "ok", "watcher": w["id"], "theme": w["theme"]}))

    elif cmd == "tick":
        result = tick()
        print(json.dumps(result, indent=2))

        # If any watchers need update, trigger LLM renderer
        if result.get("needsUpdate"):
            import subprocess
            try:
                subprocess.run(
                    [OPENCLAW, "cron", "run", WATCHER_RENDERER_ID],
                    capture_output=True, text=True, timeout=30,
                )
                print(f"🚀 Watcher renderer triggered for {len(result['needsUpdate'])} watchers")
            except Exception as e:
                print(f"⚠️ Watcher renderer trigger failed: {e}")

    elif cmd == "close":
        if len(sys.argv) < 4 or sys.argv[2] != "--id":
            print("Usage: event_watcher.py close --id <watcher_id> [--resolution '...']")
            sys.exit(1)
        wid = sys.argv[3]
        resolution = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--resolution" else "manual close"
        close_watcher(wid, resolution)
        print(json.dumps({"status": "ok", "closed": wid}))

    elif cmd == "record-update":
        if len(sys.argv) < 6:
            print("Usage: event_watcher.py record-update --id <watcher_id> --note '...'")
            sys.exit(1)
        wid = sys.argv[3]
        note = sys.argv[5]
        record_update(wid, note)
        print(json.dumps({"status": "ok", "updated": wid}))

    elif cmd == "list":
        active = list_active()
        print(json.dumps({"active": active, "count": len(active)}, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
