#!/usr/bin/env python3
"""IBKR session refresher.

Phone/TWS-priority default: the script is a no-op unless explicitly enabled.

Why: an IBKR username can have only one active brokerage session. A persistent
localhost keepalive competes with IBKR Mobile/TWS/browser trading sessions.
Use `--mode passive` to tickle only an already active localhost brokerage
session, or `--mode brokerage-claim` only during a deliberate short API window.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path('/Users/leofitz/.openclaw/workspace/ops/scripts')))
import ibkr_reader

LOG = Path('/Users/leofitz/.openclaw/logs/ibkr-tickle.log')
POLICY_FILE = Path('/Users/leofitz/.openclaw/workspace/finance/state/ibkr-session-policy.json')
DEFAULT_KEEPALIVE_MODE = os.environ.get('IBKR_KEEPALIVE_MODE', 'disabled')


def _log(message: str) -> None:
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(f"[{now}] {message}\n")


def load_policy() -> dict:
    if not POLICY_FILE.exists():
        return {}
    try:
        return json.loads(POLICY_FILE.read_text())
    except Exception:
        return {}


def resolve_mode(mode: str | None = None) -> tuple[str, dict]:
    policy = load_policy()
    resolved = mode or os.environ.get('IBKR_KEEPALIVE_MODE') or policy.get('keepalive_mode') or 'disabled'
    return str(resolved).strip().lower(), policy


def refresh_session(mode: str | None = None) -> bool:
    mode, policy = resolve_mode(mode)
    if mode in {'disabled', 'off', 'snapshot-only', 'snapshot_only'}:
        _log('SKIP: keepalive disabled for phone/TWS-priority snapshot-only mode')
        return True

    try:
        sso = ibkr_reader.validate_sso()
        auth = ibkr_reader.auth_status()
        sso_ok = bool(isinstance(sso, dict) and (sso.get('RESULT') is True or sso.get('authenticated') is True))
        auth_ok = bool(isinstance(auth, dict) and auth.get('authenticated'))
        username = sso.get('USER_NAME') if isinstance(sso, dict) else None
        expected_username = policy.get('expected_username')

        if not sso_ok:
            _log('FAIL: SSO invalid; user login required')
            print('IBKR SSO invalid; login required', file=sys.stderr)
            return False

        if expected_username and username != expected_username:
            _log(f'SKIP: logged-in username {username!r} does not match expected API username {expected_username!r}')
            print(f'IBKR username mismatch; expected {expected_username!r}, got {username!r}', file=sys.stderr)
            return False

        action = 'tickle'
        if not auth_ok:
            if mode not in {'brokerage-claim', 'claim'}:
                _log('SKIP: brokerage auth false; not claiming session in passive mode')
                print('IBKR brokerage session not authenticated; passive keepalive will not claim session', file=sys.stderr)
                return False
            ibkr_reader.init_brokerage_session()
            action = 'ssodh/init+tickle'

        tickle_result = ibkr_reader.tickle()
        auth_after = ibkr_reader.auth_status()
        auth_after_ok = bool(isinstance(auth_after, dict) and auth_after.get('authenticated'))

        session = tickle_result.get('session', '?') if isinstance(tickle_result, dict) else '?'
        _log(f"OK: action={action} mode={mode} user={username or '?'} auth={auth_after_ok} session={str(session)[:16]}...")

        if not auth_after_ok:
            print('IBKR brokerage session still not authenticated after refresh', file=sys.stderr)
            return False
        return True
    except Exception as exc:
        _log(f'FAIL: {str(exc)[:160]}')
        print(str(exc), file=sys.stderr)
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IBKR Client Portal keepalive.')
    parser.add_argument(
        '--mode',
        choices=['disabled', 'passive', 'brokerage-claim'],
        default=None,
        help='disabled=no-op; passive=tickle only active brokerage session; brokerage-claim=may call ssodh/init',
    )
    args = parser.parse_args()
    success = refresh_session(args.mode)
    sys.exit(0 if success else 1)
