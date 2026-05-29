"""Phase 3: portfolio shaper - two-bucket sizing.

Given a mispricing screen, decide per-ticker:
  - Which instrument (single call, vertical spread, straddle, LEAPS)
  - Strike / expiry
  - Size in $

Income bucket (60% × $10k = $6k): top mispriced_up rows with days_to <= 90.
Lottery bucket (40% × $10k = $4k): top long-horizon rows in emerging/growing themes.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, asdict, field
from typing import Any, Literal

from . import (
    BOOK_USD, INCOME_FRACTION, LOTTERY_FRACTION,
    MAX_INCOME_PCT_PER_TRADE, MAX_INCOME_CONCURRENT,
    LOTTERY_TICKET_USD_MAX, LOTTERY_TICKET_USD_MIN, MAX_LOTTERY_CONCURRENT,
    MAX_TOTAL_TICKER_EXPOSURE_PCT,
    MAX_THEME_EXPOSURE_PCT, MAX_CATALYST_EXPOSURE_PCT, MAX_TICKERS_PER_CATALYST,
)
from .detector import MispricingRow


@dataclass
class TradeCandidate:
    bucket: Literal["income", "lottery"]
    ticker: str
    theme_id: str
    catalyst_id: str
    event_date: str | None
    days_to_event: int | None
    structure: str           # "long_call" | "call_spread" | "straddle" | "leaps" | "risk_reversal"
    strike: float | None     # for spreads: lower leg
    strike_upper: float | None = None   # for spreads: upper leg
    expiry: str | None = None
    quantity_contracts: int = 0
    cost_per_contract_usd: float | None = None
    cost_total_usd: float | None = None
    rationale: str = ""
    convergence_score: float = 0
    mispricing_ratio: float | None = None


def _income_structure(row: MispricingRow) -> tuple[str, float | None, float | None]:
    """Pick income structure based on classification + skew assumptions.
    Returns (structure, lower_strike, upper_strike)."""
    if row.classification != "mispriced_up":
        return "skip", None, None
    if row.spot is None or row.atm_strike is None:
        return "long_call", row.atm_strike, None
    # Bullish-bias default for income trades; refine when bearish exposure
    # is tagged in the corpus (deferred per operator decision).
    if row.event_type in ("trial_readout", "fda_decision", "fda_advisory_committee"):
        # Binary event; straddle captures direction-agnostic vol expansion.
        return "straddle", row.atm_strike, None
    # Earnings / regulatory / M&A: spread to cap cost.
    upper = round(row.atm_strike * 1.10, 2)
    return "call_spread", row.atm_strike, upper


def _lottery_structure(row: MispricingRow) -> tuple[str, float | None, float | None]:
    """Long-dated OTM call (LEAPS-equivalent) at delta-ish 0.20-0.30.
    Without IB greeks, approximate via strike = spot × 1.25-1.50."""
    if row.spot is None:
        return "leaps", None, None
    target = round(row.spot * 1.30, 2)
    return "leaps", target, None


def _per_contract_cost(row: MispricingRow, structure: str,
                       lower: float | None, upper: float | None) -> float | None:
    """Rough per-contract cost in $ (premium × 100).
    Uses ATM straddle as a proxy; for spreads, half of ATM straddle is a
    safe upper bound. For LEAPS we don't have the chain yet -- use 10%
    of spot as a placeholder."""
    if row.atm_straddle_mid is None or row.spot is None:
        if structure == "leaps" and row.spot:
            return round(row.spot * 0.10 * 100, 2)
        return None
    if structure == "straddle":
        return round(row.atm_straddle_mid * 100, 2)
    if structure == "long_call":
        return round((row.atm_straddle_mid / 2) * 100, 2)
    if structure == "call_spread":
        return round((row.atm_straddle_mid / 2 * 0.6) * 100, 2)  # spread caps gains
    if structure == "leaps":
        return round(row.spot * 0.10 * 100, 2)
    return None


def shape(rows: list[MispricingRow], *,
          book_usd: float = BOOK_USD,
          held_positions: list[dict[str, Any]] | None = None) -> list[TradeCandidate]:
    """Return ranked trade candidates for both buckets.

    held_positions (optional): list of currently-open paper positions
    used to enforce MAX_TOTAL_TICKER_EXPOSURE_PCT.
    """
    held_positions = held_positions or []
    held_exposure_by_ticker: dict[str, float] = {}
    # Correlated-exposure tallies, seeded from the open book so the caps account
    # for what's already held, not just what this run adds.
    exposure_by_theme: dict[str, float] = {}
    exposure_by_catalyst: dict[str, float] = {}
    tickers_by_catalyst: dict[str, set[str]] = {}
    for p in held_positions:
        cost = float(p.get("cost_total_usd", 0))
        held_exposure_by_ticker[p["ticker"]] = (
            held_exposure_by_ticker.get(p["ticker"], 0) + cost
        )
        tid = p.get("theme_id")
        cid = p.get("catalyst_id")
        if tid:
            exposure_by_theme[tid] = exposure_by_theme.get(tid, 0) + cost
        if cid:
            exposure_by_catalyst[cid] = exposure_by_catalyst.get(cid, 0) + cost
            tickers_by_catalyst.setdefault(cid, set()).add(p["ticker"])

    income_budget = book_usd * INCOME_FRACTION
    lottery_budget = book_usd * LOTTERY_FRACTION
    max_per_trade_usd = book_usd * MAX_INCOME_PCT_PER_TRADE
    max_total_per_ticker = book_usd * MAX_TOTAL_TICKER_EXPOSURE_PCT
    max_per_theme = book_usd * MAX_THEME_EXPOSURE_PCT
    max_per_catalyst = book_usd * MAX_CATALYST_EXPOSURE_PCT

    def _correlation_headroom(row) -> float | None:
        """Remaining $ this row may take given theme/catalyst caps, or None if a
        cap is already saturated (skip the row entirely). Returns the binding
        (smallest) headroom across both caps."""
        theme_room = max_per_theme - exposure_by_theme.get(row.theme_id, 0)
        cat_room = max_per_catalyst - exposure_by_catalyst.get(row.catalyst_id, 0)
        # Distinct-underlying cap: a brand-new ticker on a catalyst that already
        # holds the max distinct names is rejected (adding to an existing name on
        # that catalyst is still allowed, subject to the $ caps).
        held_names = tickers_by_catalyst.get(row.catalyst_id, set())
        if row.ticker not in held_names and len(held_names) >= MAX_TICKERS_PER_CATALYST:
            return None
        room = min(theme_room, cat_room)
        return room if room > 0 else None

    def _book_correlated(row, total: float) -> None:
        exposure_by_theme[row.theme_id] = exposure_by_theme.get(row.theme_id, 0) + total
        exposure_by_catalyst[row.catalyst_id] = (
            exposure_by_catalyst.get(row.catalyst_id, 0) + total
        )
        tickers_by_catalyst.setdefault(row.catalyst_id, set()).add(row.ticker)

    candidates: list[TradeCandidate] = []
    income_spent = 0.0
    lottery_spent = 0.0
    income_count = 0
    lottery_count = 0

    for row in rows:
        ticker_already = held_exposure_by_ticker.get(row.ticker, 0)
        if ticker_already >= max_total_per_ticker:
            continue

        if row.bucket == "income":
            if income_count >= MAX_INCOME_CONCURRENT or income_spent >= income_budget:
                continue
            structure, lower, upper = _income_structure(row)
            if structure == "skip":
                continue
            cost_per = _per_contract_cost(row, structure, lower, upper)
            if cost_per is None or cost_per <= 0:
                continue
            corr_room = _correlation_headroom(row)
            if corr_room is None:
                continue
            sizing_cap = min(max_per_trade_usd, max_total_per_ticker - ticker_already,
                             income_budget - income_spent, corr_room)
            qty = max(1, int(sizing_cap // cost_per))
            total = round(qty * cost_per, 2)
            if total <= 0 or total > sizing_cap * 1.05:
                continue
            candidates.append(TradeCandidate(
                bucket="income", ticker=row.ticker, theme_id=row.theme_id,
                catalyst_id=row.catalyst_id, event_date=row.event_date,
                days_to_event=row.days_to_event, structure=structure,
                strike=lower, strike_upper=upper, expiry=row.expiry_used,
                quantity_contracts=qty, cost_per_contract_usd=cost_per,
                cost_total_usd=total,
                rationale=(
                    f"thesis-implied move {row.thesis_implied_move:.3f} vs "
                    f"market-implied {row.market_implied_move:.3f} "
                    f"(ratio {row.mispricing_ratio:.2f}); {row.event_type} "
                    f"in {row.days_to_event}d on {row.event_date}"
                ),
                convergence_score=row.convergence_score,
                mispricing_ratio=row.mispricing_ratio,
            ))
            held_exposure_by_ticker[row.ticker] = ticker_already + total
            _book_correlated(row, total)
            income_spent += total
            income_count += 1
            continue

        if row.bucket == "lottery":
            if lottery_count >= MAX_LOTTERY_CONCURRENT or lottery_spent >= lottery_budget:
                continue
            structure, lower, upper = _lottery_structure(row)
            cost_per = _per_contract_cost(row, structure, lower, upper)
            if cost_per is None or cost_per <= 0:
                continue
            corr_room = _correlation_headroom(row)
            if corr_room is None:
                continue
            # Lottery ticket: spend somewhere in [MIN, MAX] per ticker.
            target = min(LOTTERY_TICKET_USD_MAX,
                         max_total_per_ticker - ticker_already,
                         lottery_budget - lottery_spent, corr_room)
            if target < LOTTERY_TICKET_USD_MIN:
                continue
            qty = max(1, int(target // cost_per))
            total = round(qty * cost_per, 2)
            if total < LOTTERY_TICKET_USD_MIN:
                continue
            candidates.append(TradeCandidate(
                bucket="lottery", ticker=row.ticker, theme_id=row.theme_id,
                catalyst_id=row.catalyst_id, event_date=row.event_date,
                days_to_event=row.days_to_event, structure=structure,
                strike=lower, strike_upper=upper, expiry=row.expiry_used,
                quantity_contracts=qty, cost_per_contract_usd=cost_per,
                cost_total_usd=total,
                rationale=(
                    f"long-dated thesis ticket; convergence {row.convergence_score:.3f}; "
                    f"event {row.event_type} {row.event_date or row.horizon_bucket}"
                ),
                convergence_score=row.convergence_score,
                mispricing_ratio=row.mispricing_ratio,
            ))
            held_exposure_by_ticker[row.ticker] = ticker_already + total
            _book_correlated(row, total)
            lottery_spent += total
            lottery_count += 1

    return candidates


def candidates_summary(candidates: list[TradeCandidate]) -> dict[str, Any]:
    income = [c for c in candidates if c.bucket == "income"]
    lottery = [c for c in candidates if c.bucket == "lottery"]
    return {
        "income_count": len(income),
        "income_total_usd": round(sum(c.cost_total_usd or 0 for c in income), 2),
        "lottery_count": len(lottery),
        "lottery_total_usd": round(sum(c.cost_total_usd or 0 for c in lottery), 2),
        "grand_total_usd": round(
            sum(c.cost_total_usd or 0 for c in candidates), 2
        ),
    }
