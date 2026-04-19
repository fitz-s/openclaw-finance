#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from atomic_io import atomic_write_json, load_json_safe

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
BUFFER_DIR = FINANCE / 'buffer'
STATE_FILE = FINANCE / 'state' / 'intraday-open-scan-state.json'
ARCHIVE_DIR = FINANCE / 'buffer' / 'archive'
INVALID_DIR = FINANCE / 'buffer' / 'invalid'
REDUCER_REPORT = FINANCE / 'state' / 'finance-worker-reducer-report.json'
TZ_CHI = ZoneInfo('America/Chicago')
BUFFER_PARSE_GRACE_SECONDS = 120
MAX_OBSERVATION_AGE_HOURS = 36


def current_window(now_chicago: datetime) -> str:
    if now_chicago.weekday() >= 5:
        return 'weekend'
    hm = now_chicago.hour * 60 + now_chicago.minute
    if hm >= 19 * 60 or hm < 3 * 60 + 30:
        return 'overnight'
    if 3 * 60 + 30 <= hm < 8 * 60 + 30:
        return 'pre'
    if 8 * 60 + 30 <= hm < 11 * 60 + 30:
        return 'open'
    if 11 * 60 + 30 <= hm < 14 * 60:
        return 'mid'
    if 14 * 60 <= hm < 15 * 60:
        return 'late'
    return 'post'


def newest_observation_ts(accumulated: list) -> str | None:
    candidates = []
    for item in accumulated:
        if not isinstance(item, dict):
            continue
        ts = item.get('ts')
        if not isinstance(ts, str) or not ts:
            continue
        try:
            normalized = ts.replace('Z', '+00:00')
            datetime.fromisoformat(normalized)
        except Exception:
            continue
        candidates.append(ts)
    return max(candidates) if candidates else None


def newest_iso_ts(values: list[str | None]) -> str | None:
    candidates: list[tuple[datetime, str]] = []
    for value in values:
        parsed = parse_observation_ts(value)
        if parsed is not None and value:
            candidates.append((parsed, value))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def compact_seen_ids(values: list, limit: int = 200) -> list:
    """Return seen ids in stable observation order, capped to the newest entries."""
    ordered = []
    seen = set()
    for value in values if isinstance(values, list) else []:
        if value is None:
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered[-limit:]


def parse_observation_ts(value: str | None):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def load_buffer_payload(path: Path):
    raw = path.read_text()
    try:
        return json.loads(raw), None, False
    except Exception as exc:
        repaired = repair_common_llm_json_quoting(raw)
        if repaired != raw:
            try:
                return json.loads(repaired), None, True
            except Exception:
                pass
        return None, str(exc), False


def repair_common_llm_json_quoting(raw_text: str) -> str:
    """Best-effort repair for LLM-emitted JSON with unescaped quotes inside strings."""
    out = []
    in_string = False
    escape = False
    i = 0
    n = len(raw_text)
    while i < n:
        ch = raw_text[i]
        if ch == '"':
            if not in_string:
                in_string = True
                out.append(ch)
            elif escape:
                out.append(ch)
                escape = False
            else:
                j = i + 1
                while j < n and raw_text[j] in ' \t\r\n':
                    j += 1
                nxt = raw_text[j] if j < n else ''
                if nxt in {',', ':', '}', ']', ''}:
                    in_string = False
                    out.append(ch)
                else:
                    out.append('\\"')
            i += 1
            continue

        out.append(ch)
        if in_string:
            if ch == '\\' and not escape:
                escape = True
            else:
                escape = False
        i += 1
    return ''.join(out)


def should_quarantine_parse_error(path: Path, now_utc: datetime) -> bool:
    try:
        age_seconds = now_utc.timestamp() - path.stat().st_mtime
    except Exception:
        return True
    return age_seconds > BUFFER_PARSE_GRACE_SECONDS


def recover_valid_invalid_buffers(now_utc: datetime):
    recovered = []
    if not INVALID_DIR.exists():
        return recovered

    BUFFER_DIR.mkdir(parents=True, exist_ok=True)
    for candidate in sorted(INVALID_DIR.glob('*.json')):
        data, error, repaired = load_buffer_payload(candidate)
        if error:
            continue
        if not isinstance(data, dict):
            continue
        if not data.get('observations') and 'theme' not in data and not data.get('scan_time'):
            continue
        candidate_ts = parse_observation_ts(data.get('scan_time'))
        if candidate_ts is None and isinstance(data.get('observations'), list) and data['observations']:
            candidate_ts = parse_observation_ts(data['observations'][0].get('ts'))
        if candidate_ts is None:
            continue
        age_hours = (now_utc - candidate_ts).total_seconds() / 3600
        if age_hours > MAX_OBSERVATION_AGE_HOURS:
            continue
        target = BUFFER_DIR / candidate.name
        if target.exists():
            continue
        atomic_write_json(target, data)
        candidate.unlink()
        recovered.append(candidate.name)
    return recovered


