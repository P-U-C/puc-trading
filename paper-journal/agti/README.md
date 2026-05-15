# AGTI Paper-Trade Journal

Paper book for AGTI Intelligence Report signals. Built 2026-05-11 to backfill 5/8, 5/9, 5/10 reports.

## Why this exists

The backtest at `~/puc-trading/trades/agti/agti-backtest-2026-05-08.md` showed a 56-59% hit rate (ex-windfalls) on a 1-3 day hold against a flat tape, with concentrated edge in single-name event-driven calls and a clear 0-of-4 macro-proxy-ETF failure mode. This paper book runs the same playbook forward, with a fixed exit-rules doc and a hard go-live gate, to gather the next batch of evidence before any real capital moves.

## Structure

```
paper-journal/agti/
  README.md             ← you are here
  tracker.md            ← master open/closed positions table + stats
  exit-rules.md         ← deterministic stops/takes/time-stops
  daily/
    2026-05-08.md       ← Day-1 entries (10 from run 29)
    2026-05-09.md       ← Pending Mon-open fills (17 from run 30)
    2026-05-10.md       ← Pending Mon-open fills (20 from run 31)
    <YYYY-MM-DD>.md     ← cron writes one per trading day going forward
```

## How to read the tracker

`tracker.md` is the source of truth.

Three tables in order of relevance:

1. **Open positions** — every position with capital deployed (paper) right now, sorted by entry date. Columns: ticker, direction, entry date/price, last mark, %, T+5 exit, catalyst. Pending Mon-open fills show `—` for mark until Monday's close.
2. **Closed positions** — anything that's exited (time stop, catalyst, profit take, stop loss, or direction flip). Each row records why it closed.
3. **Stats block** — total signals, IBKR-executable count, hit rate, avg return, days-to-go-live. Stats only become meaningful at ≥ 5 closed signals.

`daily/*.md` are the **per-report logs**. Each one cites the report URL, lists every signal that report named, marks IBKR-executability per signal, applies the macro-proxy skip filter explicitly, and notes any same-ticker direction flip vs. earlier reports. The daily files are the audit trail; the tracker is the summary view.

`exit-rules.md` is the deterministic rule set. The daily cron applies it without judgment calls.

## Conventions

- **Entry price** = close on first trading day on or after report publication. Reports published mid-week fill same-day at close; reports published Sat/Sun fill Monday open.
- **Mark** = most recent yfinance daily close.
- **Direction-adjusted P&L:** positive = the signal worked, whether the trade was long or short.
- **IBKR-executable** filter: stocks/options/bonds/forex on the operator's IBKR account (account id redacted; configure via the `IBKR_ACCOUNT` env var). NO futures, NO leveraged ETPs, NO foreign direct (SBIN.NS class).
- **Macro-proxy filter:** BNO/XLE/TLT-class signals are SKIPPED per the backtest's 0-of-4 evidence. They are still logged in the daily file with a "SKIPPED" tag so the universe-of-signals count stays honest.
- **Sizing:** $1,000 notional / equity position, $500 / option ticket, $1,000 / FX position. Paper-only sizing — will be re-derived for live.

## Cron updates (daily, when the report stream is live)

A 16:30 ET daily cron will:

1. Fetch the day's new AGTI Intelligence Report from `https://agtico.github.io/intelligence-reports`.
2. Extract every named ticker and write a new `daily/<DATE>.md`.
3. For every existing open position in `tracker.md`, pull the day's close from yfinance and update the mark.
4. Apply `exit-rules.md` (time stop, catalyst stop, stop loss, profit take). Move any tripped row from "Open positions" to "Closed positions" with reason.
5. Recompute the stats block.
6. Surface any signal in the new daily file that conflicts with the existing tracker (direction flip on a same-ticker open position) and queue the close + reopen for the next trading-day open.

The cron writes; the human reviews before any of it goes live. The skill `loop` or a system cron entry handles the schedule. Cron job spec lives separately (TBD — not in scope for this backfill).

## Go-live gate

This is paper until BOTH of:

- **30 closed signals** in the tracker (denominator for hit rate to mean something).
- **4 calendar weeks** since first entry (2026-05-08 → 2026-06-05 earliest).

Pass criterion: closed-signal hit rate ≥ 55%, matching the backtest's ex-windfall headline. If we hit 30 closed signals at < 55%, that's data — pause, re-examine the signal-class filter, don't go live.

## What's NOT in this book

- Anything not in an AGTI Intelligence Report. The UFO trade, the Profound Round Robin SoftBank book, the standalone diary trades — those live in `~/puc-trading/trades/` and `~/puc-trading/journal/`. Cross-reference but don't merge.
- Private-entity signals (Anthropic, OpenAI, PSG, Arsenal). Logged in the daily file with a note; no position.
- Direct foreign equities (SBIN.NS, ^NSEI direct). IBKR-non-executable for this account; logged, no position. Use the US-listed ETF proxy (INDA) if the report's thesis allows.
- Macro-proxy ETFs (BNO/XLE/TLT). Hard skip per `exit-rules.md` §5.

## Source attribution

- Reports: AGTI Intelligence Report stream, `https://agtico.github.io/intelligence-reports`
- Price data: yfinance daily closes (Python at `/usr/bin/python3`)
- Backtest reference: `~/puc-trading/trades/agti/agti-backtest-2026-05-08.md` (110 named signals, 95 closed, 56-59% hit rate ex-windfall)
- Journal prior: `~/puc-trading/journal/2026-05-07.md`, `~/puc-trading/journal/2026-05-08.md`
