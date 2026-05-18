# mispricing-screen module

The `mispricing` package is the paper-only options pipeline layered on top of
`corpus/convergence-latest.json` and `calendar/catalysts.yaml`.

It does not place live orders. The only code path that mentions live execution is
the documented `LIVE_PUSH=1` gate in the paper executor; the current
orchestrator writes paper tickets and paper-book state.

## Phase contract

| Phase | Module | Reads | Writes |
|---|---|---|---|
| 1 | `ib_chain.py` | convergence tickers, IB Gateway or yfinance | `options-cache/<TICKER>-<DATE>.json` |
| 2 | `detector.py` | convergence artifact, catalyst calendar, chain snapshots | `mispricing/screens/screen-<DATE>.json` |
| 3 | `shaper.py` | detector rows, open paper positions | in-memory `TradeCandidate` rows |
| 4 | `tickets.py` | screen rows, candidates, paper positions | `paper-journal/mispricing/daily/<DATE>.md` |
| 5 | `morning_brief.py` | daily ticket, screen summary, Telegram env | Telegram digest |
| 6 | `paper_executor.py` | candidates, `positions.json`, `closed.json` | paper-book state and `tracker.md` |

## Data shapes

`ib_chain.ChainSnapshot` is the chain boundary. The IB path may populate IV and
greeks. The yfinance fallback preserves the same contract shape but leaves
`delta`, `gamma`, `theta`, and `vega` as `None`. Downstream callers must treat
greeks as optional.

`detector._atm_straddle()` only needs spot, expiry, strike, bid/ask, and last.
It degrades to `no_market` when the ATM call/put or their mids are unavailable.
`shaper._per_contract_cost()` also works without greeks; LEAPS use a spot-based
placeholder and income structures use the ATM straddle proxy.

## Runtime state

Generated files are runtime state, not source contracts:

- `options-cache/`
- `mispricing/screens/screen-<DATE>.json`
- `paper-journal/mispricing/positions.json`
- `paper-journal/mispricing/closed.json`
- `paper-journal/mispricing/tracker.md`

The paper-book JSON files are mutable state. Keep source changes separate from
daily refresh output when reviewing or committing this package.

Daily tickets in `paper-journal/mispricing/daily/<DATE>.md` are the durable
audit trail and stay tracked in git, mirroring the AGTI paper bucket. The
underlying screen JSON, tracker render, positions, closed state, and run
manifests are runtime state.

## Safety notes

- `detector._thesis_move()` is a heuristic. It is acceptable for paper ranking,
  but it needs calibration against historical catalyst moves before live use.
- `morning_brief.py` returns `False` when Telegram credentials are missing. The
  shell orchestrator currently prints that state; a cron preflight should make
  missing credentials fail loud before live operation.
- `scripts/refresh-mispricing.sh` publishes each phase directly to repo paths.
  A future transaction wrapper should write to temp paths and atomically publish
  only after all phases pass.
