# LLM Convergence Options Scanner

**The thesis:** Retail capital allocation is increasingly mediated by LLM stock recommendations. When a theme catalyst hits, retail investors ask ChatGPT, Gemini, Grok — and they all recommend the same 2-3 names. This creates predictable, convergent flow. We identify those names before the catalyst and buy cheap OTM calls. When the flow arrives, those calls go 5-50x.

## Philosophy

We are not stock pickers. We are flow predictors.

The insight is simple: LLMs trained on the same internet produce the same consensus. When retail asks "best quantum computing stocks," every model says IONQ first. That convergence creates a flow funnel. The money goes where the models point. And the models don't change their recommendations fast enough for the consensus to shift before the flow arrives.

We don't care if IONQ is a good company. We care that when the next quantum milestone drops, every LLM on the planet will send retail to IONQ first. That is the signal.

**The strategy is asymmetric.** Small positions, cheap options, multiple themes, lottery-ticket sizing. Most tickets expire worthless. One that hits 20x pays for the rest. The edge is knowing which names will capture the flow — not predicting the catalyst.

**What makes this different:**
- We don't predict markets. We predict what LLMs will recommend.
- We don't pick stocks. We identify convergence.
- We don't trade on fundamentals. We trade on retail flow mechanics.
- We size for asymmetry, not for conviction. 1-2% per ticket, never more.

## How It Works

### 1. Convergence Corpus

Query the top consumer LLMs (GPT, Claude, Gemini, Grok) with thematic prompts: "best [X] stocks to buy right now," "pure play [X] stocks," etc. Extract ticker mentions, rank, qualifying language. Score each ticker by cross-model recommendation density.

**convergence_score** = how many models recommend it × how consistently they rank it × how directly they recommend it

Perfect convergence (1.000): every model, every query, always rank 1. Examples: NVDA for AI infra, LLY for GLP-1.

### 2. Theme Timing

| Status | What it means | Action |
|--------|--------------|--------|
| **Emerging** | Few people talking about it. Options are cheap. Catalyst is months away. | **BUY NOW** — maximum asymmetry |
| **Growing** | Gaining attention. Options getting more expensive. Catalysts approaching. | Buy selectively |
| **Peak hype** | Everyone knows. IV is elevated. Options are expensive. | Stay out or sell |
| **Post-peak** | Hype faded. IV crushed. Cheap options reappear. | Watch for re-entry |

### 3. Options Scanning

Connect to IBKR Gateway. Pull live options chains for all high-convergence tickers. Filter:

- 20-50% out of the money (deep OTM for maximum leverage)
- 30-90 days to expiration (enough time for catalyst)
- Cheap premium (lottery ticket, not a position)
- Adequate liquidity (can exit on the spike)

Score each contract:

```
asymmetry_score = convergence_score × (1 / implied_volatility) × log(open_interest)
```

Higher score = high convergence + cheap vol + enough liquidity.

### 4. Dashboard + Alerts

- **Dashboard** at `/scanner/` shows all themes, ranked contracts, convergence bars
- **Telegram alerts** send top picks daily during market hours
- **Weekly corpus update** re-queries all LLMs to detect rank changes

## Current Themes (14)

| Theme | Status | Top Convergence Tickers | The Catalyst |
|-------|--------|------------------------|-------------|
| AI Infrastructure | peak_hype | NVDA, AVGO, VRT | Already happening |
| GLP-1 / Peptides | peak_hype | LLY, NVO, VKTX | Already happening |
| Quantum Computing | peak_hype | IONQ, QBTS, RGTI | Next qubit milestone |
| Nuclear / SMR | growing | BWXT, OKLO, SMR, GEV | Policy announcement, data center PPA |
| Robotics / Humanoid | growing | TSLA, ISRG, SYM | Figure AI IPO, Optimus milestone |
| Defense AI | growing | PLTR, LDOS | Government autonomy contract |
| Space / Satellite | growing | RKLB, ASTS, PL | Broadband or launch contract |
| Bitcoin Mining | post_peak | MARA, RIOT, CLSK | Next BTC cycle |
| **BCI / Neurotech** | **emerging** | **BFLY, QSI** | **Neuralink/Synchron/Merge IPO** |
| **Solid-State Battery** | **emerging** | **QS, SLDP** | **First commercial shipment** |
| **Synthetic Biology** | **emerging** | **CRBU, TWST, PACB** | **Next CRISPR approval** |
| **Edge AI** | **emerging** | **AMBA** | **On-device AI chip partnership** |
| Photonic Computing | emerging | LITE, COHR | Photonic chip commercialization |
| Longevity | emerging | ABBV, CELH | Longevity drug breakthrough |

**Bold = where the best asymmetry lives right now.** Emerging themes with identifiable catalysts and cheap options.

## Architecture

```
Convergence Corpus (weekly LLM queries)
  → convergence scores per ticker per theme
  
IBKR Gateway (live market data)
  → options chains for all convergence tickers
  
Scanner (Python, runs daily 10am ET)
  → filter: OTM/DTE/premium/IV/liquidity
  → score: convergence × IV-inverse × liquidity
  → export: scan-results.json
  
Dashboard (static HTML)
  → reads scan-results.json
  → theme cards + ranked contracts table
  → hosted on GitHub Pages
  
Telegram Alerts
  → top 10 contracts daily
  → threshold alerts for emerging themes
```

## Files

- `run_live_scan.py` — IBKR Gateway scanner with convergence scoring
- `scan-results.json` — latest scan output (consumed by dashboard)
- `index.html` — dashboard frontend
- `llm_options_scanner.py` — self-contained artifact with inline tests (task submission version)

## Setup

```bash
pip install ib_insync requests

# Start IB Gateway (must be running)
# Paper account: port 4002, Live: port 4001

# Run scan
python run_live_scan.py

# Run with Telegram alerts
DRY_RUN=false TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx python run_live_scan.py

# Run tests (no IBKR needed)
python llm_options_scanner.py --test
```

## Safety

- **Read-only.** No order methods exist in the code. The IBKR connection is `readonly=True`.
- **No credentials in code.** Environment variables only.
- **No trade recommendations.** Output is "research signal ranking." The human decides.
- **Paper-safe.** Works on paper accounts. Same market data, no capital risk.

## The Mental Model

Think of it like this: LLMs are the new sell-side analysts, but instead of 12 analyst reports, there are 5 billion LLM conversations happening every month. When all 5 major models agree that IONQ is the #1 quantum computing stock, that's not a stock recommendation — it's a retail flow forecast. We're not trading the stock. We're trading the flow.

---

*No capital at risk in the research phase. Position sizing for live trading is lottery-ticket only (1-2% per position). This is research infrastructure, not financial advice.*
