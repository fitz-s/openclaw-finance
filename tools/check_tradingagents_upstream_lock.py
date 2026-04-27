#!/usr/bin/env python3
"""Check the pinned TradingAgents submodule against the recorded lock."""
from __future__ import annotations

import ast
import json
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
LOCK = FINANCE / 'ops' / 'tradingagents-upstream-lock.json'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'tradingagents-upstream-lock-check.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def run_git(args: list[str], cwd: Path = FINANCE) -> tuple[int, str, str]:
    proc = subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, text=True, timeout=20)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''


def class_has_method(path: Path, class_name: str, method_name: str) -> bool:
    if not path.exists():
        return False
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(isinstance(item, ast.FunctionDef) and item.name == method_name for item in node.body)
    return False


def default_config_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if 'DEFAULT_CONFIG' in targets and isinstance(node.value, ast.Dict):
                keys: set[str] = set()
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys.add(key.value)
                return keys
    return set()


def pyproject_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding='utf-8'))


def build_report(write: bool = False) -> dict[str, Any]:
    lock = load_json(LOCK)
    submodule = FINANCE / lock['submodule_path']
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: dict[str, bool] = {}

    def check(code: str, ok: bool, message: str, *, warning: bool = False) -> None:
        checks[code] = ok
        if ok:
            return
        item = {'code': code, 'message': message}
        if warning:
            warnings.append(item)
        else:
            errors.append(item)

    check('lock:exists', LOCK.exists(), str(LOCK))
    check('gitmodules:exists', (FINANCE / '.gitmodules').exists(), '.gitmodules missing')
    gitmodules = read(FINANCE / '.gitmodules')
    check('gitmodules:url', lock['repo_url'] in gitmodules, 'submodule URL mismatch')
    check('submodule:path_exists', submodule.exists(), str(submodule))

    rc, head, stderr = run_git(['-C', str(submodule), 'rev-parse', 'HEAD'])
    check('submodule:head', rc == 0 and head == lock['locked_commit'], stderr or f'HEAD {head} != lock {lock["locked_commit"]}')

    rc, tag, stderr = run_git(['-C', str(submodule), 'describe', '--tags', '--exact-match'])
    check('submodule:tag', rc == 0 and tag == lock['locked_tag'], stderr or f'tag {tag} != lock {lock["locked_tag"]}')

    rc, status, stderr = run_git(['-C', str(submodule), 'status', '--short'])
    check('submodule:clean', rc == 0 and not status, stderr or status)

    pyproject = pyproject_data(submodule / 'pyproject.toml')
    project = pyproject.get('project') if isinstance(pyproject.get('project'), dict) else {}
    scripts = project.get('scripts') if isinstance(project.get('scripts'), dict) else {}
    expected_project = lock.get('expected_project', {})
    check('pyproject:name', project.get('name') == expected_project.get('name'), 'project.name mismatch')
    check('pyproject:version', project.get('version') == expected_project.get('version'), 'project.version mismatch')
    cli = lock['expected_cli_entrypoint']
    check('pyproject:cli_entrypoint', scripts.get(cli['script_name']) == cli['target'], 'CLI entrypoint mismatch')

    entry = lock['expected_python_entrypoint']
    graph_path = submodule / 'tradingagents' / 'graph' / 'trading_graph.py'
    check('entrypoint:class_method', class_has_method(graph_path, entry['class'], entry['method']), 'TradingAgentsGraph.propagate missing')

    config_path = submodule / 'tradingagents' / 'default_config.py'
    keys = default_config_keys(config_path)
    missing_keys = sorted(set(lock['expected_config_keys']) - keys)
    check('default_config:required_keys', not missing_keys, 'missing DEFAULT_CONFIG keys: ' + ', '.join(missing_keys))

    config_text = read(config_path)
    for env_key in lock.get('expected_env_keys', []):
        check(f'default_config:env:{env_key}', env_key in config_text, f'{env_key} not found in default_config')

    signal_text = read(submodule / 'tradingagents' / 'graph' / 'signal_processing.py')
    for signal in lock.get('expected_signal_values', []):
        check(f'signal:{signal}', signal in signal_text, f'{signal} not found in signal processing')

    trader_text = read(submodule / 'tradingagents' / 'agents' / 'trader' / 'trader.py')
    check('trader:transaction_proposal_language', 'FINAL TRANSACTION PROPOSAL' in trader_text, 'expected transaction proposal language missing', warning=True)

    policy = lock.get('openclaw_policy', {})
    check('policy:no_execution', policy.get('no_execution') is True and policy.get('execution_allowed') is False, 'lock policy must forbid execution')
    check('policy:no_runtime_import', policy.get('runtime_import_allowed') is False, 'P1 lock must not allow runtime import')

    report = {
        'generated_at': now_iso(),
        'contract': 'tradingagents-upstream-lock-check-v1',
        'status': 'pass' if not errors else 'fail',
        'lock_path': str(LOCK),
        'submodule_path': str(submodule),
        'locked_tag': lock.get('locked_tag'),
        'locked_commit': lock.get('locked_commit'),
        'observed_head': head,
        'observed_tag': tag,
        'checks': checks,
        'errors': errors,
        'warnings': warnings,
        'no_execution': True,
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


def main() -> int:
    report = build_report(write=True)
    print(json.dumps({'status': report['status'], 'error_count': len(report['errors']), 'out': str(OUT)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
