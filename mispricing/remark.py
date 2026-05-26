"""Phase 5b: re-mark open paper positions.

The original paper book never re-priced its positions — `mark` was frozen at
entry cost forever, so `pct_pnl` stayed 0 and the profit-target / stop-loss
exits in `paper_executor.evaluate_exits` could NEVER fire. Winners rode to
expiry and gave everything back; that, plus the expiry-before-catalyst bug,
is why all 20 closed trades resolved at exactly 0%.

This module re-marks each open position from the current underlying price
(free via yfinance — no OPRA / IBKR options-data subscription needed). Entry
cost was a model proxy (`atm_straddle_mid/2 * 0.6 * 100` for a call spread),
not a real two-leg quote, so we re-mark with a Black-Scholes ratio ANCHORED to
the cost actually paid:

    mark_now = cost_paid * BS_value(now) / BS_value(entry)

That keeps mark == cost on day one (no artificial jump) and then moves it by
the modeled change in the spread's value as spot and time-to-expiry move. The
implied vol is backed out of the entry straddle the position was priced from.
All inputs are recovered from fields already stored on the position; nothing
new needs to be persisted.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
from typing import Callable

LOG = logging.getLogger("mispricing.remark")

RISK_FREE = 0.045
# ATM straddle ≈ K_FACTOR * S * sigma * sqrt(T)  (2 / sqrt(2*pi) ≈ 0.7979)
_STRADDLE_K = 2.0 / math.sqrt(2.0 * math.pi)
# Entry cost = atm_straddle_mid * COST_FROM_STRADDLE for a call spread
# (atm_straddle_mid/2 * 0.6 * 100). Invert to recover the straddle.
COST_FROM_STRADDLE = 0.5 * 0.6 * 100.0  # = 30.0


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes price of a European call (per share)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S - K)  # intrinsic at/after expiry
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def _spread_value(S: float, k_long: float, k_short: float | None,
                  T: float, r: float, sigma: float) -> float:
    """Per-share value of a long call (k_long) optionally minus a short call
    (k_short). With no short leg it's a plain long call / leaps."""
    val = bs_call(S, k_long, T, r, sigma)
    if k_short:
        val -= bs_call(S, k_short, T, r, sigma)
    return max(val, 0.0)


def _years(d0: dt.date, d1: dt.date) -> float:
    return max((d1 - d0).days, 1) / 365.0


def _implied_sigma_from_cost(cost_per_contract: float, spot: float,
                             t_entry: float) -> float | None:
    """Recover the entry implied vol from the straddle the position was
    priced off: cost = straddle * 30  ->  straddle = cost/30, and
    straddle ≈ K * spot * sigma * sqrt(T)."""
    if cost_per_contract <= 0 or spot <= 0 or t_entry <= 0:
        return None
    straddle = cost_per_contract / COST_FROM_STRADDLE
    sigma = straddle / (_STRADDLE_K * spot * math.sqrt(t_entry))
    # Clamp to a sane band; option vols on these names sit roughly 15%-200%.
    return min(max(sigma, 0.05), 3.0)


def remark_position(pos: dict, spot: float, today: dt.date) -> dict:
    """Return {mark, pct_pnl} for one open position given the current spot.
    Falls back to the unchanged mark if inputs are unusable."""
    cost = pos.get("cost_per_contract_usd")
    k_long = pos.get("strike")
    k_short = pos.get("strike_upper")
    entry = pos.get("entry_date")
    expiry = pos.get("expiry")
    cur_mark = pos.get("mark", cost)
    try:
        entry_d = dt.date.fromisoformat(str(entry)[:10])
        expiry_d = dt.date.fromisoformat(str(expiry)[:10])
    except (TypeError, ValueError):
        return {"mark": cur_mark, "pct_pnl": pos.get("pct_pnl", 0.0)}
    if cost is None or k_long is None or spot <= 0:
        return {"mark": cur_mark, "pct_pnl": pos.get("pct_pnl", 0.0)}

    # Entry spot ≈ the (ATM) long strike for these structures.
    entry_spot = float(k_long)
    t_entry = _years(entry_d, expiry_d)
    t_now = _years(today, expiry_d)
    sigma = _implied_sigma_from_cost(float(cost), entry_spot, t_entry)
    if sigma is None:
        return {"mark": cur_mark, "pct_pnl": pos.get("pct_pnl", 0.0)}

    bs_entry = _spread_value(entry_spot, float(k_long), k_short, t_entry, RISK_FREE, sigma)
    bs_now = _spread_value(float(spot), float(k_long), k_short, t_now, RISK_FREE, sigma)
    if bs_entry <= 0:
        return {"mark": cur_mark, "pct_pnl": pos.get("pct_pnl", 0.0)}

    mark = float(cost) * (bs_now / bs_entry)
    # A debit spread can never be worth more than its width × 100.
    if k_short:
        mark = min(mark, abs(float(k_short) - float(k_long)) * 100.0)
    mark = max(mark, 0.0)
    pct = round((mark - float(cost)) / float(cost) * 100.0, 2)
    return {"mark": round(mark, 2), "pct_pnl": pct}


def _get(pos, key, default=None):
    """Read a field from either a dict or a dataclass-style position object."""
    if isinstance(pos, dict):
        return pos.get(key, default)
    return getattr(pos, key, default)


def _set(pos, key, value) -> None:
    if isinstance(pos, dict):
        pos[key] = value
    else:
        setattr(pos, key, value)


def remark_positions(positions, spot_fn: Callable[[str], float | None],
                     today: dt.date | None = None) -> int:
    """Re-mark every open position in place. Accepts dicts or PaperPosition
    objects. `spot_fn(ticker)` returns the current underlying price (or None).
    Returns the count re-marked."""
    today = today or dt.date.today()
    spot_cache: dict[str, float | None] = {}
    n = 0
    for pos in positions:
        if _get(pos, "status") != "open":
            continue
        tkr = _get(pos, "ticker")
        if tkr not in spot_cache:
            try:
                spot_cache[tkr] = spot_fn(tkr)
            except Exception as exc:  # noqa: BLE001 - never let one ticker break the run
                LOG.warning("spot fetch failed for %s: %s", tkr, exc)
                spot_cache[tkr] = None
        spot = spot_cache[tkr]
        if not spot or spot <= 0:
            continue
        view = {
            "cost_per_contract_usd": _get(pos, "cost_per_contract_usd"),
            "strike": _get(pos, "strike"),
            "strike_upper": _get(pos, "strike_upper"),
            "entry_date": _get(pos, "entry_date"),
            "expiry": _get(pos, "expiry"),
            "mark": _get(pos, "mark"),
            "pct_pnl": _get(pos, "pct_pnl", 0.0),
        }
        upd = remark_position(view, float(spot), today)
        _set(pos, "mark", upd["mark"])
        _set(pos, "pct_pnl", upd["pct_pnl"])
        n += 1
    return n
