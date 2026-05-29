# Canonical Trading View

**Generated:** 2026-05-29 · **Status:** PAPER on every book. No live capital.

> **Correction log (2026-05-29, post-Chad-directive):** the 13 over-concentrated
> cicadas legs were CUT and archived to `closed.json` (realized −$609.01). The
> screen engine was patched (45-day tenor floor in `detector.py`; per-theme,
> per-catalyst, and max-tickers-per-catalyst caps in `shaper.py` + `__init__.py`;
> 24/24 tests pass). The cicadas book was rebuilt back-dated to 2026-05-19 as the
> corrected engine produces it: **a single FXA call spread, currently +15.7%.**
> AGTI: edge filter added (equity-longs only) + holiday fill-price bug fixed.
> **Key finding below in §3a — the original "edge" was mostly a tenor artifact.**
>
> **Update 2:** thesis-direction reading added to the screen (per Chad). The
> calendar now carries `theme_directions` (e.g. cicadas: FXA/UNG/SOYB = short,
> grains/fertilizer = long); the screen buys PUTS for short legs, CALLS for long.
> This caught that the surviving FXA trade was counter-thesis — it's now a **put
> spread (short AUD), −22.2%**. (The wrong-way call looked +15.7% precisely
> because AUD has risen, i.e. the thesis has been wrong *so far*.) detector→
> shaper→executor→remark all direction-aware; remark now prices put spreads.
> 27/27 tests pass.

This is the single source-of-truth snapshot across every open paper book and
standing thesis. Numbers pulled live from runtime state (`paper-journal/*/`),
not from the stale tracker docs.

---

## 1. Books at a glance

| Book | Engine | Open | Cost basis | Mark | Unrealized | Status |
|------|--------|-----:|-----------:|-----:|-----------:|--------|
| **Mispricing (convergence)** | auto-screen, cron 21:15 | **1 spread (FXA put, short AUD)** | $136 | $106 | **−$30 (−22.2%)** | CUT, rebuilt, direction-corrected |
| **AGTI attention** | auto cron 14:00 | 23 + 15 pending | n/a (notional) | flat | ~0% | healthy loop; now equity-long-only |
| Cicadas (operator) | manual / staged | 0 (not opened) | — | — | — | observation stage |
| UFO / Naval / Profound | manual diary | 0 (not opened) | — | — | — | thesis-only, no fills |

Mispricing realized P&L now **−$578** (the 13 cicadas legs were cut at −$609,
locking the loss that was already on the book; earlier closes were ~$0 expiry
rolls). AGTI **~flat** over 82 closes at a 57% hit rate. §2/§3 below describe the
book *as it was* (pre-cut) — kept for the diagnosis; the correction log up top
and §3a describe the fix.

---

## 2. The −30% book is the mispricing screen — and it's the SAME bet 13 times

Every open mispricing position is one trade wearing 13 tickets:

- **Theme:** `cicadas` (100% of the book)
- **Catalyst:** `cat_noaa_enso_2026_06` — the NOAA CPC ENSO Diagnostic on **2026-06-11** (100%)
- **Underlyings:** WEAT, CORN, DBA, FXA — four *correlated* ag/commodity ETFs
- **Structure:** call spreads, **all expiring 2026-06-18**
- **Entry logic:** thesis-implied move ≫ market-implied move (ratio 1.8–6.6)

| ticker | entries | cost | worst leg | best leg |
|--------|--------:|-----:|----------:|---------:|
| WEAT | 4 | $493 | −64.6% | −15.5% |
| CORN | 3 | $484 | −64.4% | +13.1% |
| DBA  | 3 | $472 | −51.0% | −43.0% |
| FXA  | 3 | $470 | −19.2% | +35.1% |

There is **zero diversification**. The whole book rides one NOAA data release on
one date through four instruments that move together. If 6/11 prints neutral,
all 13 legs expire near-worthless on 6/18 together.

---

## 3. What's going wrong (diagnosis)

The screen is **mechanically misapplying the operator's own cicadas thesis.**
Compare `trades/cicadas.md` (the human thesis) to what the screen actually did:

| Operator thesis (`trades/cicadas.md`) | What the screen bought |
|---|---|
| Tenor **Jul 2026 – Jan 2027** ("harvest convexity before consensus") | **Jun 18 2026** — expires 1 week after the data print |
| 6/11 NOAA print is **Stage-2 *verification***, not a binary payout | Treated 6/11 as a one-shot event-vol catalyst |
| The money is in **Stage 3** (physical-damage prints: WASDE, BOM, IMD) | Book expires *before* any Stage-3 catalyst |
| Stage entries **in thirds**, add only on coupling confirmation | Loaded the full book up-front, 13 legs in 8 days |
| Sleeve capped **6% NAV**, halve at −3% drawdown | One theme = 100% of the book, now −32% |
| "Do not let theta bleed" | Short-dated spreads = pure theta into the print |

**Root cause:** `mispricing/orchestrator.py` fires on `(mispricing ratio ≥ X)
× (nearest catalyst date)` and picks the nearest listed expiry after the
catalyst. It has no concept of the thesis's staging ladder, tenor floor, or
per-theme concentration cap. So a multi-month physics thesis got expressed as a
one-week binary, 13 times over.

