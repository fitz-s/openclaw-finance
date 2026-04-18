#!/usr/bin/env python3
"""Deterministic finance semantic normalizer for market-ingest."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/Users/leofitz/.openclaw")
DEFAULT_FIXTURE = ROOT / "workspace" / "ops" / "fixtures" / "finance_false_positives" / "false_positive_cases.json"
DEFAULT_REPORT = ROOT / "workspace" / "services" / "market-ingest" / "state" / "semantic-normalizer-report.json"
UNKNOWN_TIME = "1970-01-01T00:00:00Z"

TRUSTED_SOURCES = {"reuters", "bloomberg", "associated press", "ap news", "financial times", "wsj", "cnbc"}
LOW_QUALITY_SOURCES = {"mshale", "anonymous market forum"}
CLICKBAIT_PATTERNS = [
    re.compile(r"\bcrash\s+or\s+rally\b", re.I),
    re.compile(r"\b[a-z]+\s+vs\s+[a-z]+\b", re.I),
    re.compile(r"\([A-Za-z0-9_-]{8,}\)")
]
SPECULATIVE_PATTERNS = [re.compile(r"\?$"), re.compile(r"\b(will|could|may|might|whispering|rumou?rs?)\b", re.I)]
CONFIRMED_PATTERNS = [re.compile(r"\b(halted|suspended|attacked|targeted|closed|closes?|denies|announces?|down\s+\d+(?:\.\d+)?%)\b", re.I)]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(material.encode('utf-8')).hexdigest()[:16]}"


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(value: str | None) -> str | None:
    parsed = parse_dt(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def source_tier(source: str) -> str:
    lowered = source.lower()
    if any(item in lowered for item in LOW_QUALITY_SOURCES):
        return "T4_blocked_or_low_quality"
    if any(item in lowered for item in TRUSTED_SOURCES):
        return "T1_primary_wire_or_regulator"
    return "T3_untrusted_or_syndicated"


def reliability(tier: str) -> float:
    return {
        "T1_primary_wire_or_regulator": 0.9,
        "T3_untrusted_or_syndicated": 0.3,
        "T4_blocked_or_low_quality": 0.0
    }.get(tier, 0.2)


def title_quality(title: str, source: str) -> tuple[str, list[str], bool, bool]:
    hits = [pattern.pattern for pattern in CLICKBAIT_PATTERNS if pattern.search(title)]
    speculative = any(pattern.search(title.strip()) for pattern in SPECULATIVE_PATTERNS)
    confirmed = any(pattern.search(title) for pattern in CONFIRMED_PATTERNS)
    tier = source_tier(source)
    if hits:
        return "clickbait_pattern", hits, confirmed, speculative
    if tier == "T4_blocked_or_low_quality":
        return "low_quality_source", hits, confirmed, speculative
    if speculative:
        return "speculative_question", hits, confirmed, speculative
    if confirmed:
        return "confirmed_event", hits, confirmed, speculative
    return "routine_market_color", hits, confirmed, speculative


def disposition(case: dict[str, Any], quality: str, tier: str, confirmed: bool, speculative: bool) -> tuple[str, str, str]:
    title = str(case.get("title", ""))
    published = parse_dt(case.get("published_at"))
    observed = parse_dt(case.get("observed_at"))
    age_hours = ((observed - published).total_seconds() / 3600) if published and observed else None
    if quality == "clickbait_pattern":
        return "QUARANTINE", "clickbait_pattern", "clickbait/question title"
    if quality == "low_quality_source":
        return "QUARANTINE", "low_quality_source", "blocked or anonymous source"
    if speculative:
        return "QUARANTINE", "speculative_question", "speculative title cannot wake"
    if age_hours is not None and age_hours > 36:
        return "STORE_LOW_AUTHORITY", "stale_recycled_event", "stale event retained at low authority"
    if "denies" in title.lower() or "while officials claim" in title.lower():
        return "PACKET_CONTEXT_ONLY", "contradictory_unresolved", "contradiction context only"
    if tier == "T3_untrusted_or_syndicated" and "crash" in title.lower() and not confirmed:
        return "QUARANTINE", "untrusted_unconfirmed_emergency", "untrusted emergency language"
    if tier == "T1_primary_wire_or_regulator" and confirmed:
        return "ELIGIBLE_FOR_WAKE", "accepted_confirmed_event", "trusted confirmed event"
    return "ACCEPT", "accepted_non_emergency", "accepted non-emergency evidence"


def allowed_flags(disp: str) -> tuple[bool, bool, bool]:
    if disp in {"ELIGIBLE_FOR_WAKE", "ACCEPT"}:
        return True, disp == "ELIGIBLE_FOR_WAKE", True
    if disp == "PACKET_CONTEXT_ONLY":
        return True, False, False
    if disp == "STORE_LOW_AUTHORITY":
        return True, False, False
    return True, False, False


def staleness(case: dict[str, Any]) -> str:
    published = parse_dt(case.get("published_at"))
    observed = parse_dt(case.get("observed_at"))
    if not published or not observed:
        return "unknown"
    age = (observed - published).total_seconds() / 3600
    if age <= 18:
        return "fresh"
    if age <= 36:
        return "aging"
    return "stale"


def normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = str(case.get("fixture_id", "unknown"))
    source = str(case.get("source", "unknown"))
    title = str(case.get("title", ""))
    raw_ref = str(case.get("raw_ref") or f"fixture:{fixture_id}")
    instrument = case.get("instrument") if isinstance(case.get("instrument"), list) and case.get("instrument") else ["SPY"]
    theme_refs = case.get("theme_refs") if isinstance(case.get("theme_refs"), list) else ["theme:market_structure"]
    layer = str(case.get("layer") or "L2_public_narrative_event")
    source_kind = str(case.get("source_kind") or "news_headline")
    tier = source_tier(source)
    quality, hits, confirmed, speculative = title_quality(title, source)
    disp, reason_code, reason_detail = disposition(case, quality, tier, confirmed, speculative)
    allowed_as_context, allowed_for_wake, allowed_for_judgment_support = allowed_flags(disp)
    evidence_id = stable_id("ev", fixture_id, title, source)
    source_quality_id = stable_id("sq", fixture_id, source, title)
    quarantine_id = stable_id("qr", evidence_id, disp, reason_code)
    published_at = iso(case.get("published_at"))
    observed_at = iso(case.get("observed_at"))
    detected_at = iso(case.get("detected_at")) or observed_at or published_at or UNKNOWN_TIME
    return {
        "evidence_id": evidence_id,
        "instrument": instrument,
        "theme_refs": theme_refs,
        "layer": layer,
        "source_kind": source_kind,
        "observed_at": observed_at,
        "published_at": published_at,
        "detected_at": detected_at,
        "ingested_at": detected_at,
        "effective_from": published_at,
        "effective_to": None if disp == "ELIGIBLE_FOR_WAKE" else detected_at,
        "lead_lag_window": "unknown" if not confirmed else "leading",
        "direction": "bearish" if disp == "ELIGIBLE_FOR_WAKE" else "ambiguous",
        "magnitude": 8.0 if disp == "ELIGIBLE_FOR_WAKE" else None,
        "source_reliability": reliability(tier),
        "novelty_score": 8.0 if disp == "ELIGIBLE_FOR_WAKE" else 2.0,
        "staleness_class": staleness(case),
        "supports": theme_refs if allowed_for_judgment_support else [],
        "conflicts_with": theme_refs if disp in {"PACKET_CONTEXT_ONLY", "QUARANTINE"} else [],
        "raw_ref": raw_ref,
        "normalized_summary": title,
        "structured_facts": {
            "headline": title,
            "source": source,
            "query": case.get("query"),
            "ingress_path": case.get("ingress_path")
        },
        "source_quality": {
            "source_quality_id": source_quality_id,
            "raw_ref": raw_ref,
            "source_domain": source,
            "source_reliability_tier": tier,
            "title_quality_class": quality,
            "confirmed_event_language": confirmed,
            "speculative_or_question": speculative,
            "low_quality_pattern_hits": hits,
            "decision": "ELIGIBLE_FOR_WAKE" if disp == "ELIGIBLE_FOR_WAKE" else "CONTEXT_ONLY" if disp in {"PACKET_CONTEXT_ONLY", "STORE_LOW_AUTHORITY"} else "QUARANTINE",
            "decision_reason": reason_detail
        },
        "quarantine": {
            "quarantine_id": quarantine_id,
            "evidence_id": evidence_id,
            "raw_ref": raw_ref,
            "disposition": "ELIGIBLE_FOR_WAKE" if disp == "ELIGIBLE_FOR_WAKE" else "CONTEXT_ONLY" if disp in {"PACKET_CONTEXT_ONLY", "STORE_LOW_AUTHORITY"} else "QUARANTINE",
            "reason_code": reason_code,
            "reason_detail": reason_detail,
            "allowed_as_context": allowed_as_context,
            "allowed_for_wake": allowed_for_wake,
            "allowed_for_judgment_support": allowed_for_judgment_support
        }
    }


def normalize_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_case(case) for case in cases]


def load_fixture(path: Path = DEFAULT_FIXTURE) -> list[dict[str, Any]]:
    payload = load_json(path)
    return [case for case in payload.get("cases", []) if isinstance(case, dict)]


def safe_report_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to((ROOT / "workspace" / "services" / "market-ingest" / "state").resolve(strict=False))
        return True
    except ValueError:
        pass
    try:
        resolved.relative_to((ROOT / "workspace" / "ops" / "state").resolve(strict=False))
        return True
    except ValueError:
        pass
    return False


def build_report(fixture: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    cases = load_fixture(fixture)
    records = normalize_cases(cases)
    expectation_failures = []
    by_ref = {record["raw_ref"].removeprefix("fixture:"): record for record in records}
    for case in cases:
        expected = case.get("expected_disposition")
        actual = by_ref[case["fixture_id"]]["quarantine"]["reason_code"]
        if case.get("expected_reason_code") != actual:
            expectation_failures.append({
                "fixture_id": case["fixture_id"],
                "expected_reason_code": case.get("expected_reason_code"),
                "actual_reason_code": actual
            })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not expectation_failures else "fail",
        "records_total": len(records),
        "evidence_records": records,
        "expectation_failures": expectation_failures
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    report_path = Path(args.report)
    if not safe_report_path(report_path):
        print(json.dumps({"status": "blocked", "blocking_reasons": ["unsafe_report_path"]}, ensure_ascii=False))
        return 2
    report = build_report(Path(args.fixture))
    atomic_write_json(report_path, report)
    print(json.dumps({"status": report["status"], "records_total": report["records_total"], "report_path": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
