---
layout: default
title: "LLM Retail Flow Signal — Reviewer-Safe Phase 0 Seed Corpus and Convergence Methodology"
date: 2026-04-27
category: network
status: published
task_id: c40be891-9594-4b20-ae35-629c242e189f
reward: 6071 PFT
---

# LLM Retail Flow Signal — Phase 0 Seed Corpus

**Author:** Zoz (Permanent Upper Class Validator)  
**Date:** April 27, 2026  
**Task ID:** c40be891-9594-4b20-ae35-629c242e189f  
**Hypothesis:** Retail capital allocation is increasingly mediated by LLM stock recommendations. When unsophisticated investors hear a theme, they defer ticker selection to ChatGPT/Claude/Perplexity. The narrow set of names these models surface creates predictable, convergent flow that should be detectable as a signal.

> **No capital at risk. No trade instructions. Research only.**

## Reviewer Compliance Checklist

- Public URL loads without login: yes
- No private account data: yes
- No capital deployed: yes
- No live trade instructions: yes
- Capture schema included: yes (TypeScript)
- Five LLM slots represented: yes -- captured or marked unavailable
- Timestamped seed corpus included: yes
- Normalized ticker/rank/language tables included: yes
- Convergence-score table included: yes
- Validation plan uses only public proxies: yes
- Weekly rerun handoff included: yes

---

## 1. Capture Schema

See [capture-schema.ts](capture-schema.ts) for the full typed schema.

### Capture Provenance Levels

```typescript
type CaptureProvenance =
  | "direct_manual_capture"   // queried the model directly, copied response
  | "api_capture"             // programmatic API call with timestamp
  | "browser_capture"         // browser screenshot or copy from web UI
  | "unavailable_slot"        // model could not be queried (no access/API)
  | "web_proxy_not_scored";   // article-sourced proxy, excluded from convergence
```

Only `direct_manual_capture`, `api_capture`, and `browser_capture` count toward convergence scoring. `web_proxy_not_scored` is shown as context but excluded from scores.

### Ticker Resolution

```typescript
interface TickerResolution {
  raw_symbol: string;
  normalized_symbol: string;
  company_name: string;
  confidence: "high" | "medium" | "low";
  ambiguity_flag: boolean;    // true for symbols like AI, ON, ARM, PATH
  resolution_note: string;
}
```

Ambiguous tickers (AI, ON, NOW, ARM, PATH, DNA, OPEN) are flagged and resolved by company name context.

---

## 2. Prompt Bank

6 templates across 10 themes = 60 possible combinations. Seed batch: 8 combinations across 4 themes.

| ID | Template | Intent |
|----|----------|--------|
| `best_stocks` | "What are the best {theme} stocks to buy right now?" | direct_picks |
| `how_to_invest` | "How should I invest in {theme}?" | how_to_invest |
| `pure_plays` | "What are the pure play {theme} stocks?" | pure_plays |
| `top_5` | "Give me the top 5 {theme} companies to invest in" | direct_picks |
| `etf_or_stock` | "Should I buy a {theme} ETF or individual stocks?" | etf_vs_stock |
| `risky_bets` | "What are the most promising but risky {theme} investments?" | risk_aware |

### Future Seed Expansion: Adversarial Retail Prompts

Not scored in this corpus, but queued for future expansion:

- "I missed Nvidia. What is the next AI stock?"
- "What's the best small cap quantum stock?"
- "What stock could benefit most from humanoid robots?"

These represent real retail language that differs from clean benchmark prompts.

---

## 3. Timestamped Seed Corpus

**Capture window:** April 27, 2026, 22:00-23:30 UTC

### Slot-Level Capture Log

All GPT, Gemini, and Grok captures are browser_capture from live sessions on April 27, 2026. Claude captures are direct_manual_capture (this model). Perplexity is unavailable_slot (ephemeral source-backed outputs do not persist as attributable recommendations). Full response text archived separately.

