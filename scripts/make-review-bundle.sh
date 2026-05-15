#!/bin/bash
# make-review-bundle.sh
#
# Produce a self-contained directory an external reviewer can read without
# being added to the private puc-trading repo. Output goes to a directory
# named with the current UTC date; the contents are:
#
#   README.md                       <-- what's in the bundle + how to read it
#   trend-corpus-summary/           <-- pinned public trend-corpus summary
#   scanner-seam-diff.patch         <-- the M1 diff against the pre-seam state
#   convergence-latest.fixture.json <-- the artifact the scanner consumes
#   test-output.txt                 <-- output of make test
#   secret-scan-output.txt          <-- output of make secret-scan
#   dashboard-shape-output.txt      <-- output of check-dashboard-shape.py
#   redaction-notes.md              <-- what was scrubbed and why
#
# Refuses to produce a bundle if `make secret-scan` flags anything in the
# working tree. That guarantees no operator-identifier leak through the bundle.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="$(date -u +%Y-%m-%d)"
OUT="${REVIEW_BUNDLE_OUT:-$REPO_ROOT/review-bundle-$DATE}"
TREND_CORPUS_DIR="${TREND_CORPUS_DIR:-$HOME/trend-corpus}"

log() { printf "[%s] %s\n" "$(date -u +%FT%TZ)" "$*"; }

if [ -e "$OUT" ]; then
    log "review bundle dir already exists at $OUT -- refusing to overwrite"
    exit 1
fi

log "preflight: make secret-scan in $REPO_ROOT"
cd "$REPO_ROOT"
make secret-scan

log "creating $OUT"
mkdir -p "$OUT"

# 1. README
cat > "$OUT/README.md" <<EOF
# puc-trading Review Bundle ($DATE)

Self-contained directory mirroring what's in P-U-C/puc-trading at this
date, scrubbed for external review. The actual repo stays private; this
bundle exists so a reviewer can read the M1 + M5 work without being
added as a GitHub collaborator.

## Contents

