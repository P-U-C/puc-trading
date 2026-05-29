#!/usr/bin/env python3
"""
Extract signals from the most recently fetched AGTI report.

Uses `claude -p` (the Claude Code CLI in non-interactive mode) to call the
extraction prompt. Trades $0.06/call for set-and-forget reliability. Outputs:

  daily/<rep_date>.signals-extracted.json   -- structured extraction result
  daily/<rep_date>.md                       -- appended human-readable table
  scripts/positions.json                     -- new entries added; flips handled

Skips extraction if signals-extracted.json already exists for that report
(so the cron can run idempotently). Run with --force to re-extract.

Hard rules baked into the prompt (see SIGNAL_EXTRACTION_PROMPT):
  - Output is JSON only (no prose)
  - Each entry: ticker, direction (long|short|neutral), structure, horizon,
    catalyst (if named), notes
  - Direction normalization: long, short, neutral -- nothing else
  - Macro-proxy filter applied at the END (filter-out list)
  - Flag flips against existing positions.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "daily"
RAW_DIR = DAILY_DIR / "raw"
POSITIONS_PATH = ROOT / "scripts" / "positions.json"

MACRO_PROXY_SKIPLIST = {"XLE", "BNO", "TLT", "USO", "GLD", "SLV", "TQQQ", "SQQQ"}

# Edge filter (added 2026-05-29). The closed-trade record (82 closed signals)
# shows the book's edge is concentrated in EQUITY LONGS (62-63% hit) while the
# other classes are dilutive drag that flatten average return to ~0:
#     equity-long 63% | short 44% | ETF 38% | forex 40%
# This mirrors the original backtest's "macro-proxy ETF 0-of-4" failure mode.
# When EQUITY_LONG_ONLY is on, the cron only OPENS the proven-edge class; the
# dilutive classes are still logged (denominator-honest, same as the macro-proxy
# skip) but never deployed. Flip to False to revert to all-class behaviour.
EQUITY_LONG_ONLY = True


def _edge_allows(direction: str, structure: str) -> bool:
    """True if the signal is in the proven-edge class (equity long)."""
    if not EQUITY_LONG_ONLY:
        return True
    return direction == "long" and structure == "equity"

SIGNAL_EXTRACTION_PROMPT = """You are extracting tradeable signals from a Post Fiat AGTI Intelligence Report.

Output ONLY valid JSON, no prose, no markdown fences. Schema:

{
  "report_date": "YYYY-MM-DD",
  "covers_window": "YYYY-MM-DD or short description",
  "signals": [
    {
      "ticker": "yfinance-compatible symbol (e.g. AMZN, GBPUSD=X, USDINR=X, ^NSEI)",
      "direction": "long | short | neutral",
      "structure": "equity | etf | forex | option | index",
      "horizon": "T+5_default | catalyst:YYYY-MM-DD | T+N_explicit | unspecified",
      "catalyst_text": "short free-text describing the catalyst, if any",
      "ibkr_executable": true | false,
      "notes": "1-2 sentence rationale extracted from the report"
    }
  ]
}

Rules:
- ticker must be the yfinance form. PARA -> PSKY (post-merger). LGF.A -> LION. Use =X suffix for forex.
- direction: only long, short, neutral. Reject anything else.
- structure: only those 5 enum values.
- ibkr_executable: false for private companies (Anthropic, OpenAI, sports clubs unless listed), foreign indices direct (^NSEI), delisted names (INST), or anything that needs futures/leveraged ETPs.
- Skip macro-proxy ETFs (XLE, BNO, TLT, USO, GLD, TQQQ, SQQQ) -- do NOT include them at all in the signals[] array. The user's backtest showed these hit 0-of-4.
- If the report mentions the same ticker multiple times with different framings, output ONE entry per ticker with the most-recent or strongest direction.
- Forex: long FX-pair-X means buying X. Short means selling X. Use the report's framing.
- "Long INR" -> ticker USDINR=X with direction short (selling USD against INR).
- If the report contains no extractable signals, return signals=[].

Read the raw report below and emit the JSON:

---REPORT BEGIN---
{REPORT_TEXT}
---REPORT END---
"""


def latest_report_date() -> str | None:
    if not RAW_DIR.exists():
        return None
    htmls = sorted(RAW_DIR.glob("*.html"))
    if not htmls:
        return None
    return htmls[-1].stem  # YYYY-MM-DD


def html_to_text(html: str) -> str:
    """Cheap HTML stripping. AGTI reports are mostly clean markdown rendered to HTML."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
    raw = result.stdout
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse claude JSON envelope: {e}\nfirst 500 chars: {raw[:500]}")
    return outer.get("result", "")


def parse_signals_json(claude_output: str) -> dict:
    text = claude_output.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return json.loads(text)


