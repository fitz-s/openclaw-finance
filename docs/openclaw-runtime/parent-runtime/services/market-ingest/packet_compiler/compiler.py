#!/usr/bin/env python3
"""Deterministic packet compiler for finance market-ingest evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/Users/leofitz/.openclaw")
NORMALIZER_PATH = ROOT / "workspace" / "services" / "market-ingest" / "normalizer" / "semantic_normalizer.py"
DEFAULT_REPORT = ROOT / "workspace" / "services" / "market-ingest" / "state" / "packet-report.json"
DEFAULT_LIVE_EVIDENCE_JSONL = ROOT / "workspace" / "services" / "market-ingest" / "state" / "live-evidence-records.jsonl"
DEFAULT_ALIGNMENT_REPORT = ROOT / "workspace" / "services" / "market-ingest" / "state" / "temporal-alignment-report.json"
DEFAULT_LATEST_PACKET = ROOT / "workspace" / "services" / "market-ingest" / "state" / "latest-context-packet.json"
SOURCE_REGISTRY = ROOT / "workspace" / "services" / "market-ingest" / "config" / "source-registry.json"
SOURCE_HEALTH = ROOT / "workspace" / "services" / "market-ingest" / "state" / "source-health.json"
FINANCE_STATE = ROOT / "workspace" / "finance" / "state"
THESIS_REGISTRY = FINANCE_STATE / "thesis-registry.json"
SCENARIO_CARDS = FINANCE_STATE / "scenario-cards.json"
OPPORTUNITY_QUEUE = FINANCE_STATE / "opportunity-queue.json"
INVALIDATOR_LEDGER = FINANCE_STATE / "invalidator-ledger.json"
UNKNOWN_TIME = "1970-01-01T00:00:00Z"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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
    allowed = [
        ROOT / "workspace" / "services" / "market-ingest" / "state",
        ROOT / "workspace" / "ops" / "state"
    ]
    for directory in allowed:
        try:
            resolved.relative_to(directory.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def layer_key(layer: str) -> str:
    return {
        "L0_raw_observation": "L0",
        "L1_derived_transform": "L1",
        "L2_public_narrative_event": "L2",
        "L3_flow_positioning": "L3",
        "L4_actor_intent": "L4"
    }.get(layer, "L2")


def thesis_spine_refs() -> dict[str, list[str]]:
    thesis_registry = load_json(THESIS_REGISTRY, {}) or {}
    scenarios = load_json(SCENARIO_CARDS, {}) or {}
    opportunities = load_json(OPPORTUNITY_QUEUE, {}) or {}
    invalidators = load_json(INVALIDATOR_LEDGER, {}) or {}
    return {
        "thesis_refs": [
            str(item.get("thesis_id"))
            for item in thesis_registry.get("theses", [])
            if isinstance(item, dict) and item.get("thesis_id") and item.get("status") in {"active", "watch", "candidate"}
        ][:20],
        "scenario_refs": [
            str(item.get("scenario_id"))
            for item in scenarios.get("scenarios", [])
            if isinstance(item, dict) and item.get("scenario_id") and item.get("status") in {"active", "candidate"}
        ][:20],
        "opportunity_candidate_refs": [
            str(item.get("candidate_id"))
            for item in opportunities.get("candidates", [])
            if isinstance(item, dict) and item.get("candidate_id") and item.get("status") in {"candidate", "promoted"}
        ][:20],
        "invalidator_refs": [
            str(item.get("invalidator_id"))
            for item in invalidators.get("invalidators", [])
            if isinstance(item, dict) and item.get("invalidator_id") and item.get("status") in {"open", "hit"}
        ][:20],
    }


def compile_packet(
    records: list[dict[str, Any]],
    instrument: str = "SPY",
    policy_version: str = "finance-semantic-v1",
    alignment_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = sorted(records, key=lambda record: record["evidence_id"])
    layer_digest = {"L0": [], "L1": [], "L2": [], "L3": [], "L4": []}
    for record in records:
        layer_digest[layer_key(record.get("layer", "unknown"))].append(record["evidence_id"])
    for values in layer_digest.values():
        values.sort()

    eligible = [record for record in records if record["quarantine"]["allowed_for_wake"]]
    judgment_support = [
        record for record in records
        if record.get("quarantine", {}).get("allowed_for_judgment_support") is True
    ]
    context_only = [record for record in records if not record["quarantine"]["allowed_for_wake"] and record["quarantine"]["allowed_as_context"]]
    contradictions = []
    if eligible and context_only:
        contradictions.append({
            "contradiction_key": "wake_eligible_vs_context_only",
            "supports": [record["evidence_id"] for record in eligible],
            "conflicts_with": [record["evidence_id"] for record in context_only],
            "impact": "context-only evidence cannot override wake-eligible confirmed evidence"
        })
    if isinstance(alignment_report, dict) and isinstance(alignment_report.get("contradictions"), list):
        by_key = {item.get("contradiction_key"): item for item in contradictions if isinstance(item, dict)}
        for item in alignment_report["contradictions"]:
            if isinstance(item, dict) and item.get("contradiction_key") not in by_key:
                contradictions.append(item)

    as_of = max((record["ingested_at"] for record in records), default=UNKNOWN_TIME)
    spine_refs = thesis_spine_refs()
    packet = {
        "packet_id": f"packet:market-ingest:{instrument}:{as_of}",
        "instrument": instrument,
        "as_of": as_of,
        "packet_hash": "sha256:pending",
        "position_state": {
            "authority": "review-only",
            "exposure": "unknown"
        },
        "market_state": {
            "health_fault": False,
            "source_count": len(records)
        },
        "layer_digest": layer_digest,
        "contradictions": contradictions,
        "what_changed_since_last_judgment": [f"{len(records)} normalized evidence records available"],
        "candidate_invalidators": ["source outage", "official correction", "packet staleness"],
        "evidence_refs": sorted(record["evidence_id"] for record in records) or ["none"],
        **spine_refs,
        "policy_version": policy_version,
        "source_manifest": {
            "producer": "market-ingest.packet_compiler",
            "record_hash": canonical_hash(records),
            "alignment_hash": canonical_hash(alignment_report or {}),
            "source_registry_hash": file_hash(SOURCE_REGISTRY),
            "source_health_hash": file_hash(SOURCE_HEALTH),
            "source_health_mode": "shadow_audit_only",
        },
        "accepted_evidence_records": records,
        "quarantine_records": [],
        "source_quality_summary": {
            "wake_eligible_count": len(eligible),
            "judgment_support_count": len(judgment_support),
            "support_only_count": len([record for record in judgment_support if not record["quarantine"]["allowed_for_wake"]]),
            "context_only_count": len(context_only),
            "record_count": len(records),
        },
    }
    hash_input = dict(packet)
    hash_input["packet_hash"] = "sha256:pending"
    packet["packet_hash"] = canonical_hash(hash_input)
    return packet


def default_records() -> list[dict[str, Any]]:
    normalizer = load_module(NORMALIZER_PATH, "market_ingest_semantic_normalizer_for_packet")
    return normalizer.normalize_cases(normalizer.load_fixture())


def live_records(path: Path = DEFAULT_LIVE_EVIDENCE_JSONL) -> list[dict[str, Any]]:
    return load_jsonl(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--alignment-report", default=None)
    parser.add_argument("--latest-packet", default=str(DEFAULT_LATEST_PACKET))
    parser.add_argument("--instrument", default="SPY")
    args = parser.parse_args()
    report_path = Path(args.report)
    latest_packet_path = Path(args.latest_packet)
    if not safe_report_path(report_path) or not safe_report_path(latest_packet_path):
        print(json.dumps({"status": "blocked", "blocking_reasons": ["unsafe_report_path"]}, ensure_ascii=False))
        return 2
    records = live_records(Path(args.evidence_jsonl)) if args.evidence_jsonl else default_records()
    alignment = load_json(Path(args.alignment_report), {}) if args.alignment_report else {}
    packet = compile_packet(records, instrument=args.instrument, alignment_report=alignment)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "packet": packet,
        "evidence_count": len(records),
        "mode": "live" if args.evidence_jsonl else "fixture",
        "evidence_jsonl_path": args.evidence_jsonl,
        "alignment_report_path": args.alignment_report,
        "latest_packet_path": str(latest_packet_path),
    }
    atomic_write_json(latest_packet_path, packet)
    atomic_write_json(report_path, report)
    print(json.dumps({"status": "pass", "packet_hash": packet["packet_hash"], "report_path": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
