# Finance BOOT Renderer Compatibility Hotfix — 20260418T1402Z

## Problem

Mars continued sending BOOT alerts that referenced the retired renderer-authority cutover path:

- `finance_renderer_authority_committed_evidence.py`
- `finance_renderer_authority_post_apply_verify.py`
- `finance_mainline_cutover_status.py`
- `finance_mainline_cutover_review_check.py`

Those scripts were still judging the old `finance-report-renderer` shadow prompt shape, even though user-visible finance delivery had moved to deterministic stdout via `finance_discord_report_job.py`.

## Live Runtime Changes

Updated parent workspace files outside this repo:

- `/Users/leofitz/.openclaw/workspace/BOOT.md`
- `/Users/leofitz/.openclaw/workspace/skills/market-judgment/SKILL.md`
- `/Users/leofitz/.openclaw/workspace/ops/scripts/finance_ideal_architecture_audit.py`
- `/Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py`
- `/Users/leofitz/.openclaw/workspace/ops/scripts/finance_renderer_authority_committed_evidence.py`
- `/Users/leofitz/.openclaw/workspace/ops/scripts/finance_renderer_authority_post_apply_verify.py`
- `/Users/leofitz/.openclaw/workspace/ops/tests/test_finance_openclaw_embedded_audit.py`
- `/Users/leofitz/.openclaw/workspace/ops/model-roles.json`

The old renderer scripts now pass as compatibility/retired checks under the deterministic finance report job architecture.

## Auth Noise Fix

`Provided authentication token is expired` was an OpenAI Codex OAuth/profile error, not a Discord token error. `auth-profiles.json` still contained expired `openai-codex:*` profiles and agent order overrides were `null`, so runtime could choose stale profiles.

Set per-agent `openai-codex` auth order to the valid default profile for:

- `main`
- `venus`
- `jupiter`
- `neptune`

## Verification

All pass:

```bash
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_ideal_architecture_audit.py
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_report_delivery_audit.py --max-age-minutes 1440
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_renderer_authority_committed_evidence.py
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_renderer_authority_post_apply_verify.py
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_mainline_cutover_status.py
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_mainline_cutover_review_check.py
python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_runtime_surface_contract.py
python3 -m pytest -q /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_renderer_authority_committed_evidence.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_renderer_authority_post_apply_verify.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_mainline_cutover_status.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_mainline_cutover_review_check.py /Users/leofitz/.openclaw/workspace/ops/tests/test_finance_openclaw_embedded_audit.py
```

## Residual Warnings

- `market-intel` MCP still reports `spawn python ENOENT`; this is separate from the finance renderer BOOT blocker and should be handled in a separate package.
- `minimax-portal/MiniMax-M2.7` timeout still appears in gateway logs; this is model/provider latency, not the expired OpenAI Codex token issue.
