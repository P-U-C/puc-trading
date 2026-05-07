# The Profound Round Robin Trade — SoftBank SOTP Rerate

> "After ARM and SoftBank Corp. are hedged at market value, SoftBank's residual market capitalization is below the marked OpenAI stake value; this is the core SOTP setup." — AGTI Intelligence Report, 2026-05-02

## Thesis

SoftBank Group (9984) carries the cleanest public-market exposure to private OpenAI rerating. After marking ARM and SoftBank Corp. at public prices, the residual equity value is *below* the marked OpenAI stake — meaning the market is implicitly assigning **zero positive incremental value** to the OpenAI position. Historical analog: 2014 SoftBank/Alibaba pre-IPO setup, where the stock aggressively rerated on a sum-of-the-parts basis before the IPO printed.

Three mechanical catalysts compress the window:

1. **Vision Fund 2 OpenAI tranche schedule** — $30B follow-on split into three $10B tranches: April 2026 (closed, $10B drawn from $40B March bridge), **July 2026**, **October 2026**. Each tranche is a "still buying" signal that anchors valuation expectations.
2. **OpenAI public visibility** — OpenAI weekly 2x progress claim, Codex "dramatically better" guidance, ChatGPT/Claude San Francisco search ratio at 2.19x (43% above 90-day trough).
3. **Retail vehicle scarcity** — IBKR adoption by US retail removes the "can't buy foreign stocks" friction. The only public way to own pre-IPO OpenAI exposure remains 9984.

## Structure

Three expressions, choose by execution preference.

**Expression A** is the AGTI Tracker overlay verbatim — equity pair through IBKR.
**Expression B** is the simpler ADR-only version (no futures account needed; takes Nikkei beta).
**Expression C** is the SKM LEAP — separate signal (Anthropic backdoor), included in this file because it derives from the same Profound Round Robin / lab-valuation table.

Total deployment: ~$5,000 across three expressions. Multi-month, equity-and-LEAP, not lottery options.

---

## EXPRESSION A: AGTI Tracker overlay (long 9984.T / short NIYM6)

Direct copy of the on-chain AGTI Tracker Index target: 5% long 9984 JP Equity / -5% NIYM6 (Nikkei 225 mini June 2026 future). Net market exposure: zero. Pure isolation of the SOTP rerate.

### Ticket 1: Long 9984.T — $2,500
- 9984 close 2026-05-05: **¥5,424** (+3.93% on the day, ADR equivalent ~$36.50)
- IBKR routing: `9984` on TSEJ (primary) or buy SFTBY ADR (1 ADR = 0.5 shares of 9984)
- Position: ~46 shares of 9984.T at ¥5,424 = ¥249,500 (~$2,500 USD at ¥100/USD reference)
- Or equivalent: ~68 SFTBY ADR at $18.26 = $1,242 + scale up

### Ticket 2: Short NIYM6 — notional ~$2,500 hedge
- NIYM6 = Nikkei 225 mini June 2026 future, OSE-listed
- Nikkei 225 spot 2026-05-05: **¥59,513**
- One Nikkei 225 mini contract = ¥100 × index = ¥5,951,300 notional (~$59,500). One contract is **too large** for a $2,500 hedge.
- Alternatives:
  - Skip the hedge → use Expression B (ADR-only, takes Nikkei beta)
  - Use the **Nikkei 225 micro future** (Osaka): ¥10 × index = ¥595,000 notional (~$6,000). Still too large.
  - Use **EWJ short** (iShares Japan ETF) as a synthetic Nikkei hedge — most retail-feasible expression.
  - For a clean institutional-style hedge, scale total position up to ~$30K and short one Nikkei mini.

**Recommendation for retail $2,500 sizing: skip the futures hedge and run Expression B unhedged. The hedge gets meaningful only at $25K+ total deployment.**

### Invalidation
- 9984 below ¥4,500 with no SoftBank-specific bad news (Nikkei pulling it down) → trim, the SOTP gap closed via Nikkei drawdown rather than 9984 rerate.
- 9984 below ¥4,500 *with* SoftBank-specific bad news (margin call, OpenAI mark-down, ARM dilution) → exit, thesis broken.
- ARM rallies hard (>$280) without 9984 keeping pace → SOTP gap widens further, *add* on the long.

