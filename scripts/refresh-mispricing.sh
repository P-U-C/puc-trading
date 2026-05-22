#!/bin/bash
# refresh-mispricing.sh
#
# Thin wrapper around mispricing/orchestrator.py. The orchestrator
# handles all six phases with tmp-write/atomic-rename discipline and
# emits a manifest under run-state/<RUN-ID>/. Per Codex review #3.
#
# Env:
#   DEPLOY_PUSH    1 = git push after run (default 0)
#   PREFER_SOURCE  ib | yfinance (default ib; per-ticker fallback)
#   LIVE_PUSH      1 = real IB orders (gated; default 0)
#
# Logs:
#   ~/puc-trading/logs/refresh-mispricing.log
#
# Manifest:
#   ~/puc-trading/run-state/<RUN-ID>/manifest.json

set -uo pipefail

PUC_TRADING_DIR="${PUC_TRADING_DIR:-$HOME/puc-trading}"
PREFER_SOURCE="${PREFER_SOURCE:-ib}"

cd "$PUC_TRADING_DIR"

args=(--prefer-source "$PREFER_SOURCE")
[ "${DEPLOY_PUSH:-0}" = "1" ] && args+=(--deploy-push)
[ "${LIVE_PUSH:-0}" = "1" ] && args+=(--live-push)

python3 -m mispricing.orchestrator "${args[@]}"
ORCH_RC=$?

# Refresh the public scanner dashboard book and redeploy (GitHub Pages on
# pft-validator). Gated on DEPLOY_PUSH so local/dry runs don't publish.
if [ "${DEPLOY_PUSH:-0}" = "1" ]; then
  bash "$PUC_TRADING_DIR/scripts/deploy-scanner.sh" || echo "WARN: deploy-scanner failed" >&2
fi

exit "$ORCH_RC"
