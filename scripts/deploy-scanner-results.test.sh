#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/deploy-scanner-results.sh"
TMP_ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

write_convergence() {
  local path="$1"
  local generated_at
  generated_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  cat > "$path" <<JSON
{
  "schema_version": 1,
  "generated_at": "$generated_at",
  "generator": "test",
  "themes": [{"theme": "AI Infrastructure", "status": "growing"}],
  "scores": [
    {
      "ticker": "NVDA",
      "theme": "AI Infrastructure",
      "score": 0.8,
      "tier": "HIGH",
      "status": "growing"
    }
  ]
}
JSON
}

write_scan_results() {
  local path="$1"
  local scanned_at="${2:-$(date -u '+%Y-%m-%dT%H:%M:%SZ')}"
  cat > "$path" <<JSON
{
  "scan_meta": {
    "scanned_at": "$scanned_at",
    "tickers_scanned": 1,
    "contracts_fetched": 1,
    "contracts_passed": 1,
    "themes": {"AI Infrastructure": {"tickers": ["NVDA"], "contracts": 1}}
  },
  "results": [
    {
      "ticker": "NVDA",
      "theme": "AI Infrastructure",
      "strike": 100,
      "expiry": "20260619",
      "dte": 35,
      "otm_pct": 0.25,
      "ask": 1.2,
      "mid": 1.1,
      "iv": 0.5,
      "asymmetry_score": 1.76,
      "convergence": 0.8
    }
  ],
  "convergence": [
    {
      "ticker": "NVDA",
      "theme": "AI Infrastructure",
      "score": 0.8,
      "tier": "HIGH",
      "status": "growing"
    }
  ]
}
JSON
}

make_fixture() {
  local name="$1"
  local root="$TMP_ROOT/$name"
  local puc="$root/puc-trading"
  local pft="$root/pft-validator"

  mkdir -p "$puc/corpus" "$puc/scanner" "$puc/scripts" "$pft/scanner"
  cp "$SCRIPT_DIR/check-dashboard-shape.py" "$puc/scripts/check-dashboard-shape.py"
  cat > "$puc/Makefile" <<'MAKE'
.PHONY: validate
validate:
	python3 -m json.tool corpus/convergence-latest.json >/dev/null
MAKE
  write_convergence "$puc/corpus/convergence-latest.json"
  write_scan_results "$pft/scanner/scan-results.json"

  git -C "$pft" init -q
  git -C "$pft" config user.email "codex@example.invalid"
  git -C "$pft" config user.name "Codex Test"
  cat > "$pft/.gitignore" <<'EOF_GITIGNORE'
.keystone-api-key
EOF_GITIGNORE
  git -C "$pft" add scanner/scan-results.json .gitignore
  git -C "$pft" commit -q -m "initial"

  printf '%s\n%s\n' "$puc" "$pft"
}

run_deploy() {
  local puc="$1"
  local pft="$2"
  shift 2
  PUC_TRADING_DIR="$puc" PFT_VALIDATOR_DIR="$pft" RUN_FULL_SCAN=0 DEPLOY_PUSH=0 "$@" "$DEPLOY_SCRIPT"
}

test_artifact_invalid() {
  mapfile -t paths < <(make_fixture artifact-invalid)
  local puc="${paths[0]}" pft="${paths[1]}"
  printf '{not json}\n' > "$puc/corpus/convergence-latest.json"
  if run_deploy "$puc" "$pft" bash >/tmp/m5-artifact-invalid.out 2>&1; then
    cat /tmp/m5-artifact-invalid.out >&2
    fail "artifact-invalid path unexpectedly passed"
  fi
  grep -q "make validate failed" /tmp/m5-artifact-invalid.out || fail "artifact-invalid did not fail fast at validate"
  pass "artifact-invalid path"
}

test_stale_scan() {
  mapfile -t paths < <(make_fixture stale-scan)
  local puc="${paths[0]}" pft="${paths[1]}"
  write_scan_results "$pft/scanner/scan-results.json" "2000-01-01T00:00:00Z"
  touch -t 200001010000 "$pft/scanner/scan-results.json"
  if run_deploy "$puc" "$pft" bash >/tmp/m5-stale-scan.out 2>&1; then
    cat /tmp/m5-stale-scan.out >&2
    fail "stale-scan path unexpectedly passed"
  fi
  grep -q "scan freshness check failed" /tmp/m5-stale-scan.out || fail "stale-scan did not fail freshness check"
  pass "stale-scan path"
}

test_valid_no_push() {
  mapfile -t paths < <(make_fixture valid-no-push)
  local puc="${paths[0]}" pft="${paths[1]}"
  write_scan_results "$pft/scanner/scan-results.json"
  run_deploy "$puc" "$pft" bash >/tmp/m5-valid-no-push.out 2>&1
  grep -q "would push (DEPLOY_PUSH=1 to actually push)" /tmp/m5-valid-no-push.out || fail "valid path did not stay no-push"
  git -C "$pft" log --oneline -1 | grep -q "Update scanner results" || fail "valid path did not create commit"
  pass "valid path no-push"
}

test_secret_pattern() {
  mapfile -t paths < <(make_fixture secret-pattern)
  local puc="${paths[0]}" pft="${paths[1]}"
  write_scan_results "$pft/scanner/scan-results.json"
  python3 - "$pft/scanner/scan-results.json" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    payload = json.load(f)
payload["results"][0]["debug"] = "sk-fake12345678901234567890"
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f)
PY
  if run_deploy "$puc" "$pft" bash >/tmp/m5-secret-pattern.out 2>&1; then
    cat /tmp/m5-secret-pattern.out >&2
    fail "secret-pattern path unexpectedly passed"
  fi
  grep -q "secret-pattern scan failed" /tmp/m5-secret-pattern.out || fail "secret path did not fail secret scan"
  pass "secret-pattern path"
}

test_artifact_invalid
test_stale_scan
test_valid_no_push
test_secret_pattern

printf 'all deploy-scanner-results tests passed\n'