def add_to_positions(extracted: dict, rep_date: str) -> tuple[int, int, int]:
    if not POSITIONS_PATH.exists():
        positions = {"positions": [], "_skipped": []}
    else:
        positions = json.loads(POSITIONS_PATH.read_text())

    by_ticker = {p["ticker"]: p for p in positions["positions"] if p.get("status") in {"open", "pending"}}

    added = 0
    flipped = 0
    skipped = 0

    for sig in extracted.get("signals", []):
        ticker = sig.get("ticker")
        direction = sig.get("direction")

        if direction == "neutral":
            skipped += 1
            continue

        if ticker in MACRO_PROXY_SKIPLIST:
            skipped += 1
            continue

        if not sig.get("ibkr_executable", True):
            skipped += 1
            continue

        existing = by_ticker.get(ticker)
        if existing:
            if existing["direction"] == direction:
                # Same direction reaffirmed -- no action, the original position stays open
                continue
            else:
                # Direction flip: close the old. We close on a flip even if the
                # new side is outside the edge class -- a report turning against
                # an open position is still a valid exit signal.
                existing["status"] = "closed"
                existing["exit_date"] = rep_date
                existing["exit_reason"] = f"direction_flip_to_{direction}_per_report_{rep_date}"
                existing["exit_price"] = existing.get("last_mark")
                existing["exit_pct"] = existing.get("last_mark_pct")
                flipped += 1

        # Edge filter: only OPEN positions in the proven equity-long edge class.
        # Dilutive classes are logged for denominator honesty but not deployed.
        if not _edge_allows(direction, sig.get("structure", "equity")):
            positions.setdefault("_skipped", []).append({
                "ticker": ticker,
                "reason": (f"edge-filter {rep_date}: {direction}/"
                           f"{sig.get('structure', 'equity')} outside proven "
                           f"equity-long edge class (EQUITY_LONG_ONLY)"),
            })
            skipped += 1
            continue

        new_pos = {
            "ticker": ticker,
            "direction": direction,
            "report_date": rep_date,
            "entry_date": None,
            "entry_price": None,
            "structure": sig.get("structure", "equity"),
            "horizon": sig.get("horizon", "T+5_default"),
            "stop_pct": -0.15,
            "take_pct": 0.30,
            "status": "pending",
            "ibkr_executable": True,
            "notes": sig.get("notes", "")[:500],
        }
        positions["positions"].append(new_pos)
        added += 1

    POSITIONS_PATH.write_text(json.dumps(positions, indent=2, sort_keys=True) + "\n")
    return added, flipped, skipped


def append_daily_md(rep_date: str, extracted: dict, added: int, flipped: int, skipped: int) -> None:
    daily = DAILY_DIR / f"{rep_date}.md"
    body_lines = [
        "",
        "---",
        "",
        f"## Auto-extracted signals (cron, {datetime.now(timezone.utc).isoformat()})",
        "",
        f"- Added to positions.json: **{added}**",
        f"- Direction-flipped (closed-old + added-new): **{flipped}**",
        f"- Skipped (neutral / macro-proxy / non-executable): **{skipped}**",
        "",
        "| Ticker | Direction | Structure | Horizon | Catalyst | Executable | Notes |",
        "|--------|-----------|-----------|---------|----------|:----------:|-------|",
    ]
    for sig in extracted.get("signals", []):
        body_lines.append(
            "| {ticker} | {direction} | {structure} | {horizon} | {cat} | {exec} | {notes} |".format(
                ticker=sig.get("ticker", ""),
                direction=sig.get("direction", ""),
                structure=sig.get("structure", ""),
                horizon=sig.get("horizon", ""),
                cat=(sig.get("catalyst_text") or "")[:60],
                exec="Y" if sig.get("ibkr_executable", True) else "N",
                notes=(sig.get("notes") or "")[:120].replace("|", "\\|"),
            )
        )

    if daily.exists():
        with daily.open("a") as f:
            f.write("\n".join(body_lines) + "\n")
    else:
        daily.write_text("\n".join(body_lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Report date YYYY-MM-DD; defaults to most recent saved raw")
    parser.add_argument("--force", action="store_true", help="Re-extract even if already extracted")
    args = parser.parse_args()

    rep_date = args.date or latest_report_date()
    if not rep_date:
        sys.stderr.write("no raw report found in daily/raw/, nothing to extract\n")
        return 1

    raw_path = RAW_DIR / f"{rep_date}.html"
    if not raw_path.exists():
        sys.stderr.write(f"raw report missing: {raw_path}\n")
        return 1

    extracted_path = DAILY_DIR / f"{rep_date}.signals-extracted.json"
    if extracted_path.exists() and not args.force:
        print(f"already extracted: {extracted_path} (use --force to re-extract)")
        return 0

    raw_text = html_to_text(raw_path.read_text())
    if len(raw_text) > 50000:
        # Trim to keep claude prompt reasonable; AGTI reports are typically <30k
        raw_text = raw_text[:50000] + "\n\n[TRUNCATED]"

    prompt = SIGNAL_EXTRACTION_PROMPT.replace("{REPORT_TEXT}", raw_text)
    print(f"calling claude -p for {rep_date}, prompt length {len(prompt)}...")

    claude_output = call_claude(prompt)
    try:
        extracted = parse_signals_json(claude_output)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"could not parse extracted JSON: {e}\nfirst 500 chars of output:\n{claude_output[:500]}\n")
        return 1

    extracted_path.write_text(json.dumps(extracted, indent=2, sort_keys=True) + "\n")
    print(f"wrote {extracted_path}")
    print(f"extracted {len(extracted.get('signals', []))} signals")

    added, flipped, skipped = add_to_positions(extracted, rep_date)
    print(f"positions.json: +{added} new, {flipped} flipped, {skipped} skipped")

    append_daily_md(rep_date, extracted, added, flipped, skipped)
    print(f"appended summary to daily/{rep_date}.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