---

## EXPRESSION B: SFTBY ADR equity-only (no hedge) — $1,500

Simpler exec, fewer accounts, but takes Nikkei beta. Best fit if you don't have a JP-equities-enabled IBKR account or don't want to manage futures.

### Ticket 3: Long SFTBY — $1,500
- SFTBY close 2026-05-05: **$18.26** (+1.33% on the day, vol 506K)
- Position: **82 ADR at $18.26 = $1,497**
- 1 SFTBY ADR = 0.5 shares of 9984.T → economic exposure ~$3,000 underlying
- No options listed on SFTBY, so this is buy-and-hold equity

### Risk frame
- Full loss equivalent: 9984 drawdown to ¥3,000 (-45%) → SFTBY ~$10 → mark $850 (-43%)
- Base case: 9984 to ¥7,000 (+29%) over 3-6 months on Q3 Vision Fund tranche signal → SFTBY ~$23.50 → +29%
- Upside: 9984 to ¥9,000 (+66%, full SOTP closure of the OpenAI implicit zero) → SFTBY ~$30 → +64%

### Invalidation
Same as Expression A. Add: SFTBY ADR ratio change or delisting → switch to direct 9984 on TSE.

---

## EXPRESSION C: SKM LEAP — Anthropic backdoor — $1,000

Separate signal from the same source post: SK Telecom holds an Anthropic stake (~0.58% base assumption per AGTI report). At a $900B Anthropic mark, that's $5.2B / 36.8% of SKM market cap.

**Caveats from the source post (do not skip these):**
- Stake percentage is the whole trade. Press-reported sensitivities now run as low as 0.30%, which would make SKM look much less optically cheap.
- SKT trades 6.33x EV/EBITDA vs KT/LG Uplus at 3.67x — an unadjusted **72% premium to Korean telco peers**. The Anthropic option is already partially priced in.
- Korean holdco discount, dilution, and stake-location uncertainty are all live risks.

This is **a levered look-through trade with governance risk**, sized as such.

### Ticket 4: SKM Jan 16, 2027 $45C — $1,000
- SKM spot 2026-05-05: **$37.80** (+3.62% on the day)
- 2027-01-15 $45C: bid **$5.80** / ask **$6.10** / last $5.90 / IV 66.8% / OI 2,274
- Buy 2 contracts at mid (~$5.95) = **$1,190**, or 1 contract = $595 + add on dip
- Strike is 19% OTM. 255 days to expiry.
- Catalyst: Anthropic next-round print at $900B (already reported as in motion per Bloomberg). Public confirmation forces SKM look-through repricing.
- FULL LOSS: SKM stays below $45 → lose $1,190
- WIN at $50 (Anthropic recognition): contract worth ~$8 → $1,600 (+34%)
- HOME RUN at $60 (full Anthropic look-through priced in + Korean holdco discount narrows): contract worth ~$17 → $3,400 (+185%)
- BLOWOUT at $75 (Anthropic IPO listed): contract worth ~$30 → $6,000 (+404%)

### Sizing note
Source post's tone is "the upside is Anthropic optionality and possible recognition; the risk is dilution, stake-location uncertainty, Korean holdco discount, and the fact that the telco multiple has already rerated."

**Read: small position. Don't oversize. 1 contract is the prudent expression.**

---

## ARM short — explicit deferral

The source post discusses an ARM short as a "purity leg" to the 9984 long, but explicitly: *"given ARM's underperformance of the broader semiconductor sector by more than 70 percentage points over the past year in our price tape, we are not in a rush to put that leg of the trade on."*

ARM 2026-05-05 close: **$208.84** (+2.75%).

**Decision: do not put the leg on now.** Re-evaluate if ARM rallies above $260 (closes 30% of the YoY gap to SMH) — at that point the underperformance argument inverts and the purity hedge becomes attractive.

---

## Total deployment summary