def prune_stale_accumulated(accumulated: list, now_utc: datetime):
    kept = []
    pruned = 0
    for item in accumulated:
        if not isinstance(item, dict):
            pruned += 1
            continue
        ts = parse_observation_ts(item.get('ts'))
        if ts is None:
            kept.append(item)
            continue
        age_hours = (now_utc - ts).total_seconds() / 3600
        if age_hours > MAX_OBSERVATION_AGE_HOURS:
            pruned += 1
            continue
        kept.append(item)
    return kept, pruned


def write_shadow_source_atoms(state: dict, generated_at: str) -> dict | None:
    """Best-effort shadow write; never block scanner/gate behavior."""
    try:
        from source_atom_compiler import SOURCE_ATOMS_LATEST, compile_atoms, load_source_registry, write_atoms_jsonl

        report = compile_atoms(
            state,
            registry=load_source_registry(),
            generated_at=generated_at,
            scan_file=str(STATE_FILE),
        )
        write_atoms_jsonl(SOURCE_ATOMS_LATEST, report['atoms'])
        atomic_write_json(FINANCE / 'state' / 'source-atoms' / 'latest-report.json', report)
        return report
    except Exception as exc:
        print(f"⚠️ source atom shadow write skipped: {exc}", file=sys.stderr)
        return None


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def reduce_claims_to_legacy_observations(claim_graph: dict, context_gaps: dict, *, generated_at: str, limit: int = 12) -> list[dict]:
    """Project ClaimGraph rows into legacy observation shape for old consumers.

    These rows are a compatibility view. They are not canonical ingestion and
    should not be written into accumulated until the active cutover is explicit.
    """
    claims = [claim for claim in claim_graph.get('claims', []) if isinstance(claim, dict)]
    gaps = [gap for gap in context_gaps.get('gaps', []) if isinstance(gap, dict)]
    gaps_by_claim: dict[str, list[dict]] = {}
    for gap in gaps:
        for claim_id in gap.get('weak_claim_ids', []) if isinstance(gap.get('weak_claim_ids'), list) else [gap.get('claim_id')]:
            if claim_id:
                gaps_by_claim.setdefault(str(claim_id), []).append(gap)

    rows = []
    for claim in claims[:limit]:
        claim_id = str(claim.get('claim_id') or '')
        subject = str(claim.get('subject') or 'unknown')
        predicate = str(claim.get('predicate') or 'mentions')
        direction = str(claim.get('direction') or 'ambiguous')
        weak_gaps = gaps_by_claim.get(claim_id, [])
        gap_lanes = sorted({str(gap.get('missing_lane')) for gap in weak_gaps if gap.get('missing_lane')})
        urgency = 4.0 if weak_gaps else 3.0
        importance = 4.0 if claim.get('source_lane') in {'market_structure', 'corp_filing_ir'} else 3.0
        novelty = max(1.0, float(claim.get('source_uniqueness_score') or 0.4) * 5)
        rows.append({
            'id': f"claim-reducer:{claim_id}",
            'ts': generated_at,
            'theme': f"{subject} {predicate} ({direction})",
            'urgency': urgency,
            'importance': importance,
            'novelty': round(novelty, 2),
            'cumulative_value': 3.0,
            'summary': str(claim.get('object') or '')[:280],
            'sources': [claim.get('source_id')] if claim.get('source_id') else [],
            'candidate_type': 'claim_reducer_projection',
            'discovery_scope': 'claim_graph_projection',
            'object_links': {
                'claim_refs': [claim_id],
                'context_gap_refs': [gap.get('gap_id') for gap in weak_gaps if gap.get('gap_id')],
            },
            'confirmation_needed': gap_lanes,
            'legacy_bridge_only': True,
            'canonical_ingestion': False,
            'no_execution': True,
        })
    return rows


