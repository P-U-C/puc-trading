#!/usr/bin/env python3
"""build-longterm-basket.py - the long-term convergence basket (paper).

THE THESIS (Chad, 2026-06-12): order flow is driven by funnels. Google was
the funnel; production LLMs from the top labs are becoming it. When retail
asks an LLM "how do I get exposure to robotics / quantum / biomechanics",
the tickers the models converge on receive the flow -- knowledge moves from
asymmetric to symmetric. So the long-term book is simply the AGGREGATE of
the trend tickers production LLMs recommend, weighted by how strongly they
converge.

Mechanics (paper book at paper-journal/longterm/):
  - Universe: llm_survey rows from corpus/convergence-latest.json with
    convergence_tier HIGH or MEDIUM (LT_MIN_TIER env), private trading
    theses excluded. One row per ticker (max convergence_score wins when a
    ticker spans themes).
  - Weights: proportional to convergence_score.
  - Capital: LT_BASE_USD (default $1,000 paper) + net realized P&L from
    closed SHORT-TERM convergence trades (the compounding rule -- short-term
    profits buy more of the long-term basket).
  - Fills: paper, at the latest yfinance close; fractional shares allowed.
  - Buy-and-hold: existing holdings are re-marked, never drift-rebalanced.
    A ticker ENTERING the universe is bought at its target weight of
    current capital. A ticker LEAVING the universe is closed at mark and
    its realized P&L stays in the pool.

Runs daily from cron at 21:05 UTC, before refresh-mispricing (21:15)
publishes the book to the public page.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PUC = Path(os.environ.get("PUC_TRADING_DIR", os.path.expanduser("~/puc-trading")))
ARTIFACT = PUC / "corpus" / "convergence-latest.json"
LT_DIR = PUC / "paper-journal" / "longterm"
LT_OPEN = LT_DIR / "positions.json"
LT_CLOSED = LT_DIR / "closed.json"
ST_CLOSED = PUC / "paper-journal" / "mispricing" / "closed.json"

LT_BASE_USD = float(os.environ.get("LT_BASE_USD", "1000"))
# Default LOW = ALL LLM-recommended tickers. Chad's spec is the AGGREGATE of
# what the models recommend, so nothing the funnel points at is excluded;
# convergence weighting already sizes weak names small.
LT_MIN_TIER = os.environ.get("LT_MIN_TIER", "LOW").upper()
LONG_TERM_MIN_DTE = int(os.environ.get("LONG_TERM_MIN_DTE", "120"))
PRIVATE_THEME_IDS = {
    t.strip()
    for t in os.environ.get("BOOK_PRIVATE_THEME_IDS", "cicadas").split(",")
    if t.strip()
}
TIER_OK = {
    "HIGH": {"HIGH"},
    "MEDIUM": {"HIGH", "MEDIUM"},
    "LOW": {"HIGH", "MEDIUM", "LOW"},
}.get(LT_MIN_TIER, {"HIGH", "MEDIUM", "LOW"})


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"WARN: {path} unreadable ({exc})", file=sys.stderr)
        return default


def _days_between(a, b):
    try:
        from datetime import date
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


def compounded_pool() -> float:
    """Net realized P&L from closed short-term convergence trades."""
    closed = _read_json(ST_CLOSED, [])
    seen, total = set(), 0.0
    for r in closed:
        rid = r.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        if r.get("theme_id") in PRIVATE_THEME_IDS:
            continue
        dte = _days_between(r.get("entry_date"), r.get("expiry"))
        if dte is not None and dte >= LONG_TERM_MIN_DTE:
            continue  # long-term options realize into the pool elsewhere
        total += (r.get("cost_total_usd") or 0.0) * (r.get("pct_pnl") or 0.0) / 100.0
    # realized basket exits also stay in the pool
    for r in _read_json(LT_CLOSED, []):
        total += r.get("realized_usd") or 0.0
    return round(total, 2)


def target_universe() -> dict[str, dict]:
    art = _read_json(ARTIFACT, {})
    best: dict[str, dict] = {}
    for r in art.get("scores", []):
        if "llm_survey" not in (r.get("row_sources") or []):
            continue
        if r.get("theme_id") in PRIVATE_THEME_IDS:
            continue
        cs = r.get("convergence_score")
        if cs is None or (r.get("convergence_tier") or "").upper() not in TIER_OK:
            continue
        t = r.get("ticker")
        if not t:
            continue
        if t not in best or cs > best[t]["convergence_score"]:
            best[t] = {
                "ticker": t,
                "theme_id": r.get("theme_id"),
                "theme": r.get("theme"),
                "convergence_score": cs,
                "convergence_tier": r.get("convergence_tier"),
                "models_mentioning": r.get("models_mentioning"),
            }
    return best


def fetch_prices(tickers: list[str]) -> dict[str, float]:
    import yfinance as yf

    out: dict[str, float] = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="5d")["Close"]
            if len(h):
                out[t] = float(h.iloc[-1])
        except Exception as exc:
            print(f"WARN: no price for {t}: {exc}", file=sys.stderr)
    return out


def main() -> int:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    universe = target_universe()
    if not universe:
        print("build-longterm: empty universe; artifact missing llm_survey rows?", file=sys.stderr)
        return 1

    open_rows = _read_json(LT_OPEN, [])
    closed_rows = _read_json(LT_CLOSED, [])
    held = {p["ticker"]: p for p in open_rows}

    pool = compounded_pool()
    capital = round(LT_BASE_USD + pool, 2)

    entering = [t for t in universe if t not in held]
    leaving = [t for t in held if t not in universe]
    prices = fetch_prices(sorted(set(entering) | set(held)))

    # Close positions whose ticker left the LLM-convergence universe.
    for t in leaving:
        p = held.pop(t)
        px = prices.get(t)
        if px is None:
            held[t] = p  # no price -> keep until we can mark it
            continue
        realized = round(px * p["quantity_shares"] - p["cost_total_usd"], 2)
        closed_rows.append(
            {
                **p,
                "status": "closed",
                "closed_at": today,
                "close_price": round(px, 2),
                "close_reason": "left LLM-convergence universe",
                "realized_usd": realized,
                "pct_pnl": round(realized / p["cost_total_usd"] * 100.0, 2)
                if p["cost_total_usd"]
                else 0.0,
            }
        )
        print(f"close {t}: realized ${realized:+.2f} (left universe)")

    # Buy tickers entering the universe at their target weight of capital.
    total_cs = sum(u["convergence_score"] for u in universe.values())
    for t in entering:
        u = universe[t]
        px = prices.get(t)
        if px is None or px <= 0:
            print(f"skip {t}: no price", file=sys.stderr)
            continue
        alloc = capital * (u["convergence_score"] / total_cs)
        if alloc < 1.0:
            continue
        shares = round(alloc / px, 4)
        held[t] = {
            "id": f"LT-{t}-{today}",
            "ticker": t,
            "theme_id": u["theme_id"],
            "theme": u["theme"],
            "bucket": "long_term",
            "structure": "equity",
            "direction": "long",
            "quantity_shares": shares,
            "quantity_contracts": shares,  # page displays this column
            "entry_price": round(px, 2),
            "cost_total_usd": round(shares * px, 2),
            "entry_date": today,
            "status": "open",
            "entry_rationale": (
                f"LLM-convergence basket: cs={u['convergence_score']:.2f} "
                f"({u['convergence_tier']}, {u.get('models_mentioning') or '?'} models) "
                f"for {u['theme_id']}"
            ),
        }

    # Re-mark everything still held.
    for t, p in held.items():
        px = prices.get(t)
        if px is None:
            continue
        p["mark"] = round(px, 2)
        if p.get("cost_total_usd"):
            p["pct_pnl"] = round(
                (px * p["quantity_shares"] - p["cost_total_usd"])
                / p["cost_total_usd"]
                * 100.0,
                2,
            )
        # refresh convergence metadata so the page shows current scores
        if t in universe:
            p["convergence_score"] = universe[t]["convergence_score"]
            p["convergence_tier"] = universe[t]["convergence_tier"]

    out_rows = sorted(held.values(), key=lambda p: -(p.get("convergence_score") or 0))
    LT_DIR.mkdir(parents=True, exist_ok=True)
    LT_OPEN.write_text(json.dumps(out_rows, indent=1) + "\n", encoding="utf-8")
    LT_CLOSED.write_text(json.dumps(closed_rows, indent=1) + "\n", encoding="utf-8")

    invested = sum(p.get("cost_total_usd") or 0 for p in out_rows)
    mark = sum((p.get("mark") or p.get("entry_price") or 0) * p["quantity_shares"] for p in out_rows)
    print(
        f"build-longterm: {len(out_rows)} holdings, capital=${capital:.2f} "
        f"(base ${LT_BASE_USD:.0f} + compounded ${pool:+.2f}), "
        f"invested=${invested:.2f}, mark=${mark:.2f}, "
        f"+{len(entering)} new / -{len(leaving)} closed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
