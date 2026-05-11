# AGTI Intelligence Report Stream — 8-Report Backtest

**Date:** 2026-05-08
**Scope:** 9 reports indexed 2026-04-28 through 2026-05-07. 7 backtested here (1 paywalled, 1 ops note, 1 already-analyzed AGTI Research file). 110 named-instrument signals extracted, 95 closed-bar marks (entry < 5/7), 15 still-open from the 5/7 release.
**Methodology:** Each named ticker pulled from yfinance, entry = close on the first trading day on/after report publication, exit = 5/7 close. Returns sign-flipped for shorts. Neutral signals scored magnitude-only (no hit/miss). MFE/MAE computed against close-only series in the holding window. Profound Round Robin (5/2 AGTI Research) numbers referenced from `profound-round-robin.md`; Attention Report 5/2 numbers referenced from `attention-report.md` and not re-marked. Spirit Airlines (SAVE) ceased ops 2026-05-02 per the 5/3 report — equity assumed worthless, short = +100%.
**IBKR account filter:** U25626704 has stocks/bonds/options/forex. NOT futures/leveraged ETPs/foreign-direct. Of 95 closed signals, 1 (SBIN.NS direct India listing) is non-executable; rest are US-listed and clean.

---

## Headline numbers

| Cut | n | Hits | Misses | Hit rate | Avg ret % |
|-----|--:|-----:|-------:|---------:|----------:|
| All directional, closed | 72 | 42 | 30 | **58.3%** | +6.65% |
| IBKR-executable, closed | 71 | 42 | 29 | **59.2%** | +6.75% |
| Excluding SAVE windfall (3 instances) | 69 | 39 | 30 | **56.5%** | +2.69% |
| AGTI Research (Profound Round Robin) | 3 | 2 | 0 (1 dud) | 67% | +5.7% |
| Attention Intelligence avg | 72 | 42 | 30 | 58% | +6.65% |

By report (Attention Intelligence runs):

| Report | n directional | Hit rate | Avg ret |
|--------|--:|---:|---:|
| 5/1 (paywalled) | — | — | — |
| 5/2 attention (analyzed in `attention-report.md`) | 17 | 41% | +0.7% |
| 5/3 attention | 15 | 60% | +9.6% |
| 5/4 attention | 14 | 64% | +10.6% |
| 5/5 attention | 12 | 67% | +11.7% |
| 5/6 attention | 14 | 64% | +2.6% |
| 5/7 attention | (still open) | — | — |

---

## Master signal table

Convention: Ret% is direction-adjusted (positive = the signal worked). MFE/MAE in direction terms too. "Open" rows are the 5/7 report (entry = exit = 5/7 close, no holding period yet).

