#!/usr/bin/env python3
"""Deterministic wake policy for market-ingest packets."""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/Users/leofitz/.openclaw")
COMPILER_PATH = ROOT / "workspace" / "services" / "market-ingest" / "packet_compiler" / "compiler.py"
DEFAULT_REPORT = ROOT / "workspace" / "services" / "market-ingest" / "state" / "wake-report.json"
DEFAULT_LIVE_EVIDENCE_JSONL = ROOT / "workspace" / "services" / "market-ingest" / "state" / "live-evidence-records.jsonl"
DEFAULT_LATEST_PACKET = ROOT / "workspace" / "services" / "market-ingest" / "state" / "latest-context-packet.json"
DEFAULT_LATEST_WAKE = ROOT / "workspace" / "finance" / "state" / "latest-wake-decision.json"
ALLOWED_WAKE_CLASSES = {"NO_WAKE", "PACKET_UPDATE_ONLY", "ISOLATED_JUDGMENT_WAKE", "OPS_ESCALATION"}
DEFAULT_SCORE_THRESHOLD = 0.72
WAKE_WEIGHTS = {
    "novelty": 0.35,
    "source_reliability": 0.25,
    "freshness": 0.15,
    "contradiction_impact": 0.15,
    "position_relevance": 0.10,
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def safe_report_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    resolved = path.resolve(strict=False)
    for directory in [
        ROOT / "workspace" / "services" / "market-ingest" / "state",
        ROOT / "workspace" / "finance" / "state",
        ROOT / "workspace" / "ops" / "state",
    ]:
        try:
            resolved.relative_to(directory.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def bounded(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(low, min(high, number))


def freshness_score(record: dict[str, Any]) -> float:
    return {
        "fresh": 1.0,
        "aging": 0.55,
        "stale": 0.0,
        "unknown": 0.25,
    }.get(str(record.get("staleness_class") or "unknown"), 0.25)


def position_relevance(record: dict[str, Any], packet: dict[str, Any]) -> float:
    instruments = {str(item) for item in (record.get("instrument") or [])}
    packet_instrument = str(packet.get("instrument") or "")
    if "PORTFOLIO" in instruments:
        return 1.0
    if packet_instrument and packet_instrument in instruments:
        return 0.8
    if instruments & {"SPY", "QQQ"}:
        return 0.6
    if instruments:
        return 0.35
    return 0.0


def score_record(record: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    contradiction_impact = 1.0 if packet.get("contradictions") else 0.0
    inputs = {
        "novelty": bounded(record.get("novelty_score", 0), 0, 10) / 10,
        "source_reliability": bounded(record.get("source_reliability", 0)),
        "freshness": freshness_score(record),
        "contradiction_impact": contradiction_impact,
        "position_relevance": position_relevance(record, packet),
    }
    score = round(sum(inputs[key] * WAKE_WEIGHTS[key] for key in WAKE_WEIGHTS), 4)
    return {
        "evidence_id": record.get("evidence_id"),
        "wake_score": score,
        "score_inputs": inputs,
    }


def classify(packet: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        score_record(record, packet)
        for record in records
        if record.get("quarantine", {}).get("allowed_for_wake") is True
    ]
    top_score = max((item["wake_score"] for item in scored), default=0.0)
    top_refs = [
        str(item["evidence_id"])
        for item in sorted(scored, key=lambda item: item["wake_score"], reverse=True)[:5]
        if item.get("evidence_id")
    ]
    if packet.get("market_state", {}).get("health_fault"):
        wake_class = "OPS_ESCALATION"
        reason = "market-ingest health fault"
    elif not records:
        wake_class = "NO_WAKE"
        reason = "no evidence records"
    elif scored and top_score >= DEFAULT_SCORE_THRESHOLD:
        wake_class = "ISOLATED_JUDGMENT_WAKE"
        reason = f"wake_score={top_score} >= {DEFAULT_SCORE_THRESHOLD}"
    elif scored:
        wake_class = "PACKET_UPDATE_ONLY"
        reason = f"wake-eligible evidence below score threshold ({top_score} < {DEFAULT_SCORE_THRESHOLD})"
    elif any(record["quarantine"]["allowed_as_context"] for record in records):
        wake_class = "PACKET_UPDATE_ONLY"
        reason = "context-only evidence updated packet"
    else:
        wake_class = "NO_WAKE"
        reason = "no context or wake eligible evidence"
    decision = {
        "wake_id": f"wake:{packet['packet_id']}",
        "packet_id": packet["packet_id"],
        "packet_hash": packet["packet_hash"],
        "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "wake_class": wake_class,
        "wake_reason": reason,
        "score_inputs": {
            "novelty": max((record.get("novelty_score", 0) for record in records), default=0),
            "source_reliability": max((record.get("source_reliability", 0) for record in records), default=0),
            "position_relevance": max((position_relevance(record, packet) for record in records), default=0),
            "contradiction_impact": 1 if packet.get("contradictions") else 0,
            "freshness": 1 if any(record.get("staleness_class") == "fresh" for record in records) else 0,
            "wake_score": top_score,
            "wake_score_threshold": DEFAULT_SCORE_THRESHOLD,
            "scored_wake_refs": top_refs,
            "score_policy": {
                "weights": WAKE_WEIGHTS,
                "rule": "only allowed_for_wake evidence can trigger isolated judgment wake",
            },
        },
        "evidence_refs": packet["evidence_refs"] if packet["evidence_refs"] else ["none"],
        "quarantine_refs": [
            record["quarantine"]["quarantine_id"]
            for record in records
            if not record["quarantine"]["allowed_for_wake"]
        ],
        "thesis_refs": packet.get("thesis_refs", []),
        "scenario_refs": packet.get("scenario_refs", []),
        "opportunity_candidate_refs": packet.get("opportunity_candidate_refs", []),
        "invalidator_refs": packet.get("invalidator_refs", []),
        "policy_version": packet["policy_version"]
    }
    assert decision["wake_class"] in ALLOWED_WAKE_CLASSES
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--packet", default=None)
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--latest-wake", default=str(DEFAULT_LATEST_WAKE))
    args = parser.parse_args()
    report_path = Path(args.report)
    latest_wake_path = Path(args.latest_wake)
    if not safe_report_path(report_path) or not safe_report_path(latest_wake_path):
        print(json.dumps({"status": "blocked", "blocking_reasons": ["unsafe_report_path"]}, ensure_ascii=False))
        return 2
    compiler = load_module(COMPILER_PATH, "market_ingest_packet_compiler_for_wake")
    records = load_jsonl(Path(args.evidence_jsonl)) if args.evidence_jsonl else None
    packet = load_json(Path(args.packet), {}) if args.packet else {}
    if records is None:
        records = compiler.live_records(DEFAULT_LIVE_EVIDENCE_JSONL)
    if not isinstance(packet, dict) or not packet.get("packet_hash"):
        packet = load_json(DEFAULT_LATEST_PACKET, {})
    if not isinstance(packet, dict) or not packet.get("packet_hash"):
        if records:
            packet = compiler.compile_packet(records)
        else:
            records = compiler.default_records()
            packet = compiler.compile_packet(records)
    decision = classify(packet, records)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "wake_decision": decision,
        "packet_path": args.packet or str(DEFAULT_LATEST_PACKET),
        "evidence_jsonl_path": args.evidence_jsonl or str(DEFAULT_LIVE_EVIDENCE_JSONL),
        "latest_wake_path": str(latest_wake_path),
    }
    atomic_write_json(latest_wake_path, decision)
    atomic_write_json(report_path, report)
    print(json.dumps({"status": "pass", "wake_class": decision["wake_class"], "report_path": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