def write_shadow_claim_gap_reducer_report(generated_at: str) -> dict | None:
    """Compile ClaimGraph/ContextGap and a reducer report; never block worker."""
    try:
        from claim_graph_compiler import OUT as CLAIM_GRAPH_OUT, compile_claim_graph
        from context_gap_compiler import OUT as CONTEXT_GAPS_OUT, compile_context_gaps
        from source_atom_compiler import SOURCE_ATOMS_LATEST

        atoms = load_jsonl(SOURCE_ATOMS_LATEST)
        claim_graph = compile_claim_graph(atoms, generated_at=generated_at)
        atomic_write_json(CLAIM_GRAPH_OUT, claim_graph)
        context_gaps = compile_context_gaps(claim_graph, generated_at=generated_at)
        atomic_write_json(CONTEXT_GAPS_OUT, context_gaps)
        reduced = reduce_claims_to_legacy_observations(claim_graph, context_gaps, generated_at=generated_at)
        report = {
            'generated_at': generated_at,
            'status': 'pass',
            'contract': 'finance-worker-reducer-report-v1',
            'worker_role': 'compatibility_reducer',
            'migration_mode': 'legacy_and_shadow',
            'evaluation_mode': 'both',
            'idempotency_key': claim_graph.get('graph_hash'),
            'canonical_ingestion_authority': 'EvidenceAtom/ClaimGraph/ContextGap shadow substrate',
            'accumulated_authority': 'legacy_bridge_not_canonical_ingestion',
            'legacy_bridge_status': 'active_compatibility_output',
            'source_atom_count': len(atoms),
            'claim_count': claim_graph.get('claim_count', 0),
            'gap_count': context_gaps.get('gap_count', 0),
            'reduced_legacy_observation_count': len(reduced),
            'reduced_legacy_observation_preview': reduced[:5],
            'claim_graph_hash': claim_graph.get('graph_hash'),
            'context_gap_hash': context_gaps.get('context_gap_hash'),
            'parity_basis': 'legacy accumulated remains primary compatibility output; reduced observations are shadow comparison rows',
            'shadow_only': True,
            'no_execution': True,
        }
        atomic_write_json(REDUCER_REPORT, report)
        return report
    except Exception as exc:
        print(f"⚠️ claim/gap reducer shadow write skipped: {exc}", file=sys.stderr)
        return None