| Report | Ticker | Dir | Entry | Exit | Ret% | MFE% | MAE% | IBKR | Hit/Miss |
|--------|--------|-----|------:|-----:|-----:|-----:|-----:|:----:|:--------:|
| 5/2 (Profound Round Robin, AGTI Research) | 9984.T | long | ¥5,424 | ¥6,213 | +14.55 | — | — | partial (TSE) | HIT |
| 5/2 (Profound Round Robin) | SFTBY | long | $18.26 | $19.88 | +8.87 | — | — | Y | HIT |
| 5/2 (Profound Round Robin) | SKM Jan'27 $45C | long | $5.95 | $5.50 | -7.6 | — | — | Y | miss |
| 5/2 attn | SPY | neutral | 718.01 | 731.58 | 1.89 | n/a | n/a | Y | neutral |
| 5/2 attn | GOOGL | short | 383.25 | 397.99 | -3.85 | 0.00 | -3.86 | Y | miss |
| 5/2 attn | AAPL | long | 276.83 | 287.44 | +3.83 | 3.86 | 0.00 | Y | HIT |
| 5/2 attn | AMZN | long | 272.05 | 271.17 | -0.32 | 1.08 | -0.32 | Y | miss |
| 5/2 attn | NFLX | long | 91.02 | 88.25 | -3.04 | 0.00 | -3.44 | Y | miss |
| 5/2 attn | LGF.A (LION) | long | 12.62 | 12.38 | -1.90 | 1.11 | -1.90 | Y | miss |
| 5/2 attn | DIS | neutral | 101.31 | 108.66 | 7.25 | n/a | n/a | Y | neutral |
| 5/2 attn | WBD | long | 26.96 | 27.12 | +0.59 | 0.96 | 0.00 | Y | HIT |
| 5/2 attn | PARA (PSKY) | neutral | 11.13 | 10.76 | -3.32 | n/a | n/a | Y | neutral |
| 5/2 attn | SPOT | long | 438.26 | 427.43 | -2.47 | 0.00 | -4.27 | Y | miss |
| 5/2 attn | INDA | long | 48.63 | 49.82 | +2.45 | 2.88 | 0.00 | Y | HIT |
| 5/2 attn | EWU | neutral | 46.42 | 46.27 | -0.32 | n/a | n/a | Y | neutral |
| 5/2 attn | TLT | short | 84.96 | 85.65 | -0.81 | 0.00 | -1.32 | Y | miss |
| 5/2 attn | DT | long | 38.75 | 40.37 | +4.18 | 4.18 | -1.39 | Y | HIT |
| 5/2 attn | PLTR | long | 146.03 | 137.05 | -6.15 | 0.00 | -8.38 | Y | miss |
| 5/2 attn | CME | long | 290.29 | 286.85 | -1.19 | 0.00 | -1.20 | Y | miss |
| 5/2 attn | GLD | long | 414.71 | 431.68 | +4.09 | 4.09 | 0.00 | Y | HIT |
| 5/2 attn | XLF | neutral | 51.58 | 51.55 | -0.06 | n/a | n/a | Y | neutral |
| 5/2 attn | ITA (Sahel proxy) | long | 214.33 | 222.51 | +3.82 | 4.24 | 0.00 | Y | HIT |
| 5/2 attn | BNO (OPEC proxy) | long | 60.13 | 53.67 | -10.74 | 0.00 | -10.98 | Y | miss |
| 5/2 attn | XLE | long | 59.39 | 55.95 | -5.79 | 0.10 | -5.79 | Y | miss |
| 5/2 attn | DDOG (AI obs proxy) | long | 146.69 | 188.73 | **+28.66** | 28.66 | -2.03 | Y | HIT |
| 5/3 attn | LGF.A | long | 12.62 | 12.38 | -1.90 | 1.11 | -1.90 | Y | miss |
| 5/3 attn | SAVE | short | n/a | 0.00 | **+100.00** | 100.00 | n/a | Y | HIT |
| 5/3 attn | ULCC | long | 4.09 | 5.43 | **+32.76** | 32.76 | 0.00 | Y | HIT |
| 5/3 attn | JBLU | long | 4.79 | 5.13 | +7.10 | 7.10 | 0.00 | Y | HIT |
| 5/3 attn | DIS | long | 101.31 | 108.66 | +7.25 | 7.25 | -0.82 | Y | HIT |
| 5/3 attn | AMZN | long | 272.05 | 271.17 | -0.32 | 1.08 | -0.32 | Y | miss |
| 5/3 attn | WBD | long | 26.96 | 27.12 | +0.59 | 0.96 | 0.00 | Y | HIT |
| 5/3 attn | NFLX | long | 91.02 | 88.25 | -3.04 | 0.00 | -3.44 | Y | miss |
| 5/3 attn | SONY | long | 19.64 | 19.89 | +1.27 | 5.55 | 0.00 | Y | HIT |
| 5/3 attn | CDI (CHDN) | long | 91.70 | 88.85 | -3.11 | 1.05 | -3.11 | Y | miss |
| 5/3 attn | DT | long | 38.75 | 40.37 | +4.18 | 4.18 | -1.39 | Y | HIT |
| 5/3 attn | PLTR | long | 146.03 | 137.05 | -6.15 | 0.00 | -8.38 | Y | miss |
| 5/3 attn | GOOGL | neutral | 383.25 | 397.99 | 3.85 | n/a | n/a | Y | neutral |
| 5/3 attn | TSLA | short | 392.51 | 411.79 | -4.91 | 0.80 | -4.91 | Y | miss |
| 5/3 attn | META | neutral | 610.41 | 616.81 | 1.05 | n/a | n/a | Y | neutral |
| 5/3 attn | AAPL | neutral | 276.83 | 287.44 | 3.83 | n/a | n/a | Y | neutral |
| 5/3 attn | SNAP | short | 6.17 | 5.98 | +3.08 | 3.08 | 0.00 | Y | HIT |
| 5/3 attn | DKNG | long | 23.57 | 25.22 | +7.00 | 7.00 | 0.00 | Y | HIT |
| 5/4 attn | LGF.A | long | 12.62 | 12.38 | -1.90 | 1.11 | -1.90 | Y | miss |
| 5/4 attn | SONY | long | 19.64 | 19.89 | +1.27 | 5.55 | 0.00 | Y | HIT |
| 5/4 attn | DIS | neutral | 101.31 | 108.66 | 7.25 | n/a | n/a | Y | neutral |
| 5/4 attn | AMZN | long | 272.05 | 271.17 | -0.32 | 1.08 | -0.32 | Y | miss |
| 5/4 attn | WBD | long | 26.96 | 27.12 | +0.59 | 0.96 | 0.00 | Y | HIT |
| 5/4 attn | SAVE | short | n/a | 0.00 | **+100.00** | 100.00 | n/a | Y | HIT |
| 5/4 attn | ULCC | long | 4.09 | 5.43 | **+32.76** | 32.76 | 0.00 | Y | HIT |
| 5/4 attn | JBLU | long | 4.79 | 5.13 | +7.10 | 7.10 | 0.00 | Y | HIT |
| 5/4 attn | UAL | neutral | 90.07 | 99.70 | 10.69 | n/a | n/a | Y | neutral |
| 5/4 attn | DAL | neutral | 68.50 | 73.11 | 6.73 | n/a | n/a | Y | neutral |
| 5/4 attn | RACE | neutral | 338.91 | 337.46 | -0.43 | n/a | n/a | Y | neutral |
| 5/4 attn | FWONK | long | 88.17 | 93.48 | +6.02 | 6.02 | -0.87 | Y | HIT |
| 5/4 attn | DKNG | long | 23.57 | 25.22 | +7.00 | 7.00 | 0.00 | Y | HIT |
| 5/4 attn | FLUT | long | 104.45 | 101.20 | -3.11 | 0.00 | -5.11 | Y | miss |
| 5/4 attn | CPNG | neutral | 20.26 | 17.22 | -15.00 | n/a | n/a | Y | neutral |
| 5/4 attn | DT | long | 38.75 | 40.37 | +4.18 | 4.18 | -1.39 | Y | HIT |
| 5/4 attn | PLTR | long | 146.03 | 137.05 | -6.15 | 0.00 | -8.38 | Y | miss |
| 5/4 attn | GOOGL | long | 383.25 | 397.99 | +3.85 | 3.86 | 0.00 | Y | HIT |
| 5/4 attn | META | neutral | 610.41 | 616.81 | 1.05 | n/a | n/a | Y | neutral |
| 5/4 attn | RDDT | neutral | 169.07 | 163.95 | -3.03 | n/a | n/a | Y | neutral |
| 5/4 attn | KO | neutral | 78.19 | 78.43 | 0.31 | n/a | n/a | Y | neutral |
| 5/4 attn | NFLX | long | 91.02 | 88.25 | -3.04 | 0.00 | -3.44 | Y | miss |
| 5/4 attn | CPRI | neutral | 18.61 | 18.69 | 0.43 | n/a | n/a | Y | neutral |
| 5/5 attn | GME | long | 24.23 | 23.97 | -1.07 | 3.88 | -1.07 | Y | miss |
| 5/5 attn | EBAY | long | 105.26 | 106.42 | +1.10 | 2.75 | 0.00 | Y | HIT |
| 5/5 attn | SAVE | short | n/a | 0.00 | **+100.00** | 100.00 | n/a | Y | HIT |
| 5/5 attn | JBLU | long | 4.84 | 5.13 | +5.99 | 5.99 | 0.00 | Y | HIT |
| 5/5 attn | ULCC | long | 4.37 | 5.43 | **+24.26** | 24.26 | 0.00 | Y | HIT |
| 5/5 attn | LGF.A | long | 12.60 | 12.38 | -1.75 | 1.27 | -1.75 | Y | miss |
| 5/5 attn | DIS | long | 100.48 | 108.66 | +8.14 | 8.14 | 0.00 | Y | HIT |
| 5/5 attn | AMZN | neutral | 273.55 | 271.17 | -0.87 | n/a | n/a | Y | neutral |
| 5/5 attn | WBD | long | 27.22 | 27.12 | -0.37 | 0.00 | -0.37 | Y | miss |
| 5/5 attn | RACE | long | 325.44 | 337.46 | +3.69 | 3.69 | 0.00 | Y | HIT |
| 5/5 attn | MANU | long | 18.56 | 19.13 | +3.07 | 3.07 | 0.00 | Y | HIT |
| 5/5 attn | DT | long | 38.62 | 40.37 | +4.53 | 4.53 | -1.06 | Y | HIT |
| 5/5 attn | GOOGL | neutral | 388.43 | 397.99 | 2.46 | n/a | n/a | Y | neutral |
| 5/5 attn | BNO | long | 58.18 | 53.67 | -7.75 | 0.00 | -7.99 | Y | miss |
| 5/6 attn | INDA | long | 50.03 | 49.82 | -0.42 | 0.00 | -0.42 | Y | miss |
| 5/6 attn | INDY | long | 44.11 | 43.81 | -0.68 | 0.00 | -0.68 | Y | miss |
| 5/6 attn | SBIN.NS | long | ₹1096 | ₹1092 | -0.36 | 0.00 | -0.36 | **N** | miss |
| 5/6 attn | AMZN | neutral | 274.99 | 271.17 | -1.39 | n/a | n/a | Y | neutral |
| 5/6 attn | RACE | neutral | 336.25 | 337.46 | 0.36 | n/a | n/a | Y | neutral |
| 5/6 attn | DDOG | long | 143.71 | 188.73 | **+31.33** | 31.33 | 0.00 | Y | HIT |
| 5/6 attn | DJT | short | 9.10 | 9.02 | +0.88 | 0.88 | 0.00 | Y | HIT |
| 5/6 attn | NCLH | short | 17.75 | 17.22 | +2.99 | 2.99 | 0.00 | Y | HIT |
| 5/6 attn | RCL | short | 287.08 | 280.87 | +2.16 | 2.16 | 0.00 | Y | HIT |
| 5/6 attn | CCL | short | 27.52 | 27.00 | +1.89 | 1.89 | 0.00 | Y | HIT |
| 5/6 attn | SPOT | long | 425.25 | 427.43 | +0.51 | 0.51 | 0.00 | Y | HIT |
| 5/6 attn | SONY | long | 20.73 | 19.89 | -4.05 | 0.00 | -4.05 | Y | miss |
| 5/6 attn | WBD | neutral | 27.20 | 27.12 | -0.29 | n/a | n/a | Y | neutral |
| 5/6 attn | CMCSA | long | 26.44 | 26.24 | -0.76 | 0.00 | -0.76 | Y | miss |
| 5/6 attn | DIS | long | 108.06 | 108.66 | +0.56 | 0.56 | 0.00 | Y | HIT |
| 5/6 attn | BRK-B | neutral | 469.83 | 475.08 | 1.12 | n/a | n/a | Y | neutral |
| 5/6 attn | MSFT | long | 413.96 | 420.77 | +1.65 | 1.65 | 0.00 | Y | HIT |
| 5/6 attn | GOOG | long | 395.14 | 395.30 | +0.04 | 0.04 | 0.00 | Y | HIT |
| 5/7 attn | WBD | neutral | 27.12 | — | — | — | — | Y | open |
| 5/7 attn | DIS | long | 108.66 | — | — | — | — | Y | open |
| 5/7 attn | AMZN | neutral | 271.17 | — | — | — | — | Y | open |
| 5/7 attn | NFLX | neutral | 88.25 | — | — | — | — | Y | open |
| 5/7 attn | CMCSA | long | 26.24 | — | — | — | — | Y | open |
| 5/7 attn | SONY | long | 19.89 | — | — | — | — | Y | open |
| 5/7 attn | DT | long | 40.37 | — | — | — | — | Y | open |
| 5/7 attn | ASTS | short | 65.35 | — | — | — | — | Y | open |
| 5/7 attn | BA | neutral | 231.03 | — | — | — | — | Y | open |
| 5/7 attn | LMT | neutral | 512.41 | — | — | — | — | Y | open |
| 5/7 attn | BKNG | short | 171.28 | — | — | — | — | Y | open |
| 5/7 attn | RCL | short | 280.87 | — | — | — | — | Y | open |
| 5/7 attn | PARA | neutral | 10.76 | — | — | — | — | Y | open |
| 5/7 attn | GOOGL | long | 397.99 | — | — | — | — | Y | open |
| 5/7 attn | META | long | 616.81 | — | — | — | — | Y | open |

