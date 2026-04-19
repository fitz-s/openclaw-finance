#!/usr/bin/env python3
"""Export sanitized recent finance report packets for remote reviewers.

Live finance reports and Discord follow-up registries are intentionally ignored
under state/. This exporter creates bounded, sanitized packets that let remote
reviewers inspect report quality and information acquisition coverage without
committing Discord conversations, thread ids, portfolio state, account ids, or
raw licensed snippets.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
WORKSPACE = OPENCLAW_HOME / 'workspace'
STATE = FINANCE / 'state'
DEFAULT_OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'reviewer-packets'
DEFAULT_SOURCE_HEALTH = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'source-health.json'
ARCHIVE_ROOT_NAME = 'report-archive'
DECISION_LOG = WORKSPACE / 'decisions' / 'state' / 'finance-decision-log.jsonl'

SAFE_TEXT_LIMIT = 240
TOP_OBJECT_LIMIT = 12
TOP_CAMPAIGN_LIMIT = 8
TOP_SOURCE_ATOM_LIMIT = 20
TOP_CLAIM_LIMIT = 20
TOP_GAP_LIMIT = 20


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(FINANCE))
    except ValueError:
        return sanitize_path_text(path)


def safe_text(value: Any, limit: int = SAFE_TEXT_LIMIT) -> str:
    text = ' '.join(str(value or '').replace('\n', ' ').split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + '…'


def sanitize_path_text(value: Any) -> str:
    text = str(value or '')
    replacements = {
        str(FINANCE): '<finance>',
        str(WORKSPACE): '<workspace>',
        str(OPENCLAW_HOME): '<openclaw>',
    }
    for needle, repl in replacements.items():
        text = text.replace(needle, repl)
    return text


def recent_report_paths(reader_dir: Path, limit: int) -> list[Path]:
    paths = sorted(
        [path for path in reader_dir.glob('*.json') if path.name != 'latest.json'],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        report_id = path.stem
        if report_id in seen:
            continue
        seen.add(report_id)
        result.append(path)
        if len(result) >= limit:
            break
    return result


def load_decision_entries(path: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict):
            continue
        report_id = str(entry.get('report_id') or '').strip()
        if report_id:
            entries[report_id] = entry
    return entries


def sanitize_decision_entry(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {'available': False}
    return {
        'available': True,
        'created_at': entry.get('created_at'),
        'decision_id': entry.get('decision_id'),
        'report_id': entry.get('report_id'),
        'operator_action': entry.get('operator_action'),
        'execution_decision': entry.get('execution_decision'),
        'judgment_id': entry.get('judgment_id'),
        'policy_version': entry.get('policy_version'),
        'wake_class': (entry.get('wake_threshold_attribution') or {}).get('wake_class') if isinstance(entry.get('wake_threshold_attribution'), dict) else None,
        'wake_dispatch_action': (entry.get('wake_threshold_attribution') or {}).get('wake_dispatch_action') if isinstance(entry.get('wake_threshold_attribution'), dict) else None,
        'ref_counts': {
            'thesis_refs': len(entry.get('thesis_refs') or []),
            'scenario_refs': len(entry.get('scenario_refs') or []),
            'opportunity_candidate_refs': len(entry.get('opportunity_candidate_refs') or []),
            'invalidator_refs': len(entry.get('invalidator_refs') or []),
            'capital_agenda_refs': len(entry.get('capital_agenda_refs') or []),
            'displacement_case_refs': len(entry.get('displacement_case_refs') or []),
        },
        'hashes_present': {
            'discord_primary_hash': bool(entry.get('discord_primary_hash')),
            'thread_seed_hash': bool(entry.get('thread_seed_hash')),
            'campaign_live_board_hash': bool(entry.get('campaign_live_board_hash')),
            'campaign_scout_board_hash': bool(entry.get('campaign_scout_board_hash')),
            'campaign_risk_board_hash': bool(entry.get('campaign_risk_board_hash')),
        },
    }


def sanitize_object_card(card: dict[str, Any]) -> dict[str, Any]:
    keep = {
        'handle',
        'type',
        'agenda_type',
        'label',
        'instrument',
        'theme',
        'status',
        'maturity',
        'priority_score',
        'score',
        'role_text',
        'operator_summary',
        'attention_justification',
        'positive_for',
        'not_positive_for',
        'source_freshness',
    }
    out = {key: card.get(key) for key in keep if key in card and card.get(key) not in (None, '', [])}
    for key in ['required_questions', 'confirmation_needed', 'required_confirmations', 'related_opportunities', 'source_refs']:
        value = card.get(key)
        if isinstance(value, list):
            out[key] = [safe_text(item) for item in value[:6]]
    for key in ['description', 'summary']:
        if key in card:
            out[f'{key}_preview'] = safe_text(card.get(key))
    return out


def sanitize_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    keep = {
        'campaign_id',
        'campaign_type',
        'board_class',
        'stage',
        'human_title',
        'priority_score',
        'why_now_delta',
        'why_not_now',
        'capital_relevance',
        'source_freshness_summary',
        'contradiction_summary',
        'directional_implication',
        'top_known_unknown',
        'thread_key',
    }
    out = {key: campaign.get(key) for key in keep if key in campaign and campaign.get(key) not in (None, '', [])}
    for key in ['confirmations_needed', 'kill_switches', 'known_unknowns', 'source_refs']:
        value = campaign.get(key)
        if isinstance(value, list):
            out[key] = [safe_text(item if not isinstance(item, dict) else item.get('why_load_bearing') or item.get('subject') or item) for item in value[:6]]
    return out


def sanitize_markdown(value: Any) -> str:
    text = sanitize_path_text(value)
    forbidden_tokens = ['accountId', 'acctAlias', 'Flex XML', 'packet_hash', 'graph_hash']
    for token in forbidden_tokens:
        text = text.replace(token, f'<redacted:{token}>')
    return text.strip()


def report_operator_surface(report_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
    if envelope.get('report_id') == report_id:
        return {
            'operator_surface_available': True,
            'surface_source': 'state/finance-decision-report-envelope.json',
            'discord_primary_markdown': sanitize_markdown(envelope.get('discord_primary_markdown')),
            'discord_thread_seed_markdown': sanitize_markdown(envelope.get('discord_thread_seed_markdown')),
            'discord_live_board_markdown': sanitize_markdown(envelope.get('discord_live_board_markdown')),
            'discord_scout_board_markdown': sanitize_markdown(envelope.get('discord_scout_board_markdown')),
            'discord_risk_board_markdown': sanitize_markdown(envelope.get('discord_risk_board_markdown')),
        }
    return {
        'operator_surface_available': False,
        'surface_source': 'reader-bundle-derived-summary',
        'reason': 'Historical per-report Discord primary markdown was not archived before reviewer packet export.',
    }


def archive_manifest_for(state_dir: Path, report_id: str) -> dict[str, Any] | None:
    manifest = state_dir / ARCHIVE_ROOT_NAME / report_id / 'manifest.json'
    payload = load_json(manifest, None)
    return payload if isinstance(payload, dict) else None


def archive_artifact_json(manifest: dict[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(manifest, dict):
        return default
    artifact = (manifest.get('artifacts') or {}).get(key) if isinstance(manifest.get('artifacts'), dict) else None
    if not isinstance(artifact, dict) or not artifact.get('available'):
        return default
    path = Path(str(artifact.get('path') or ''))
    return load_json(path, default)


def archive_replay_summary(manifest: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {
            'exact_replay_available': False,
            'archive_manifest_available': False,
            'reason': 'No report-time archive manifest for this report.',
        }
    artifacts = manifest.get('artifacts') if isinstance(manifest.get('artifacts'), dict) else {}
    line_refs = archive_artifact_json(manifest, 'line_to_claim_refs', {}) or {}
    return {
        'exact_replay_available': bool(manifest.get('exact_replay_available')),
        'archive_manifest_available': True,
        'archive_contract': manifest.get('contract'),
        'missing_required_artifacts': manifest.get('missing_required_artifacts') or [],
        'artifact_availability': {
            key: bool(value.get('available')) for key, value in artifacts.items() if isinstance(value, dict)
        },
        'line_to_claim_refs': {
            'available': bool(line_refs),
            'line_count': line_refs.get('line_count'),
            'matched_line_count': line_refs.get('matched_line_count'),
            'match_method': 'heuristic_subject_match',
        },
    }


def report_packet(
    bundle_path: Path,
    *,
    envelope: dict[str, Any],
    decision_entries: dict[str, dict[str, Any]],
    info_snapshot: dict[str, Any],
    state_dir: Path = STATE,
) -> dict[str, Any]:
    bundle = load_json(bundle_path, {}) or {}
    report_id = str(bundle.get('report_handle') or bundle_path.stem)
    archive_manifest = archive_manifest_for(state_dir, report_id)
    archived_bundle = archive_artifact_json(archive_manifest, 'reader_bundle', None)
    if isinstance(archived_bundle, dict):
        bundle = archived_bundle
    archived_envelope = archive_artifact_json(archive_manifest, 'envelope', None)
    operator_envelope = archived_envelope if isinstance(archived_envelope, dict) else envelope
    archived_info = information_acquisition_snapshot_from_archive(archive_manifest)
    effective_info = archived_info if archived_info is not None else info_snapshot
    cards = [card for card in bundle.get('object_cards', []) if isinstance(card, dict)]
    campaigns = [campaign for campaign in bundle.get('campaigns', []) if isinstance(campaign, dict)]
    replay = archive_replay_summary(archive_manifest)
    return {
        'generated_at': now_iso(),
        'contract': 'finance-reviewer-report-packet-v1',
        'report_id': report_id,
        'source_file': sanitize_path_text(bundle_path),
        'sanitization': {
            'discord_conversation_included': False,
            'discord_thread_ids_included': False,
            'account_ids_included': False,
            'portfolio_raw_state_included': False,
            'raw_licensed_snippets_included': False,
        },
        'report_time_replay': replay,
        'operator_surface': report_operator_surface(report_id, operator_envelope),
        'bundle_summary': {
            'bundle_id': bundle.get('bundle_id'),
            'generated_at': bundle.get('generated_at'),
            'report_hash_present': bool(bundle.get('report_hash')),
            'object_card_count': len(cards),
            'campaign_count': len(campaigns),
            'starter_queries': [safe_text(item) for item in (bundle.get('starter_queries') or [])[:12]],
            'followup_digest': [safe_text(item, 500) for item in (bundle.get('followup_digest') or [])[:8]],
            'object_alias_map_sample': {
                str(key): safe_text(value)
                for key, value in list((bundle.get('object_alias_map') or {}).items())[:24]
            },
        },
        'decision_log_summary': sanitize_decision_entry(decision_entries.get(report_id)),
        'top_object_cards': [sanitize_object_card(card) for card in cards[:TOP_OBJECT_LIMIT]],
        'top_campaigns': [sanitize_campaign(campaign) for campaign in campaigns[:TOP_CAMPAIGN_LIMIT]],
        'information_acquisition_snapshot': effective_info,
        'reviewer_notes': [
            'This packet is for report quality review, not for trading or execution.',
            'Uses report-time archive when available; otherwise falls back to current sanitized finance/OpenClaw source state.',
            'Raw Discord user messages and thread registry are intentionally excluded.',
        ],
        'no_execution': True,
    }


def sanitize_source_health(source_health: dict[str, Any]) -> dict[str, Any]:
    sources = source_health.get('sources') if isinstance(source_health.get('sources'), list) else []
    return {
        'available': bool(source_health),
        'generated_at': source_health.get('generated_at'),
        'status': source_health.get('status'),
        'source_count': source_health.get('source_count') or len(sources),
        'summary': source_health.get('summary') if isinstance(source_health.get('summary'), dict) else {},
        'sources': [
            {
                'source_id': source.get('source_id'),
                'freshness_status': source.get('freshness_status'),
                'latency_status': source.get('latency_status'),
                'schema_status': source.get('schema_status'),
                'validation_status': source.get('validation_status'),
                'rights_status': source.get('rights_status'),
                'coverage_status': source.get('coverage_status'),
                'breach_reasons': source.get('breach_reasons') or [],
                'last_seen_at_present': bool(source.get('last_seen_at')),
                'last_success_at_present': bool(source.get('last_success_at')),
            }
            for source in sources[:20] if isinstance(source, dict)
        ],
    }


def sanitize_atom(atom: dict[str, Any]) -> dict[str, Any]:
    compliance_class = str(atom.get('compliance_class') or 'unknown')
    return {
        'atom_id': atom.get('atom_id'),
        'source_id': atom.get('source_id'),
        'source_class': atom.get('source_class'),
        'source_lane': atom.get('source_lane'),
        'candidate_type': atom.get('candidate_type'),
        'discovery_scope': atom.get('discovery_scope'),
        'published_at': atom.get('published_at'),
        'observed_at': atom.get('observed_at'),
        'ingested_at': atom.get('ingested_at'),
        'event_time': atom.get('event_time'),
        'symbol_candidates': atom.get('symbol_candidates') or [],
        'freshness_budget_seconds': atom.get('freshness_budget_seconds'),
        'reliability_score': atom.get('reliability_score'),
        'uniqueness_score': atom.get('uniqueness_score'),
        'compliance_class': compliance_class,
        'raw_ref': atom.get('raw_ref'),
        'point_in_time_hash_present': bool(atom.get('point_in_time_hash')),
        'raw_snippet_included': False,
        'raw_snippet_redaction_reason': 'Raw snippets are excluded from reviewer packets, especially for licensed/restricted sources.',
    }


def sanitize_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        'claim_id': claim.get('claim_id'),
        'atom_id': claim.get('atom_id'),
        'subject': claim.get('subject'),
        'predicate': claim.get('predicate'),
        'direction': claim.get('direction'),
        'horizon': claim.get('horizon'),
        'certainty': claim.get('certainty'),
        'event_class': claim.get('event_class'),
        'source_lane': claim.get('source_lane'),
        'why_it_matters_tags': claim.get('why_it_matters_tags') or [],
        'capital_relevance_tags': claim.get('capital_relevance_tags') or [],
        'supports_count': len(claim.get('supports') or []),
        'contradicts_count': len(claim.get('contradicts') or []),
        'object_preview': safe_text(claim.get('object')),
    }


def sanitize_gap(gap: dict[str, Any]) -> dict[str, Any]:
    return {
        'gap_id': gap.get('gap_id'),
        'campaign_id': gap.get('campaign_id'),
        'claim_id': gap.get('claim_id'),
        'subject': gap.get('subject'),
        'missing_lane': gap.get('missing_lane'),
        'why_load_bearing': safe_text(gap.get('why_load_bearing')),
        'which_source_could_close_it': gap.get('which_source_could_close_it') or [],
        'cost_of_ignorance': gap.get('cost_of_ignorance'),
    }


def information_acquisition_snapshot(state_dir: Path, source_health_path: Path) -> dict[str, Any]:
    source_atoms = load_json(state_dir / 'source-atoms' / 'latest-report.json', {}) or {}
    claim_graph = load_json(state_dir / 'claim-graph.json', {}) or {}
    context_gaps = load_json(state_dir / 'context-gaps.json', {}) or {}
    source_health = load_json(source_health_path, {}) or {}
    atoms = [atom for atom in source_atoms.get('atoms', []) if isinstance(atom, dict)]
    claims = [claim for claim in claim_graph.get('claims', []) if isinstance(claim, dict)]
    gaps = [gap for gap in context_gaps.get('gaps', []) if isinstance(gap, dict)]
    return {
        'generated_at': now_iso(),
        'scope': 'current sanitized finance/source state; not exact per-report historical replay',
        'source_health': sanitize_source_health(source_health),
        'source_atom_summary': {
            'available': bool(source_atoms),
            'generated_at': source_atoms.get('generated_at'),
            'status': source_atoms.get('status'),
            'atom_count': source_atoms.get('atom_count') or len(atoms),
            'by_source_lane': dict(Counter(str(atom.get('source_lane') or 'unknown') for atom in atoms)),
            'by_compliance_class': dict(Counter(str(atom.get('compliance_class') or 'unknown') for atom in atoms)),
            'by_candidate_type': dict(Counter(str(atom.get('candidate_type') or 'unknown') for atom in atoms)),
            'atoms': [sanitize_atom(atom) for atom in atoms[:TOP_SOURCE_ATOM_LIMIT]],
        },
        'claim_graph_summary': {
            'available': bool(claim_graph),
            'generated_at': claim_graph.get('generated_at'),
            'status': claim_graph.get('status'),
            'claim_count': claim_graph.get('claim_count') or len(claims),
            'by_direction': dict(Counter(str(claim.get('direction') or 'unknown') for claim in claims)),
            'by_source_lane': dict(Counter(str(claim.get('source_lane') or 'unknown') for claim in claims)),
            'claims': [sanitize_claim(claim) for claim in claims[:TOP_CLAIM_LIMIT]],
        },
        'context_gap_summary': {
            'available': bool(context_gaps),
            'generated_at': context_gaps.get('generated_at'),
            'status': context_gaps.get('status'),
            'gap_count': context_gaps.get('gap_count') or len(gaps),
            'by_missing_lane': dict(Counter(str(gap.get('missing_lane') or 'unknown') for gap in gaps)),
            'gaps': [sanitize_gap(gap) for gap in gaps[:TOP_GAP_LIMIT]],
        },
        'known_limitations': [
            'OpenClaw parent-side raw web search logs, Discord logs, and cron run transcripts are not exported.',
            'Source registry/source health is exported as status metadata, not as raw vendor content.',
            'Historical per-report source atoms were not versioned before this packet export; this snapshot is current-state evidence coverage.',
        ],
    }


def information_acquisition_snapshot_from_archive(manifest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    source_atoms = archive_artifact_json(manifest, 'source_atoms', {}) or {}
    claim_graph = archive_artifact_json(manifest, 'claim_graph', {}) or {}
    context_gaps = archive_artifact_json(manifest, 'context_gaps', {}) or {}
    source_health = archive_artifact_json(manifest, 'source_health', {}) or {}
    options_iv = archive_artifact_json(manifest, 'options_iv_surface', {}) or {}
    atoms = [atom for atom in source_atoms.get('atoms', []) if isinstance(atom, dict)]
    claims = [claim for claim in claim_graph.get('claims', []) if isinstance(claim, dict)]
    gaps = [gap for gap in context_gaps.get('gaps', []) if isinstance(gap, dict)]
    snapshot = information_acquisition_snapshot(Path('/nonexistent'), Path('/nonexistent'))
    snapshot['scope'] = 'exact report-time archive snapshot'
    snapshot['source_health'] = sanitize_source_health(source_health)
    snapshot['source_atom_summary'].update({
        'available': bool(source_atoms),
        'generated_at': source_atoms.get('generated_at'),
        'status': source_atoms.get('status'),
        'atom_count': source_atoms.get('atom_count') or len(atoms),
        'by_source_lane': dict(Counter(str(atom.get('source_lane') or 'unknown') for atom in atoms)),
        'by_compliance_class': dict(Counter(str(atom.get('compliance_class') or 'unknown') for atom in atoms)),
        'by_candidate_type': dict(Counter(str(atom.get('candidate_type') or 'unknown') for atom in atoms)),
        'atoms': [sanitize_atom(atom) for atom in atoms[:TOP_SOURCE_ATOM_LIMIT]],
    })
    snapshot['claim_graph_summary'].update({
        'available': bool(claim_graph),
        'generated_at': claim_graph.get('generated_at'),
        'status': claim_graph.get('status'),
        'claim_count': claim_graph.get('claim_count') or len(claims),
        'by_direction': dict(Counter(str(claim.get('direction') or 'unknown') for claim in claims)),
        'by_source_lane': dict(Counter(str(claim.get('source_lane') or 'unknown') for claim in claims)),
        'claims': [sanitize_claim(claim) for claim in claims[:TOP_CLAIM_LIMIT]],
    })
    snapshot['context_gap_summary'].update({
        'available': bool(context_gaps),
        'generated_at': context_gaps.get('generated_at'),
        'status': context_gaps.get('status'),
        'gap_count': context_gaps.get('gap_count') or len(gaps),
        'by_missing_lane': dict(Counter(str(gap.get('missing_lane') or 'unknown') for gap in gaps)),
        'gaps': [sanitize_gap(gap) for gap in gaps[:TOP_GAP_LIMIT]],
    })
    snapshot['options_iv_surface_summary'] = {
        'available': bool(options_iv),
        'generated_at': options_iv.get('generated_at'),
        'status': options_iv.get('status'),
        'summary': options_iv.get('summary') if isinstance(options_iv.get('summary'), dict) else {},
    }
    snapshot['known_limitations'] = [
        'Snapshot came from local report-time archive when available.',
        'Raw snippets and Discord conversation remain excluded from reviewer packet.',
        'Line-to-claim refs are heuristic until renderer emits explicit bindings.',
    ]
    return snapshot


def markdown_index(packets: list[dict[str, Any]]) -> str:
    lines = [
        '# Finance Reviewer Report Packets',
        '',
        'Generated sanitized packets for recent finance reports.',
        '',
        'Boundary:',
        '- Includes operator/report summaries, bundle summaries, top objects/campaigns, and sanitized information acquisition metadata.',
        '- Excludes Discord user conversation, thread ids, account ids, raw portfolio state, secrets, and raw licensed snippets.',
        '- Information acquisition snapshot is current sanitized finance/OpenClaw source state, not exact historical replay for older reports.',
        '',
        'Reports:',
    ]
    for packet in packets:
        surface = packet.get('operator_surface', {})
        lines.append(
            f"- `{packet.get('report_id')}`: objects={packet.get('bundle_summary', {}).get('object_card_count')} "
            f"campaigns={packet.get('bundle_summary', {}).get('campaign_count')} "
            f"operator_surface_available={surface.get('operator_surface_available')}"
        )
    lines.append('')
    lines.append('Use the per-report JSON files for detailed review.')
    return '\n'.join(lines) + '\n'


def export_packets(
    *,
    state_dir: Path = STATE,
    out_dir: Path = DEFAULT_OUT,
    source_health_path: Path = DEFAULT_SOURCE_HEALTH,
    limit: int = 5,
) -> dict[str, Any]:
    reader_dir = state_dir / 'report-reader'
    report_paths = recent_report_paths(reader_dir, limit)
    envelope = load_json(state_dir / 'finance-decision-report-envelope.json', {}) or {}
    decision_entries = load_decision_entries(DECISION_LOG)
    info_snapshot = information_acquisition_snapshot(state_dir, source_health_path)
    packets = [
        report_packet(path, envelope=envelope, decision_entries=decision_entries, info_snapshot=info_snapshot, state_dir=state_dir)
        for path in report_paths
    ]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for packet in packets:
        path = out_dir / f"{packet['report_id']}.json"
        write_json(path, packet)
        written.append(display_path(path))
    index = {
        'generated_at': now_iso(),
        'contract': 'finance-reviewer-report-packet-index-v1',
        'packet_count': len(packets),
        'reports': [
            {
                'report_id': packet.get('report_id'),
                'file': f"{packet.get('report_id')}.json",
                'operator_surface_available': packet.get('operator_surface', {}).get('operator_surface_available'),
                'object_card_count': packet.get('bundle_summary', {}).get('object_card_count'),
                'campaign_count': packet.get('bundle_summary', {}).get('campaign_count'),
                'exact_replay_available': packet.get('report_time_replay', {}).get('exact_replay_available'),
            }
            for packet in packets
        ],
        'sanitization': {
            'discord_conversation_included': False,
            'discord_thread_ids_included': False,
            'raw_licensed_snippets_included': False,
            'account_ids_included': False,
        },
        'written_files': written,
    }
    write_json(out_dir / 'index.json', index)
    (out_dir / 'README.md').write_text(markdown_index(packets), encoding='utf-8')
    return {'status': 'pass', 'out_dir': str(out_dir), 'packet_count': len(packets), 'reports': [p.get('report_id') for p in packets]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export sanitized reviewer packets for recent finance reports.')
    parser.add_argument('--state-dir', default=str(STATE))
    parser.add_argument('--out-dir', default=str(DEFAULT_OUT))
    parser.add_argument('--source-health', default=str(DEFAULT_SOURCE_HEALTH))
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args(argv)
    result = export_packets(
        state_dir=Path(args.state_dir),
        out_dir=Path(args.out_dir),
        source_health_path=Path(args.source_health),
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
