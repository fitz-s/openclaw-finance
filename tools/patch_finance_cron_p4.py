#!/usr/bin/env python3
"""Patch active OpenClaw finance cron prompts to P4 deterministic wrappers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CRON = Path('/Users/leofitz/.openclaw/cron/jobs.json')
FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
PYTHON = Path('/opt/homebrew/bin/python3')


def scanner_prompt(mode: str) -> str:
    return f"""【OpenClaw Finance Deterministic Scanner Job】
Run exactly:
{PYTHON} {FINANCE}/scripts/finance_scanner_job.py --mode {mode}

Contract markers:
- finance_scanner_job.py runs finance_llm_context_pack.py, query_pack_planner.py, finance_worker.py, finance_parent_market_ingest_cutover.py, and gate_evaluator.py.
- Read-only scanner context is {FINANCE}/state/llm-job-context/scanner.json.
- Context pack is a view cache and must have pack_is_not_authority=true.
- QueryPack is not evidence; object_links and unknown_discovery_exhausted_reason remain required contract fields.
- unknown_discovery cannot be satisfied by held/watchlist tickers.
- unknown_discovery_minimum_attempts remains enforced by scanner.json/query_pack_planner.py.
- 不得把已在 watchlist/held 的标的当作 unknown_discovery。

Output discipline:
- Return stdout exactly.
- Do not summarize.
- Do not emit progress text.
- Do not send messages yourself; delivery.mode is none.
- No execution; review-only."""


def report_prompt(mode: str) -> str:
    return f"""【OpenClaw Finance Deterministic Report Job】
Run exactly:
{PYTHON} {FINANCE}/scripts/finance_discord_report_job.py --mode {mode}

Output discipline:
- Return stdout exactly.
- If stdout is NO_REPLY, return only NO_REPLY.
- Do not summarize.
- Do not emit progress text.
- Do not send messages yourself; OpenClaw delivery handles Discord.
- Review-only; no execution."""


def patch_jobs(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    changed: list[str] = []
    for job in payload.get('jobs', []) if isinstance(payload.get('jobs'), list) else []:
        if not isinstance(job, dict):
            continue
        name = job.get('name')
        jpayload = job.setdefault('payload', {})
        if not isinstance(jpayload, dict):
            continue
        if name == 'finance-subagent-scanner':
            jpayload['message'] = scanner_prompt('market-hours-scan')
            jpayload['lightContext'] = True
            jpayload['timeoutSeconds'] = 300
            job['timeout'] = 300
            changed.append(name)
        elif name == 'finance-subagent-scanner-offhours':
            jpayload['message'] = scanner_prompt('offhours-scan')
            jpayload['lightContext'] = True
            jpayload['timeoutSeconds'] = 300
            job['timeout'] = 300
            changed.append(name)
        elif name in {'finance-premarket-brief', 'finance-midday-operator-review', 'finance-premarket-delivery-watchdog'}:
            if name == 'finance-premarket-delivery-watchdog':
                mode = 'morning-watchdog'
            elif name == 'finance-midday-operator-review':
                mode = 'marketday-core-review'
            else:
                mode = 'marketday-review'
            jpayload['message'] = report_prompt(mode)
            jpayload['lightContext'] = True
            jpayload['timeoutSeconds'] = 420
            job['timeout'] = 420
            changed.append(name)
    return payload, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cron', default=str(CRON))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    path = Path(args.cron)
    payload = json.loads(path.read_text(encoding='utf-8'))
    patched, changed = patch_jobs(payload)
    if not args.dry_run:
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(json.dumps(patched, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(path)
    print(json.dumps({'status': 'pass', 'changed': changed, 'dry_run': args.dry_run, 'cron': str(path)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
