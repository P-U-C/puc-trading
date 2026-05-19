#!/usr/bin/env bash
set -euo pipefail

PUC_TRADING_DIR="${PUC_TRADING_DIR:-$HOME/puc-trading}"
PFT_VALIDATOR_DIR="${PFT_VALIDATOR_DIR:-$HOME/pft-validator}"
SCAN_RESULTS="$PFT_VALIDATOR_DIR/scanner/scan-results.json"
MAX_AGE_HOURS="${DEPLOY_MAX_SCAN_AGE_HOURS:-48}"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

ensure_gitignore() {
  local gitignore="$PFT_VALIDATOR_DIR/.gitignore"
  local patterns=(
    "jts.ini"
    "launcher.log"
    "dgpdjeilgkccmlebkicghonjccocflnajmhbcnmh/"
    "__pycache__/"
    ".DS_Store"
  )

  touch "$gitignore"
  for pattern in "${patterns[@]}"; do
    if ! grep -Fxq "$pattern" "$gitignore"; then
      printf '%s\n' "$pattern" >> "$gitignore"
      log "added .gitignore pattern: $pattern"
    fi
  done
}

validate_scan_json() {
  python3 - "$SCAN_RESULTS" "$MAX_AGE_HOURS" <<'PY'
import json
import sys
from datetime import datetime, timezone, timedelta

path = sys.argv[1]
max_age_hours = float(sys.argv[2])

try:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
except Exception as exc:
    raise SystemExit(f"{path}: invalid JSON: {exc}")

if not isinstance(payload, dict):
    raise SystemExit("scan-results root must be an object")

missing = [key for key in ("scan_meta", "results", "convergence") if key not in payload]
if missing:
    raise SystemExit("scan-results missing top-level keys: " + ", ".join(missing))

scan_meta = payload["scan_meta"]
if not isinstance(scan_meta, dict):
    raise SystemExit("scan_meta must be an object")

scanned_at_raw = scan_meta.get("scanned_at")
if not isinstance(scanned_at_raw, str) or not scanned_at_raw:
    raise SystemExit("scan_meta.scanned_at must be a non-empty string")

normalized = scanned_at_raw.replace("Z", "+00:00")
if normalized.endswith(" UTC"):
    normalized = normalized[:-4] + "+00:00"
try:
    scanned_at = datetime.fromisoformat(normalized)
except ValueError as exc:
    raise SystemExit(f"scan_meta.scanned_at is not ISO 8601 parseable: {scanned_at_raw}") from exc

if scanned_at.tzinfo is None:
    scanned_at = scanned_at.replace(tzinfo=timezone.utc)
scanned_at = scanned_at.astimezone(timezone.utc)

age = datetime.now(timezone.utc) - scanned_at
if age > timedelta(hours=max_age_hours):
    raise SystemExit(
        f"scan-results stale: age_hours={age.total_seconds() / 3600:.2f} "
        f"threshold_hours={max_age_hours:g}"
    )

if not isinstance(payload["results"], list):
    raise SystemExit("results must be a list")
if not isinstance(payload["convergence"], list):
    raise SystemExit("convergence must be a list")

print(scanned_at.isoformat())
PY
}

run_secret_scan() {
  local staged
  staged="$(git diff --cached --name-only -- scanner/scan-results.json .gitignore)"
  if [[ -z "$staged" ]]; then
    return 0
  fi

  STAGED_FILES="$staged" python3 - <<'PY'
import os
import re
import sys
from pathlib import Path

patterns = [
    r"OPENAI_API_KEY",
    r"ANTHROPIC_API_KEY",
    r"GITHUB_TOKEN",
    r"TELEGRAM_BOT_TOKEN",
    r"AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)",
    r"IBKR",
    r"PRIVATE_KEY",
    r"MNEMONIC",
    r"ghp_[A-Za-z0-9_]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"sk-[A-Za-z0-9]{20,}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"-----BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----",
    r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]",
]
compiled = [re.compile(pattern) for pattern in patterns]
findings = []

for rel in os.environ["STAGED_FILES"].splitlines():
    path = Path(rel)
    if not path.exists() or not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern in compiled:
        if pattern.search(text):
            findings.append(f"{rel}: matched secret pattern")
            break

if findings:
    print("secret scan failed over staged files:", file=sys.stderr)
    for finding in findings:
        print(finding, file=sys.stderr)
    raise SystemExit(1)
PY
}

log "validating convergence artifact via make validate"
(cd "$PUC_TRADING_DIR" && make validate) || fail "make validate failed"

if [[ "${RUN_FULL_SCAN:-0}" == "1" ]]; then
  log "RUN_FULL_SCAN=1; running scanner"
  (cd "$PUC_TRADING_DIR" && python3 scanner/run_live_scan.py)
else
  log "RUN_FULL_SCAN not set; publish-only mode"
fi

[[ -f "$SCAN_RESULTS" ]] || fail "missing scan results: $SCAN_RESULTS"

log "merging paper-book + live-book into scan-results"
SCAN_RESULTS_PATH="$SCAN_RESULTS" PUC_TRADING_DIR="$PUC_TRADING_DIR" \
  python3 "$PUC_TRADING_DIR/scripts/merge-book-into-scan.py" \
  || fail "book merge failed"

log "checking dashboard JSON shape"
SCAN_RESULTS_PATH="$SCAN_RESULTS" python3 "$PUC_TRADING_DIR/scripts/check-dashboard-shape.py" \
  || fail "dashboard shape check failed"

log "checking scan freshness"
SCAN_TS="$(validate_scan_json)" || fail "scan freshness check failed"
log "scan timestamp: $SCAN_TS"

log "ensuring pft-validator ignore patterns"
ensure_gitignore

cd "$PFT_VALIDATOR_DIR"
git add scanner/scan-results.json .gitignore

if git diff --cached --quiet -- scanner/scan-results.json .gitignore; then
  log "nothing to publish"
  exit 0
fi

log "scanning staged files for secrets"
run_secret_scan || fail "secret-pattern scan failed"

COMMIT_TS="$(printf '%s' "$SCAN_TS" | tr ':' '-')"
log "committing scan results"
git commit -m "Update scanner results ${COMMIT_TS}"

if [[ "${DEPLOY_PUSH:-0}" == "1" ]]; then
  log "DEPLOY_PUSH=1; pushing pft-validator"
  git push
else
  log "would push (DEPLOY_PUSH=1 to actually push)"
fi