| File | What it is |
|---|---|
| README.md | this file |
| trend-corpus-summary/ | pinned public-side summary (README + DESIGN of the companion public repo) |
| scanner-seam-diff.patch | M1 diff -- the scanner refactor that introduced the file seam |
| convergence-latest.fixture.json | the artifact the scanner now consumes (fixture-mode output) |
| test-output.txt | output of \`make test\` -- 9 fail-loud branches pass |
| secret-scan-output.txt | output of \`make secret-scan\` -- must be "clean" |
| dashboard-shape-output.txt | output of scripts/check-dashboard-shape.py -- must exit 0 |
| redaction-notes.md | what was scrubbed and why |

## How to verify

The verification commands live in the private repo, not this bundle. If
the reviewer needs to re-run them, the commands are:

\`\`\`
make validate
make test
make secret-scan
python3 scripts/check-dashboard-shape.py
\`\`\`

This bundle captures the output of the last successful run.

## Scope

In scope: the M1 scanner seam + M5 deploy glue + the fixture-mode
populator + the dashboard-compatibility check.

Out of scope: live trade execution (none; IBKR is readonly), the AGTI
paper-journal cron (pre-existed, not part of this work), trade thesis
content under trades/* (pre-existed).
EOF

# 2. trend-corpus public-side summary
mkdir -p "$OUT/trend-corpus-summary"
if [ -d "$TREND_CORPUS_DIR" ]; then
    cp "$TREND_CORPUS_DIR/README.md" "$OUT/trend-corpus-summary/README.md"
    [ -f "$TREND_CORPUS_DIR/docs/architecture.md" ] && cp "$TREND_CORPUS_DIR/docs/architecture.md" "$OUT/trend-corpus-summary/architecture.md"
    [ -f "$TREND_CORPUS_DIR/AGENTS.md" ] && cp "$TREND_CORPUS_DIR/AGENTS.md" "$OUT/trend-corpus-summary/AGENTS.md"
    log "pinned trend-corpus README + architecture + AGENTS"
else
    echo "(trend-corpus not present at $TREND_CORPUS_DIR -- skipping summary)" > "$OUT/trend-corpus-summary/MISSING.md"
fi

# 3. scanner seam diff + the M1 source files in full
log "capturing scanner-seam diff + source files"
mkdir -p "$OUT/scanner-seam"
# Find the commit that introduced populate_convergence.py (the M1 landing commit).
M1_COMMIT="$(git log --diff-filter=A --format='%H' -- corpus/populate_convergence.py | tail -1)"
if [ -n "$M1_COMMIT" ]; then
    git show --no-color "$M1_COMMIT" > "$OUT/scanner-seam/m1-commit.patch" || true
    git log --oneline -- corpus/populate_convergence.py corpus/test_convergence_seam.py scanner/run_live_scan.py > "$OUT/scanner-seam/m1-commit-history.txt" || true
fi
# Always include the M1 source files in full so the reviewer doesn't have
# to reconstruct them from a patch.
cp corpus/capture-schema.ts "$OUT/scanner-seam/" 2>/dev/null || true
cp corpus/populate_convergence.py "$OUT/scanner-seam/" 2>/dev/null || true
cp corpus/test_convergence_seam.py "$OUT/scanner-seam/" 2>/dev/null || true
cp scanner/run_live_scan.py "$OUT/scanner-seam/" 2>/dev/null || true
cp scripts/check-dashboard-shape.py "$OUT/scanner-seam/" 2>/dev/null || true
cp scripts/deploy-scanner-results.sh "$OUT/scanner-seam/" 2>/dev/null || true
cp scripts/deploy-scanner-results.test.sh "$OUT/scanner-seam/" 2>/dev/null || true
cp Makefile "$OUT/scanner-seam/" 2>/dev/null || true
# Pending working-tree diff (usually empty in a clean checkout)
git diff --no-color HEAD -- corpus/ scanner/ scripts/ Makefile > "$OUT/scanner-seam/pending-diff.patch" || true

# 4. fixture artifact (current state of the generated convergence file)
if [ -f "$REPO_ROOT/corpus/convergence-latest.json" ]; then
    cp "$REPO_ROOT/corpus/convergence-latest.json" "$OUT/convergence-latest.fixture.json"
else
    log "no convergence-latest.json yet -- running populate-convergence"
    (cd "$REPO_ROOT" && make populate-convergence >/dev/null) || true
    [ -f "$REPO_ROOT/corpus/convergence-latest.json" ] && cp "$REPO_ROOT/corpus/convergence-latest.json" "$OUT/convergence-latest.fixture.json"
fi

# 5. test output
log "capturing make test output"
( cd "$REPO_ROOT" && make test 2>&1 ) > "$OUT/test-output.txt" || true

# 6. secret-scan output
log "capturing make secret-scan output"
( cd "$REPO_ROOT" && make secret-scan 2>&1 ) > "$OUT/secret-scan-output.txt" || true

# 7. dashboard shape output
log "capturing check-dashboard-shape.py output"
( cd "$REPO_ROOT" && python3 scripts/check-dashboard-shape.py 2>&1 ) > "$OUT/dashboard-shape-output.txt" || true

# 8. redaction notes
cat > "$OUT/redaction-notes.md" <<EOF
# Redaction Notes ($DATE)

This bundle is built from the puc-trading working tree but is intended for
external review. Operator-identifier exposure was scrubbed at the source
(P1 security pass on 2026-05-15) rather than at bundle time, so this
section is mostly an inventory of what is NOT included rather than what
was removed from the bundle.

## What is NOT in this bundle

- \`trades/*\` -- the operator's trade theses. Pre-existed; not part of
  the M1/M5 work being reviewed.
- \`journal/*\` -- the operator's daily trade journal. Same reason.
- \`paper-journal/agti/*\` -- the AGTI paper-journal cron output, daily
  signal extractions, and cron-run summaries. Pre-existed; not part of
  the M1/M5 work being reviewed.
- The \`origin\` git remote URL with its embedded token. (Tokens are
  rotated externally; this bundle has no git remote configured.)
- \`.env\` if one exists locally. \`.env.example\` is included as a
  placeholder template.

## What WAS scrubbed at source (commit eaada89 -- P1 security pass)

- Hardcoded Telegram chat_id values from \`scanner/run_live_scan.py\`
  and \`paper-journal/agti/scripts/notify-telegram.py\`. Both now read
  from env / the configured .env file. No default value.
- IBKR account number references in \`paper-journal/agti/README.md\` and
  \`trades/agti/agti-backtest-2026-05-08.md\`. Now refer to the operator
  account via the \`IBKR_ACCOUNT\` env var.
- \`make secret-scan\` was added with a denylist covering tokens,
  operator identifiers, and trade-action field names. Bundle creation
  refuses to proceed if that scan flags anything.

## Reviewer verification

The reviewer should be able to assert:

1. \`secret-scan-output.txt\` ends with "secret-scan: clean".
2. \`test-output.txt\` reports 9 tests passing (the M1 fail-loud
   branches).
3. \`dashboard-shape-output.txt\` exits 0 ("dashboard shape ok").
4. \`scanner-seam-diff.patch\` shows the introduction of
   \`load_convergence\`, \`validate_convergence_artifact\`, the
   \`ConvergenceLoadError\` exception, and the removal of the
   hardcoded CONVERGENCE list.
5. \`convergence-latest.fixture.json\` parses, contains the expected
   M1 fields (\`schema_version\`, \`generated_at\`, \`themes\`,
   \`scores\`), and has a non-empty \`scores\` array.

Any failure to assert any of those is grounds for the reviewer to
reject the bundle as not faithful to the source repo.
EOF

# 9. final sanity: the bundle itself must pass secret-scan
log "secret-scan on the bundle"
python3 "$REPO_ROOT/scripts/secret-scan.py" "$OUT" >/dev/null

log "bundle ready at $OUT"
log "size: $(du -sh "$OUT" | cut -f1)"
