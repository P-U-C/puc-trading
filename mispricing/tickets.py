"""Phase 4: daily trade-ticket generator.

Reads the latest screen + shaper output + current paper positions,
emits paper-journal/mispricing/daily/YYYY-MM-DD.md.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import BOOK_USD, INCOME_FRACTION, LOTTERY_FRACTION
from .detector import MispricingRow
from .shaper import TradeCandidate, candidates_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = REPO_ROOT / "paper-journal" / "mispricing" / "daily"
TRACKER_PATH = REPO_ROOT / "paper-journal" / "mispricing" / "tracker.md"


def _row_table(rows: list[TradeCandidate], header: str) -> list[str]:
    if not rows:
        return [f"## {header}", "", "_(no candidates this run)_", ""]
    lines = [f"## {header}", ""]
    lines.append("| # | ticker | theme | structure | strike | upper | expiry | qty | cost/ct | cost | rationale |")
    lines.append("|--:|--------|-------|-----------|-------:|------:|--------|----:|--------:|-----:|-----------|")
    for i, r in enumerate(rows, 1):
        strike = f"${r.strike:.2f}" if r.strike else "—"
        upper = f"${r.strike_upper:.2f}" if r.strike_upper else "—"
        cost = f"${r.cost_total_usd:,.2f}" if r.cost_total_usd else "—"
        cost_per = f"${r.cost_per_contract_usd:,.2f}" if r.cost_per_contract_usd else "—"
        lines.append(
            f"| {i} | {r.ticker} | {r.theme_id} | {r.structure} | {strike} | {upper} | "
            f"{r.expiry or '—'} | {r.quantity_contracts} | {cost_per} | {cost} | "
            f"{r.rationale} |"
        )
    lines.append("")
    return lines


def build_daily(
    *,
    today: dt.date | None = None,
    screen_rows: list[MispricingRow],
    candidates: list[TradeCandidate],
    held_positions: list[dict[str, Any]] | None = None,
    closes: list[dict[str, Any]] | None = None,
) -> str:
    today = today or dt.date.today()
    summary = candidates_summary(candidates)
    income = [c for c in candidates if c.bucket == "income"]
    lottery = [c for c in candidates if c.bucket == "lottery"]
    closes = closes or []
    held = held_positions or []

    lines: list[str] = [
        f"# mispricing-screen daily ticket {today.isoformat()}",
        "",
        f"Book size: ${BOOK_USD:,} | income budget: ${BOOK_USD * INCOME_FRACTION:,.0f} "
        f"| lottery budget: ${BOOK_USD * LOTTERY_FRACTION:,.0f}",
        "",
        f"Recommendations: {summary['income_count']} income, {summary['lottery_count']} lottery, "
        f"${summary['grand_total_usd']:,.2f} total proposed deployment.",
        "",
    ]
    lines.extend(_row_table(income, "NEW INCOME"))
    lines.extend(_row_table(lottery, "NEW LOTTERY"))

    lines.append("## CLOSE")
    if closes:
        lines.append("")
        lines.append("| ticker | structure | reason | exit_price | pnl |")
        lines.append("|--------|-----------|--------|-----------:|----:|")
        for c in closes:
            lines.append(
                f"| {c['ticker']} | {c.get('structure', '?')} | {c.get('reason', '?')} | "
                f"${c.get('exit_price', 0):.2f} | ${c.get('pnl', 0):+.2f} |"
            )
    else:
        lines.append("")
        lines.append("_(no exits triggered today)_")
    lines.append("")

    lines.append("## HOLD")
    if held:
        lines.append("")
        lines.append("| ticker | structure | strike | expiry | cost | mark | %p&l |")
        lines.append("|--------|-----------|-------:|--------|-----:|-----:|----:|")
        for p in held:
            lines.append(
                f"| {p['ticker']} | {p.get('structure', '?')} | "
                f"${p.get('strike', 0):.2f} | {p.get('expiry', '?')} | "
                f"${p.get('cost_total_usd', 0):,.2f} | "
                f"${p.get('mark', 0):.2f} | {p.get('pct_pnl', 0):+.1f}% |"
            )
    else:
        lines.append("")
        lines.append("_(no open positions)_")
    lines.append("")

    # Screen summary
    by_bucket = {"income": 0, "lottery": 0, "excluded": 0}
    by_class = {"mispriced_up": 0, "fair": 0, "mispriced_down": 0,
                "no_market": 0, "no_chain": 0}
    for r in screen_rows:
        by_bucket[r.bucket] = by_bucket.get(r.bucket, 0) + 1
        by_class[r.classification] = by_class.get(r.classification, 0) + 1

    lines.append("## SCREEN SUMMARY")
    lines.append("")
    lines.append(f"- screen rows: {len(screen_rows)}")
    lines.append(f"- by bucket: " + ", ".join(f"{k}={v}" for k, v in by_bucket.items()))
    lines.append(f"- by class: " + ", ".join(f"{k}={v}" for k, v in by_class.items()))
    lines.append("")

    return "\n".join(lines)


def write_daily(text: str, today: dt.date | None = None) -> Path:
    today = today or dt.date.today()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out = DAILY_DIR / f"{today.isoformat()}.md"
    out.write_text(text)
    return out