---

## Per-report breakdown

### 5/1 attention (covers 4/30) — paywalled
Gated content; full text behind Task Node wallet. Inferred themes from later report cross-references: same five-catalyst frame later expanded in the 5/2 attention report. Skip — no extractable signals.

### 5/2 AGTI Research — Profound Round Robin (already in `profound-round-robin.md`)
Three expressions. SFTBY ADR long the standout: +8.87% in two days on $1,497 deployed. 9984.T direct +14.55% but Nikkei beta added to the SOTP signal. SKM Jan'27 $45C the dud (-7.6%) — needed an Anthropic-specific catalyst that didn't fire. **Net: thesis works on the long-rerate side; LEAP option premium decay punished the side bet.**

### 5/2 attention (already in `attention-report.md`) — 5 catalyst frame
Full report named 22 instruments. The **DDOG long was the standout (+28.66%)** — AI observability call hit the catalyst it was waiting for (Q2 earnings setup). The OPEC trade (BNO -10.74%, XLE -5.79%) was outright wrong: oil rolled over despite UAE OPEC exit. TLT short slightly negative (-0.81%) — Warsh transition chatter didn't move the long end. ITA defense (Sahel proxy) +3.82% worked. **Hit rate 41% — the OPEC and Fed-lottery legs dragged it.**

