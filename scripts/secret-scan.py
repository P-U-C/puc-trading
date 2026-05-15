#!/usr/bin/env python3
"""
Local secret + operator-identifier scan over the puc-trading working tree.

Exits 0 on clean, non-zero on any hit. Designed to run before commits and
before producing a review bundle. Mirrors the trend-corpus validator's
SECRET_PATTERNS plus a denylist for operator-specific identifiers (Telegram
chat_id, IBKR account numbers) and trade-action field names that must not
appear in any artifact intended for public review.

Run:
  python3 scripts/secret-scan.py [path]   # defaults to repo root
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (r"OPENAI_API_KEY\s*=\s*[\"'][^\"']+[\"']", "OPENAI_API_KEY assignment"),
    (r"ANTHROPIC_API_KEY\s*=\s*[\"'][^\"']+[\"']", "ANTHROPIC_API_KEY assignment"),
    (r"GITHUB_TOKEN\s*=\s*[\"'][^\"']+[\"']", "GITHUB_TOKEN assignment"),
    (r"TELEGRAM_BOT_TOKEN\s*=\s*[\"'][^\"']+[\"']", "TELEGRAM_BOT_TOKEN assignment"),
    (r"AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)\s*=\s*[\"'][^\"']+[\"']", "AWS key assignment"),
    (r"PRIVATE_KEY\s*=\s*[\"'][^\"']+[\"']", "PRIVATE_KEY assignment"),
    (r"MNEMONIC\s*=\s*[\"'][^\"']+[\"']", "MNEMONIC assignment"),
    (r"ghp_[A-Za-z0-9_]{20,}", "GitHub classic PAT"),
    (r"github_pat_[A-Za-z0-9_]{40,}", "GitHub fine-grained PAT"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style sk- token"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack-style token"),
    (r"-----BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----", "private key block"),
    (r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]", "generic api-key/secret assignment"),
]

OPERATOR_ID_PATTERNS = [
    (r"\b505841972\b", "Telegram chat_id 505841972 (operator)"),
    (r"\bU\d{8}\b", "IBKR account number pattern U\\d{8}"),
]

TRADE_ACTION_FIELDS = [
    "approved_for_private_execution",
    "place_order",
    "order_type",
    "limit_price",
    "account_id",
]

TRADE_ACTION_FIELD_PATTERN = re.compile(
    r"(?:^|[\s,{\"'])(" + "|".join(re.escape(f) for f in TRADE_ACTION_FIELDS) + r")[\"']?\s*[:=]"
)

EXCLUDED_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
EXCLUDED_FILES = {
    "secret-scan.py",                       # this file documents the patterns
    "REVIEWER_ACCESS.md",                   # documents what gets scrubbed
    ".env.example",                         # placeholder values are intentionally not real
    "deploy-scanner-results.test.sh",       # injects a fake sk- key to test the deploy script's own secret-rejection path
}
EXCLUDED_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".db", ".sqlite"}


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            if name in EXCLUDED_FILES:
                continue
            path = Path(dirpath) / name
            if path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            yield path


def scan_file(path: Path, root: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rel = path.relative_to(root)
    findings: list[str] = []
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            findings.append(f"{rel}: SECRET -- {label}")
    for pattern, label in OPERATOR_ID_PATTERNS:
        if re.search(pattern, text):
            findings.append(f"{rel}: OPERATOR-ID -- {label}")
    for m in TRADE_ACTION_FIELD_PATTERN.finditer(text):
        findings.append(f"{rel}: TRADE-ACTION-FIELD -- {m.group(1)}")
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    findings: list[str] = []
    for path in iter_files(root):
        findings.extend(scan_file(path, root))
    if findings:
        for f in findings:
            print(f)
        print(f"\n{len(findings)} finding(s)")
        return 1
    print("secret-scan: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
