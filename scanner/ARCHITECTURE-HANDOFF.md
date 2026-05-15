# LLM Convergence Scanner — Architecture & Integration Handoff

Handoff doc for the agent building the **segregated corpus populator**. Describes the
existing system, where it runs, and the exact seam your corpus plugs into.

---

## 1. What this system is

The scanner is a retail-flow forecasting tool. Thesis: when a theme catalyst hits,
retail investors ask consumer LLMs which stocks to buy, and the LLMs converge on the
same 2-3 names. That convergence is a predictable flow funnel. The scanner ranks cheap
OTM options on high-convergence tickers so a human can place lottery-ticket positions
before the flow arrives.

Two stages:
- **Convergence layer** — which tickers the LLMs agree on, per theme. *This is what
  your corpus populator feeds.*
- **Options layer** — live IBKR options chains for those tickers, filtered + scored by
  `convergence x (1/IV) x log(liquidity)`.

Output is a static JSON consumed by a public dashboard.

---

## 2. Repos & file layout

Two repos are involved.

### a) `~/puc-trading` (private — logic + source corpus)
```
puc-trading/
  scanner/
    run_live_scan.py        # the live scanner — connects to IBKR, scores, exports JSON
    llm_options_scanner.py  # self-contained artifact w/ inline tests (task-submission copy)
    scan-results.json       # last scan output (LOCAL copy; real one lives in pft-validator)
    index.html              # dashboard frontend (LOCAL copy)
    README.md               # thesis + strategy
    ARCHITECTURE-HANDOFF.md # this file
  corpus/
    capture-schema.ts       # TypeScript schema for LLM-recommendation capture + scoring
    convergence-corpus.md   # the seed corpus writeup (Phase 0, published as a PFT task)
    validation-plan.md      # how convergence scores get validated
```

### b) `~/pft-validator` (published — GitHub Pages site)
```
pft-validator/
  scanner/
    index.html              # LIVE dashboard (this is what the public sees)
    scan-results.json       # LIVE data the dashboard fetches
  CNAME -> pft.permanentupperclass.com
```
Remote: `github.com/P-U-C/pft-validator`. Push token is embedded in the remote URL.

---

## 3. Hosting

- GitHub Pages off the `P-U-C/pft-validator` repo.
- Custom domain: **pft.permanentupperclass.com** (CNAME file in repo root).
- Live dashboard URL: **https://pft.permanentupperclass.com/scanner/**
- The page is pure static HTML + a `fetch('/scanner/scan-results.json')` call. No
  backend, no build step. Deploy = `git push` the two files (`index.html`,
  `scan-results.json`) to the repo; Pages serves them.
- `run_live_scan.py` writes directly to `~/pft-validator/scanner/scan-results.json`
  (see `OUTPUT_JSON` on line 14), so a scan + `git push` is the whole deploy.

---

## 4. Current data flow

```
[convergence corpus]              <-- YOUR populator replaces this stage
   |  (today: a hardcoded Python list)
   v
CONVERGENCE list in run_live_scan.py   (lines 20-84: ticker, theme, score, tier, status)
   |
   v
run_live_scan.py
   - connects to IB Gateway (127.0.0.1:4002, readonly)
   - for each ticker: pulls option chain, filters OTM 20-50% / DTE 30-90 / premium / IV / liquidity
   - scores each contract: convergence x (1/IV) x log(liquidity)
   - writes ~/pft-validator/scanner/scan-results.json  { scan_meta, results[:50], convergence }
   - optional Telegram alert (top 10)
   |
   v
index.html  (fetches scan-results.json, renders theme cards + ranked-contracts table)
```

---

## 5. The convergence/corpus layer — current state (READ THIS)

This is the stage you are replacing, so here is exactly how it works today.

**Today it is hardcoded and manual.** The `CONVERGENCE` constant in
`run_live_scan.py` (lines 20-84) is a hand-maintained Python list of ~47 rows:

```python
{"ticker": "NVDA", "theme": "AI Infrastructure", "score": 0.800, "tier": "HIGH", "status": "peak_hype"}
```

Those scores were derived by hand from a one-time Phase 0 corpus exercise
(`corpus/convergence-corpus.md`) — querying GPT/Claude/Gemini/Perplexity/Grok with
thematic prompts, extracting ticker mentions, and scoring. There is **no live pipeline**
that regenerates this. It has not been refreshed since 2026-04-28.