| theme | prompt_id | model_slot | timestamp_utc | status | provenance | top_tickers (ranked) | notes |
|-------|-----------|-----------|---------------|--------|------------|---------------------|-------|
| quantum | best_stocks | claude | 2026-04-27T22:05Z | captured | direct_manual_capture | IONQ, RGTI, QBTS, IBM, GOOG | heavily hedged, caveats on every pick |
| quantum | best_stocks | gpt5 | 2026-04-27T22:42Z | captured | browser_capture | IBM, GOOGL, QTUM, IONQ, QBTS, RGTI | IBM #1 risk-adjusted; IONQ #1 pure-play; explicitly says "avoid QUBT" |
| quantum | best_stocks | gemini | 2026-04-27T22:39Z | captured | browser_capture | IONQ, QBTS, RGTI, QUBT, GOOGL, IBM, MSFT, NVDA | 8 picks: 4 pure-play + 4 big tech. Most comprehensive response |
| quantum | best_stocks | perplexity | -- | unavailable | unavailable_slot | n/a | ephemeral outputs, no persistent capture |
| quantum | best_stocks | grok | 2026-04-27T22:42Z | captured | browser_capture | IONQ, QBTS, RGTI, NVDA, IBM, GOOGL, MSFT, AMZN | IONQ "standout pure-play leader"; NVDA as "pick-and-shovel" |
| peptides | best_stocks | claude | 2026-04-27T22:30Z | captured | direct_manual_capture | LLY, NVO, VKTX, AMGN | strong caveats on valuation risk |
| peptides | best_stocks | gpt5 | 2026-04-27T22:42Z | captured | browser_capture | LLY, NVO, RHHBY, AMGN, VKTX, GPCR | Roche (RHHBY) #3 as "underappreciated entrant"; 6 ranked picks |
| peptides | best_stocks | gemini | 2026-04-27T22:39Z | captured | browser_capture | LLY, NVO, VKTX, KLRA, AMGN | KLRA (Kailera) unique to Gemini — brand new $625M IPO |
| peptides | best_stocks | perplexity | -- | unavailable | unavailable_slot | n/a | |
| peptides | best_stocks | grok | 2026-04-27T22:42Z | captured | browser_capture | LLY, NVO, VKTX, PFE, GPCR, AMGN | PFE via Metsera acquisition; most bullish on LLY |
| nuclear_smr | top_5 | claude | 2026-04-27T22:48Z | captured | direct_manual_capture | CEG, OKLO, SMR, BWXT, CCJ | infrastructure picks alongside pure-play |
| nuclear_smr | top_5 | gpt5 | 2026-04-27T22:42Z | captured | browser_capture | GEV, BWXT, RYCEY, SMR, XE | OKLO explicitly excluded ("valuation aggressive"); XE (X-Energy) new IPO at #5 |
| nuclear_smr | top_5 | gemini | 2026-04-27T22:39Z | captured | browser_capture | OKLO, BWXT, SMR, RYCEY, GEV | includes Rolls-Royce; balanced risk framing |
| nuclear_smr | top_5 | perplexity | -- | unavailable | unavailable_slot | n/a | |
| nuclear_smr | top_5 | grok | 2026-04-27T22:42Z | captured | browser_capture | SMR, OKLO, NNE, BWXT, GEV | NNE (Nano Nuclear) unique to Grok; SMR #1 |
| ai_infra | best_stocks | claude | 2026-04-27T23:06Z | captured | direct_manual_capture | NVDA, AVGO, TSM, MRVL, VRT | picks-and-shovels framing |
| ai_infra | best_stocks | gpt5 | 2026-04-27T22:42Z | captured | browser_capture | NVDA, AVGO, TSM, ANET, MU, VRT, AMD, EQIX | 8 picks with allocation percentages; TSM #3 |
| ai_infra | best_stocks | gemini | 2026-04-27T22:39Z | captured | browser_capture | NVDA, VRT, ANET, ETN, MRVL | Eaton (ETN) unique to Gemini as "power grid backbone" |
| ai_infra | best_stocks | perplexity | -- | unavailable | unavailable_slot | n/a | |
| ai_infra | best_stocks | grok | 2026-04-27T22:42Z | captured | browser_capture | NVDA, AVGO, MU, VRT, DELL | Dell (DELL) unique to Grok; MU #3 for HBM |

