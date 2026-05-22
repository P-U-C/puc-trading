#!/bin/bash
# deploy-scanner.sh
#
# Merge the current paper/live book into the scanner dashboard JSON and
# redeploy the public page (GitHub Pages served from the pft-validator repo).
# Idempotent: if the book is unchanged, it commits/pushes nothing.
#
# The push token is read from the existing export scripts so there is one
# source of truth for the pft-validator deploy credential (it rotates there).
set -uo pipefail

PUC_TRADING_DIR="${PUC_TRADING_DIR:-$HOME/puc-trading}"
PFT="${PFT_VALIDATOR_DIR:-$HOME/pft-validator}"
TOKEN_SRC="${TOKEN_SRC:-$HOME/pf-scout-bot/deploy/export-graph.sh}"

python3 "$PUC_TRADING_DIR/scripts/merge-book-into-scan.py" || { echo "deploy-scanner: merge failed" >&2; exit 1; }

cd "$PFT" || { echo "deploy-scanner: $PFT missing" >&2; exit 1; }

git add scanner/scan-results.json
if git diff --cached --quiet; then
  echo "deploy-scanner: no book change; nothing to deploy"
  exit 0
fi

PAT="$(grep -hoE 'github_pat_[A-Za-z0-9_]+' "$TOKEN_SRC" 2>/dev/null | head -1)"
if [ -z "$PAT" ]; then
  echo "deploy-scanner: no push token found in $TOKEN_SRC" >&2
  exit 1
fi
REMOTE="https://0xzoz:${PAT}@github.com/P-U-C/pft-validator.git"

git -c user.email=zeroexzoz@gmail.com -c user.name="scanner-deploy" \
  commit -q -m "scanner: book refresh $(date -u +%Y-%m-%dT%H:%MZ)"
git -c rebase.autoStash=true pull --rebase -q "$REMOTE" main || true
git push "$REMOTE" HEAD:main >/dev/null 2>&1 && echo "deploy-scanner: deployed $(git rev-parse --short HEAD)" || { echo "deploy-scanner: push failed" >&2; exit 1; }
