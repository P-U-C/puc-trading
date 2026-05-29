"""One-shot: cut the 13 over-concentrated cicadas legs and rebuild the book as
the CORRECTED screen (tenor floor + concentration caps, 2026-05-29) would have
produced it. Audit trail preserved: the 13 buggy legs are archived to
closed.json; the corrected positions are back-dated to the original entry date.

Run once, by hand, after the engine patch + tests pass. Reversible via the
positions.json backup it writes to backups/ first.
"""
from __future__ import annotations
import datetime as dt
import glob
import json
import shutil
from pathlib import Path

from mispricing import detector, shaper, paper_executor, remark

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "backups"
ENTRY_DATE = dt.date(2026, 5, 19)   # original cicadas entry date to back-date to
CUT_DATE = "2026-05-29"
CIC_THEME = "cicadas"


def _latest_cache_spot(ticker: str) -> float | None:
    fs = sorted(glob.glob(str(REPO / "options-cache" / f"{ticker}-*.json")))
    if not fs:
        return None
    try:
        d = json.loads(Path(fs[-1]).read_text())
        s = d.get("spot")
        return float(s) if s else None
    except Exception:
        return None


def main() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = "20260529-cicadas-realign"
    shutil.copy2(paper_executor.POSITIONS_PATH, BACKUP_DIR / f"positions.json.{stamp}")
    shutil.copy2(paper_executor.CLOSED_PATH, BACKUP_DIR / f"closed.json.{stamp}")

    positions = paper_executor._load_positions()
    open_cic = [p for p in positions if p.status == "open" and p.theme_id == CIC_THEME]
    print(f"open cicadas legs to cut: {len(open_cic)}")
    realized = 0.0
    for p in open_cic:
        # close at the position's current model mark (its last yfinance re-mark)
        p.status = "closed"
        p.closed_at = CUT_DATE
        p.close_price = p.mark
        p.close_reason = ("re-screened 2026-05-29: concentration/tenor fix + "
                          "thesis-direction reading (FXA is SHORT AUD per cicadas.md, "
                          "not bullish calls); replaced with direction-correct structure")
        if p.cost_per_contract_usd is not None and p.close_price is not None:
            realized += (p.close_price - p.cost_per_contract_usd) * p.quantity_contracts
    print(f"realized P&L locked by the cut: ${realized:,.2f}")
    paper_executor._save_positions(positions)

    # --- rebuild: run the CORRECTED engine on the original entry-date cache ---
    rows = detector.screen(today=ENTRY_DATE, prefer_source="yfinance")
    cands = shaper.shape(rows)
    cic_cands = [c for c in cands if c.theme_id == CIC_THEME]
    # Dedup identical contracts attributed to multiple catalysts (the same FXA
    # 70/77 call spread is tagged to the ENSO / ECMWF / IRI catalysts — it is one
    # trade, not three). Keep the canonical NOAA-ENSO attribution. open_paper
    # does not dedup within a single batch, so we must do it here.
    seen: set = set()
    deduped = []
    PREF = "cat_noaa_enso_2026_06"
    cic_cands.sort(key=lambda c: 0 if c.catalyst_id == PREF else 1)
    for c in cic_cands:
        k = (c.ticker, c.structure, c.strike, c.strike_upper, c.expiry)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    cic_cands = deduped
    print(f"\ncorrected cicadas candidates (deduped by contract): {len(cic_cands)}")
    for c in cic_cands:
        print(f"  {c.ticker} {c.structure} K={c.strike}/{c.strike_upper} "
              f"exp={c.expiry} qty={c.quantity_contracts} ${c.cost_total_usd} "
              f"[{c.catalyst_id}] {c.rationale}")

    new = paper_executor.open_paper(cic_cands, today=ENTRY_DATE)
    print(f"\nnewly opened (back-dated {ENTRY_DATE}): {len(new)}")

    # mark the survivors to current spot (same yfinance-cache basis the cron uses)
    positions = paper_executor._load_positions()
    n = remark.remark_positions(positions, _latest_cache_spot)
    paper_executor._save_positions(positions)
    print(f"re-marked {n} open positions to current spot")

    summary = paper_executor.settle(today=dt.date(2026, 5, 29))
    print(f"\nsettle: {summary}")

    open_after = [p for p in paper_executor._load_positions()]
    print("\n=== OPEN BOOK AFTER REBUILD ===")
    for p in open_after:
        print(f"  {p.ticker} {p.structure} K={p.strike}/{p.strike_upper} exp={p.expiry} "
              f"entry={p.entry_date} cost=${p.cost_total_usd} mark={p.mark} "
              f"pnl={p.pct_pnl:+.1f}% [{p.theme_id}]")


if __name__ == "__main__":
    main()