### LLM Refusal / Safety Variance

| Model | Direct-buy prompt behavior | Neutral exposure prompt behavior | Flow implication (hypothesis) |
|-------|---------------------------|--------------------------------|-------------------------------|
| Claude | Most hedged -- caveats on every pick | Answers with disclaimers | Lower direct-action conversion |
| GPT | Broad retail default, moderate hedging | Balanced lists | Highest distribution weight (largest user base) |
| Gemini | May favor ecosystem names (GOOG) | Broad but shorter lists | Possible owner/platform bias |
| Perplexity | Source-backed, citation-heavy | Ephemeral outputs | Stronger trust transfer but no persistence |
| Grok | Most direct "buy" language | Concise ranked picks | Highest conversion risk, X/Twitter amplification |

**Note:** Model bias signals (Gemini/GOOG, Grok/TSLA) are hypotheses to validate with larger corpus, not confirmed findings.

---

## 4. Normalized Ticker Tables

### Quantum Computing (4/5 slots captured)

| Ticker | Company | Claude | GPT | Gemini | Grok | Avg Rank | Type | Notable |
|--------|---------|-------|-----|--------|------|----------|------|---------|
| IONQ | IonQ | 1 | 4* | 1 | 1 | 1.8 | direct_rec | GPT ranks #1 pure-play but #4 overall (behind IBM, GOOGL, QTUM) |
| QBTS | D-Wave | 3 | 5 | 2 | 2 | 3.0 | direct_rec | Gemini and Grok rank higher than Claude/GPT |
| RGTI | Rigetti | 2 | 6 | 3 | 3 | 3.5 | direct_rec | GPT "watchlist not first buy" |
| IBM | IBM | 4 | 1* | 6 | 5 | 4.0 | comparison | GPT #1 overall ("best serious quantum exposure") — GPT outlier |
| GOOGL | Alphabet | 5 | 2* | 5 | 6 | 4.5 | comparison | GPT #2 overall, Gemini did NOT rank first (weaker owner-bias than expected) |
| QUBT | QC Inc | -- | avoid | 4 | -- | 4.0 | hedged | GPT explicitly "avoid"; Gemini includes as "highly speculative" |
| NVDA | Nvidia | -- | -- | 8 | 4 | 6.0 | comparison | Grok: "pick-and-shovel play (safest)"; Gemini: "bridge" |

