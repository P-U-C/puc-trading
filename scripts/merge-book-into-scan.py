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

GO_LIVE_TRADES = int(os.environ.get("GO_LIVE_TRADES", "30"))
LIVE_PUSH = os.environ.get("LIVE_PUSH", "0") == "1"


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


def _build_paper() -> dict[str, Any]:
    open_rows = _read_json(PAPER_OPEN)
    closed_rows = _read_json(PAPER_CLOSED)
    return {
        "open": open_rows,
        "closed": closed_rows,
        "stats": _summary(open_rows, closed_rows),
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
    closed_count = paper["stats"]["closed_count"]

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
