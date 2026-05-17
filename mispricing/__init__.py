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