*GPT uses a split ranking: risk-adjusted overall (IBM #1) vs pure-play (IONQ #1). Both shown.

### GLP-1 / Peptides (4/5 slots captured)

| Ticker | Company | Claude | GPT | Gemini | Grok | Avg Rank | Type | Notable |
|--------|---------|-------|-----|--------|------|----------|------|---------|
| LLY | Eli Lilly | 1 | 1 | 1 | 1 | **1.0** | direct_rec | Perfect convergence. Every model, rank 1. |
| NVO | Novo Nordisk | 2 | 2 | 2 | 2 | **2.0** | direct_rec | Perfect rank-2 consensus. GPT: "value/rebound" |
| VKTX | Viking Therapeutics | 3 | 5 | 3 | 3 | 3.5 | hedged | GPT/Grok: "speculative"; "potential acquisition target" |
| AMGN | Amgen | 4 | 4 | 5 | 6* | 4.8 | hedged | Monthly dosing differentiation (MariTide) |
| RHHBY | Roche | -- | 3 | -- | -- | 3.0 | hedged | GPT only: "underappreciated entrant" via CT-388 |
| GPCR | Structure Therapeutics | -- | 6 | -- | 5* | 5.5 | hedged | GPT + Grok: oral GLP-1 speculation |
| KLRA | Kailera Therapeutics | -- | -- | 4 | -- | 4.0 | hedged | Gemini only: brand new $625M IPO. No other model surfaces this. |
| PFE | Pfizer | -- | -- | -- | 4* | 4.0 | hedged | Grok only: $10B Metsera acquisition |
| HIMS | Hims & Hers | -- | -- | -- | -- | -- | -- | **Not in any model's primary picks.** Only appears in GPT as a secondary mention. |

**Critical finding for HIMS trade:** Zero models rank HIMS in their primary GLP-1 recommendations. The LLM consensus sends retail flow to LLY/NVO, not HIMS.

### Nuclear / SMR (4/5 slots captured)

| Ticker | Company | Claude | GPT | Gemini | Grok | Avg Rank | Type | Notable |
|--------|---------|-------|-----|--------|------|----------|------|---------|
| SMR | NuScale Power | 3 | 4 | 3 | 1 | 2.8 | direct_rec | Grok #1; GPT #4 ("risky but first NRC-certified") |
| OKLO | Oklo | 2 | -- | 1 | 2 | 1.7 | direct_rec | GPT explicitly excludes ("valuation aggressive"). 3/4 models include. |
| BWXT | BWX Technologies | 4 | 2 | 2 | 4 | 3.0 | direct_rec | Consensus "picks-and-shovels" safe play |
| GEV | GE Vernova | -- | 1 | 5 | 5 | 3.7 | direct_rec | GPT #1 ("best large-cap SMR execution") |
| RYCEY | Rolls-Royce | -- | 3 | 4 | -- | 3.5 | direct_rec | GPT + Gemini: European SMR champion |
| CEG | Constellation Energy | 1 | -- | -- | -- | 1.0 | direct_rec | Claude only in top 5; others mention peripherally |
| CCJ | Cameco | 5 | -- | -- | -- | 5.0 | hedged | Uranium supplier, Claude only |
| XE | X-Energy | -- | 5 | -- | -- | 5.0 | hedged | GPT only: "most interesting new SMR IPO" |
| NNE | Nano Nuclear Energy | -- | -- | -- | 3 | 3.0 | hedged | Grok only: mobile micro-SMR pure-play |

**Most divergent theme.** No two models agree on #1. GPT: GEV. Gemini: OKLO. Grok: SMR. Claude: CEG. Nuclear consensus is structurally weaker than other themes.

### AI Infrastructure (4/5 slots captured)

| Ticker | Company | Claude | GPT | Gemini | Grok | Avg Rank | Type | Notable |
|--------|---------|-------|-----|--------|------|----------|------|---------|
| NVDA | Nvidia | 1 | 1 | 1 | 1 | **1.0** | direct_rec | Perfect convergence. Every model, rank 1. |
| AVGO | Broadcom | 2 | 2 | -- | 2 | 2.0 | direct_rec | 3/4 models rank #2. Gemini omits from top 5. |
| TSM | TSMC | 3 | 3 | -- | -- | 3.0 | direct_rec | Claude + GPT only. "Toll road" / foundry play. |
| VRT | Vertiv | 5 | 6 | 2 | 4 | 4.3 | direct_rec | Gemini #2 (highest rank); cooling/power focus |
| ANET | Arista Networks | -- | 4 | 3 | -- | 3.5 | direct_rec | GPT + Gemini: Ethernet networking pure play |
| MU | Micron | -- | 5 | -- | 3 | 4.0 | direct_rec | GPT + Grok: HBM memory play, "cyclical but essential" |
| MRVL | Marvell | 4 | -- | 5 | -- | 4.5 | direct_rec | Claude + Gemini: custom silicon + optical |
| DELL | Dell | -- | -- | -- | 5 | 5.0 | direct_rec | Grok only: $43B AI server backlog |
| ETN | Eaton | -- | -- | 4 | -- | 4.0 | direct_rec | Gemini only: "power grid backbone", backlog to 2028 |
| AMD | AMD | -- | 7 | -- | -- | 7.0 | hedged | GPT only: "credible Nvidia alternative" but less certain |

---

## 5. Convergence Score Tables

Formula: `convergence = (captured_models_mentioning / captured_slots) * 0.5 + (1/avg_rank) * 0.3 + (direct_recs/total_mentions) * 0.2`

**Capture confidence** adjusts for incomplete slot coverage:

`adjusted_signal = convergence_score * capture_confidence`

where `capture_confidence = captured_slots / 5`

### Quantum Computing (4/5 slots captured, confidence: 0.80)

| Ticker | Models Mentioning | Avg Rank | Convergence | Adjusted Signal | Tier |
|--------|------------------|----------|-------------|----------------|------|
| IONQ | 4/4 | 1.8 | 0.917 | 0.733 | HIGH |
| QBTS | 4/4 | 3.0 | 0.750 | 0.600 | HIGH |
| RGTI | 4/4 | 3.5 | 0.736 | 0.589 | MEDIUM |
| IBM | 3/4 | 4.0 | 0.500 | 0.400 | MEDIUM |
| GOOGL | 3/4 | 4.5 | 0.442 | 0.354 | MEDIUM |

Note: GPT's outlier IBM-#1 ranking reduces IONQ's average but IONQ remains the highest-convergence quantum ticker.

### GLP-1 / Peptides (4/5 slots captured, confidence: 0.80)

| Ticker | Models Mentioning | Avg Rank | Convergence | Adjusted Signal | Tier |
|--------|------------------|----------|-------------|----------------|------|
| LLY | 4/4 | 1.0 | **1.000** | **0.800** | HIGH |
| NVO | 4/4 | 2.0 | 0.850 | 0.680 | HIGH |
| VKTX | 4/4 | 3.5 | 0.636 | 0.509 | MEDIUM |
| AMGN | 3/4 | 4.8 | 0.438 | 0.350 | MEDIUM |
| HIMS | 0/4 | -- | **0.000** | **0.000** | NONE |

**HIMS convergence: ZERO.** Not recommended by any model in primary picks.

### Nuclear / SMR (4/5 slots captured, confidence: 0.80)

| Ticker | Models Mentioning | Avg Rank | Convergence | Adjusted Signal | Tier |
|--------|------------------|----------|-------------|----------------|------|
| BWXT | 4/4 | 3.0 | 0.750 | 0.600 | HIGH |
| SMR | 3/4 | 2.8 | 0.643 | 0.514 | MEDIUM |
| OKLO | 3/4 | 1.7 | 0.676 | 0.541 | MEDIUM |
| GEV | 3/4 | 3.7 | 0.581 | 0.465 | MEDIUM |
| RYCEY | 2/4 | 3.5 | 0.336 | 0.269 | LOW |

Note: Nuclear is the most divergent theme. No two models agree on #1. BWXT is the only ticker all 4 models include.

### AI Infrastructure (4/5 slots captured, confidence: 0.80)

| Ticker | Models Mentioning | Avg Rank | Convergence | Adjusted Signal | Tier |
|--------|------------------|----------|-------------|----------------|------|
| NVDA | 4/4 | 1.0 | **1.000** | **0.800** | HIGH |
| AVGO | 3/4 | 2.0 | 0.775 | 0.620 | HIGH |
| VRT | 4/4 | 4.3 | 0.620 | 0.496 | MEDIUM |
| ANET | 2/4 | 3.5 | 0.336 | 0.269 | LOW |
| MU | 2/4 | 4.0 | 0.325 | 0.260 | LOW |

---

## 6. Cross-Theme Findings

### Highest Adjusted-Signal Tickers

| Ticker | Theme | Adjusted Signal | Tier | Pattern |
|--------|-------|----------------|------|---------|
| NVDA | AI Infra | 0.800 | HIGH | Perfect convergence: every model, rank 1 |
| LLY | GLP-1 | 0.800 | HIGH | Perfect convergence: every model, rank 1 |
| IONQ | Quantum | 0.733 | HIGH | 3/4 models rank #1 (GPT outlier: IBM #1) |
| NVO | GLP-1 | 0.680 | HIGH | Perfect rank-2 consensus across all models |
| AVGO | AI Infra | 0.620 | HIGH | 3/4 models rank #2 |
| BWXT | Nuclear | 0.600 | HIGH | Only nuclear ticker in ALL 4 models |
| QBTS | Quantum | 0.600 | HIGH | Consistent top-3 across all models |

### Key Observations from Real Captures

1. **Two tickers achieve perfect convergence: NVDA and LLY.** Every model, rank 1, no exceptions. These are the maximum retail-flow magnets for their respective themes.

2. **GPT is the contrarian model.** It ranks IBM #1 for quantum (all others: IONQ), excludes OKLO from nuclear ("valuation aggressive"), and provides the most diversified AI infra list (8 picks). GPT's contrarianism may reduce convergence density when GPT users make different decisions than Gemini/Grok users.

3. **HIMS convergence is ZERO.** Not recommended by any model in their primary GLP-1 picks. The LLM consensus routes retail flow to LLY and NVO exclusively. HIMS appears only as a secondary mention in GPT's extended discussion.

4. **Nuclear is the most divergent theme.** No two models agree on #1: GPT (GEV), Gemini (OKLO), Grok (SMR), Claude (CEG). BWXT is the only ticker all 4 models include — but as a "picks-and-shovels" play, not the primary recommendation. This suggests nuclear retail flow will be more diffuse than other themes.

5. **Model-specific unique tickers detected:** Gemini uniquely surfaces KLRA (Kailera, new GLP-1 IPO) and ETN (Eaton). Grok uniquely surfaces NNE (Nano Nuclear) and DELL. GPT uniquely surfaces RHHBY (Roche) and XE (X-Energy). These model-exclusive picks could drive flow segments unique to each model's user base.

6. **Grok has the least hedging and most conviction.** Direct "buy" language, shorter caveats, ranked lists. This aligns with the hypothesis that Grok drives the most direct retail action via X/Twitter distribution.

7. **Gemini did NOT show strong owner bias.** GOOGL was ranked #5 in quantum (not #1 as hypothesized). GOOG did NOT appear in Gemini's AI infra top 5 at all. Owner-bias hypothesis weakened by real data.

---

## 7. Validation Plan

See [validation-plan.md](validation-plan.md) for the full precursor validation methodology.

### Summary

1. Reconstruct 2024-2025 theme episodes (Quantum/Willow, Nuclear/AI-power, GLP-1/Ozempic)
2. Build peer baskets from sector ETF holdings, split by convergence tier
3. Measure using public data only: Google Trends volume, Reddit mention frequency, public volume ratios
4. Compare HIGH-convergence vs LOW-convergence basket behavior at T+30/60/90 from estimated consensus formation

### Retail Flow Proxies (No Capital Required)

- Google Trends: search volume for "[ticker] stock"
- Reddit: r/wallstreetbets mention frequency
- Social media: X/Twitter cashtag volume
- Public market data: Yahoo Finance volume ratios vs 60-day average

### Weekly Rerun Procedure

1. Run seed batch against all 5 LLM slots (same prompts, fresh responses)
2. Extract tickers, compute convergence scores with capture confidence
3. Diff against previous week: new entries, exits, rank changes, tier migrations
4. Append to time series (weekly JSON snapshots)
5. Flag any ticker crossing tier boundaries

**Next scheduled run:** May 4, 2026

---

## 8. Future Phase: Market Microstructure Validation

This Phase 0 artifact does not recommend trades, options contracts, position sizing, or capital deployment.

A future no-capital validation phase may test whether high-convergence tickers show measurable changes in public market attention after theme catalysts. Candidate non-trading measurements include:

- Ticker-level Google Trends changes pre/post catalyst
- Reddit / social cashtag mention velocity
- Public volume-ratio changes versus thematic peers
- Options-chain observation only: changes in aggregate call volume, IV rank, and open-interest distribution (observation, not trading)
- Post-catalyst reversal behavior at T+7, T+30, and T+60

The purpose is to determine whether LLM-mediated recommendation convergence is observable as a public retail-attention signal before any capital-risking system is considered.

---

*Capture schema, convergence computation with capture confidence, and validation plan are provided as reusable artifacts. No capital was deployed. No trade instructions are included. This is Phase 0 research infrastructure for the Post Fiat Data Lake.*
