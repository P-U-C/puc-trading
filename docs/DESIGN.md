# puc-trading - Design

This repo's job is to turn a versioned convergence artifact into a ranked
list of asymmetric options trades, and to publish that ranking to a public
static dashboard without ever exposing the corpus that produced it or the
trade book that consumes it.

The pieces are arranged around three boundaries:

1. **Corpus / scanner boundary** -- a JSON file (`corpus/convergence-latest.json`)
2. **Scanner / dashboard boundary** -- a JSON file (`scanner/scan-results.json`,
   really written to `~/pft-validator/scanner/`)
3. **Public / private boundary** -- this repo is private; the public template
   is [`trend-corpus`](https://github.com/P-U-C/trend-corpus); the public
   dashboard is [`pft-validator`](https://github.com/P-U-C/pft-validator)

All three boundaries are file-shaped. No in-process integration, no shared
imports, no shared database. That is the deliberate design.

## Composition

```
[private corpus populator]   ->   convergence-latest.json   ->   [private scanner runtime]
                                  (file seam, M1 contract)         this repo, IBKR readonly
                                                                          |
                                                                          v
                                                                  scan-results.json
                                                                  (M5 deploy contract)
                                                                          |
                                                                          v
                                                              [public scanner artifact]
                                                              pft-validator/scanner/scan-results.json
                                                                          |
                                                                          v
                                                                 [public dashboard]
                                                            pft.permanentupperclass.com/scanner/
```

The scanner runtime is private. Only the scanner's output artifact is
public. The dashboard is a static page that reads the artifact. No
public interface accepts a query, and no order method exists anywhere
in this chain -- the IBKR connection is `readonly=True` and the deploy
script default has `DEPLOY_PUSH=0`.

## Why file boundaries

The original convergence input to the scanner was a hardcoded Python list of
~47 rows inside `run_live_scan.py`. It was hand-maintained, drifted, and
made the scanner impossible to refresh without re-editing code.

M1 replaced that with a generated, validated artifact at
`corpus/convergence-latest.json` and a fail-loud loader (`load_convergence`
in `run_live_scan.py`). The artifact format is documented in
`corpus/capture-schema.ts` and is the contract any future corpus populator
(human, agent, third-party service) must produce.

This lets the populator live independently of the scanner. It can be a
research-mode Codex agent, a private LLM-survey pipeline, or anything else,
as long as it writes a conforming JSON. The scanner doesn't care.

## What the scanner expects from the artifact

```
{
  "schema_version": "0.1.0",
  "generated_at": "<ISO 8601 UTC>",
  "generator": {"name": "...", "version": "...", "mode": "fixture|production"},
  "themes": [{"theme_id", "theme_name", "status"}],
  "scores": [
    {"ticker", "theme_id", "theme", "score", "tier", "status", ...}
  ]
}
```

Minimum required per score row: `ticker, theme, score, tier, status`. Theme
names are the join key with both the IBKR scan output and the public
dashboard's theme cards. They must be consistent.

The loader enforces:

- schema_version present
- generated_at present and ISO-parseable
- scores non-empty list
- every score row has the required minimum fields
- generated_at within `CORPUS_MAX_AGE_DAYS` (env, default 14)

Any failure exits non-zero with a specific error. The scanner never silently
runs against an empty or stale universe.

## What the dashboard expects from scan-results.json

The static `index.html` at `~/pft-validator/scanner/index.html` does a
single `fetch('/scanner/scan-results.json')` and renders two things:

- A grid of theme cards (driven by `scan_meta.themes` and `convergence`).
- A table of ranked contracts (driven by `results`).

`scripts/check-dashboard-shape.py` enforces that the JSON has the exact
fields `index.html` reads. The deploy script runs it before any commit so
the dashboard never gets a partially-shaped file.

## Deploy contract (M5)

`scripts/deploy-scanner-results.sh` has two modes, both gated on env vars:

- `RUN_FULL_SCAN=1`: actually invokes the scanner (requires IB Gateway).
  Default off; the script assumes scan-results.json was refreshed
  out-of-band.
- `DEPLOY_PUSH=1`: actually `git push`es the pft-validator working tree.
  Default off; commit happens, push doesn't.

Other safeties:

- `set -euo pipefail`.
- Stages by whitelist (`scanner/scan-results.json` and `.gitignore` only).
  Never `git add -A`.
- Secret-pattern scan over staged files; refuses to commit on a hit.
- Freshness check on scan_meta.scanned_at; default refuses scans older than
  48h.
- `ensure_gitignore` idempotently adds the IB-Gateway-junk patterns
  (`jts.ini`, `launcher.log`, `dgpdjeilg...`) to `pft-validator/.gitignore`
  so they never land in a commit.

Recommended cadence is daily, not hourly. Convergence does not move that
fast.

## Paper journal vs convergence scanner

`paper-journal/agti/` is unrelated to the convergence stack. It is a
separate cron-driven workflow that:

1. Pulls the daily AGTI Intelligence Report HTML
2. Extracts signals
3. Updates a synthetic paper-trade book (`scripts/positions.json`)
4. Notifies on Telegram

The cron entry is `0 14 * * * /home/ubuntu/puc-trading/paper-journal/agti/scripts/daily-pull.sh`.
It commits to `paper-journal/agti/daily/` and `paper-journal/agti/cron-runs/`
on this repo, but those commits are not touched by the convergence deploy
script.

## Things this repo deliberately does NOT do

- It does not implement live order execution. The IBKR connection is
  readonly. No order methods exist in the code.
- It does not host the public dashboard. That's `pft-validator`.
- It does not collect the convergence corpus from live LLMs. The populator
  in fixture mode is faithful to the hardcoded list it replaced; a real
  research-mode populator is a separate concern and may live in a different
  agent / runtime entirely.
- It does not push automatically. Every push requires explicit
  `DEPLOY_PUSH=1`.

## Pointers

- The contract that any future corpus populator must implement:
  `corpus/capture-schema.ts` plus the validator in `scanner/run_live_scan.py`
  (`validate_convergence_artifact`, `load_convergence`, `map_convergence_scores`).
- The scanner architecture handoff:
  `scanner/ARCHITECTURE-HANDOFF.md` -- written for the corpus-populator agent.
- The public template for sector decision corpora:
  [`P-U-C/trend-corpus`](https://github.com/P-U-C/trend-corpus).
- The public dashboard:
  https://pft.permanentupperclass.com/scanner/
