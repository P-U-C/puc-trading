"""Phase 5: morning Telegram brief.

Reads the latest daily ticket and sends a compressed Telegram digest.
Uses TG_BOT_TOKEN + TG_CHAT_ID from environment (same pattern as the
trend-corpus runtime notify helper).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any  # noqa: F401  # exposed in preflight() return type

REPO_ROOT = Path(__file__).resolve().parent.parent
SCREEN_DIR = REPO_ROOT / "mispricing" / "screens"
DAILY_DIR = REPO_ROOT / "paper-journal" / "mispricing" / "daily"
MAX_LEN = 4000


def preflight() -> dict[str, Any]:
    """Loud check of Telegram creds + send a canary message. Returns a
    dict the cron logs grep for; raises RuntimeError if creds missing
    OR send fails. Per Codex review structural rec #7: silent daily
    Telegram failures should fail loud on a schedule, not stay silent."""
    token = os.environ.get("TG_BOT_TOKEN")
    chat = os.environ.get("TG_CHAT_ID")
    missing = [k for k, v in (("TG_BOT_TOKEN", token), ("TG_CHAT_ID", chat))
               if not v]
    if missing:
        raise RuntimeError(
            f"morning_brief preflight: missing env vars: {missing}. "
            "Set them in the user shell profile or pass them to the cron job."
        )
    sent = _send_telegram(
        f"preflight canary {dt.datetime.utcnow().isoformat(timespec='seconds')}Z",
        prefix="[puc-trading preflight]",
    )
    if not sent:
        raise RuntimeError("morning_brief preflight: telegram send returned False")
    return {"token_present": True, "chat_present": True, "canary_sent": True}


def _send_telegram(text: str, *, prefix: str = "[puc-trading mispricing]") -> bool:
    token = os.environ.get("TG_BOT_TOKEN")
    chat = os.environ.get("TG_CHAT_ID")
    if not token or not chat:
        print("morning_brief: TG_BOT_TOKEN / TG_CHAT_ID missing", file=sys.stderr)
        return False
    if prefix:
        text = f"{prefix}\n{text}"
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN] + "\n...[truncated]"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"morning_brief: send failed: {exc}", file=sys.stderr)
        return False


def compose_brief(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    daily_path = DAILY_DIR / f"{today.isoformat()}.md"
    screen_path = SCREEN_DIR / f"screen-{today.isoformat()}.json"
    if not daily_path.exists():
        return f"no daily ticket for {today.isoformat()}; run mispricing refresh first"
    text = daily_path.read_text()
    # Strip everything after SCREEN SUMMARY to keep brief tight.
    if "## SCREEN SUMMARY" in text:
        text = text.split("## SCREEN SUMMARY")[0]
    # Compact: collapse multiple blank lines.
    out_lines: list[str] = []
    blank = 0
    for line in text.splitlines():
        if not line.strip():
            blank += 1
            if blank <= 1:
                out_lines.append("")
        else:
            blank = 0
            out_lines.append(line)
    out = "\n".join(out_lines)
    if screen_path.exists():
        try:
            j = json.loads(screen_path.read_text())
            s = j.get("summary", {})
            out += (
                f"\n\nscreen: {s.get('total', 0)} total | "
                f"income {s.get('income', 0)} | lottery {s.get('lottery', 0)} | "
                f"mispriced_up {s.get('mispriced_up', 0)} | no_chain {s.get('no_chain', 0)}"
            )
        except json.JSONDecodeError:
            pass
    return out


def send_brief(today: dt.date | None = None, *, dry_run: bool = False) -> bool:
    text = compose_brief(today)
    if dry_run:
        print(text)
        return True
    return _send_telegram(text)
