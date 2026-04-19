#!/usr/bin/env python3
"""Live finance state adapter that emits promoted EvidenceRecord rows."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/Users/leofitz/.openclaw")
WORKSPACE = ROOT / "workspace"
FINANCE_STATE = WORKSPACE / "finance" / "state"
SERVICE = WORKSPACE / "services" / "market-ingest"
STATE_DIR = SERVICE / "state"
SOURCE_PROMOTION_PATH = SERVICE / "normalizer" / "source_promotion.py"
SEMANTIC_NORMALIZER_PATH = SERVICE / "normalizer" / "semantic_normalizer.py"

SCAN_STATE = FINANCE_STATE / "intraday-open-scan-state.json"
PRICES = FINANCE_STATE / "prices.json"
PORTFOLIO_RESOLVED = FINANCE_STATE / "portfolio-resolved.json"
OPTION_RISK = FINANCE_STATE / "portfolio-option-risk.json"
SEC_DISCOVERY = FINANCE_STATE / "sec-discovery.json"
SEC_SEMANTICS = FINANCE_STATE / "sec-filing-semantics.json"
BROAD_MARKET = FINANCE_STATE / "broad-market-proxy.json"
OPTIONS_FLOW = FINANCE_STATE / "options-flow-proxy.json"
SOURCE_ATOMS = FINANCE_STATE / "source-atoms" / "latest.jsonl"
CLAIM_GRAPH = FINANCE_STATE / "claim-graph.json"
CONTEXT_GAPS = FINANCE_STATE / "context-gaps.json"
DEFAULT_EVIDENCE_JSONL = STATE_DIR / "live-evidence-records.jsonl"
DEFAULT_REPORT = STATE_DIR / "live-evidence-report.json"

TICKER_RE = re.compile(r"\b[A-Z]{2,5}(?:/[A-Z]{3})?\b")
KNOWN_NON_TICKERS = {"USD", "ET", "CDT", "AI", "TVA", "VLCC", "CPI", "WTI", "FEED", "GW"}
ACTOR_INTENT_PATTERNS = [
    re.compile(r"\b(bought|purchased|acquired|sold|buyback|insider|form\s*4|13d|13g|8-k|treasury|financing|funding|offering|guidance)\b", re.I),
    re.compile(r"(融资|投资|回购|增持|减持|发行|尚未落地|收购|商业化部署|原则性投资决定)")
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    tmp.replace(path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    for directory in [STATE_DIR, WORKSPACE / "ops" / "state"]:
        try:
            path.resolve(strict=False).relative_to(directory.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def extract_instruments(*texts: Any) -> list[str]:
    symbols: set[str] = set()
    for text in texts:
        for match in TICKER_RE.findall(str(text or "")):
            if match not in KNOWN_NON_TICKERS:
                symbols.add(match)
    return sorted(symbols) or ["SPY"]


def first_source(sources: Any) -> str:
    if isinstance(sources, list) and sources:
        return str(sources[0])
    if isinstance(sources, str) and sources:
        return sources
    return "unknown"


def theme_ref(value: Any) -> str:
    raw = str(value or "market_structure").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")[:80]
    return f"theme:{slug or 'market_structure'}"


def cases_from_scan_state(scan_state: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    accumulated = scan_state.get("accumulated", [])
    observations = [item for item in accumulated if isinstance(item, dict)]
    observations.sort(
        key=lambda item: (
            float(item.get("cumulative_value") or 0),
            float(item.get("importance") or 0),
            float(item.get("urgency") or 0),
        ),
        reverse=True,
    )
    cases: list[dict[str, Any]] = []
    for item in observations[:limit]:
        obs_id = str(item.get("id") or item.get("ts") or item.get("theme") or "unknown")
        title = str(item.get("theme") or item.get("summary") or obs_id)
        summary = str(item.get("summary") or "")
        ts = item.get("ts") or scan_state.get("last_scan_time") or scan_state.get("last_updated")
        source = first_source(item.get("sources"))
        cases.append({
            "fixture_id": obs_id,
            "raw_ref": f"finance-scan:{obs_id}",
            "ingress_path": "openclaw_llm_scanner",
            "title": title,
            "summary": summary,
            "source": source,
            "query": item.get("query") or item.get("theme"),
            "published_at": item.get("published_at") or ts,
            "observed_at": item.get("observed_at") or ts,
            "detected_at": item.get("detected_at") or scan_state.get("last_updated") or ts,
            "instrument": extract_instruments(title, summary),
            "theme_refs": [theme_ref(title)],
            "layer": "L2_public_narrative_event",
            "source_kind": "source_candidate_from_scanner",
        })
    return cases


def actor_intent_kind(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["bought", "purchased", "acquired", "增持", "买入", "收购"]):
        return "large_actor_accumulation"
    if any(token in lowered for token in ["sold", "insider", "form 4", "减持", "卖出"]):
        return "insider_or_large_actor_distribution"
    if any(token in lowered for token in ["financing", "funding", "offering", "融资", "投资", "发行", "尚未落地"]):
        return "issuer_financing_signal"
    if any(token in lowered for token in ["guidance", "8-k", "announced", "公告", "宣布"]):
        return "issuer_guidance_or_filing"
    return "actor_intent_candidate"


def actor_direction(text: str) -> str:
    lowered = text.lower()
    bearish_tokens = ["not yet", "uncertain", "lawsuit", "fraud", "delay", "尚未", "未落地", "不确定", "诉讼", "欺诈", "跌幅"]
    bullish_tokens = ["bought", "purchased", "buyback", "secured financing", "raises guidance", "增持", "回购", "融资落地", "上调指引"]
    if any(token in lowered for token in bearish_tokens):
        return "bearish"
    if any(token in lowered for token in bullish_tokens):
        return "bullish"
    return "ambiguous"


def cases_from_actor_intent(scan_state: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    accumulated = scan_state.get("accumulated", [])
    observations = [item for item in accumulated if isinstance(item, dict)]
    cases: list[dict[str, Any]] = []
    for item in observations:
        title = str(item.get("theme") or item.get("summary") or item.get("id") or "")
        summary = str(item.get("summary") or "")
        text = f"{title} {summary}"
        if not any(pattern.search(text) for pattern in ACTOR_INTENT_PATTERNS):
            continue
        obs_id = str(item.get("id") or item.get("ts") or title or "unknown")
        ts = item.get("ts") or scan_state.get("last_scan_time") or scan_state.get("last_updated")
        cases.append({
            "fixture_id": f"actor:{obs_id}",
            "raw_ref": f"finance-actor-intent:{obs_id}",
            "ingress_path": "openclaw_llm_scanner_actor_intent_extractor",
            "title": f"Actor intent candidate: {title}",
            "summary": summary,
            "source": first_source(item.get("sources")),
            "query": item.get("query") or item.get("theme"),
            "published_at": item.get("published_at") or ts,
            "observed_at": item.get("observed_at") or ts,
            "detected_at": item.get("detected_at") or scan_state.get("last_updated") or ts,
            "instrument": extract_instruments(title, summary),
            "theme_refs": [theme_ref(title), "theme:actor_intent"],
            "layer": "L4_actor_intent",
            "source_kind": actor_intent_kind(text),
            "direction_hint": actor_direction(text),
        })
        if len(cases) >= limit:
            break
    return cases


def cases_from_sec_discovery(sec_discovery: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    discoveries = sec_discovery.get("discoveries", []) if isinstance(sec_discovery, dict) else []
    cases: list[dict[str, Any]] = []
    for item in discoveries:
        if not isinstance(item, dict):
            continue
        discovery_id = str(item.get("discovery_id") or item.get("accession_number") or item.get("title") or "unknown")
        company = str(item.get("company_name") or "unknown company")
        form_type = str(item.get("form_type") or "SEC filing")
        title = str(item.get("title") or f"{company} filed {form_type}")
        summary = str(item.get("summary") or title)
        filed_at = item.get("published_at") or item.get("observed_at") or sec_discovery.get("generated_at")
        cases.append({
            "fixture_id": f"sec:{discovery_id}",
            "raw_ref": item.get("raw_ref") or item.get("url") or f"sec:{discovery_id}",
            "ingress_path": "deterministic_sec_discovery_fetcher",
            "title": f"SEC discovery: {title}",
            "summary": summary,
            "source": "sec.gov",
            "query": form_type,
            "published_at": filed_at,
            "observed_at": item.get("observed_at") or filed_at,
            "detected_at": item.get("detected_at") or sec_discovery.get("generated_at") or filed_at,
            "instrument": [f"CIK:{item.get('cik')}"] if item.get("cik") else ["SEC:UNKNOWN"],
            "theme_refs": [theme_ref(company), "theme:sec_discovery", "theme:unknown_discovery"],
            "layer": "L4_actor_intent",
            "source_kind": "sec_current_filing",
            "direction_hint": item.get("direction") if item.get("direction") in {"bullish", "bearish", "neutral", "ambiguous"} else "ambiguous",
            "magnitude_hint": item.get("novelty_score"),
            "structured_fact_hints": {
                "candidate_type": "unknown_discovery",
                "discovery_scope": "non_watchlist",
                "source": "sec.gov",
                "form_type": form_type,
                "company_name": company,
                "cik": item.get("cik"),
                "accession_number": item.get("accession_number"),
                "url": item.get("url"),
            },
        })
        if len(cases) >= limit:
            break
    return cases


def cases_from_sec_semantics(sec_semantics: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    semantics = sec_semantics.get("semantics", []) if isinstance(sec_semantics, dict) else []
    cases: list[dict[str, Any]] = []
    for item in semantics:
        if not isinstance(item, dict):
            continue
        semantic_id = str(item.get("semantic_id") or item.get("discovery_id") or item.get("raw_ref") or "unknown")
        issuer = str(item.get("issuer_name") or "unknown issuer")
        form_type = str(item.get("form_type") or "SEC filing")
        semantic_type = str(item.get("filing_semantic_type") or "sec_filing_metadata_only")
        cases.append({
            "fixture_id": f"sec-sem:{semantic_id}",
            "raw_ref": item.get("raw_ref") or item.get("url") or f"sec-sem:{semantic_id}",
            "ingress_path": "deterministic_sec_filing_semantics",
            "title": f"SEC filing semantic: {issuer} {form_type} {semantic_type}",
            "summary": f"{issuer} {form_type} classified as {semantic_type}; reasons={item.get('classification_reasons', [])}",
            "source": "sec.gov",
            "query": form_type,
            "published_at": item.get("published_at") or sec_semantics.get("generated_at"),
            "observed_at": item.get("observed_at") or item.get("published_at") or sec_semantics.get("generated_at"),
            "detected_at": item.get("detected_at") or sec_semantics.get("generated_at"),
            "instrument": [f"CIK:{item.get('issuer_cik')}"] if item.get("issuer_cik") else ["SEC:UNKNOWN"],
            "theme_refs": [theme_ref(issuer), "theme:sec_discovery", "theme:unknown_discovery", f"theme:{semantic_type}"],
            "layer": "L4_actor_intent",
            "source_kind": "sec_filing_semantic",
            "direction_hint": item.get("direction") if item.get("direction") in {"bullish", "bearish", "neutral", "ambiguous"} else "ambiguous",
            "magnitude_hint": item.get("transaction_value_estimate") or item.get("ownership_percent") or 0,
            "structured_fact_hints": {
                "candidate_type": "unknown_discovery",
                "discovery_scope": "non_watchlist",
                "source": "sec.gov",
                "semantic_id": item.get("semantic_id"),
                "discovery_id": item.get("discovery_id"),
                "form_type": form_type,
                "filing_semantic_type": semantic_type,
                "issuer_name": issuer,
                "issuer_cik": item.get("issuer_cik"),
                "issuer_symbol": item.get("issuer_symbol"),
                "reporting_owner": item.get("reporting_owner"),
                "owner_role": item.get("owner_role"),
                "transaction_direction": item.get("transaction_direction"),
                "transaction_value_estimate": item.get("transaction_value_estimate"),
                "ownership_percent": item.get("ownership_percent"),
                "activist_or_control_signal": item.get("activist_or_control_signal"),
                "material_event_hint": item.get("material_event_hint"),
                "semantic_wake_candidate": item.get("semantic_wake_candidate") is True,
                "support_only": item.get("support_only") is True,
                "confidence": item.get("confidence"),
                "classification_reasons": item.get("classification_reasons", []),
                "url": item.get("url"),
            },
        })
        if len(cases) >= limit:
            break
    return cases


def cases_from_prices(prices: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    quotes = prices.get("quotes", {}) if isinstance(prices, dict) else {}
    cases: list[dict[str, Any]] = []
    for symbol, quote in list(quotes.items())[:limit]:
        if not isinstance(quote, dict) or quote.get("status") != "ok":
            continue
        as_of = quote.get("as_of") or prices.get("fetched_at")
        pct = quote.get("pct_change") if quote.get("pct_change") is not None else quote.get("change_pct")
        cases.append({
            "fixture_id": f"price:{symbol}:{as_of}",
            "raw_ref": f"finance-price:{symbol}:{as_of}",
            "ingress_path": "deterministic_price_fetcher",
            "title": f"{symbol} quote snapshot {pct:+.2f}%" if isinstance(pct, (int, float)) else f"{symbol} quote snapshot",
            "summary": f"price={quote.get('price')} previous_close={quote.get('previous_close')} source=yfinance",
            "source": prices.get("source") or "yfinance",
            "published_at": as_of,
            "observed_at": as_of,
            "detected_at": prices.get("fetched_at") or as_of,
            "instrument": [str(symbol)],
            "theme_refs": [f"theme:price:{symbol}"],
            "layer": "L0_raw_observation",
            "source_kind": "provider_quote_snapshot",
        })
    return cases


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def cases_from_flow_proxy(prices: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    quotes = prices.get("quotes", {}) if isinstance(prices, dict) else {}
    rows: list[tuple[float, str, dict[str, Any]]] = []
    for symbol, quote in quotes.items():
        if not isinstance(quote, dict) or quote.get("status") != "ok":
            continue
        pct = numeric(quote.get("pct_change") if quote.get("pct_change") is not None else quote.get("change_pct"))
        volume = max(0.0, numeric(quote.get("volume")))
        pressure_score = abs(pct) * math.log10(volume + 10.0)
        rows.append((pressure_score, str(symbol), quote))
    rows.sort(reverse=True)
    cases: list[dict[str, Any]] = []
    for rank, (pressure_score, symbol, quote) in enumerate(rows[:limit], start=1):
        as_of = quote.get("as_of") or prices.get("fetched_at")
        pct = numeric(quote.get("pct_change") if quote.get("pct_change") is not None else quote.get("change_pct"))
        volume = int(numeric(quote.get("volume")))
        direction = "bullish" if pct > 0 else "bearish" if pct < 0 else "neutral"
        cases.append({
            "fixture_id": f"flow-proxy:{symbol}:{as_of}",
            "raw_ref": f"finance-flow-proxy:{symbol}:{as_of}",
            "ingress_path": "deterministic_watchlist_flow_proxy",
            "title": f"{symbol} watchlist flow proxy {pct:+.2f}% on volume {volume} (rank {rank})",
            "summary": f"pressure_score={pressure_score:.2f}; price={quote.get('price')} previous_close={quote.get('previous_close')} source=yfinance",
            "source": prices.get("source") or "yfinance",
            "published_at": as_of,
            "observed_at": as_of,
            "detected_at": prices.get("fetched_at") or as_of,
            "instrument": [symbol],
            "theme_refs": [f"theme:flow_proxy:{symbol}", f"theme:price:{symbol}"],
            "layer": "L3_flow_positioning",
            "source_kind": "watchlist_volume_pressure_proxy",
            "direction_hint": direction,
            "magnitude_hint": round(pressure_score, 4),
            "structured_fact_hints": {
                "symbol": symbol,
                "pct_change": round(pct, 4),
                "volume": volume,
                "pressure_score": round(pressure_score, 4),
                "flow_proxy_rank": rank,
                "flow_proxy_semantics": "abs(percent move) * log10(volume + 10); relative watchlist pressure proxy, not true order flow",
            },
        })
    return cases


def cases_from_broad_market_proxy(broad_market: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    rows = broad_market.get("top_dislocations", []) if isinstance(broad_market, dict) else []
    cases: list[dict[str, Any]] = []
    for rank, item in enumerate([row for row in rows if isinstance(row, dict)][:limit], start=1):
        symbol = str(item.get("symbol") or "UNKNOWN")
        as_of = item.get("as_of") or broad_market.get("generated_at") or now_iso()
        rel = numeric(item.get("relative_to_spy_pct"))
        direction = item.get("direction") if item.get("direction") in {"bullish", "bearish", "neutral"} else "ambiguous"
        semantics = str(item.get("semantics") or "broad_market_proxy")
        category = str(item.get("category") or "unknown")
        cases.append({
            "fixture_id": f"broad-market:{symbol}:{as_of}",
            "raw_ref": f"finance-broad-market:{symbol}:{as_of}",
            "ingress_path": "deterministic_broad_market_proxy_fetcher",
            "title": f"{symbol} broad proxy {rel:+.2f}% vs SPY ({semantics}, rank {rank})",
            "summary": f"pct_change={item.get('pct_change')} relative_to_spy={rel} pressure_score={item.get('pressure_score')} source=yfinance",
            "source": broad_market.get("source") or "yfinance",
            "published_at": as_of,
            "observed_at": as_of,
            "detected_at": broad_market.get("generated_at") or as_of,
            "instrument": [symbol],
            "theme_refs": [f"theme:broad_market:{category}", f"theme:{semantics}", f"theme:unknown_discovery"],
            "layer": "L3_flow_positioning",
            "source_kind": semantics,
            "direction_hint": direction,
            "magnitude_hint": item.get("pressure_score") or abs(rel),
            "structured_fact_hints": {
                "candidate_type": "unknown_discovery",
                "discovery_scope": "non_watchlist",
                "symbol": symbol,
                "category": category,
                "pct_change": item.get("pct_change"),
                "relative_to_spy_pct": rel,
                "volume": item.get("volume"),
                "pressure_score": item.get("pressure_score"),
                "broad_proxy_rank": rank,
                "broad_proxy_semantics": "sector/credit/rates/commodity proxy vs SPY; not fund-flow truth",
            },
        })
    return cases


def cases_from_options_flow(options_flow: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    rows = options_flow.get("top_events", []) if isinstance(options_flow, dict) else []
    cases: list[dict[str, Any]] = []
    for rank, item in enumerate([row for row in rows if isinstance(row, dict)][:limit], start=1):
        symbol = str(item.get("symbol") or "UNKNOWN")
        as_of = options_flow.get("generated_at") or now_iso()
        signal_type = str(item.get("option_signal_type") or "options_chain_context")
        call_put = str(item.get("call_put") or "unknown")
        direction = item.get("direction") if item.get("direction") in {"bullish", "bearish", "neutral", "ambiguous"} else "ambiguous"
        cases.append({
            "fixture_id": f"options-flow:{symbol}:{item.get('expiry')}:{item.get('contract_symbol')}",
            "raw_ref": f"finance-options-flow:{symbol}:{item.get('expiry')}:{item.get('contract_symbol')}",
            "ingress_path": "deterministic_options_flow_proxy_fetcher",
            "title": f"{symbol} {call_put} options proxy {item.get('volume')} vol / {item.get('open_interest')} OI ({signal_type}, rank {rank})",
            "summary": f"expiry={item.get('expiry')} strike={item.get('strike')} volume_oi_ratio={item.get('volume_oi_ratio')} iv={item.get('implied_volatility')} notional_proxy={item.get('notional_proxy')} source=yfinance",
            "source": "yfinance",
            "published_at": as_of,
            "observed_at": as_of,
            "detected_at": as_of,
            "instrument": [symbol],
            "theme_refs": [f"theme:options_flow:{symbol}", f"theme:{signal_type}", "theme:unknown_discovery"],
            "layer": "L3_flow_positioning",
            "source_kind": signal_type,
            "direction_hint": direction,
            "magnitude_hint": item.get("score") or item.get("notional_proxy") or 0,
            "structured_fact_hints": {
                "candidate_type": "unknown_discovery",
                "discovery_scope": "non_watchlist",
                "source": "yfinance options chain",
                "symbol": symbol,
                "expiry": item.get("expiry"),
                "call_put": call_put,
                "contract_symbol": item.get("contract_symbol"),
                "strike": item.get("strike"),
                "volume": item.get("volume"),
                "open_interest": item.get("open_interest"),
                "volume_oi_ratio": item.get("volume_oi_ratio"),
                "implied_volatility": item.get("implied_volatility"),
                "notional_proxy": item.get("notional_proxy"),
                "score": item.get("score"),
                "option_signal_type": signal_type,
                "options_flow_semantics": "yfinance option-chain volume/OI/IV proxy; delayed/incomplete; not true options tape",
            },
        })
    return cases


def atom_by_id(atoms: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(atom.get("atom_id")): atom
        for atom in atoms
        if isinstance(atom, dict) and atom.get("atom_id")
    }


def layer_for_claim(claim: dict[str, Any], atom: dict[str, Any] | None) -> str:
    event_class = str(claim.get("event_class") or "")
    lane = str(claim.get("source_lane") or (atom or {}).get("source_lane") or "")
    if event_class in {"price"} or lane == "market_structure":
        return "L3_flow_positioning" if event_class == "flow" else "L0_raw_observation"
    if event_class == "filing" or lane in {"corp_filing_ir", "corporate_filing"}:
        return "L4_actor_intent"
    if event_class == "portfolio" or lane == "internal_private":
        return "L3_flow_positioning"
    return "L2_public_narrative_event"


def cases_from_claim_graph(claim_graph: dict[str, Any], atoms: list[dict[str, Any]], context_gaps: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    claims = [claim for claim in claim_graph.get("claims", []) if isinstance(claim, dict) and claim.get("claim_id")]
    atoms_by_id = atom_by_id(atoms)
    gap_claims = {
        str(claim_id)
        for gap in (context_gaps.get("gaps", []) if isinstance(context_gaps.get("gaps"), list) else [])
        if isinstance(gap, dict)
        for claim_id in (gap.get("weak_claim_ids") if isinstance(gap.get("weak_claim_ids"), list) else [gap.get("claim_id")])
        if claim_id
    }
    cases: list[dict[str, Any]] = []
    for claim in claims[:limit]:
        atom = atoms_by_id.get(str(claim.get("atom_id") or ""))
        claim_id = str(claim.get("claim_id") or "unknown")
        source_id = str(claim.get("source_id") or (atom or {}).get("source_id") or "source:unknown_web")
        lane = str(claim.get("source_lane") or (atom or {}).get("source_lane") or "news_policy_narrative")
        subject = str(claim.get("subject") or "unknown")
        predicate = str(claim.get("predicate") or "mentions")
        obj = str(claim.get("object") or "")
        event_time = (atom or {}).get("event_time") or (atom or {}).get("published_at") or claim_graph.get("generated_at") or now_iso()
        cases.append({
            "fixture_id": f"claim:{claim_id}",
            "raw_ref": f"finance-claim:{claim_id}",
            "ingress_path": "finance_claim_graph_shadow",
            "title": f"{subject} {predicate}: {obj[:160]}",
            "summary": obj,
            "source": source_id,
            "query": predicate,
            "published_at": event_time,
            "observed_at": (atom or {}).get("observed_at") or event_time,
            "detected_at": (atom or {}).get("ingested_at") or event_time,
            "instrument": [subject] if subject else ["SPY"],
            "theme_refs": [f"theme:claim_graph:{lane}", f"theme:{predicate}"],
            "layer": layer_for_claim(claim, atom),
            "source_kind": f"claim_graph_{claim.get('event_class') or 'event'}",
            "direction_hint": claim.get("direction") if claim.get("direction") in {"bullish", "bearish", "neutral", "ambiguous"} else "ambiguous",
            "magnitude_hint": 6 if claim_id in gap_claims else 3,
            "structured_fact_hints": {
                "claim_id": claim_id,
                "atom_id": claim.get("atom_id"),
                "source_lane": lane,
                "context_gap_open": claim_id in gap_claims,
                "source_id": source_id,
            },
        })
    return cases


def infer_pct_from_summary(text: str) -> float | None:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)%", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def apply_direction_hints(record: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["structured_facts"] = dict(record.get("structured_facts", {}))
    if isinstance(case.get("structured_fact_hints"), dict):
        record["structured_facts"].update(case["structured_fact_hints"])
    if case.get("direction_hint") in {"bullish", "bearish", "neutral", "ambiguous"}:
        record["direction"] = case["direction_hint"]
        if case.get("magnitude_hint") is not None:
            record["magnitude"] = numeric(case.get("magnitude_hint"))
    elif record.get("layer") == "L0_raw_observation":
        pct = infer_pct_from_summary(str(case.get("title") or ""))
        if pct is not None:
            record["direction"] = "bullish" if pct > 0 else "bearish" if pct < 0 else "neutral"
            record["magnitude"] = abs(pct)
    return record


def cases_from_portfolio(portfolio: dict[str, Any], option_risk: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    resolved_at = portfolio.get("resolved_at") or option_risk.get("generated_at") or now_iso()
    status = portfolio.get("data_status") or "unknown"
    cases.append({
        "fixture_id": f"portfolio-source-status:{resolved_at}",
        "raw_ref": f"finance-portfolio-resolved:{resolved_at}",
        "ingress_path": "deterministic_portfolio_resolver",
        "title": f"Portfolio source status {status}",
        "summary": str(portfolio.get("stale_reason") or portfolio.get("source") or status),
        "source": portfolio.get("source") or option_risk.get("source") or "IBKR Flex Web Service",
        "published_at": resolved_at,
        "observed_at": resolved_at,
        "detected_at": resolved_at,
        "instrument": ["PORTFOLIO"],
        "theme_refs": ["theme:portfolio_source_quality"],
        "layer": "L3_flow_positioning",
        "source_kind": "portfolio_source_status",
    })
    if option_risk:
        generated_at = option_risk.get("generated_at") or resolved_at
        cases.append({
            "fixture_id": f"option-risk:{generated_at}",
            "raw_ref": f"finance-option-risk:{generated_at}",
            "ingress_path": "deterministic_option_risk_enricher",
            "title": f"Option risk source status {option_risk.get('data_status') or 'unknown'}",
            "summary": "; ".join(str(item) for item in option_risk.get("blocking_reasons", [])),
            "source": option_risk.get("source") or "IBKR Flex Web Service",
            "published_at": generated_at,
            "observed_at": generated_at,
            "detected_at": generated_at,
            "instrument": ["PORTFOLIO"],
            "theme_refs": ["theme:option_risk_source_quality"],
            "layer": "L3_flow_positioning",
            "source_kind": "option_risk_status",
        })
    return cases


def apply_promotion(record: dict[str, Any], promotion: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["structured_facts"] = dict(record.get("structured_facts", {}))
    record["structured_facts"].update({
        "source_candidate_id": candidate.get("candidate_id"),
        "promotion_id": promotion.get("promotion_id"),
        "promotion_decision": promotion.get("decision"),
        "promotion_reason_code": promotion.get("reason_code"),
        "allowed_for_judgment_support": promotion.get("allowed_for_judgment_support"),
    })
    for key in ("support_requires_primary_confirmation", "support_scope", "support_reason_code"):
        if promotion.get(key) is not None:
            record["structured_facts"][key] = promotion.get(key)
    if promotion.get("source_reliability_score") is not None:
        record["source_reliability"] = promotion["source_reliability_score"]
    if promotion.get("source_reliability_tier"):
        record["source_quality"] = dict(record.get("source_quality", {}))
        record["source_quality"]["source_reliability_tier"] = promotion["source_reliability_tier"]
    if promotion.get("source_registry_ref") == "source:sec_edgar":
        record["source_quality"] = dict(record.get("source_quality", {}))
        record["source_quality"]["title_quality_class"] = "official_filing_title"
        record["source_quality"]["low_quality_pattern_hits"] = []
        if record.get("source_kind") == "sec_filing_semantic" and record.get("structured_facts", {}).get("semantic_wake_candidate") is not True:
            record["quarantine"] = dict(record.get("quarantine", {}))
            record["source_quality"]["decision"] = "CONTEXT_ONLY"
            record["quarantine"]["disposition"] = "CONTEXT_ONLY"
            record["quarantine"]["allowed_for_wake"] = False
            record["quarantine"]["allowed_for_judgment_support"] = True
    if promotion["decision"] == "ACCEPT":
        wake_allowed = bool(promotion.get("allowed_for_wake"))
        support_allowed = bool(promotion.get("allowed_for_judgment_support"))
        record["source_quality"] = dict(record["source_quality"])
        record["quarantine"] = dict(record["quarantine"])
        record["source_quality"]["decision"] = "ELIGIBLE_FOR_WAKE" if wake_allowed else "CONTEXT_ONLY"
        record["source_quality"]["decision_reason"] = promotion["reason_code"]
        record["quarantine"]["disposition"] = "ELIGIBLE_FOR_WAKE" if wake_allowed else "CONTEXT_ONLY"
        record["quarantine"]["reason_code"] = promotion["reason_code"]
        record["quarantine"]["allowed_for_wake"] = wake_allowed
        record["quarantine"]["allowed_for_judgment_support"] = support_allowed
        if not support_allowed:
            record["supports"] = []
    if promotion["decision"] == "CONTEXT_ONLY":
        support_allowed = bool(promotion.get("allowed_for_judgment_support"))
        record["source_quality"] = dict(record["source_quality"])
        record["quarantine"] = dict(record["quarantine"])
        record["source_quality"]["decision"] = "CONTEXT_ONLY"
        record["source_quality"]["decision_reason"] = promotion["reason_code"]
        record["quarantine"]["disposition"] = "CONTEXT_ONLY"
        record["quarantine"]["reason_code"] = promotion["reason_code"]
        record["quarantine"]["reason_detail"] = ";".join(promotion["blocking_reasons"])
        record["quarantine"]["allowed_for_wake"] = False
        record["quarantine"]["allowed_for_judgment_support"] = support_allowed
        for key in ("support_requires_primary_confirmation", "support_scope", "support_reason_code"):
            if promotion_result_value := promotion.get(key):
                record["quarantine"][key] = promotion_result_value
        if not support_allowed:
            record["supports"] = []
    return record


def build_live_evidence(
    *,
    scan_state: dict[str, Any],
    prices: dict[str, Any],
    portfolio: dict[str, Any],
    option_risk: dict[str, Any],
    sec_discovery: dict[str, Any] | None = None,
    sec_semantics: dict[str, Any] | None = None,
    broad_market: dict[str, Any] | None = None,
    options_flow: dict[str, Any] | None = None,
    source_atoms: list[dict[str, Any]] | None = None,
    claim_graph: dict[str, Any] | None = None,
    context_gaps: dict[str, Any] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    promotion = load_module(SOURCE_PROMOTION_PATH, "live_finance_source_promotion")
    normalizer = load_module(SEMANTIC_NORMALIZER_PATH, "live_finance_semantic_normalizer")
    registry = promotion.load_registry()
    cases = (
        cases_from_scan_state(scan_state, limit=limit)
        + cases_from_actor_intent(scan_state, limit=max(3, limit // 2))
        + (cases_from_sec_semantics(sec_semantics or {}, limit=max(3, limit // 2)) or cases_from_sec_discovery(sec_discovery or {}, limit=max(3, limit // 2)))
        + cases_from_prices(prices, limit=limit)
        + cases_from_flow_proxy(prices, limit=min(6, limit))
        + cases_from_broad_market_proxy(broad_market or {}, limit=min(8, limit))
        + cases_from_options_flow(options_flow or {}, limit=min(8, limit))
        + cases_from_claim_graph(claim_graph or {}, source_atoms or [], context_gaps or {}, limit=limit)
        + cases_from_portfolio(portfolio, option_risk)
    )
    candidates = [promotion.candidate_from_case(case, registry) for case in cases]
    promotions = [promotion.promote_candidate(candidate, registry) for candidate in candidates]
    records = []
    quarantined = []
    for case, candidate, promotion_result in zip(cases, candidates, promotions):
        if not promotion_result["promote_to_evidence"]:
            quarantined.append({
                "candidate_id": candidate["candidate_id"],
                "decision": promotion_result["decision"],
                "reason_code": promotion_result["reason_code"],
                "raw_ref": candidate.get("raw_ref"),
            })
            continue
        record = apply_direction_hints(normalizer.normalize_case(case), case)
        records.append(apply_promotion(record, promotion_result, candidate))
    return {
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "live_adapter",
        "candidate_count": len(candidates),
        "evidence_count": len(records),
        "quarantine_count": len(quarantined),
        "source_candidates": candidates,
        "promotions": promotions,
        "evidence_records": records,
        "quarantined_candidates": quarantined,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-state", default=str(SCAN_STATE))
    parser.add_argument("--prices", default=str(PRICES))
    parser.add_argument("--portfolio", default=str(PORTFOLIO_RESOLVED))
    parser.add_argument("--option-risk", default=str(OPTION_RISK))
    parser.add_argument("--sec-discovery", default=str(SEC_DISCOVERY))
    parser.add_argument("--sec-semantics", default=str(SEC_SEMANTICS))
    parser.add_argument("--broad-market", default=str(BROAD_MARKET))
    parser.add_argument("--options-flow", default=str(OPTIONS_FLOW))
    parser.add_argument("--source-atoms", default=str(SOURCE_ATOMS))
    parser.add_argument("--claim-graph", default=str(CLAIM_GRAPH))
    parser.add_argument("--context-gaps", default=str(CONTEXT_GAPS))
    parser.add_argument("--evidence-jsonl", default=str(DEFAULT_EVIDENCE_JSONL))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    evidence_path = Path(args.evidence_jsonl)
    report_path = Path(args.report)
    if not safe_state_path(evidence_path) or not safe_state_path(report_path):
        print(json.dumps({"status": "blocked", "blocking_reasons": ["unsafe_output_path"]}, ensure_ascii=False))
        return 2
    report = build_live_evidence(
        scan_state=load_json(Path(args.scan_state), {}) or {},
        prices=load_json(Path(args.prices), {}) or {},
        portfolio=load_json(Path(args.portfolio), {}) or {},
        option_risk=load_json(Path(args.option_risk), {}) or {},
        sec_discovery=load_json(Path(args.sec_discovery), {}) or {},
        sec_semantics=load_json(Path(args.sec_semantics), {}) or {},
        broad_market=load_json(Path(args.broad_market), {}) or {},
        options_flow=load_json(Path(args.options_flow), {}) or {},
        source_atoms=load_jsonl(Path(args.source_atoms)),
        claim_graph=load_json(Path(args.claim_graph), {}) or {},
        context_gaps=load_json(Path(args.context_gaps), {}) or {},
        limit=args.limit,
    )
    atomic_write_jsonl(evidence_path, report["evidence_records"])
    report["evidence_jsonl_path"] = str(evidence_path)
    atomic_write_json(report_path, report)
    print(json.dumps({
        "status": report["status"],
        "candidate_count": report["candidate_count"],
        "evidence_count": report["evidence_count"],
        "quarantine_count": report["quarantine_count"],
        "report_path": str(report_path),
        "evidence_jsonl_path": str(evidence_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
