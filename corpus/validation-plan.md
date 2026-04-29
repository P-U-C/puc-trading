# Precursor Validation Plan — No Capital at Risk

## Objective

Validate whether LLM-consensus tickers exhibit different return/volume characteristics than thematically-similar low-convergence peers, using only public data and no capital deployment.

## 2024-2025 Theme Episodes to Reconstruct

| Theme | Catalyst | Peak Retail Interest | Proxies |
|-------|----------|---------------------|---------|
| Quantum Computing | Google Willow announcement (Dec 2024) | Dec 2024 - Feb 2025 | Google Trends "quantum computing stocks", r/wallstreetbets mentions |
| Nuclear / SMR | AI datacenter power demand narrative | Sep 2024 - Jan 2025 | Google Trends "nuclear stocks", Robinhood top movers |
| GLP-1 / Ozempic | Obesity drug earnings beats | Q3-Q4 2024 | Google Trends "weight loss stocks", retail broker reports |

## Reconstruction Method

For each theme episode:

1. **Reconstruct the LLM consensus basket (T-30, T-60, T-90 before peak).**
   - Re-query the 5 consumer LLMs with the same prompt bank
   - Note: models have been updated since 2024, so current recommendations approximate what the 2024 models would have surfaced (directionally useful, not perfectly historical)
   - Alternative: use Wayback Machine / cached responses from 2024 if available

2. **Build the peer basket.**
   - For each theme, identify 10-15 thematically-related tickers from sector ETF holdings
   - Split into LLM-favored (convergence score >= 0.6) and non-favored (convergence score < 0.3)
   - Control for market cap tier (mega/large/mid/small)

3. **Measure return characteristics.**
   - Public data sources: Yahoo Finance, Google Finance (free, no account needed)
   - Metrics at T+30, T+60, T+90 from estimated LLM consensus formation:
     - Cumulative return (LLM-favored basket vs non-favored peers)
     - Volume ratio (normalized by 60-day average)
     - Max drawdown from peak
     - Return reversal after peak retail interest

4. **Measure retail flow proxies.**
   - Google Trends: search volume for "[ticker] stock" and "[theme] stocks"
   - Reddit mentions: pushshift API or academic datasets for r/wallstreetbets frequency
   - Robinhood data: Robintrack historical or similar retail-broker popularity proxies

## Peer Basket Construction Rules

- Include only US-listed equities with daily volume > 100K shares
- Exclude ADRs, OTC, and SPACs unless they are the primary listing
- Match market cap tier within theme (don't compare IONQ with GOOGL)
- At least 3 tickers in each convergence tier per theme
- If fewer than 3 high-convergence tickers exist, note the theme as "narrow consensus"

## Weekly Rerun Procedure

1. Run the seed batch prompt bank against all 5 LLM slots (same prompts, fresh responses)
2. Extract tickers, compute convergence scores
3. Diff against previous week: new entries, exits, rank changes
4. Append to time series (weekly JSON snapshots in /corpus/ directory)
5. Flag any ticker that crosses convergence tier boundaries (low->medium, medium->high)

## Success Criteria (Phase 0)

Phase 0 is successful if:
- [ ] Convergence scores are computable and distinguish tickers meaningfully
- [ ] At least 2 of 3 historical themes show measurably different return characteristics between high-convergence and low-convergence baskets
- [ ] The weekly rerun procedure is documented and reproducible by another contributor
- [ ] No capital was deployed, no trade instructions were published