| Ticket | Instrument | Direction | Size | Time horizon |
|--------|-----------|-----------|------|--------------|
| 1 | 9984.T | Long | $2,500 | 6-12 months |
| 2 | NIYM6 hedge | Short | (skip retail / scale to $25K+) | 6-12 months |
| 3 | SFTBY ADR (alt to 1+2) | Long | $1,500 | 6-12 months |
| 4 | SKM Jan'27 $45C | Long | $1,000-$1,200 | 9 months to expiry |

If picking one expression: **3 + 4 = $2,500 retail-feasible setup**. If running the full overlay at retail scale, **1 unhedged + 4 = $3,500**. Institutional ($25K+): **1 + 2 hedged + 4**.

---

## Missed-execution / What-If P&L — 2026-05-07

Trade was written 2026-05-05 from the AGTI Tracker post (2026-05-02). Chad did not execute. Marking what the book would have done if any expression had been opened at 2026-05-05 close.

### Underlying moves (2026-05-05 close → 2026-05-07 close)

| Asset | 2026-05-05 | 2026-05-07 | Move |
|-------|-----------:|-----------:|-----:|
| 9984.T | ¥5,424 | ¥6,213 | **+14.55%** |
| SFTBY ADR | $18.26 | $19.88 | **+8.87%** |
| Nikkei 225 | 59,513 | 62,721 | +5.39% |
| SKM | $37.80 | $36.88 | -2.43% |
| ARM (deferred-short reference) | $208.84 | $237.30 | +13.63% |

### Expression P&L

| Expression | Cost | Now | P&L | % |
|------------|-----:|----:|----:|--:|
| A — 9984.T long / NIYM6 short hedged pair | $2,500 | $2,614 | **+$114** | +4.6% on gross (hedge isolates SOTP spread) |
| B — SFTBY ADR equity (82 shares) | $1,497 | $1,630 | **+$133** | **+8.9%** |
| C — SKM Jan'27 $45C (2 contracts at $5.95 mid) | $1,190 | $1,100 | -$90 | -7.6% (theta + SKM stall) |
| Combined retail (B + C) | $2,687 | $2,730 | +$43 | +1.6% |

### Reads

- **B alone is the trade.** The unhedged SFTBY ADR equity move (+8.87% in 2 days on $1,497) was the cleanest expression and the one this file flagged as highest conviction. The SKM leg stalled — it needs an Anthropic-specific catalyst (next-round print, listing rumor) and got none.
- **Expression A captured the spread, not the rally.** The hedged 9984/NIYM6 pair returned +4.6% gross on the SOTP spread — exactly what the AGTI Tracker overlay was designed to isolate. It's working as specified, but the unhedged thesis (long 9984 alone) returned 3x as much in absolute terms because the broader Nikkei rally added beta.
- **The ARM short deferral was correct.** ARM ripped +13.63% over the same window. The deferred-short logic ("ARM has underperformed semis 70pp YoY, not in a rush to short") would have given back ~13.6% of its notional — roughly canceling the long leg. Don't second-guess that decision in future SOTP setups.

### Lessons applied for the next setup

1. When the AGTI Tracker overlay says "5% long X / -5% short Y" but the trade is fundamentally directional on X, the unhedged version of X often beats the hedged pair in absolute return. Decide whether you want the spread or the directional rerate before sizing.
2. Anthropic-backdoor LEAPs (SKM-style) need a specific catalyst window, not a passive multi-month hold. Reconsider sizing only when an Anthropic round / listing event is in the next 30-60 days.
3. Foreign-equity speed-to-execution matters. SFTBY ADR is the lowest-friction US-listed expression. If the JP-equity-enabled IBKR account isn't already configured, default to ADR so the trade is one click away the next time the signal fires.

---

## Source attribution

- AGTI Intelligence Report 2026-05-02 — "The Profound Round Robin: A Peer-Judged Frontier Model Tape"
- AGTI Tracker Index pft.snap.78a8c0f6ee03b44f3b6f9278d92223d0 (90% BOXX / 5% 9984 / -5% NIYM6 sleeve)
- IPFS CID: bafkreicmq5vzzy4zokbdiplc6syvv7whxdvqymgsku3smbik22kct7yy2u
- PFTL pub: 5A335D82B0...5D905078 (semantic_kind=INDEX, pf.ptr:v4)