**The intended schema already exists.** `corpus/capture-schema.ts` defines the real
data model and the scoring function the populator should target:

- `CaptureRecord` — one LLM response: model slot, theme, prompt, extracted
  `TickerMention[]`, raw excerpt.
- `TickerMention` — ticker, rank in response, mention type
  (direct_recommendation / hedged / pure_play / comparison / warning), qualifying language.
- `ConvergenceScore` — the aggregate per ticker per theme. Scoring formula:
  `convergence_score = (models_mentioning/5)*0.5 + (1/avg_rank)*0.3 + (direct/total)*0.2`
- `computeConvergence(records, themeId)` — pure function, `CaptureRecord[] -> ConvergenceScore[]`.
- `PROMPT_TEMPLATES` (6 prompt intents) and `THEMES` (10 themes) define the query grid.

So the capture schema and the math are already specified — what is missing is the
**populator**: the thing that actually runs the prompt grid against the 5 models,
produces `CaptureRecord[]`, and emits `ConvergenceScore[]` on a schedule.

---

## 6. Integration seam for the segregated corpus populator

The cleanest contract: **your populator owns the corpus; the scanner consumes a file.**

Recommended seam:
1. Your populator writes a versioned artifact, e.g.
   `~/puc-trading/corpus/convergence-latest.json` — an array conforming to
   `ConvergenceScore[]` from `capture-schema.ts`, plus a `theme -> status` map
   (emerging / growing / peak_hype / post_peak) and a `generated_at` timestamp.
2. `run_live_scan.py` is changed to **load that file instead of the hardcoded
   `CONVERGENCE` list**. Mapping is 1:1 — the scanner only needs
   `ticker, theme, score, tier, status` per row, all of which are in `ConvergenceScore`
   (`tier` = `convergence_tier`, `score` = `convergence_score`).
3. If the file is missing or stale beyond N days, the scanner should fail loudly
   rather than silently scanning an empty list.

Why a file boundary (not an import): it keeps your populator **segregated** — it can
live in its own repo / its own runtime / its own model credentials, and the only
coupling is a JSON schema. The scanner never needs to know how the corpus was built.

"Richer flow" hooks, if you want them:
- Keep raw `CaptureRecord[]` alongside the scored output for auditability /
  back-testing rank drift.
- Emit a diff vs. the previous corpus (new tickers, rank changes, status transitions)
  — `emerging -> growing` is the highest-value signal in this whole system.
- Per-theme `status` is currently a hand-label; deriving it from corpus dynamics
  (mention velocity, IV context) would be a real upgrade.

Things to NOT break:
- Theme names must stay consistent between the corpus and the scanner (they are the
  join key, and the dashboard groups by them).
- Output stays research-only: scores and rankings, no trade instructions. The scanner
  and dashboard are deliberately read-only / paper-safe.

---

## 7. What is missing / not automated (independent of your work)

- **No cron.** `run_live_scan.py` has only ever been run by hand. It is NOT in
  `~/pf-scout-bot/deploy/hourly-pipeline.sh` (which refreshes the other validator-site
  feeds hourly).
- **No exporter / deploy step.** Someone has to `git push` `pft-validator` manually
  after a scan.
- **Stale.** Live dashboard data is frozen at 2026-04-28.

Once your corpus populator exists, the remaining glue is small: a daily cron that runs
the populator -> runs `run_live_scan.py` -> commits + pushes `pft-validator`. Convergence
does not move hour-to-hour, so daily (or even weekly for the corpus, daily for the
options layer) is the right cadence.

---

## 8. Quick reference

| Thing | Location |
|---|---|
| Live dashboard | https://pft.permanentupperclass.com/scanner/ |
| Live data file | `~/pft-validator/scanner/scan-results.json` |
| Scanner logic | `~/puc-trading/scanner/run_live_scan.py` |
| Corpus schema (target contract) | `~/puc-trading/corpus/capture-schema.ts` |
| Seed corpus writeup | `~/puc-trading/corpus/convergence-corpus.md` |
| Hardcoded corpus (to be replaced) | `run_live_scan.py` lines 20-84 |
| IBKR | IB Gateway, `127.0.0.1:4002`, `readonly=True`, delayed data |
