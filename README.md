# puc-trading

Private runtime for the LLM Convergence flow-prediction thesis. Houses the
options scanner, the convergence corpus + populator, the published-paper
trade journal, and the deploy glue that pushes scan output to the public
dashboard.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the architectural decisions: why
the runtime is split this way, how the file-boundary seam with `trend-corpus`
works, and how M1-M5 wire together.

## Repo map

```
puc-trading/
|-- README.md                    <-- you are here
|-- Makefile                     <-- validate / test / populate-convergence / scan
|-- docs/
|   `-- DESIGN.md                <-- why this exists + how the pieces fit
|
|-- corpus/                      <-- the convergence corpus + populator (M1)
|   |-- capture-schema.ts        # TypeScript contract for capture + scoring
|   |-- convergence-corpus.md    # Phase 0 seed corpus writeup
|   |-- validation-plan.md       # backtesting methodology
|   |-- populate_convergence.py  # deterministic fixture-mode populator
|   |-- test_convergence_seam.py # tests for load / freshness / fail-loud paths
|   |-- convergence-latest.json  # the generated artifact the scanner consumes
|   `-- captures/YYYY-MM-DD/     # raw capture records, per-day partitioned
|
|-- scanner/                     <-- the live IBKR options scanner
|   |-- README.md                # scanner philosophy + setup
|   |-- ARCHITECTURE-HANDOFF.md  # integration contract for the corpus populator
|   |-- run_live_scan.py         # IB Gateway scanner, reads convergence-latest.json
|   |-- llm_options_scanner.py   # self-contained artifact + inline tests
|   |-- index.html               # local copy of the dashboard
|   `-- scan-results.json        # last scan output (real file lives in pft-validator)
|
|-- scripts/                     <-- deploy glue (M5)
|   |-- deploy-scanner-results.sh        # validate -> stage -> commit -> (DEPLOY_PUSH=1 to push)
|   |-- deploy-scanner-results.test.sh   # 4-test harness, no real git push
|   `-- check-dashboard-shape.py         # asserts scan-results.json fields the dashboard reads
|
|-- trades/                      <-- active human-curated trade theses
|   |-- naval-thesis.md          # SaaSpocalypse short + hardware moats long
|   |-- ufo-disclosure.md        # release-day P&L log
|   `-- agti/                    # AGTI Intelligence Report trade theses
|
|-- journal/                     <-- daily trade diary (markdown per day)
|   `-- YYYY-MM-DD.md
|
`-- paper-journal/agti/          <-- automated AGTI paper-trade journal
    |-- scripts/                 # daily-pull.sh, notify-telegram.py, extract-signals.py
    |-- daily/                   # extracted signals + daily writeups
    |-- daily/raw/               # raw AGTI HTML pulls
    `-- cron-runs/               # cron run summaries
```

## Make targets

| Target | What it does |
|---|---|
| `make validate` | Validate `corpus/convergence-latest.json` against the M1 contract. Fails loud on missing / malformed / stale / empty. |
| `make test` | Run `corpus/test_convergence_seam.py` (9 tests covering every fail-loud branch). |
| `make populate-convergence` | Regenerate `corpus/convergence-latest.json` + the day's capture-records (fixture mode, no API keys, no network). |
| `make scan` | `validate` + run `scanner/run_live_scan.py` against a live IB Gateway. |

## How it ties to the other repos

- The scanner writes `~/pft-validator/scanner/scan-results.json`, which is
  the file the public dashboard at `pft.permanentupperclass.com/scanner/`
  fetches. See [`pft-validator`](https://github.com/P-U-C/pft-validator).
- The convergence corpus model + schemas are mirrored in the public template
  at [`trend-corpus`](https://github.com/P-U-C/trend-corpus). The public repo
  documents the pattern; this repo is the live runtime.
- The AGTI paper journal in `paper-journal/agti/` is unrelated to the
  convergence scanner. It's the published-research-driven discretionary
  trade journal, cron'd daily at 14:00 UTC.

## Bringup

```bash
git clone https://github.com/P-U-C/puc-trading.git
cd puc-trading
python3 -m pip install ib_insync requests  # only needed for live scans
make populate-convergence  # writes corpus/convergence-latest.json
make test
make validate
# scanning needs IB Gateway up on port 4002:
make scan
```

## Safety posture

- Scanner is `readonly=True` on the IBKR connection. No order methods exist.
- Convergence artifact is enforced fresh (default 14d) before any scan.
- Deploy glue does NOT push without explicit `DEPLOY_PUSH=1`. Secret-pattern
  scan runs before any commit.
- Position sizing is lottery-ticket. See [`trades/naval-thesis.md`](trades/naval-thesis.md)
  for the live capital budget.

Research infrastructure. Not financial advice.
