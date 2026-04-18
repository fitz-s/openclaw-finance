#!/usr/bin/env python3
"""SourceCandidate promotion gate before EvidenceRecord creation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/Users/leofitz/.openclaw")
SERVICE = ROOT / "workspace" / "services" / "market-ingest"
DEFAULT_REGISTRY = SERVICE / "config" / "source-registry.json"
DEFAULT_FIXTURE = ROOT / "workspace" / "ops" / "fixtures" / "finance_false_positives" / "false_positive_cases.json"
DEFAULT_REPORT = SERVICE / "state" / "source-promotion-report.json"
UNKNOWN_TIME = "1970-01-01T00:00:00Z"

CLICKBAIT_PATTERNS = [
    re.compile(r"\bcrash\s+or\s+rally\b", re.I),
    re.compile(r"\b[a-z]+\s+vs\s+[a-z]+\b", re.I),
    re.compile(r"\([A-Za-z0-9_-]{8,}\)"),
]
SPECULATIVE_PATTERNS = [
    re.compile(r"\?$"),
    re.compile(r"\b(could|may|might|will .*\?|whispering|rumou?rs?)\b", re.I),
]
CONFIRMED_EVENT_PATTERNS = [
    re.compile(r"\b(halted|suspended|attacked|targeted|closed|closes?|blocked|announces?|announced|files?|filed|bought|purchased|acquired|sold|buyback|financing|funding|offering|down\s+\d+(?:\.\d+)?%|up\s+\d+(?:\.\d+)?%)\b", re.I),
    re.compile(r"(宣布|公告|收购|买入|卖出|回购|融资|投资|发行|增持|减持)"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(material.encode('utf-8')).hexdigest()[:16]}"


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def iso_or_none(value: Any) -> str | None:
    parsed = parse_dt(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def load_registry(path: Path = DEFAULT_REGISTRY) -> list[dict[str, Any]]:
    payload = load_json(path, {})
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return [source for source in sources if isinstance(source, dict)]


def registry_match(source_name: str, registry: list[dict[str, Any]]) -> dict[str, Any] | None:
    lowered = source_name.lower()
    wildcard = None
    for source in registry:
        patterns = source.get("domain_patterns", [])
        if "*" in patterns:
            wildcard = source
            continue
        for pattern in patterns:
            if str(pattern).lower() in lowered:
                return source
    return wildcard


def candidate_from_case(case: dict[str, Any], registry: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    source_name = str(case.get("source") or "unknown")
    matched = registry_match(source_name, registry)
    published_at = iso_or_none(case.get("published_at"))
    observed_at = iso_or_none(case.get("observed_at"))
    discovered_at = iso_or_none(case.get("detected_at")) or observed_at or published_at or UNKNOWN_TIME
    fixture_id = str(case.get("fixture_id") or stable_id("fixture", case.get("title"), source_name))
    raw_ref = case.get("raw_ref") or f"fixture:{fixture_id}"
    return {
        "candidate_id": stable_id("src-cand", raw_ref, case.get("title"), source_name),
        "raw_ref": raw_ref,
        "url": case.get("url"),
        "title": str(case.get("title") or ""),
        "snippet": case.get("snippet") or case.get("summary"),
        "source": source_name,
        "discovered_at": discovered_at,
        "discovered_by": str(case.get("discovered_by") or case.get("ingress_path") or "fixture_adapter"),
        "ingress_path": str(case.get("ingress_path") or "unknown"),
        "proposed_instruments": case.get("instrument") if isinstance(case.get("instrument"), list) else ["SPY"],
        "proposed_themes": [str(case.get("theme") or case.get("query") or "theme:market_structure")],
        "source_registry_ref": matched.get("source_id") if matched else None,
        "published_at": published_at,
        "observed_at": observed_at,
        "raw_capture_sha256": case.get("raw_capture_sha256"),
    }


def age_hours(candidate: dict[str, Any]) -> float | None:
    published = parse_dt(candidate.get("published_at"))
    observed = parse_dt(candidate.get("observed_at"))
    if not published or not observed:
        return None
    return (observed - published).total_seconds() / 3600


def title_flags(title: str) -> dict[str, Any]:
    return {
        "clickbait_hits": [pattern.pattern for pattern in CLICKBAIT_PATTERNS if pattern.search(title)],
        "speculative": any(pattern.search(title.strip()) for pattern in SPECULATIVE_PATTERNS),
        "confirmed_event_language": any(pattern.search(title) for pattern in CONFIRMED_EVENT_PATTERNS),
    }


def reliability_score(tier: str | None) -> float:
    return {
        "T0_official_or_exchange": 1.0,
        "T1_primary_wire_or_regulator": 0.9,
        "T2_reputable_secondary": 0.75,
        "T3_untrusted_or_syndicated": 0.3,
        "T4_blocked_or_low_quality": 0.0,
    }.get(str(tier or ""), 0.2)


def confirmed_support_requires_primary(
    *,
    candidate: dict[str, Any],
    source: dict[str, Any] | None,
    source_id: str | None,
    flags: dict[str, Any],
    blockers: list[str],
) -> bool:
    """Allow fresh confirmed headline metadata to be visible, but never wake.

    Unknown/restricted web is not authoritative enough to wake the operator.
    Suppressing confirmed-event metadata entirely is worse: it makes fresh
    context invisible and pushes reports back toward stale primary-wire reuse.
    This path is support-only and explicitly requires primary confirmation.
    """
    if not flags.get("confirmed_event_language"):
        return False
    if not candidate.get("raw_ref") or not candidate.get("published_at") or not candidate.get("observed_at"):
        return False
    if age_hours(candidate) is not None and age_hours(candidate) > 6:
        return False
    if any(blocker in {"low_quality_source", "clickbait_pattern", "speculative_question"} for blocker in blockers):
        return False
    if source_id == "source:unknown_web":
        return True
    if source and source.get("eligible_for_judgment_support") is True and source.get("license_usage") in {"unknown", "summary_only"}:
        return True
    return False


def promote_candidate(candidate: dict[str, Any], registry: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    source = registry_match(str(candidate.get("source") or ""), registry)
    source_id = source.get("source_id") if source else None
    official_sec_source = source_id == "source:sec_edgar"
    title = str(candidate.get("title") or "")
    flags = title_flags(title)
    blockers: list[str] = []
    decision = "ACCEPT"
    reason_code = "accepted_for_evidence"

    if not candidate.get("raw_ref"):
        blockers.append("missing_raw_ref")
    if not source or not candidate.get("source_registry_ref"):
        blockers.append("missing_source_registry_ref")
    if not candidate.get("published_at") or not candidate.get("observed_at"):
        blockers.append("missing_minimum_timestamps")

    if source:
        if source.get("license_usage") in {"unknown", "blocked"}:
            blockers.append("source_license_not_allowed_for_wake")
        if source.get("latency_class") == "unknown":
            blockers.append("source_latency_unknown")
        if source.get("reliability_tier") == "T4_blocked_or_low_quality":
            blockers.append("low_quality_source")
        if source.get("title_only_policy") == "quarantine" and not candidate.get("raw_capture_sha256"):
            blockers.append("title_only_quarantine_policy")

    if flags["clickbait_hits"] and not official_sec_source:
        blockers.append("clickbait_pattern")
    if flags["speculative"]:
        blockers.append("speculative_question")
    if age_hours(candidate) is not None and age_hours(candidate) > 36:
        blockers.append("stale_recycled_event")

    hard_quarantine = {
        "missing_raw_ref",
        "low_quality_source",
        "title_only_quarantine_policy",
        "clickbait_pattern",
        "speculative_question",
    }
    context_only = {
        "missing_source_registry_ref",
        "missing_minimum_timestamps",
        "source_license_not_allowed_for_wake",
        "source_latency_unknown",
        "stale_recycled_event",
    }
    if any(blocker in hard_quarantine for blocker in blockers):
        decision = "QUARANTINE"
        reason_code = next(blocker for blocker in blockers if blocker in hard_quarantine)
    elif any(blocker in context_only for blocker in blockers):
        decision = "CONTEXT_ONLY"
        reason_code = next(blocker for blocker in blockers if blocker in context_only)
    elif source and source.get("eligible_for_wake") is not True:
        decision = "CONTEXT_ONLY"
        reason_code = "source_not_wake_eligible"
    elif not flags["confirmed_event_language"] and source and source.get("title_only_policy") == "allow_if_confirmed":
        decision = "CONTEXT_ONLY"
        reason_code = "title_not_confirmed_event"

    support_only_reason_codes = {"source_not_wake_eligible"}
    if official_sec_source:
        support_only_reason_codes.add("title_not_confirmed_event")
    support_requires_primary_confirmation = confirmed_support_requires_primary(
        candidate=candidate,
        source=source,
        source_id=source_id,
        flags=flags,
        blockers=blockers,
    )
    allowed_for_judgment_support = (
        decision == "ACCEPT"
        or support_requires_primary_confirmation
        or (
            decision == "CONTEXT_ONLY"
            and reason_code in support_only_reason_codes
            and bool(source and source.get("eligible_for_judgment_support"))
        )
    )

    return {
        "promotion_id": stable_id("promotion", candidate.get("candidate_id"), decision, reason_code),
        "candidate_id": candidate.get("candidate_id"),
        "source_registry_ref": candidate.get("source_registry_ref"),
        "evaluated_at": now_iso(),
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": sorted(set(blockers)),
        "promote_to_evidence": decision in {"ACCEPT", "CONTEXT_ONLY"},
        "allowed_for_wake": decision == "ACCEPT" and bool(source and source.get("eligible_for_wake")),
        "allowed_for_judgment_support": allowed_for_judgment_support,
        "support_requires_primary_confirmation": support_requires_primary_confirmation,
        "support_scope": "confirmed_headline_metadata_only" if support_requires_primary_confirmation else None,
        "support_reason_code": (
            "confirmed_untrusted_headline_requires_primary_confirmation"
            if support_requires_primary_confirmation else None
        ),
        "source_reliability_tier": source.get("reliability_tier") if source else None,
        "source_reliability_score": reliability_score(source.get("reliability_tier") if source else None),
        "title_flags": flags,
    }


def build_report(fixture: Path = DEFAULT_FIXTURE, registry_path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    registry = load_registry(registry_path)
    cases = (load_json(fixture, {}) or {}).get("cases", [])
    candidates = [candidate_from_case(case, registry) for case in cases if isinstance(case, dict)]
    promotions = [promote_candidate(candidate, registry) for candidate in candidates]
    return {
        "generated_at": now_iso(),
        "status": "pass",
        "registry_path": str(registry_path),
        "candidate_count": len(candidates),
        "promotion_counts": {
            decision: sum(1 for item in promotions if item["decision"] == decision)
            for decision in ["ACCEPT", "CONTEXT_ONLY", "QUARANTINE"]
        },
        "source_candidates": candidates,
        "promotions": promotions,
    }


def safe_report_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    for allowed in [SERVICE / "state", ROOT / "workspace" / "ops" / "state"]:
        try:
            path.resolve(strict=False).relative_to(allowed.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    report_path = Path(args.report)
    if not safe_report_path(report_path):
        print(json.dumps({"status": "blocked", "blocking_reasons": ["unsafe_report_path"]}, ensure_ascii=False))
        return 2
    report = build_report(Path(args.fixture), Path(args.registry))
    atomic_write_json(report_path, report)
    print(json.dumps({"status": report["status"], "candidate_count": report["candidate_count"], "report_path": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
