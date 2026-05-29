"""Mispricing-screen + two-bucket options portfolio.

See ~/trend-corpus/ops/runbooks/mispricing-screen-plan.md for the
end-to-end architecture. Modules:

  ib_chain.py       Phase 1 - options-chain pull (IB Gateway primary,
                              yfinance fallback)
  detector.py       Phase 2 - thesis-vs-market mispricing detector
  shaper.py         Phase 3 - two-bucket portfolio sizing
  tickets.py        Phase 4 - daily trade-ticket generator
  morning_brief.py  Phase 5 - Telegram morning digest
  paper_executor.py Phase 6 - paper-trade tracker + tracker.md updates
"""

__version__ = "0.1.0"

# Capital allocation per Chad's 2026-05-17 decisions:
BOOK_USD = 10_000
INCOME_FRACTION = 0.60
LOTTERY_FRACTION = 0.40
MAX_INCOME_PCT_PER_TRADE = 0.02   # 1-2% per income trade
MAX_INCOME_CONCURRENT = 15
LOTTERY_TICKET_USD_MIN = 200
LOTTERY_TICKET_USD_MAX = 400
MAX_LOTTERY_CONCURRENT = 20
MAX_TOTAL_TICKER_EXPOSURE_PCT = 0.05  # income + lottery on a single ticker

# Concentration caps across CORRELATED positions (added 2026-05-29 after the
# cicadas blow-up: the per-ticker cap held, but 4 correlated ag ETFs all on the
# single NOAA-ENSO catalyst stacked to ~19% of book and -32% as one undiversified
# bet). The per-ticker cap alone cannot see that WEAT/CORN/DBA/FXA are the same
# trade. These cap the SUM of open exposure sharing a theme_id / catalyst_id, and
# the number of distinct underlyings the screen will load onto one catalyst.
MAX_THEME_EXPOSURE_PCT = 0.10      # all open positions sharing a theme_id ($1,000 on $10k)
MAX_CATALYST_EXPOSURE_PCT = 0.08   # all open positions sharing a catalyst_id ($800 on $10k)
MAX_TICKERS_PER_CATALYST = 2       # distinct underlyings the screen will buy per catalyst
