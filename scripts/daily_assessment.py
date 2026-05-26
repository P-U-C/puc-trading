#!/usr/bin/env python3
"""Daily system assessment — a nightly sweep that catches the classes of
silent failure that previously went unnoticed for days:

  - trades whose option expires BEFORE their catalyst (the bug that made all
    20 of the first paper book's closed trades resolve at 0%)
  - P&L frozen at 0 because positions were never re-marked
  - the mispricing pipeline silently not running
  - stale corpus / scanner data
  - IB Gateway down, bot heartbeats stale, an unnoticed reboot

It prints a PASS/WARN/FAIL report and (unless --no-send) delivers it to
Telegram. It is observability, not a gate: it always exits 0 so it can never
block a cron chain. Run it AFTER the nightly refresh so it assesses fresh state.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent
POSITIONS = REPO / "paper-journal" / "mispricing" / "positions.json"
RUN_STATE = REPO / "run-state"
CONVERGENCE = REPO / "corpus" / "convergence-latest.json"
SCAN_RESULTS = HOME / "pft-validator" / "scanner" / "scan-results.json"
HEARTBEAT_STATE = HOME / "pf-scout-bot" / "deploy" / ".heartbeat-state"
TG_ENV = HOME / ".claude" / "channels" / "telegram" / ".env"
# System-wide corpus/surface freshness
TREND_INTEL = HOME / "trend-intel-private"
SWELL_DB = HOME / "swell-checker" / "db.sqlite"
EDITORIAL_ISSUES = HOME / "editorial" / "issues"

OK, WARN, FAIL = "🟢", "🟡", "🔴"
RANK = {OK: 0, WARN: 1, FAIL: 2}


class Report:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def add(self, level: str, text: str) -> None:
        self.lines.append((level, text))

    def worst(self) -> str:
        return max((lvl for lvl, _ in self.lines), key=lambda l: RANK[l], default=OK)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _date(s) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _age_hours(p: Path) -> float | None:
    try:
        return (_now().timestamp() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def check_book(r: Report) -> None:
    try:
        positions = json.loads(POSITIONS.read_text())
    except (OSError, ValueError):
        r.add(WARN, "Book: positions.json unreadable")
        return
    open_pos = [p for p in positions if p.get("status") == "open"]
    if not open_pos:
        r.add(OK, "Book: no open positions")
        return

    today = _now().date()
    expired_before = []
    thin_buffer = []
    for p in open_pos:
        ev, ex = _date(p.get("event_date")), _date(p.get("expiry"))
        if ev and ex:
            gap = (ex - ev).days
            if gap < 0:
                expired_before.append((p.get("ticker"), gap))
            elif gap < 5:
                thin_buffer.append((p.get("ticker"), gap))
    if expired_before:
        r.add(FAIL, f"Book: {len(expired_before)} open trade(s) expire BEFORE "
                    f"their catalyst (the 0% bug): "
                    + ", ".join(f"{t}{g}d" for t, g in expired_before[:6]))
    if thin_buffer:
        r.add(WARN, f"Book: {len(thin_buffer)} trade(s) expire <5d after "
                    "catalyst (thin time-value buffer)")

    # Frozen-mark detector: real re-marking should produce nonzero P&L spread.
    pnls = [p.get("pct_pnl", 0) for p in open_pos]
    cost = sum((p.get("cost_per_contract_usd") or 0) * (p.get("quantity_contracts") or 0)
               for p in open_pos)
    value = sum((p.get("mark") or 0) * (p.get("quantity_contracts") or 0)
                for p in open_pos)
    if all(abs(x) < 1e-9 for x in pnls):
        r.add(WARN, f"Book: all {len(open_pos)} open marks == cost (re-mark may "
                    "not be running — P&L frozen at 0)")
    unreal = value - cost
    pct = (value / cost - 1) * 100 if cost else 0
    r.add(OK, f"Book: {len(open_pos)} open, cost ${cost:,.0f} → value "
              f"${value:,.0f} ({pct:+.1f}%, {unreal:+,.0f} unrealized)")
    if not expired_before and not thin_buffer:
        r.add(OK, "Book: all open trades clear their catalyst ✓")


def check_pipeline(r: Report) -> None:
    runs = sorted([d for d in RUN_STATE.glob("*/") if (d / "manifest.json").exists()],
                  reverse=True) if RUN_STATE.exists() else []
    if not runs:
        r.add(FAIL, "Pipeline: no mispricing run-state found")
        return
    latest = runs[0] / "manifest.json"
    age = _age_hours(latest)
    try:
        m = json.loads(latest.read_text())
    except (OSError, ValueError):
        m = {}
    started = m.get("started_at", "?")
    if age is None or age > 28:
        r.add(FAIL, f"Pipeline: last mispricing run was {started} "
                    f"({age:.0f}h ago) — nightly refresh stale/not running")
    else:
        r.add(OK, f"Pipeline: last run {started} ({age:.0f}h ago)")
    failed = [p["name"] for p in m.get("phases", []) if not p.get("ok")]
    if failed:
        r.add(WARN, f"Pipeline: phases failing last run: {', '.join(failed)}")


def check_freshness(r: Report) -> None:
    for label, path, warn_h in (
        ("convergence corpus", CONVERGENCE, 36),
        ("scanner book", SCAN_RESULTS, 28),
    ):
        age = _age_hours(path)
        if age is None:
            r.add(WARN, f"Data: {label} missing ({path.name})")
        elif age > warn_h:
            r.add(WARN, f"Data: {label} stale ({age:.0f}h old)")
        else:
            r.add(OK, f"Data: {label} fresh ({age:.0f}h)")


def _newest_mtime_hours(paths) -> float | None:
    """Hours since the most-recently-modified file in an iterable of paths."""
    newest = None
    for p in paths:
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        if newest is None or mt > newest:
            newest = mt
    if newest is None:
        return None
    return (_now().timestamp() - newest) / 3600.0


def check_corpuses(r: Report) -> None:
    # trend-intel-private runtime: artifacts are gitignored (so the repo looks
    # stale), but they should regenerate each convergence refresh. Assess the
    # ARTIFACT mtimes, not git.
    arts = list(TREND_INTEL.glob("themes/*/artifacts/opportunity-rows.json")) if TREND_INTEL.exists() else []
    age = _newest_mtime_hours(arts)
    if not arts:
        r.add(WARN, "Corpus: trend-intel-private artifacts not found")
    elif age is None or age > 36:
        r.add(WARN, f"Corpus: trend-intel-private artifacts stale ({age:.0f}h) — runtime not regenerating")
    else:
        r.add(OK, f"Corpus: trend-intel-private artifacts fresh ({age:.0f}h, {len(arts)} themes)")

    # swell-checker: lives on a separate host (city-worker-301); this is only
    # the local checkout's DB as a proxy. Flag loudly — it's a known half-built
    # runtime, so staleness here means it isn't producing.
    age = _age_hours(SWELL_DB)
    if age is None:
        r.add(WARN, "Corpus: swell-checker local DB missing")
    elif age > 48:
        r.add(WARN, f"Corpus: swell-checker local DB stale ({age/24:.0f}d) — remote runtime may be down/half-built")
    else:
        r.add(OK, f"Corpus: swell-checker DB fresh ({age:.0f}h)")


def check_editorial(r: Report) -> None:
    issues = list(EDITORIAL_ISSUES.glob("*.json")) if EDITORIAL_ISSUES.exists() else []
    age = _newest_mtime_hours(issues)
    if not issues:
        r.add(WARN, "Editorial: no issues found")
    elif age is None or age > 24 * 7:
        r.add(WARN, f"Editorial: no new issue in {age/24:.0f}d (publishing is manual — Beehiiv gated)")
    else:
        r.add(OK, f"Editorial: latest issue {age/24:.1f}d old ({len(issues)} total)")


def check_infra(r: Report) -> None:
    # IB Gateway API port
    try:
        out = subprocess.run(["ss", "-ltn"], capture_output=True, text=True, timeout=10).stdout
        if ":4002 " in out:
            r.add(OK, "Infra: IB Gateway up (4002)")
        else:
            r.add(WARN, "Infra: IB Gateway DOWN (port 4002) — watchdog should relaunch")
    except (OSError, subprocess.SubprocessError):
        pass
    # Bot heartbeats
    try:
        state = HEARTBEAT_STATE.read_text().strip()
        r.add(OK if state == "healthy" else WARN, f"Infra: bot heartbeats {state}")
    except OSError:
        r.add(WARN, "Infra: heartbeat state file missing")
    # Recent reboot
    try:
        since = subprocess.run(["uptime", "-s"], capture_output=True, text=True, timeout=10).stdout.strip()
        boot = dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc)
        if (_now() - boot).total_seconds() < 86400:
            r.add(WARN, f"Infra: host rebooted in last 24h ({since}) — verify /tmp configs")
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def update_badge(repo_path: Path, verdict: str) -> bool:
    """Update the public org-README traffic light between STATUS markers and
    push. Deliberately overall-light-ONLY (no component details) — the org
    README is public, so the per-component breakdown stays in the private
    Telegram report. Returns True on push."""
    readme = repo_path / "profile" / "README.md"
    label = {OK: "🟢 nominal", WARN: "🟡 attention needed",
             FAIL: "🔴 action needed"}[verdict]
    block = (f"<!-- STATUS:START -->\n**System status:** {label} · updated "
             f"{_now():%Y-%m-%d %H:%M UTC}\n<!-- STATUS:END -->")
    try:
        text = readme.read_text()
        new = re.sub(r"<!-- STATUS:START -->.*?<!-- STATUS:END -->",
                     block, text, flags=re.DOTALL)
        if new == text:
            return False
        readme.write_text(new)
    except OSError:
        return False
    env = {**os.environ}
    def _git(*args):
        return subprocess.run(["git", "-C", str(repo_path), *args],
                              capture_output=True, text=True, env=env, timeout=60)
    _git("add", "profile/README.md")
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return False
    commit = _git("-c", "user.email=zeroexzoz@gmail.com", "-c", "user.name=puc-status",
                  "commit", "-q", "-m", f"status: {label} {_now():%Y-%m-%d}")
    if commit.returncode != 0:
        return False
    return _git("push", "-q", "origin", "HEAD:main").returncode == 0


def send_telegram(text: str) -> bool:
    try:
        env = dict(line.split("=", 1) for line in TG_ENV.read_text().splitlines()
                   if "=" in line)
    except OSError:
        return False
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = env.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-send", action="store_true", help="print only, don't Telegram")
    ap.add_argument("--badge-repo", default=None,
                    help="path to the org .github checkout; updates the public README traffic light")
    args = ap.parse_args(argv)

    r = Report()
    for check in (check_book, check_pipeline, check_freshness,
                  check_corpuses, check_editorial, check_infra):
        try:
            check(r)
        except Exception as exc:  # noqa: BLE001 - one check must not sink the rest
            r.add(WARN, f"{check.__name__} errored: {exc}")

    verdict = r.worst()
    header = {OK: "🟢 all clear", WARN: "🟡 needs a look", FAIL: "🔴 action needed"}[verdict]
    body = "\n".join(f"{lvl} {txt}" for lvl, txt in r.lines)
    report = f"📋 Daily system assessment — {header}\n{_now():%Y-%m-%d %H:%M UTC}\n\n{body}"
    print(report)
    if not args.no_send:
        ok = send_telegram(report)
        print(f"\n[telegram: {'sent' if ok else 'NOT sent'}]", file=sys.stderr)
    if args.badge_repo:
        try:
            pushed = update_badge(Path(args.badge_repo).expanduser(), verdict)
        except Exception as exc:  # noqa: BLE001 - badge must never fail the cron
            pushed = False
            print(f"[org badge: error {exc}]", file=sys.stderr)
        else:
            print(f"[org badge: {'updated' if pushed else 'unchanged/failed'}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
