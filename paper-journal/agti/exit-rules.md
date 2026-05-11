# AGTI Paper-Trade Exit Rules

Owner: Chad
Effective: 2026-05-08
Status: ACTIVE for paper book; **NOT live until confidence-threshold gate is cleared** (see `tracker.md` "Go-live gate").

These rules apply to every signal logged in `daily/*.md` and surfaced in `tracker.md`. They are deterministic so the daily cron can run them without judgment calls.

---

## 1. Time stop (default exit)

- **Default holding window: T+5 trading days.**
- T is the trading day of entry fill (5/8 close fills are T=5/8; pending Mon-open fills are T=5/11).
- Position closes at the **5th trading day's close**.
- Examples:
  - Entry 5/8 close → exit 5/15 close.
  - Entry 5/11 open → exit 5/18 close.
- Why 5: the backtest in `~/puc-trading/trades/agti/agti-backtest-2026-05-08.md` ran 1-3 day holds and the signal density was concentrated in days 1-3. T+5 gives the catalyst one full week to play out without leaving theta on the table for option proxies.

---

## 2. Catalyst stop (override)

If the report **explicitly named a dated catalyst** for the signal, replace the time stop with the catalyst date.

- Catalyst date BEFORE T+5 → exit at the catalyst-date close.
- Catalyst date AFTER T+5 → keep T+5. (The report is asking us to hold longer than the data supports.)

Worked example: 5/9 report INST short cites "May 12 ShinyHunters ransom deadline." Entry 5/11 open, catalyst 5/12. Exit at **5/12 close**, not T+5 = 5/18.

Worked example: 5/10 report CMCSA long cites "Nolan's Odyssey July 17." Catalyst is post-T+5. Use T+5 = 5/18 close.

---

## 3. Stop loss (intra-window override)

- **Equity:** -15% from entry. Closes immediately on the close that breaches.
- **Option premium proxies:** -50% from entry premium. Same logic.
- **Forex:** -3% from entry rate (FX vol is much lower; -15% never trips on a daily timescale). Closes on the close that breaches.

Sign convention: stop is on the **direction-adjusted** P&L, so a short with the underlying up 15% trips the equity stop.

---

## 4. Profit take (intra-window override)

- **Equity:** +30%. On breach close, exit half (50% of position) and let the runner trail with a tightened -10% stop on the remainder.
- **Option premium proxies:** +100%. On breach close, exit full position. Don't let an option round-trip through the moneyness curve.
- **Forex:** +6% (2× the stop, mirrors the asymmetry of the equity rule).

Reassess at +30% rather than blanket-exit because the backtest's biggest hits (DDOG +28.66%, ULCC +32.76%, SAVE +100%) all blew through this in a single window. Cutting at +30% would have left ~$0.70 on the dollar uncaptured for SAVE/ULCC.

---

## 5. Macro-proxy filter (HARD SKIP)

**DO NOT take any signal whose primary expression is via a macro/geopolitical-proxy ETF.**

- Hard-skip list: **BNO, XLE, TLT** (and any other broad commodity, broad-energy, or broad-rates ETF when used as a single-event geopolitical proxy).
- Soft-skip extension: any broad sector ETF (XRT, IYM, XLF, etc.) when the report cites it as a *proxy* for a single named catalyst rather than as the trade itself.
- Basis: the existing backtest at `~/puc-trading/trades/agti/agti-backtest-2026-05-08.md` shows **0-of-4 hit rate** on this signal class (BNO long 5/2 -10.74%, XLE long 5/2 -5.79%, TLT short 5/2 -0.81%, BNO long 5/5 -7.75%). The report's geopolitical-thesis-via-ETF route has consistently faded.

What still counts as **kept** (NOT skipped):
- Single-country equity ETFs as the executable instrument (INDA for India, EWU for UK) when the report's actual thesis is the country's equity-market direction. These are the trade, not a proxy.
- Sector single-name longs/shorts (CRWD/PANW for cybersecurity is the sector trade — kept; XRT for "retail-strength via entertainment" would be skipped).

When skipped, the daily file logs the signal as **"SKIPPED per macro-proxy filter"** with the report's stated price ref, so the tracker reflects the universe of named signals, not just the executed ones.

---

## 6. Same-ticker repeat handling

When a ticker appears in consecutive daily reports:

- **Same direction** → keep the existing position; do NOT add to it. Exit timer continues from original entry. (No martingaling.)
- **Direction flip** → close the existing position at the next trading day's open, open a new opposite position at the same open price. Both legs are recorded in the tracker (closed leg + new open leg).
- **Direction → NEUTRAL** → keep the existing position open; the timer continues unmodified. (Neutral isn't a sell signal, just an attention-tracking marker.)
- **NEUTRAL → direction** → open a fresh position at the next trading day's open. (Neutral was never a position to flip from.)

---

## 7. Forex specifics

- Sizing convention: $1,000 notional per FX position.
- Stop / take: -3% / +6% of the rate (per rule 3 / 4).
- The "long INR" signal expresses as **short USD/INR**: gain when USD/INR falls. Tracker shows direction in plain language, not the FX-pair convention, but P&L math runs on the pair quote.

---

## 8. Position sizing (paper)

- Equity: $1,000 notional per position. Round shares down to whole.
- Option proxy (for entries that name a specific contract): $500 notional per ticket.
- Forex: $1,000 notional, 1:1 (no margin).

This sizing is paper-only. Live sizing will be re-derived after the go-live gate clears.

---

## 9. Cron application

The intent: a daily 16:30 ET cron job (`scheduled-job.md` to be written separately) reads `tracker.md`, checks each open position against rules 1-4 using yfinance, and writes a daily mark + any auto-closed positions into a new `daily/<DATE>.md` for that day. Human review is required before any auto-close becomes live.
