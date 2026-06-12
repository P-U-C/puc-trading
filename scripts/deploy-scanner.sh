#!/bin/bash
# deploy-scanner.sh
#
# Merge the current paper/live book into the scanner dashboard JSON and
# redeploy the public page (GitHub Pages served from the pft-validator repo).
# Idempotent: if the book is unchanged, it commits/pushes nothing.
#
# Auth: pft-validator's remote is tokenless and pushes via the git credential
# store (see [[git-credential-setup]] memory: repo-local helper override on
# pft-validator forces store-only for github.com, bypassing the gh helper).
set -uo pipefail

PUC_TRADING_DIR="${PUC_TRADING_DIR:-$HOME/puc-trading}"
PFT="${PFT_VALIDATOR_DIR:-$HOME/pft-validator}"

python3 "$PUC_TRADING_DIR/scripts/merge-book-into-scan.py" || { echo "deploy-scanner: merge failed" >&2; exit 1; }

# Refresh the page's theme/convergence table from the daily corpus artifact
# (13:55 refresh-convergence). Non-fatal: a missing artifact must not block
# the book deploy.
python3 "$PUC_TRADING_DIR/scripts/merge-convergence-into-scan.py" || echo "deploy-scanner: convergence merge failed (book deploy continues)" >&2

cd "$PFT" || { echo "deploy-scanner: $PFT missing" >&2; exit 1; }

git add scanner/scan-results.json
if git diff --cached --quiet; then
  echo "deploy-scanner: no book change; nothing to deploy"
  exit 0
fi

git -c user.email=zeroexzoz@gmail.com -c user.name="scanner-deploy" \
  commit -q -m "scanner: book refresh $(date -u +%Y-%m-%dT%H:%MZ)"
git -c rebase.autoStash=true pull --rebase -q origin main || true
git push origin HEAD:main >/dev/null 2>&1 && echo "deploy-scanner: deployed $(git rev-parse --short HEAD)" || { echo "deploy-scanner: push failed" >&2; exit 1; }
