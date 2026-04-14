#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, List, Optional

def atomic_write_json(path: Union[Path, str], data: Union[Dict, List], indent: int = 2):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def load_json_safe(path: Union[Path, str], default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ load_json_safe failed for {path}: {e}", file=sys.stderr)
        return default

def validate_json(path: Union[Path, str]):
    path = Path(path)
    if not path.exists():
        return False, f"File does not exist: {path}"
    try:
        json.loads(path.read_text())
        return True, 'Valid JSON'
    except json.JSONDecodeError as e:
        return False, f'Invalid JSON: {e}'
    except OSError as e:
        return False, f'Read error: {e}'

def repair_json(path: Union[Path, str]):
    path = Path(path)
    valid, msg = validate_json(path)
    if valid:
        return True, 'Already valid, no repair needed'
    text = path.read_text()
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = path.with_suffix(f'.broken-{ts}.json')
    shutil.copy2(path, backup)
    for end_pos in range(len(text), 0, -1):
        candidate = text[:end_pos].rstrip()
        try:
            data = json.loads(candidate)
            atomic_write_json(path, data)
            return True, f'Repaired by truncation at position {end_pos}. Backup: {backup}'
        except json.JSONDecodeError:
            continue
    return False, f'Could not repair. Broken file backed up to: {backup}'

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python3 atomic_io.py [validate|repair] <path>')
        sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == 'validate':
        ok, msg = validate_json(path)
        print(f"{'✅' if ok else '❌'} {msg}")
        sys.exit(0 if ok else 1)
    elif cmd == 'repair':
        ok, msg = repair_json(path)
        print(f"{'✅' if ok else '❌'} {msg}")
        sys.exit(0 if ok else 1)
    else:
        print(f'Unknown command: {cmd}')
        sys.exit(1)
