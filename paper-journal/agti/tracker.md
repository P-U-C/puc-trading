# AGTI Paper-Trade Master Tracker

**As of:** 2026-05-10 (post 5/10 report, pre 5/11 Mon open)
**Book status:** PAPER. Not live.
**Rules:** see `exit-rules.md`.
**Daily files:** `daily/<DATE>.md`.

---

## Go-live gate

This paper book becomes live only when **both** of the following are cleared:

1. **30 closed signals minimum** in the tracker.
2. **4-week elapsed window minimum** since the first paper entry (2026-05-08).

Earliest possible go-live: 2026-06-05, AND 30 signals must be closed by then. Current closed-signal count: **0**.

Hit-rate target to clear the gate: **≥ 55%** on closed directional signals (matches the backtest's 56.5% ex-SAVE-windfall headline).

---

## Open positions

All times = trading days. Entries marked "5/8 close" are filled at 2026-05-08 close ($XYZ). Entries marked "5/11 open" are pending fills at Monday's open. Marks shown as `—` for pending fills.

| # | Ticker | Direction | Structure | Entry date | Entry price | Last mark | % | T+5 exit | Status / catalyst |
|--:|--------|-----------|-----------|------------|------------:|----------:|--:|----------|-------------------|
| 1 | AMZN | LONG | Equity | 2026-05-08 | $272.68 | $272.68 | 0.00 | 5/15 close | AI infra; Anthropic add-on (5/8 + 5/9 + 5/10 reports — same dir, no add) |
| 2 | WBD | LONG | Equity | 2026-05-08 | $27.11 | $27.11 | 0.00 | 5/15 close | Ted Turner legacy; 5/9 report flipped NEUTRAL (held), 5/10 reaffirmed LONG (no add) |
| 3 | NVDA | LONG | Equity | 2026-05-08 | $215.20 | $215.20 | 0.00 | 5/15 close | Anthropic GPU lease + AWS Trainium |
| 4 | EBAY | LONG | Equity | 2026-05-08 | $107.69 | $107.69 | 0.00 | 5/15 close | Ryan Cohen $56B bid framing |
| 5 | INR (short USD/INR) | LONG INR | Forex | 2026-05-08 | 94.253 USD/INR | 94.253 | 0.00 | 5/15 close | BJP governance continuity |
| 6 | GOOGL | NEUTRAL→LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Search/AI-Overviews monetization (5/9 upgraded to LONG) |
| 7 | DIS | NEUTRAL→LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Devil Wears Prada 2 $77M opening (5/9 upgraded; 5/10 reaffirmed) |
| 8 | NFLX | NEUTRAL→LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | LotF / Apex content pipeline (5/9 upgraded; 5/10 reaffirmed) |
| 9 | AAPL | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Cape Fear Apple TV+ (June 5) |
| 10 | CRWD | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Cybersecurity sector tailwind (Canvas breach) |
| 11 | PANW | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Same cyber tailwind |
| 12 | NTDOY | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Star Fox / Switch 2 launch June 25 |
| 13 | DJT | SHORT | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Truth Social attention de-rating |
| 14 | INDA | LONG | ETF (single-country equity) | 2026-05-11 (open) | pending | — | — | 5/18 close | BJP state expansion |
| 15 | EWU | SHORT | ETF (single-country equity) | 2026-05-11 (open) | pending | — | — | 5/18 close | UK political fragmentation |
| 16 | LGF.A (LION) | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | MJ biopic record open ~$97M |
| 17 | SONY | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | MJ catalog +95% WoW; Thriller back in Top 10 |
| 18 | RCL | SHORT | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Hantavirus cruise sentiment |
| 19 | CCL | NEUTRAL→SHORT | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Hantavirus cruise sentiment (5/10 first SHORT call) |
| 20 | CMCSA | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Nolan's Odyssey July 17 IMAX |
| 21 | IMAX | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Same Odyssey IMAX-format play |
| 22 | DT | LONG | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Dynatrace +6.50 Term score; 6th consecutive report |
| 23 | BRK-B | NEUTRAL→SHORT | Equity | 2026-05-11 (open) | pending | — | — | 5/18 close | Post-annual-meeting attention fade -1.17 |
| 24 | GBPUSD | LONG | Forex | 2026-05-11 (FX open) | pending | — | — | 5/18 close | 5/10 flipped LONG GBP (after 5/8+5/9 SHORT) — **see closed-out leg below** |

### Open neutral-tracker positions (not directional, no P&L target)

These are tracked for attention-coverage stats but have no entry/exit P&L target. They exist to make hit-rate math denominator-honest.

| Ticker | First report | Notes |
|--------|--------------|-------|
| PARA (PSKY) | 5/8 (NEUTRAL across all 3) | Yellowstone fatigue; merger flux |
| BA | 5/10 (NEUTRAL) | 777X cert attention only |

---

## Closed positions

| # | Ticker | Direction | Entry date / price | Exit date / price | % | Reason |
|--:|--------|-----------|-------------------:|------------------:|--:|--------|
| 1 | GBPUSD | SHORT | 2026-05-08 close, 1.3556 | 2026-05-11 (open, pending) | (pending mark) | **Direction flip per 5/10 report** — close short, open new long. Per exit-rules §6, both legs recorded. |

(All other open positions remain open until either T+5, catalyst date, or stop/take trips.)

---

## Universe of named signals (denominator for stats)

This counts every named instrument across the 3 reports (dedup by ticker × direction-as-of-most-recent). Used for hit-rate denominator and IBKR-coverage stat.

| Bucket | Count |
|--------|------:|
| Equity (long) | 17 |
| Equity (short) | 4 (DJT, RCL, CCL, BRK-B) |
| Equity (neutral, tracker only) | 2 (PARA, BA) |
| ETF single-country (long) | 1 (INDA) |
| ETF single-country (short) | 1 (EWU) |
| Forex (long) | 2 (GBPUSD, INR-via-short-USD/INR) |
| Forex (short) | 0 (GBPUSD short was closed in flip) |
| Macro-proxy ETF — SKIPPED | 3 (XLE, IYM, XRT) |
| Non-executable / private | 6 (Anthropic, OpenAI, PSG, Arsenal, NSEI direct, INST) |
| **Total named instruments** | **36** |
| **Of which IBKR-tradable + entered** | **27** (24 open + 1 closed-flip + 2 neutral-tracker — leaves 9 not entered: 6 non-exec + 3 macro-proxy) |

Note on "27 entered": 24 currently-open + 1 closed-leg (5/8 GBPUSD short) + 2 neutral tracker (PARA, BA) = 27. Position count of 24 open is what shows in the open-table; the 27 is the cumulative entries-this-window count for stats.

---

## Stats block

| Metric | Value |
|--------|------:|
| Total named signals (3 reports) | 36 |
| IBKR-executable + entered | 27 (75%) |
| Macro-proxy SKIPS | 3 |
| Non-executable / private | 6 |
| Open directional positions | 22 |
| Open neutral-tracker positions | 2 |
| Closed directional positions | 1 (flipped) |
| Hit rate | **N/A** — needs ≥ 5 closed signals |
| Avg ret % (closed, directional) | **N/A** — needs ≥ 5 closed signals |
| Avg days held (closed) | **N/A** |
| First-entry date | 2026-05-08 |
| Days since first entry | 3 (calendar) / 1 (trading) |
| Days to earliest go-live | 25 calendar days |

---

## Most-actionable still-open signal (this snapshot)

**DT (Dynatrace) LONG — entry pending Mon 5/11 open.**
- 6th consecutive report flag (5/4, 5/5, 5/6, 5/7, 5/9, 5/10).
- Backtest hit rate on this name: 4-of-4 prior windows. Avg +4.3% per window in backtest.
- 5/10 Term Report score +6.50 — the highest weekly mention strength in the entire batch of 3 reports.
- IBKR-clean, optionable, US-listed. T+5 exit = 5/18 close.
- Sole conviction-multiplier in the queue: same name, same direction, repeated for 6 consecutive runs is the strongest signal-stability marker we have.

Runner-up: **CCL/RCL paired short** — first time the cruise-sector sentiment thesis was upgraded from NEUTRAL to SHORT, mirrors backtest pattern where 5/6 NCLH/RCL/CCL shorts hit 3-of-3 on hantavirus catalyst.

---

## Cross-references

- Backtest basis: `~/puc-trading/trades/agti/agti-backtest-2026-05-08.md`
- Daily files: `daily/2026-05-08.md`, `daily/2026-05-09.md`, `daily/2026-05-10.md`
- Exit rules: `exit-rules.md`
- README: `README.md`
