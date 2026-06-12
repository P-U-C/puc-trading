#!/usr/bin/env python3
"""Merge paper-book + live-book positions into the scanner dashboard JSON.

Reads:
  - paper-journal/mispricing/positions.json  (open paper)
  - paper-journal/mispricing/closed.json     (closed paper)
  - IBKR Gateway 4002 if reachable AND env LIVE_PUSH=1 (open live)

Writes a `book` key into scan-results.json with paper + live sub-objects,
each containing { open, closed, stats } plus a top-level `live_unlocked`
flag. The schema is additive -- existing consumers continue to work.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PUC = Path(os.environ.get("PUC_TRADING_DIR", os.path.expanduser("~/puc-trading")))
SCAN_PATH = Path(
    os.environ.get(
        "SCAN_RESULTS_PATH",
        str(Path(os.path.expanduser("~/pft-validator/scanner/scan-results.json"))),
    )
)
PAPER_OPEN = PUC / "paper-journal" / "mispricing" / "positions.json"
PAPER_CLOSED = PUC / "paper-journal" / "mispricing" / "closed.json"
# The long-term convergence basket (LLM-recommended trend tickers, paper)
# lives in its own book and publishes alongside the screen's trades.
LT_OPEN = PUC / "paper-journal" / "longterm" / "positions.json"
LT_CLOSED = PUC / "paper-journal" / "longterm" / "closed.json"

GO_LIVE_TRADES = int(os.environ.get("GO_LIVE_TRADES", "30"))
LIVE_PUSH = os.environ.get("LIVE_PUSH", "0") == "1"

# The published book carries only convergence-architecture trades; private
# trading theses (cicadas/ENSO) stay in the runtime book but off the page --
# their ranked structure would publish the thesis.
PRIVATE_THEME_IDS = {
    t.strip()
    for t in os.environ.get("BOOK_PRIVATE_THEME_IDS", "cicadas").split(",")
    if t.strip()
}

# Term split: entry->expiry horizon at entry. Short-term realized P&L
# compounds into long-term capital (Chad's bucket directive, 2026-06-12).
LONG_TERM_MIN_DTE = int(os.environ.get("LONG_TERM_MIN_DTE", "120"))


def _read_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"WARN: {path} unreadable ({exc}); treating as empty", file=sys.stderr)
        return []
    return data if isinstance(data, list) else []


def _days_between(a: str, b: str) -> int | None:
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


def _term_bucket(row: dict[str, Any]) -> str:
    """long_term / short_term from the entry->expiry horizon at entry.

    Equity basket holdings have no expiry -- they ARE the long-term book
    (buy-and-hold LLM-convergence basket).
    """
    if row.get("structure") == "equity":
        return "long_term"
    dte = _days_between(row.get("entry_date"), row.get("expiry"))
    if dte is None:
        return "short_term"
    return "long_term" if dte >= LONG_TERM_MIN_DTE else "short_term"


def _is_public(row: dict[str, Any]) -> bool:
    return row.get("theme_id") not in PRIVATE_THEME_IDS


def _realized_usd(row: dict[str, Any]) -> float:
    """pct_pnl is stored as a percent (30.12 == +30.12%), not a fraction."""
    cost = row.get("cost_total_usd") or 0.0
    pct = row.get("pct_pnl") or 0.0
    return cost * pct / 100.0


def _bucket_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compute per-bucket stats from closed rows."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        buckets.setdefault(r.get("bucket", "unknown"), []).append(r)

    out: dict[str, dict[str, Any]] = {}
    for bucket, items in buckets.items():
        wins = sum(1 for r in items if (r.get("pct_pnl") or 0) > 0)
        pnls = [r.get("pct_pnl") for r in items if isinstance(r.get("pct_pnl"), (int, float))]
        holds = [
            _days_between(r["entry_date"], r["closed_at"])
            for r in items
            if r.get("entry_date") and r.get("closed_at")
        ]
        holds = [h for h in holds if h is not None]
        out[bucket] = {
            "closed": len(items),
            "wins": wins,
            "hit_rate": (wins / len(items)) if items else None,
            "mean_pct_pnl": (sum(pnls) / len(pnls)) if pnls else None,
            "median_hold_days": int(statistics.median(holds)) if holds else None,
            "realized_usd": round(sum(_realized_usd(r) for r in items), 2),
        }
    return out


def _summary(open_rows: list, closed_rows: list) -> dict[str, Any]:
    invested = sum(r.get("cost_total_usd", 0) or 0 for r in open_rows)
    mark = sum((r.get("mark") or 0) * (r.get("quantity_contracts") or 0) for r in open_rows)
    return {
        "open_count": len(open_rows),
        "closed_count": len(closed_rows),
        "invested_usd": round(invested, 2),
        "mark_to_market_usd": round(mark, 2),
        "unrealized_pnl_usd": round(mark - invested, 2),
        "buckets": _bucket_stats(closed_rows),
    }


def _dedupe_by_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop rows with a duplicate `id`, keeping first occurrence.

    The orchestrator can double-write identical positions on re-runs; this
    keeps the published book clean regardless of upstream dedup. Rows without
    an `id` pass through untouched.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        rid = r.get("id")
        if rid is None:
            out.append(r)
            continue
        if rid in seen:
            continue
        seen.add(rid)
        out.append(r)
    return out


def _build_paper() -> dict[str, Any]:
    open_all = _dedupe_by_id(_read_json(PAPER_OPEN) + _read_json(LT_OPEN))
    closed_all = _dedupe_by_id(_read_json(PAPER_CLOSED) + _read_json(LT_CLOSED))

    # Publish convergence-architecture trades only, re-bucketed by term.
    open_rows = [{**r, "bucket": _term_bucket(r)} for r in open_all if _is_public(r)]
    closed_rows = [{**r, "bucket": _term_bucket(r)} for r in closed_all if _is_public(r)]

    stats = _summary(open_rows, closed_rows)
    stats["private_excluded"] = {
        "open": len(open_all) - len(open_rows),
        "closed": len(closed_all) - len(closed_rows),
    }

    # Compounding ledger: net realized short-term P&L flows into long-term
    # capital. long_term_capital_usd = what's deployed long-term now plus
    # everything short-term has contributed (realized, both signs -- losses
    # drain the pool the same way profits feed it).
    st_realized = round(
        sum(_realized_usd(r) for r in closed_rows if r["bucket"] == "short_term"), 2
    )
    lt_realized = round(
        sum(_realized_usd(r) for r in closed_rows if r["bucket"] == "long_term"), 2
    )
    lt_open_invested = round(
        sum(r.get("cost_total_usd") or 0 for r in open_rows if r["bucket"] == "long_term"), 2
    )
    stats["compounding"] = {
        "rule": "net realized short-term P&L compounds into long-term capital",
        "short_term_realized_usd": st_realized,
        "long_term_realized_usd": lt_realized,
        "long_term_open_invested_usd": lt_open_invested,
        # Deployed long-term capital. The basket builder already sizes from
        # base + compounded realized P&L, so the deployed figure IS the
        # capital -- summing the pool in again would double-count it.
        "long_term_capital_usd": lt_open_invested,
    }

    return {
        "open": open_rows,
        "closed": closed_rows,
        "stats": stats,
        # Engine-wide closed count (private legs included) -- the go-live
        # gate measures the engine's track record, not page visibility.
        "engine_closed_count": len(closed_all),
    }


def _build_live() -> dict[str, Any]:
    """Pull live positions from IBKR Gateway if LIVE_PUSH=1.

    Skipped until the 30-trade paper gate clears. Returns empty book
    with an explanatory note in stats.
    """
    closed_count = len(_read_json(PAPER_CLOSED))
    gate_remaining = max(0, GO_LIVE_TRADES - closed_count)

    if not LIVE_PUSH:
        return {
            "open": [],
            "closed": [],
            "stats": {
                "open_count": 0,
                "closed_count": 0,
                "invested_usd": 0.0,
                "mark_to_market_usd": 0.0,
                "unrealized_pnl_usd": 0.0,
                "buckets": {},
                "gate_status": "paper-only",
                "gate_remaining_trades": gate_remaining,
            },
        }

    try:
        from ib_insync import IB
    except ImportError:
        print("WARN: ib_insync not installed; live book empty", file=sys.stderr)
        return {"open": [], "closed": [], "stats": {"open_count": 0, "closed_count": 0, "buckets": {}}}

    ib = IB()
    try:
        ib.connect("127.0.0.1", 4002, clientId=42, timeout=5)
        positions = ib.positions()
        out_open = []
        for p in positions:
            c = p.contract
            out_open.append({
                "ticker": c.symbol,
                "structure": c.secType,
                "strike": getattr(c, "strike", None),
                "expiry": getattr(c, "lastTradeDateOrContractMonth", None),
                "quantity_contracts": p.position,
                "avg_cost": p.avgCost,
                "status": "open",
            })
        return {
            "open": out_open,
            "closed": [],  # live closed history would come from IB executions API
            "stats": _summary(out_open, []),
        }
    except Exception as exc:
        print(f"WARN: IBKR query failed ({exc}); live book empty", file=sys.stderr)
        return {"open": [], "closed": [], "stats": {"open_count": 0, "closed_count": 0, "buckets": {}}}
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass


def main() -> int:
    if not SCAN_PATH.exists():
        print(f"ERROR: {SCAN_PATH} not found", file=sys.stderr)
        return 1

    with SCAN_PATH.open(encoding="utf-8") as f:
        scan = json.load(f)

    paper = _build_paper()
    live = _build_live()
    closed_count = paper.pop("engine_closed_count")

    scan["book"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live_unlocked": LIVE_PUSH,
        "go_live_gate": {
            "required_closed_trades": GO_LIVE_TRADES,
            "current_closed_trades": closed_count,
            "remaining_trades": max(0, GO_LIVE_TRADES - closed_count),
        },
        "paper": paper,
        "live": live,
    }

    with SCAN_PATH.open("w", encoding="utf-8") as f:
        json.dump(scan, f, indent=2)
        f.write("\n")

    print(
        f"merge-book: paper open={paper['stats']['open_count']} "
        f"closed={closed_count} live_unlocked={LIVE_PUSH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