Secondary: marks are yfinance-derived (no OPRA sub), so the −32% is a model
mark on illiquid spreads — directionally real (underlyings haven't moved + theta),
but the precise figure is soft.

### 3a. THE finding — the "edge" was a tenor artifact (discovered while patching)

When the corrected engine re-screens the same cicadas names at the *proper*
tenor (Aug–Jan expiries the chain already carried), the mispricing edge mostly
**evaporates**:

| ticker | OLD ratio (6/18 expiry) | CORRECTED ratio (proper tenor) | verdict |
|--------|------------------------:|-------------------------------:|---------|
| FXA  | 3.8–6.6 | **1.71** | still mispriced_up — the only survivor |
| CORN | 2.2–2.6 | 1.23 | **fair** — no edge |
| WEAT | 1.8–2.4 | 0.82 | **fair** — no edge |
| DBA  | 1.8–2.4 | 0.83 | **fair** — no edge |
| MOO/SOYB/SB | — | 0.21–0.54 | **over**priced |

Why: the screen computes edge as `thesis_implied_move / market_implied_move`.
At a 1-week expiry the market-implied move is tiny, so a multi-month thesis move
looks like a 2–6× mispricing. Stretch the expiry to where the move actually has
time to play out and the market-implied move grows — the "mispricing" was the
short tenor, not real underpricing. **The screen was manufacturing fake edge.**
Done correctly, this book barely trades: 1 small FXA spread instead of $1,918
across 13 legs.

Caveat flagged for Chad: FXA long-calls are *bullish AUD*, but `cicadas.md`'s
thesis is **short** AUD/USD (Australia dryness). The one trade the screen keeps
is arguably counter-thesis — the screen has no direction model (assumes upside).
Worth a follow-up decision on whether the screen should read thesis direction.

### Fix candidates (for Chad to pick)
1. **Tenor floor** — screen must buy ≥ 90 DTE (or the thesis's stated tenor
   window), never the expiry that dies the week of the catalyst.
2. **Per-theme / per-catalyst concentration cap** — e.g. ≤ 30% of book in one
   `theme_id`, ≤ 2 correlated underlyings per catalyst.
3. **Honor the staging ladder** — only Stage-1 sizing (30–40%) until coupling
   confirmation flags flip in the cicadas indicator hierarchy.
4. **Drawdown kill-switch** — auto-halve a sleeve at −3%, cap at −6% (already
   written in the thesis, not wired into the screen).

---

## 4. AGTI book — healthy loop, but edge isn't paying

Cron at 14:00 UTC pulls the daily AGTI Intelligence Report, extracts signals,
marks, and applies T+5 / catalyst / stop / take exit rules. Source of truth is
`paper-journal/agti/scripts/positions.json` (124 lifetime, 86 closed, 23 open,
15 pending). The `tracker.md` doc is **stale (frozen 5/10)** — ignore it.

**Go-live gate is technically cleared:** 82 closed ≥ 30, > 4 weeks elapsed,
**57% hit rate ≥ 55% target.** BUT average return is **~flat** — wins and
losses are symmetric and small, so the hit-rate edge isn't converting to P&L.

Where the edge actually lives (closed-trade breakdown):

| Slice | n | hit | avg |
|-------|--:|----:|----:|
| equity | 64 | **62%** | + |
| long | 57 | **63%** | + |
| short | 25 | 44% | − |
| ETF | 13 | 38% | − |
| forex | 5 | 40% | ~0 |

**Takeaway:** the equity-long single-name signals carry the book (62–63% hit).
Shorts, ETFs, and forex are dilutive — same pattern the original backtest
flagged as the "macro-proxy ETF 0-of-4 failure mode." Pruning to equity-longs
would likely lift both hit rate and average return.

**Operational issue:** latest run threw 11 `could not fetch fill price` errors
(DIS, META, CZR, MGM, MANU, EWI, EWU, RDDT, TKO, RACE, DYT) — yfinance ticker
resolution failures leaving signals un-filled. Needs a retry/fallback path.

---

## 5. Standing theses (no capital deployed)

| Thesis | File | One-line | Trigger |
|--------|------|----------|---------|
| **Cicadas** | `trades/cicadas.md` | ENSO → ag supply-elasticity collapse; fertilizer+weather+policy are one trade | Stage-2 coupling confirm (Jun–Jul); 6/11 NOAA, 6/12 WASDE |
| **UFO disclosure** | `trades/ufo-disclosure.md` | Trump file-drop → attention flow into UFOD ETF holdings (small-caps AMTM/AMSC) | File release event |
| **Naval / SaaSpocalypse** | `trades/naval-thesis.md` | AI agents commoditize software; value migrates SaaS→hardware/data/network | Earnings-wave confirmation |
| **Profound Round Robin** | `trades/agti/profound-round-robin.md` | SoftBank (9984) SOTP rerate — residual mkt-cap below marked OpenAI stake | VF2 OpenAI tranches Jul/Oct 2026 |

---

## 6. Recommended next actions

1. **Mispricing:** stop the screen from adding to cicadas; decide whether to let
   the 13 legs ride to 6/11 or cut now. Then patch the screen (tenor floor +
   concentration cap) before it does this on the next theme.
2. **AGTI:** prune the signal filter to equity-longs (drop ETF/forex/short
   classes); fix the yfinance fill-price fallback. Gate is cleared on the
   metrics that matter — the question is whether flat avg-return is good enough
   to risk live capital, or whether the prune comes first.
3. Keep cicadas/UFO/Naval/Profound as documented theses; none need action today.
