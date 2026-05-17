"""Phase 6: paper-trade executor + tracker.md updater.

Simulates entries / exits on the candidates emitted by Phase 4.
Tracks open positions in paper-journal/mispricing/positions.json,
updates tracker.md, applies exit rules deterministically.

Live execution is gated -- requires LIVE_PUSH=1 env var. When LIVE_PUSH
is 0 (default) the executor only updates the paper book; no IB orders
placed.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from .shaper import TradeCandidate

REPO_ROOT = Path(__file__).resolve().parent.parent
JOURNAL_DIR = REPO_ROOT / "paper-journal" / "mispricing"
POSITIONS_PATH = JOURNAL_DIR / "positions.json"
CLOSED_PATH = JOURNAL_DIR / "closed.json"
TRACKER_PATH = JOURNAL_DIR / "tracker.md"


@dataclass
class PaperPosition:
    id: str                 # ticker-structure-strike-expiry-entry_date
    bucket: str             # income | lottery
    ticker: str
    theme_id: str
    catalyst_id: str | None
    event_date: str | None
    structure: str
    strike: float | None
    strike_upper: float | None
    expiry: str | None
    quantity_contracts: int
    cost_per_contract_usd: float
    cost_total_usd: float
    entry_date: str
    entry_rationale: str
    mark: float = 0.0
    pct_pnl: float = 0.0
    status: str = "open"     # open | closed
    closed_at: str | None = None
    close_reason: str | None = None
    close_price: float | None = None


def _load_positions() -> list[PaperPosition]:
    if not POSITIONS_PATH.exists():
        return []
    raw = json.loads(POSITIONS_PATH.read_text())
    return [PaperPosition(**p) for p in raw]


def _load_closed() -> list[PaperPosition]:
    if not CLOSED_PATH.exists():
        return []
    raw = json.loads(CLOSED_PATH.read_text())
    return [PaperPosition(**p) for p in raw]


def _save_positions(positions: list[PaperPosition]) -> None:
    POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    POSITIONS_PATH.write_text(
        json.dumps([asdict(p) for p in positions], indent=2, default=str)
    )


def _save_closed(closed: list[PaperPosition]) -> None:
    CLOSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLOSED_PATH.write_text(
        json.dumps([asdict(p) for p in closed], indent=2, default=str)
    )


def open_paper(candidates: list[TradeCandidate],
               *, today: dt.date | None = None) -> list[PaperPosition]:
    """Convert candidates into paper positions. Returns the newly-opened."""
    today = today or dt.date.today()
    positions = _load_positions()
    existing_keys = {
        (p.ticker, p.structure, p.strike, p.expiry, p.entry_date)
        for p in positions if p.status == "open"
    }
    new: list[PaperPosition] = []
    for c in candidates:
        if c.cost_total_usd is None or c.cost_per_contract_usd is None:
            continue
        key = (c.ticker, c.structure, c.strike, c.expiry, today.isoformat())
        if key in existing_keys:
            continue
        pos = PaperPosition(
            id=f"{c.ticker}-{c.structure}-{c.strike}-{c.expiry}-{today.isoformat()}",
            bucket=c.bucket, ticker=c.ticker, theme_id=c.theme_id,
            catalyst_id=c.catalyst_id, event_date=c.event_date,
            structure=c.structure, strike=c.strike,
            strike_upper=c.strike_upper, expiry=c.expiry,
            quantity_contracts=c.quantity_contracts,
            cost_per_contract_usd=c.cost_per_contract_usd,
            cost_total_usd=c.cost_total_usd,
            entry_date=today.isoformat(),
            entry_rationale=c.rationale,
            mark=c.cost_per_contract_usd,
            pct_pnl=0.0, status="open",
        )
        positions.append(pos)
        new.append(pos)
    _save_positions(positions)
    return new


# Exit rules (mirror agtico bucket discipline):
# 1. +50% gain → close
# 2. 1 day pre-catalyst → close (income only; lottery holds)
# 3. -50% loss for income trades, -70% for lottery → close (stop loss)
# 4. Expiry-week → close at week start
def evaluate_exits(positions: list[PaperPosition], *,
                   today: dt.date | None = None) -> list[PaperPosition]:
    """Apply exit rules; return positions that were closed this run."""
    today = today or dt.date.today()
    just_closed: list[PaperPosition] = []
    open_positions = [p for p in positions if p.status == "open"]
    for p in open_positions:
        if p.pct_pnl >= 50.0:
            _close(p, today, "+50% gain target", p.mark)
            just_closed.append(p)
            continue
        if p.bucket == "income" and p.pct_pnl <= -50.0:
            _close(p, today, "income stop loss (-50%)", p.mark)
            just_closed.append(p)
            continue
        if p.bucket == "lottery" and p.pct_pnl <= -70.0:
            _close(p, today, "lottery stop loss (-70%)", p.mark)
            just_closed.append(p)
            continue
        event_date = _parse(p.event_date) if p.event_date else None
        expiry_date = _parse(p.expiry) if p.expiry else None
        if (p.bucket == "income" and event_date
                and (event_date - today).days == 1):
            _close(p, today, "1 day pre-catalyst (income)", p.mark)
            just_closed.append(p)
            continue
        if expiry_date and (expiry_date - today).days <= 7:
            _close(p, today, "expiry week", p.mark)
            just_closed.append(p)
            continue
    # Persist mutations so settle() sees them on disk.
    if just_closed:
        _save_positions(positions)
    return just_closed


def _close(p: PaperPosition, today: dt.date, reason: str, mark: float) -> None:
    p.status = "closed"
    p.closed_at = today.isoformat()
    p.close_reason = reason
    p.close_price = mark


def settle(today: dt.date | None = None) -> dict[str, Any]:
    """Move closed positions out of positions.json into closed.json,
    rewrite tracker.md, return a summary."""
    today = today or dt.date.today()
    positions = _load_positions()
    closed = _load_closed()
    still_open = [p for p in positions if p.status == "open"]
    just_closed = [p for p in positions if p.status == "closed"]
    closed.extend(just_closed)
    _save_positions(still_open)
    _save_closed(closed)
    _rewrite_tracker(still_open, closed)
    return {
        "today": today.isoformat(),
        "open": len(still_open),
        "closed_today": len(just_closed),
        "closed_total": len(closed),
    }


def _parse(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _rewrite_tracker(open_positions: list[PaperPosition],
                     closed: list[PaperPosition]) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    lines: list[str] = [
        "# mispricing-screen paper-trade tracker",
        "",
        f"**As of:** {today}",
        "**Book status:** PAPER (live gated at `LIVE_PUSH=1` after 30-day validation)",
        "**Rules:** see `exit-rules.md`",
        "",
        "## Go-live gate",
        "",
        "Becomes live when BOTH:",
        "1. 30 closed paper trades minimum",
        "2. 30 calendar days from first open",
        "",
        f"Current closed count: **{len(closed)}**",
        "",
        "---",
        "",
        "## Open positions",
        "",
    ]
    if not open_positions:
        lines.append("_(no open positions)_")
    else:
        lines.append("| # | bucket | ticker | structure | strike | exp | qty | cost | mark | %p&l |")
        lines.append("|--:|--------|--------|-----------|-------:|-----|----:|-----:|-----:|----:|")
        for i, p in enumerate(open_positions, 1):
            lines.append(
                f"| {i} | {p.bucket} | {p.ticker} | {p.structure} | "
                f"${p.strike or 0:.2f} | {p.expiry or '—'} | "
                f"{p.quantity_contracts} | ${p.cost_total_usd:,.2f} | "
                f"${p.mark:.2f} | {p.pct_pnl:+.1f}% |"
            )
    lines.append("")
    lines.append("## Closed positions (last 30)")
    lines.append("")
    if not closed:
        lines.append("_(none)_")
    else:
        lines.append("| ticker | structure | entry | exit | reason | cost | exit_px | %p&l |")
        lines.append("|--------|-----------|-------|------|--------|-----:|--------:|----:|")
        for p in closed[-30:][::-1]:
            net = p.close_price or 0
            pnl_pct = ((net - p.cost_per_contract_usd) / p.cost_per_contract_usd * 100
                       if p.cost_per_contract_usd else 0)
            lines.append(
                f"| {p.ticker} | {p.structure} | {p.entry_date} | {p.closed_at} | "
                f"{p.close_reason} | ${p.cost_total_usd:,.2f} | "
                f"${net:.2f} | {pnl_pct:+.1f}% |"
            )
    lines.append("")
    TRACKER_PATH.write_text("\n".join(lines))


def held_positions_for_shaper() -> list[dict[str, Any]]:
    """Format current open positions for shaper.shape(held_positions=...)."""
    return [asdict(p) for p in _load_positions() if p.status == "open"]
