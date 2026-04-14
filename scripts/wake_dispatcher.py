#!/usr/bin/env python3
"""Dispatch canonical WakeDecision outcomes to OpenClaw jobs."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json, load_json_safe


OPENCLAW = "/Users/leofitz/.npm-global/bin/openclaw"
WORKSPACE = Path("/Users/leofitz/.openclaw/workspace")
FINANCE = WORKSPACE / "finance"
STATE_DIR = FINANCE / "state"
LATEST_WAKE = STATE_DIR / "latest-wake-decision.json"
ORCHESTRATOR_INPUT = STATE_DIR / "report-orchestrator-input.json"
DISPATCH_STATE = STATE_DIR / "wake-dispatch-state.json"
REPORT_ORCHESTRATOR_ID = "b2c3d4e5-f6a7-8901-bcde-f01234567890"
COOLDOWN_SECONDS = 3600
TZ_CHICAGO = ZoneInfo("America/Chicago")
MAX_EVENT_REPORTS_PER_DAY = 2
MAX_OPS_ESCALATIONS_PER_DAY = 2


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def day_key() -> str:
    return now_utc().astimezone(TZ_CHICAGO).strftime("%Y-%m-%d")


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE_DIR.resolve(strict=False))
        return True
    except ValueError:
        return False


def previous_dispatch_map(state: dict[str, Any]) -> dict[str, str]:
    previous = state.get("dispatched_wake_ids")
    return previous if isinstance(previous, dict) else {}


def daily_counts(state: dict[str, Any], key: str) -> dict[str, int]:
    counts = state.get("daily_dispatch_counts")
    if not isinstance(counts, dict):
        return {}
    day_counts = counts.get(key)
    if not isinstance(day_counts, dict):
        return {}
    return {str(name): int(value) for name, value in day_counts.items() if isinstance(value, int)}


def increment_daily_count(state: dict[str, Any], key: str, report_class: str) -> dict[str, Any]:
    counts = state.get("daily_dispatch_counts")
    if not isinstance(counts, dict):
        counts = {}
    day_counts = counts.get(key)
    if not isinstance(day_counts, dict):
        day_counts = {}
    day_counts[report_class] = int(day_counts.get(report_class, 0)) + 1
    counts[key] = day_counts
    return counts


def in_cooldown(wake_id: str, previous: dict[str, str], cooldown_seconds: int) -> bool:
    ts = parse_dt(previous.get(wake_id))
    if not ts:
        return False
    return (now_utc() - ts).total_seconds() < cooldown_seconds


def report_class_for(wake_class: str) -> str | None:
    if wake_class == "ISOLATED_JUDGMENT_WAKE":
        return "event_wake"
    if wake_class == "OPS_ESCALATION":
        return "ops_escalation"
    return None


def build_orchestrator_input(wake: dict[str, Any], report_class: str) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "report_class": report_class,
        "wake_id": wake.get("wake_id"),
        "wake_class": wake.get("wake_class"),
        "wake_reason": wake.get("wake_reason"),
        "packet_id": wake.get("packet_id"),
        "packet_hash": wake.get("packet_hash"),
        "evidence_refs": wake.get("evidence_refs", []),
        "policy_version": wake.get("policy_version"),
    }


def dispatch_wake(
    wake: dict[str, Any],
    *,
    openclaw_bin: str = OPENCLAW,
    orchestrator_id: str = REPORT_ORCHESTRATOR_ID,
    no_dispatch: bool = False,
    force: bool = False,
    cooldown_seconds: int = COOLDOWN_SECONDS,
    max_event_reports_per_day: int = MAX_EVENT_REPORTS_PER_DAY,
    max_ops_escalations_per_day: int = MAX_OPS_ESCALATIONS_PER_DAY,
) -> dict[str, Any]:
    wake_id = str(wake.get("wake_id") or "")
    wake_class = str(wake.get("wake_class") or "")
    state = load_json_safe(DISPATCH_STATE, {}) or {}
    previous = previous_dispatch_map(state)
    today = day_key()
    counts_today = daily_counts(state, today)
    report_class = report_class_for(wake_class)
    action = "no_dispatch"
    blocking_reasons: list[str] = []
    run_result: dict[str, Any] | None = None
    dispatched = False

    if wake_class in {"NO_WAKE", "PACKET_UPDATE_ONLY"}:
        action = "persist_only"
    elif not wake_id:
        action = "blocked"
        blocking_reasons.append("missing_wake_id")
    elif in_cooldown(wake_id, previous, cooldown_seconds) and not force:
        action = "cooldown_suppressed"
        blocking_reasons.append("wake_already_dispatched_in_cooldown")
    elif (
        report_class == "event_wake"
        and counts_today.get("event_wake", 0) >= max_event_reports_per_day
        and not force
    ):
        action = "daily_cap_suppressed"
        blocking_reasons.append("daily_event_report_cap_reached")
    elif (
        report_class == "ops_escalation"
        and counts_today.get("ops_escalation", 0) >= max_ops_escalations_per_day
        and not force
    ):
        action = "daily_cap_suppressed"
        blocking_reasons.append("daily_ops_escalation_cap_reached")
    elif no_dispatch:
        action = "would_dispatch"
    elif wake_class in {"ISOLATED_JUDGMENT_WAKE", "OPS_ESCALATION"} and report_class:
        orchestrator_input = build_orchestrator_input(wake, report_class)
        atomic_write_json(ORCHESTRATOR_INPUT, orchestrator_input)
        try:
            result = subprocess.run(
                [openclaw_bin, "cron", "run", orchestrator_id],
                capture_output=True,
                text=True,
                timeout=30,
            )
            run_result = {
                "returncode": result.returncode,
                "stdout_preview": result.stdout.strip()[:500],
                "stderr_preview": result.stderr.strip()[:500],
            }
            if result.returncode == 0:
                action = "dispatched"
                dispatched = True
                previous[wake_id] = now_iso()
                state["daily_dispatch_counts"] = increment_daily_count(state, today, report_class)
            else:
                action = "dispatch_failed"
                blocking_reasons.append("openclaw_cron_run_failed")
        except Exception as exc:
            action = "dispatch_failed"
            blocking_reasons.append("openclaw_cron_run_exception")
            run_result = {"error": str(exc)[:500]}
    else:
        action = "blocked"
        blocking_reasons.append(f"unsupported_wake_class:{wake_class}")

    report = {
        "generated_at": now_iso(),
        "status": "pass" if action in {"persist_only", "would_dispatch", "dispatched", "cooldown_suppressed", "daily_cap_suppressed"} else "fail",
        "wake_id": wake_id,
        "wake_class": wake_class,
        "packet_id": wake.get("packet_id"),
        "packet_hash": wake.get("packet_hash"),
        "report_class": report_class,
        "action": action,
        "dispatched": dispatched,
        "blocking_reasons": blocking_reasons,
        "openclaw": {
            "bin": openclaw_bin,
            "orchestrator_id": orchestrator_id,
            "no_dispatch": no_dispatch,
            "run_result": run_result,
        },
        "dispatched_wake_ids": previous,
        "rate_limit": {
            "day_key": today,
            "event_wake_count": daily_counts(state, today).get("event_wake", 0),
            "ops_escalation_count": daily_counts(state, today).get("ops_escalation", 0),
            "max_event_reports_per_day": max_event_reports_per_day,
            "max_ops_escalations_per_day": max_ops_escalations_per_day,
        },
        "daily_dispatch_counts": state.get("daily_dispatch_counts", {}),
    }
    atomic_write_json(DISPATCH_STATE, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wake-decision", default=str(LATEST_WAKE))
    parser.add_argument("--openclaw-bin", default=OPENCLAW)
    parser.add_argument("--report-orchestrator-id", default=REPORT_ORCHESTRATOR_ID)
    parser.add_argument("--no-dispatch", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--cooldown-seconds", type=int, default=COOLDOWN_SECONDS)
    parser.add_argument("--max-event-reports-per-day", type=int, default=MAX_EVENT_REPORTS_PER_DAY)
    parser.add_argument("--max-ops-escalations-per-day", type=int, default=MAX_OPS_ESCALATIONS_PER_DAY)
    args = parser.parse_args(argv)
    wake_path = Path(args.wake_decision)
    if not safe_state_path(wake_path):
        print(json.dumps({"status": "blocked", "blocking_reasons": ["unsafe_wake_path"]}, ensure_ascii=False))
        return 2
    wake = load_json_safe(wake_path, {}) or {}
    report = dispatch_wake(
        wake,
        openclaw_bin=args.openclaw_bin,
        orchestrator_id=args.report_orchestrator_id,
        no_dispatch=args.no_dispatch,
        force=args.force,
        cooldown_seconds=args.cooldown_seconds,
        max_event_reports_per_day=args.max_event_reports_per_day,
        max_ops_escalations_per_day=args.max_ops_escalations_per_day,
    )
    print(json.dumps({"status": report["status"], "action": report["action"], "dispatched": report["dispatched"], "blocking_reasons": report["blocking_reasons"]}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
