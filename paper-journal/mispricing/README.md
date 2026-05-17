# mispricing-screen paper-trade bucket

Paper book for the two-bucket mispricing-screen options strategy.
Built 2026-05-17 against the live convergence-latest.json + catalyst
calendar pipeline.

## Why this exists

The trend-corpus pipeline produces a daily 14-theme convergence ranking
of 108 tickers. The mispricing-screen layer on top of that asks: given
our thesis conviction, what is the **market** pricing for the next
catalyst window, and where is the gap big enough to trade?

Two buckets:

| bucket | horizon | shape | sizing | exit |
|---|---|---|---|---|
| **income** | 0-90d to dated catalyst | ATM/near-ATM directional (calls, spreads, straddles around dated events) | 1-2% of options book / trade; max 15 concurrent | +50% gain target OR 1 day pre-catalyst OR -50% stop |
| **lottery** | 12-24mo out | OTM long calls / LEAPS on theme keystones | $200-$400 / ticket; max 20 tickets | hold to expiry-week OR -70% stop OR thesis-break |

Book size: $10,000 paper. Income budget: $6,000 (60%). Lottery budget:
$4,000 (40%). Total ticker exposure (income + lottery) capped at 5%
of book = $500.

## Structure

```
paper-journal/mispricing/
  README.md             ← you are here
  exit-rules.md         ← deterministic stops/takes/time-stops
  tracker.md            ← master open/closed positions table + stats
  positions.json        ← runtime state (open positions)
  closed.json           ← runtime state (closed positions)
  daily/
    YYYY-MM-DD.md       ← per-day ticket: NEW INCOME / NEW LOTTERY / CLOSE / HOLD
```

## How to read

`tracker.md` is the source of truth. Three tables:

1. **Open positions** — bucket / ticker / structure / strike / expiry /
   qty / cost / mark / %p&l, sorted by entry date.
2. **Closed positions (last 30)** — every closure with reason + p&l.
3. **Go-live gate progress** — counter toward the 30-trade / 30-day
   threshold before live execution unlocks.

`daily/<DATE>.md` is the audit trail. Each day's file lists the
recommendations the system generated (NEW), the exits triggered
(CLOSE), and the held positions (HOLD).

## Conventions

- **Entry**: paper entry at the day's mid-of-bid-ask on the chosen
  expiry/strike. Filled same-day if recommended pre-market;
  next-trading-day-open if recommended after close.
- **Mark**: cached from the daily chain snapshot. Refreshed each day at
  16:30 ET (post-market close).
- **Direction-agnostic for income**: long calls, long puts, straddles,
  spreads. Direction follows mispricing detector's classification
  (`mispriced_up` for bullish skew; deferred for bearish until corpus
  carries direction-tagged claims).
- **Lottery is long-only**: per operator decision. Deep-OTM calls or
  LEAPS at ~delta 0.20-0.30; without IB greeks we approximate via
  spot × 1.30 strike.
- **Hard caps**: $500 / ticker, $200 / income-trade, $400 / lottery-ticket.

## Cron updates

Daily 16:30 ET on the orchestration box:
1. `mispricing/ib_chain.py` -- refresh option chains for all 108
   convergence tickers (IB Gateway preferred; yfinance fallback).
2. `mispricing/detector.py` -- screen against catalyst calendar; emit
   `mispricing/screens/screen-YYYY-MM-DD.json`.
3. `mispricing/shaper.py` -- two-bucket sizing.
4. `mispricing/tickets.py` -- write `paper-journal/mispricing/daily/YYYY-MM-DD.md`.
5. `mispricing/paper_executor.py` -- evaluate exits, settle book,
   rewrite tracker.md.
6. `mispricing/morning_brief.py` -- 06:00 ET Telegram digest.

`scripts/refresh-mispricing.sh` orchestrates all six steps.

## Go-live gate

Paper-only until BOTH:
- **30 closed trades** in the tracker (denominator for hit rate)
- **30 calendar days** since first open

Pass criterion (informal): closed-trade book p&l > 0 net of slippage
assumption. The hit-rate threshold from agtico (55% on directional)
doesn't apply directly because most income trades here are spreads or
straddles (not directional); use mean-reverting p&l math instead.

If we hit 30 closed trades with negative p&l, that's data -- pause,
re-examine the thesis-implied-move heuristic, don't go live.

## What's NOT in this book

- Direct foreign equities (Insilico 2018.HK, Idemitsu 5019.T, Mitsui
  5706.T, Samsung 006400.KS, SK 096770.KS, LG 373220.KS, Toyota TM is
  the only TSE name with US ADR). Document gaps in daily ticket.
- Private-entity signals (Anduril, Lightmatter, Ayar Labs, Neuralink,
  Altos, Figure AI, etc.). Listed in catalyst calendar with `tickers:
  []`; tracked for indirect reprice but no position.
- Macro-proxy positions (TLT, BNO, XLE-class). Out of scope; agtico
  bucket handles those.

## Source attribution

- Convergence data: `~/puc-trading/corpus/convergence-latest.json`
  (refreshed daily by `~/trend-corpus/scripts/refresh-convergence.sh`)
- Catalyst calendar: `~/puc-trading/calendar/catalysts.yaml`
- Options chain: IB Gateway 4002 (primary), yfinance (fallback)
- Mark refresh: yfinance daily close
- Plan reference: `~/trend-corpus/ops/runbooks/mispricing-screen-plan.md`
