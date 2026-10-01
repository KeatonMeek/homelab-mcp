"""Heuristic release checks. Manual privacy/security review is still required."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.ruff_cache'}
BAD_NAMES = {'credentials.json', 'settings.json', '.env', 'health.json', 'broker.sock'}
PATTERNS = [
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
]


def check(root=ROOT):
    errors = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in SKIP for part in relative.parts):
            continue
        if path.is_symlink():
            errors.append(f'{relative}: symlink not allowed in release artifact')
            continue
        if not path.is_file():
            continue
        if path.name in BAD_NAMES or path.suffix in {'.pem', '.key', '.p12', '.pfx', '.jsonl', '.log'}:
            errors.append(f'{relative}: runtime or credential-like file')
        if path.stat().st_size > 2_000_000:
            errors.append(f'{relative}: unexpectedly large file')
            continue
        text = path.read_text(errors='replace')
        # Only explicitly synthetic markers from the redaction regression test.
        if relative.as_posix() == 'tests/test_broker.py':
            text = text.replace('-----BEGIN ' + 'PRIVATE KEY-----', 'SYNTHETIC_TEST_MARKER')
        if any(pattern.search(text) for pattern in PATTERNS):
            errors.append(f'{relative}: possible embedded credential')
    return errors


if __name__ == '__main__':
    errors = check()
    for error in errors:
        print(error)
    if errors:
        sys.exit(1)
    print('Public tree heuristic checks passed; this is not a security certification.')
