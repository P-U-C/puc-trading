# PUC Trading

## The Thesis

LLMs are the new sell-side analysts for 5 billion monthly conversations. When retail investors hear a theme, they don't Google anymore — they ask ChatGPT, Gemini, Grok. Every model trained on the same internet produces the same consensus. That convergence creates a predictable flow funnel.

**We are not stock pickers. We are flow predictors.**

When all 5 major models agree that IONQ is the #1 quantum computing stock, that's not a stock recommendation — it's a retail flow forecast. We don't care if IONQ is a good company. We care that when the next quantum milestone drops, every LLM on the planet will send retail to IONQ first.

## The Edge

1. **Convergence Corpus** — We query GPT, Claude, Gemini, Grok with thematic prompts and score each ticker by cross-model recommendation density. [Full corpus →](corpus/convergence-corpus.md)

2. **Theme Timing** — Emerging themes (pre-catalyst, cheap options) beat peak-hype themes (expensive options, flow already arrived). We buy before retail asks the question.

3. **Asymmetric Sizing** — Deep OTM options, penny premiums, lottery-ticket sizing. Most expire worthless. One hit at 20-50x pays for everything.

## Active Strategies

### [The Naval Thesis](trades/naval-thesis.md)
> "Pure software is uninvestable. Full stop." — Naval Ravikant

Short SaaS (Apple, Salesforce, Workday) + Long Hardware Moats (Palantir, Tesla, QuantumScape, Rocket Lab). 12 lottery tickets across 3 time horizons. $15K deployed.

**The SaaSpocalypse is real:** $2T wiped from software sector YTD. IGV -21%. SaaS trades at a discount to S&P 500 for the first time ever. Naval says 18 months of repricing ahead.

### [LLM Convergence Scanner](scanner/)
Automated IBKR Gateway scanner that pulls live options chains for 49 tickers across 14 themes, filters for cheap OTM calls/puts, and ranks by convergence × IV-inverse × liquidity.

- [Scanner Dashboard](scanner/index.html)
- [Scanner Code](scanner/run_live_scan.py)
- [Self-Contained Artifact with Tests](scanner/llm_options_scanner.py)

## Convergence Scores — Who Gets the Flow

### Perfect Convergence (every model, rank 1)
| Ticker | Theme | Score | Status |
|--------|-------|-------|--------|
| NVDA | AI Infrastructure | 1.000 | peak_hype |
| LLY | GLP-1 / Peptides | 1.000 | peak_hype |

### High Convergence (consensus pure-play leaders)
| Ticker | Theme | Score | Status |
|--------|-------|-------|--------|
| IONQ | Quantum Computing | 0.733 | peak_hype |
| NVO | GLP-1 / Peptides | 0.680 | peak_hype |
| AVGO | AI Infrastructure | 0.620 | peak_hype |
| BWXT | Nuclear / SMR | 0.600 | growing |
| PLTR | Defense AI | 0.600 | growing |
| QBTS | Quantum Computing | 0.600 | peak_hype |

### Where the Asymmetry Lives (Emerging Themes)
| Ticker | Theme | Score | Status | The Catalyst |
|--------|-------|-------|--------|-------------|
| QS | Solid-State Battery | 0.550 | **emerging** | First commercial shipment |
| BFLY | BCI / Neurotech | 0.500 | **emerging** | Neuralink/Synchron IPO |
| AMBA | Edge AI | 0.500 | **emerging** | On-device AI partnership |
| RKLB | Space / Satellite | 0.500 | **growing** | Neutron rocket / defense contract |
| CRBU | Synthetic Biology | 0.400 | **emerging** | Next CRISPR approval |

## How It Works

```
Weekly: Query 5 LLMs with thematic prompts
  → Score convergence per ticker
  → Identify emerging themes with catalysts ahead

Daily: IBKR scan of options chains
  → Filter: 20-50% OTM, 30-90 DTE, cheap premium
  → Score: convergence × (1/IV) × log(liquidity)
  → Alert: top 10 to Telegram

Trade: Buy lottery tickets on high-convergence + emerging themes
  → Size: 1-2% per ticket, never more
  → TP: sell 30% at 5x, 30% at 10x, trail rest
  → Kill switch: close all if thesis clearly wrong by Q4 2026
```

## Risk Rules

- Total capital at risk: $12,000 max (80% of $15K allocation)
- Each ticket is independent. Never average down.
- Dry powder ($3K) only for adding to confirmed winners.
- Most tickets expire worthless. That is expected.
- The edge is knowing which names capture the flow, not predicting the catalyst.

## Repo Structure

```
puc-trading/
├── README.md              ← you are here
├── trades/
│   └── naval-thesis.md    ← active trade plan with real pricing
├── corpus/
│   ├── convergence-corpus.md  ← full seed corpus + analysis
│   ├── capture-schema.ts     ← typed capture schema
│   └── validation-plan.md    ← backtesting methodology
├── scanner/
│   ├── README.md              ← scanner philosophy + setup
│   ├── index.html             ← dashboard
│   ├── scan-results.json      ← latest scan data
│   ├── run_live_scan.py       ← IBKR live scanner
│   └── llm_options_scanner.py ← self-contained artifact + tests
└── journal/
    └── (daily trade logs)
```

---

*No capital at risk in the research phase. Position sizing for live trading is lottery-ticket only. This is research infrastructure, not financial advice.*

*Per Operam, Nomen — Through work, a name.*
