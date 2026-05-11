#!/usr/bin/env python3
"""
Push the day's cron-run summary to Chad's Telegram via the existing bot.

Reads:
  cron-runs/<UTC-date>.summary.txt
  /home/ubuntu/.claude/channels/telegram/.env   (TELEGRAM_BOT_TOKEN)

Sends to chat_id=505841972 (Chad). The bot used is the same Claude-Code
plugin bot (@claude_pft_chad_bot). Outbound API sends do not trigger inbound
delivery to a Claude Code session, so this is safe to run from cron.

Exit codes:
  0  message sent OR no summary file (no-op silent)
  1  network/auth error from Telegram
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "cron-runs"
TG_ENV = Path("/home/ubuntu/.claude/channels/telegram/.env")
CHAD_CHAT_ID = 505841972


def read_token() -> str | None:
    if not TG_ENV.exists():
        return None
    for line in TG_ENV.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    return None


def build_message(summary_json_path: Path, summary_txt_path: Path, today_str: str) -> str:
    if not summary_json_path.exists():
        return ""
    s = json.loads(summary_json_path.read_text())
    fills = s.get("fills_triggered", [])
    exits = s.get("exits_triggered", [])
    errors = s.get("errors", [])
    marks = s.get("marks_computed", 0)
    rep_url = s.get("report_url")
    rep_pub = s.get("report_publication_date")

    lines = [
        f"AGTI paper-journal cron — {today_str}",
        "",
    ]
    if s.get("report_fetched"):
        lines.append(f"Report: {rep_pub}  →  {rep_url}")
    else:
        lines.append("Report: not fetched (see errors below)")
    lines.append("")
    lines.append(f"Marks computed: {marks}")
    lines.append(f"Fills triggered: {len(fills)}")
    lines.append(f"Exits triggered: {len(exits)}")
    if fills:
        lines.append("")
        lines.append("Fills:")
        for f in fills:
            lines.append(f"  {f['ticker']} @ {f['fill_price']:.4f} on {f['fill_date']}")
    if exits:
        lines.append("")
        lines.append("Exits:")
        for e in exits:
            lines.append(f"  {e['ticker']} ({e['reason']}) → {e['exit_pct']:+.2%}")

    # If signal extraction has not run, surface the prompt
    extracted_path = ROOT / "daily" / f"{rep_pub}.signals-extracted.json" if rep_pub else None
    if extracted_path and not extracted_path.exists() and rep_url:
        lines.append("")
        lines.append("⚠ New report not yet signal-extracted.")
        lines.append("  reply /extract to pull signals into positions.json")

    if errors:
        # Trim to top 5 — full list in cron-runs/<date>.summary.txt
        lines.append("")
        lines.append(f"Errors ({len(errors)}, showing first 3):")
        for err in errors[:3]:
            lines.append(f"  - {err}")

    return "\n".join(lines)


def send(token: str, chat_id: int, text: str) -> bool:
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
            return bool(body.get("ok"))
    except Exception as e:
        sys.stderr.write(f"telegram send failed: {e}\n")
        return False


def main() -> int:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary_json = RUNS_DIR / f"{today_str}.summary.json"
    summary_txt = RUNS_DIR / f"{today_str}.summary.txt"

    if not summary_json.exists():
        sys.stderr.write(f"no summary at {summary_json}, skipping notify\n")
        return 0

    token = read_token()
    if not token:
        sys.stderr.write(f"no TELEGRAM_BOT_TOKEN at {TG_ENV}\n")
        return 1

    msg = build_message(summary_json, summary_txt, today_str)
    if not msg:
        return 0

    ok = send(token, CHAD_CHAT_ID, msg)
    if not ok:
        return 1
    print(f"sent telegram notification ({len(msg)} chars) to chat_id={CHAD_CHAT_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
