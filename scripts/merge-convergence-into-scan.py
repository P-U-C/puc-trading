#!/usr/bin/env python3
"""Merge the daily convergence corpus artifact into the scanner dashboard JSON.

Reads:
  - corpus/convergence-latest.json  (written by trend-corpus
    refresh-convergence, daily 13:55 UTC)

Rewrites the `convergence` key of scanner/scan-results.json -- one row per
scored ticker: {ticker, theme, score, tier, status} -- and stamps
scan_meta.convergence_refreshed_at with the artifact's generated_at.

Until 2026-06-12 the page served the hardcoded April fixture list baked into
run_live_scan.py, so themes added after April (biomechanics, cicadas) and all
daily score movement never reached the public page. The row schema is
unchanged; check-dashboard-shape.py still validates.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PUC = Path(os.environ.get("PUC_TRADING_DIR", os.path.expanduser("~/puc-trading")))
SCAN_PATH = Path(
    os.environ.get(
        "SCAN_RESULTS_PATH",
        os.path.expanduser("~/pft-validator/scanner/scan-results.json"),
    )
)
ARTIFACT = Path(
    os.environ.get("CONVERGENCE_FILE", str(PUC / "corpus" / "convergence-latest.json"))
)

# theme_ids kept OFF the public page. The corpus artifact mixes public sector
# themes with private trading theses -- cicadas (the ENSO commodity cycle
# thesis) is a live trading position set, not a sector theme, and exposing
# its ranked ticker list publishes the thesis.
EXCLUDE_THEME_IDS = {
    t.strip()
    for t in os.environ.get("SCANNER_EXCLUDE_THEME_IDS", "cicadas").split(",")
    if t.strip()
}


def main() -> int:
    if not ARTIFACT.exists():
        print(f"merge-convergence: artifact missing: {ARTIFACT}", file=sys.stderr)
        return 1
    if not SCAN_PATH.exists():
        print(f"merge-convergence: scan results missing: {SCAN_PATH}", file=sys.stderr)
        return 1

    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    payload = json.loads(SCAN_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("merge-convergence: scan-results root must be an object", file=sys.stderr)
        return 1

    # Canonical display name per theme_id -- score rows from different
    # generators disagree on it (e.g. "Peptides" vs "GLP-1 / Peptides" for
    # theme_id=peptides), which would split one theme into two page cards.
    canonical = {
        t.get("theme_id"): t.get("theme_name")
        for t in artifact.get("themes", [])
        if t.get("theme_id") and t.get("theme_name")
    }

    rows = []
    for r in artifact.get("scores", []):
        if r.get("theme_id") in EXCLUDE_THEME_IDS:
            continue
        ticker = r.get("ticker")
        theme = canonical.get(r.get("theme_id")) or r.get("theme") or r.get("theme_id")
        if not ticker or not theme:
            continue
        rows.append(
            {
                "ticker": ticker,
                "theme": theme,
                "score": round(float(r.get("score") or 0.0), 3),
                "tier": r.get("tier") or "LOW",
                "status": r.get("status") or "emerging",
            }
        )

    if not rows:
        print("merge-convergence: artifact yielded 0 rows; leaving page as-is", file=sys.stderr)
        return 1

    rows.sort(key=lambda r: (r["theme"], -r["score"], r["ticker"]))
    payload["convergence"] = rows
    meta = payload.setdefault("scan_meta", {})
    meta["convergence_refreshed_at"] = artifact.get("generated_at")

    SCAN_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    themes = sorted({r["theme"] for r in rows})
    print(
        f"merge-convergence: {len(rows)} rows across {len(themes)} themes "
        f"(artifact {artifact.get('generated_at')})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