def main():
    now_utc = datetime.now(timezone.utc)
    now_chi = now_utc.astimezone(TZ_CHI)
    state = load_json_safe(STATE_FILE, {
        "seen_ids": [],
        "accumulated": [],
        "short_reports": [],
        "core_reports": []
    })

    seen_ids_ordered = compact_seen_ids(state.get('seen_ids', []))
    seen_ids = set(seen_ids_ordered)
    accumulated = state.get('accumulated', [])

    new_observations_count = 0
    unknown_discovery_exhausted_reasons: list[dict[str, str]] = []

    recovered_files = recover_valid_invalid_buffers(now_utc)

    # Process all JSON files in buffer
    if not BUFFER_DIR.exists():
        BUFFER_DIR.mkdir(parents=True, exist_ok=True)

    buffer_files = sorted(list(BUFFER_DIR.glob('*.json')))
    invalid_files = []
    successful_scan_times: list[str] = []

    for bf in buffer_files:
        if bf.name == 'subagent-bootstrap-test.json':
            continue

        data, error, repaired = load_buffer_payload(bf)
        if error:
            if not should_quarantine_parse_error(bf, now_utc):
                continue
            INVALID_DIR.mkdir(parents=True, exist_ok=True)
            os.rename(bf, INVALID_DIR / bf.name)
            invalid_files.append({
                'file': bf.name,
                'error': error,
            })
            continue

        if not data:
            continue

        if repaired:
            atomic_write_json(bf, data)

        if isinstance(data.get('scan_time'), str):
            successful_scan_times.append(data['scan_time'])
        if data.get('unknown_discovery_exhausted_reason'):
            unknown_discovery_exhausted_reasons.append({
                'file': bf.name,
                'reason': str(data.get('unknown_discovery_exhausted_reason'))[:500],
                'scan_time': str(data.get('scan_time') or ''),
            })

        obs = data.get('observations', [])
        if not obs and 'theme' in data: # Handle single observation format
            obs = [data]

        def remember_seen_id(obs_id: str) -> None:
            if obs_id not in seen_ids:
                seen_ids.add(obs_id)
                seen_ids_ordered.append(obs_id)

        for o in obs:
            obs_id = str(o.get('id') or o.get('ts') or bf.stem)
            if obs_id not in seen_ids:
                # Normalize observation — use float to preserve decay precision,
                # floor at 1 (below decay min_threshold=1.5 so low signals get pruned)
                normalized = {
                    "id": obs_id,
                    "ts": o.get('ts') or o.get('scan_time') or data.get('scan_time') or now_utc.isoformat(),
                    "theme": o.get('theme', 'Unknown'),
                    "urgency": max(float(o.get('urgency', 5)), 1),
                    "importance": max(float(o.get('importance', 5)), 1),
                    "novelty": max(float(o.get('novelty', 5)), 1),
                    "cumulative_value": max(float(o.get('cumulative_value') or o.get('cv') or 5), 1),
                    "summary": o.get('summary') or o.get('description', ''),
                    "sources": o.get('sources', [o.get('source', 'unknown')])
                }
                for optional_key in [
                    'candidate_type',
                    'discovery_scope',
                    'exploration_lane',
                    'tickers',
                    'non_watchlist_reason',
                    'object_links',
                    'supports',
                    'conflicts_with',
                    'confirmation_needed',
                    'unknown_discovery_exhausted_reason',
                ]:
                    if optional_key in o:
                        normalized[optional_key] = o.get(optional_key)
                # Semantic dedup: skip if theme is near-identical to an existing item
                theme_lower = normalized['theme'].lower().strip()
                is_dup = False
                for existing in accumulated:
                    if isinstance(existing, dict):
                        existing_theme = str(existing.get('theme', '')).lower().strip()
                    else:
                        # Backward compatibility: older state files may contain
                        # plain strings (for example buffer ids or theme labels).
                        existing_theme = str(existing).lower().strip()
                    if theme_lower == existing_theme:
                        is_dup = True
                        break
                    # Check if one is a substring of the other
                    if len(theme_lower) > 20 and len(existing_theme) > 20:
                        shorter, longer = sorted([theme_lower, existing_theme], key=len)
                        if shorter in longer:
                            is_dup = True
                            break
                    # Check high word overlap (catches "Brent $108" vs "Brent $108 (+5.66%)")
                    if len(theme_lower) > 15 and len(existing_theme) > 15:
                        words_a = set(theme_lower.split())
                        words_b = set(existing_theme.split())
                        if len(words_a) >= 4 and len(words_b) >= 4:
                            overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
                            if overlap > 0.7:
                                is_dup = True
                                break
                if is_dup:
                    remember_seen_id(obs_id)  # Mark as seen but don't accumulate
                    continue
                accumulated.append(normalized)
                remember_seen_id(obs_id)
                new_observations_count += 1

        # Archive processed buffer
        if not ARCHIVE_DIR.exists():
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        os.rename(bf, ARCHIVE_DIR / bf.name)

    # Limit accumulated size to avoid prompt bloat
    accumulated, pruned_count = prune_stale_accumulated(accumulated, now_utc)
    if len(accumulated) > 50:
        accumulated = accumulated[-50:]

    state['seen_ids'] = compact_seen_ids(seen_ids_ordered) # Keep recent history deterministically
    state['accumulated'] = accumulated
    state['date'] = now_chi.strftime('%Y-%m-%d')
    state['intraday_window'] = current_window(now_chi)
    state['last_updated'] = now_utc.isoformat()
    state['last_worker_run_at'] = now_utc.isoformat()
    state['worker_role'] = 'compatibility_reducer'
    state['accumulated_authority'] = 'legacy_bridge_not_canonical_ingestion'
    state['canonical_ingestion_authority'] = 'EvidenceAtom/ClaimGraph/ContextGap shadow substrate'
    state['invalid_buffer_files'] = invalid_files[-20:]
    state['recovered_invalid_buffer_files'] = recovered_files[-20:]
    state['stale_accumulated_pruned_count'] = pruned_count
    if unknown_discovery_exhausted_reasons:
        state['unknown_discovery_exhausted_reasons'] = (
            state.get('unknown_discovery_exhausted_reasons', [])[-20:]
            + unknown_discovery_exhausted_reasons
        )[-20:]

    latest_signal_ts = newest_observation_ts(accumulated)
    if latest_signal_ts:
        state['last_signal_ingest_time'] = latest_signal_ts
    else:
        state.setdefault('last_signal_ingest_time', None)

    latest_scan_ts = newest_iso_ts([*successful_scan_times, latest_signal_ts])
    if latest_scan_ts:
        state['last_scan_time'] = latest_scan_ts
    else:
        state.setdefault('last_scan_time', None)

    atomic_write_json(STATE_FILE, state)
    generated_at = now_utc.isoformat().replace('+00:00', 'Z')
    write_shadow_source_atoms(state, generated_at)
    write_shadow_claim_gap_reducer_report(generated_at)
    print(
        f"✅ Processed {len(buffer_files)} files. Added {new_observations_count} new observations. "
        f"Recovered invalid files: {len(recovered_files)}. Invalid files quarantined: {len(invalid_files)}."
    )

if __name__ == '__main__':
    main()