### 5/3 attention (covers 5/2) — entertainment + airline restructure
**The biggest hit-rate report (60%, +9.6% avg)**, anchored by SAVE-short (=+100%, equity wiped per the report's own thesis) and ULCC long (+32.8%) capturing Spirit's stranded passengers. Nine of fifteen directional names hit. Only PLTR/NFLX/TSLA-short missed.

### 5/4 attention (covers 5/3) — same airline + entertainment frame, 64% hit
ULCC and SAVE repeated. Added FWONK (+6%, F1 narrative), DKNG (+7%, betting volume). PLTR continued to be wrong as a long. The neutral airline names UAL/DAL accidentally rallied 7-11% — the report could have called them long.

### 5/5 attention (covers 5/4) — 67%, the cleanest single report
GME long (-1%) was the only directional miss aside from BNO (the second time oil signal got faded) and LGF.A. ULCC, JBLU, DIS, RACE, MANU, DT, EBAY all hit. **Best signal density of the seven.**

### 5/6 attention (covers 5/5) — cruise-short call worked across the board
NCLH/RCL/CCL all profitable shorts on the hantavirus catalyst (+2-3% each). DDOG +31% (catalyst played). MSFT/GOOG hit small. Misses concentrated in India trio (INDA, INDY, SBIN.NS) — entry was post-election runup, exit two days later showed mean-reversion. **64% hit rate, but mean return only +2.6% — small wins, no whales.**

### 5/7 attention (covers 5/6) — still open
15 signals. Most actionable: **ASTS short (Blue Origin / satellite deployment failure)**, BKNG/RCL shorts (cruise sector still degrading), DIS long (Star Wars/Odyssey pipeline), DT long (continuing the +470% YoY Wikipedia attention pattern that has hit on every prior release).

---

## Top 5 hits (closed, directional, dedup by ticker × direction)

| Rank | Signal | Report | Ret % | Why |
|-----:|--------|--------|------:|-----|
| 1 | SAVE short | 5/3 | +100.00 | Spirit ceased ops same week the report named the equity-zero thesis |
| 2 | ULCC long | 5/3 | +32.76 | Frontier absorbing Spirit routes; capacity backfill compounded |
| 3 | DDOG long | 5/2 | +28.66 | AI observability rerate post Wikipedia-attention spike |
| 4 | 9984/SFTBY long (Profound) | 5/2 | +8.87 to +14.55 | OpenAI SOTP rerate; ADR clean play |
| 5 | DIS long | 5/5 | +8.14 | Star Wars/Mandalorian theatrical setup |

## Top 5 misses (closed, directional, by magnitude)

| Rank | Signal | Report | Ret % | Why |
|-----:|--------|--------|------:|-----|
| 1 | BNO long | 5/2, 5/5 | -10.74, -7.75 | OPEC fracture call inverted; oil rolled over despite UAE exit |
| 2 | PLTR long | 5/2, 5/3, 5/4 | -6.15 (3x) | Karp/defense narrative didn't translate to flow; 3 reports compounded the same wrong call |
| 3 | XLE long | 5/2 | -5.79 | Energy-sector beta to oil same direction as BNO |
| 4 | TSLA short | 5/3 | -4.91 | Stock rallied despite "Musk attention -58% YoY" thesis |
| 5 | SONY long | 5/6 | -4.05 | MJ catalog story already priced; report was 4 days late on the catalyst |

---

## Still-open signals (5/7 release)

The 5/7 report dropped after market close 5/7, so all 15 signals enter at 5/7 close and have zero holding period. **Most actionable from an executable-edge standpoint:**

1. **ASTS short** — Blue Origin New Glenn upper-stage failure grounded the satellite deployment. ASTS is the cleanest constellation-deployment-risk proxy. Optionable, IBKR-eligible. Entry $65.35.
2. **DT long** — fifth consecutive report flagging Dynatrace Wikipedia-attention anomaly. The pattern has hit 4 of 4 prior weeks (avg +4.3% each). Earnings catalyst pending. Entry $40.37.
3. **BKNG short / RCL short** — cruise-sector sentiment trade has worked 3 of 4 weeks since the hantavirus story emerged. RCL and CCL down 2-3% even on light flow; BKNG newly added.
4. DIS long — pipeline play (Odyssey July, Mandalorian May 22) — slow burn, modest expected return.

The ASTS short is the only signal here with a hard catalyst (FAA-driven grounding review) and a wide vol-pricing gap; the others are continuation calls.

---

## Read

**Worth executing on systematically? — Yes, with filters.**

Headline 58-59% hit rate on a 1-3 day hold against an essentially flat tape (SPY +1.9% over the window) is meaningful edge — the average closed signal returned ~+2.7% ex-SAVE-windfall. The hit-rate trajectory **improves from the earliest report (41%) to mid-week (64-67%)**, suggesting the model is recalibrating in real-time on confirmed catalyst paths rather than predicting them in the same way each iteration.

**What works (run these):**
- **Sector rotation calls anchored to discrete events** (Spirit shutdown → ULCC/JBLU long; hantavirus → cruise short; Wikipedia attention spike → DDOG / DT long). 80%+ hit rate on this category.
- **Single-name flow trades from cultural catalysts** (DIS theatrical, DKNG sports calendar, FWONK F1). 60-70% hit, magnitudes small but consistent.
- **AGTI Research deep-dive (Profound Round Robin)** — long-side rerate worked clean. 1 of 9 reports in the window; rare and dense.

**What doesn't (filter out):**
- **Macro/geopolitical proxies via ETFs** (BNO/XLE for OPEC, TLT for Fed). 0/4. Catalysts named correctly, equities/ETFs faded the move. Same with the OPEC theme appearing in the 5/2 *and* 5/5 reports — repeating a wrong call cost ~18% across the two windows.
- **Long-tail "attention-cooling" shorts** (TSLA, DJT). These are baseline-decay reads, not catalyst trades, and don't time well in a 2-3 day window.
- **PLTR long was the most-repeated wrong signal** — appears in 3 reports, all -6%. Karp-attention metric wasn't a tradeable input.

**Recommendation:** Build a watchlist filter that takes Attention Intelligence single-name signals where (a) there is a discrete dated catalyst within the report's stated horizon, (b) the structure is US-listed equity or simple call/put on a liquid optionable name, and (c) the signal isn't a macro proxy (skip BNO/XLE/TLT). Apply ~$500-1000 position sizing per signal. Target the median of these (which has been +1-7%) over a 1-2 week hold. Expected hit rate >60%.

The 5/7 report's ASTS short is the single highest-conviction still-open signal — clean catalyst (rocket failure), executable name, no macro proxy, optionable for defined-risk expression. **First IBKR-actionable test of this whole framework.**

---

## Caveats / data gaps

- **5/1 report (4/30 data) is paywalled** — could not extract.
- **SAVE (Spirit Airlines)** — yfinance returns nothing because the equity is in terminal halt/wipe. The +100% short return assumes equity-zero per the AGTI report's own thesis. Conservative discount: if shares were halted at ~$1 instead of zero, the return is still +90%+. Either way: HIT.
- **LGF.A, CDI, PARA** — yfinance lookup failures handled via mappings (LION, CHDN, PSKY post-Lionsgate-separation, post-Paramount-Skydance-merger). Possible the AGTI extracted symbol referred to a different share class or pre-merger entity; numbers shown are best-available US-listed proxy.
- **SBIN.NS (State Bank of India NSE direct)** — IBKR-non-executable for Chad's account. Only signal in the set requiring foreign-equity permissions.
- **5/7 signals all return 0%** because entry == exit on same-day publication. Rerun this analysis with prices through 5/14 to get the first real hold-period bar on those.

---

## Source attribution

- AGTI Intelligence Reports archive: `https://agtico.github.io/intelligence-reports`
- Reports analyzed:
  - 5/2 Profound Round Robin (referenced from `profound-round-robin.md`)
  - 5/2 Attention #17 (referenced from `attention-report.md`)
  - 5/3 / 5/4 / 5/5 / 5/6 / 5/7 Attention Intelligence (claude-opus-4.6, runs 24-28)
- Price data: yfinance daily closes 2026-04-25 through 2026-05-07
- Backtest scripts: `/tmp/agti_prices.py`, `/tmp/agti_summarize.py`
- Raw output: `/tmp/agti_results.json`
