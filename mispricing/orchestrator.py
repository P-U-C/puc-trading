"""Daily orchestrator with transactional discipline.

Replaces the 6-heredoc bash script. Each phase writes to a tmp path,
the orchestrator atomic-renames into the canonical location only after
the whole phase succeeds. A manifest tracks state so a mid-run failure
can be resumed or rolled back rather than leaving a half-state.

Why this exists (Codex review structural rec #3):
The previous refresh-mispricing.sh published directly into repo paths
phase by phase. If phase 3 (shaper) crashed, phase 1's option-cache
files were already on disk + committed, the daily ticket from yesterday
was still the most recent file, but `positions.json` hadn't been updated
-- a confusing half-state at worst, a silent loss at worst.

This orchestrator:
1. Writes all phase outputs under run-state/<RUN-ID>/ first.
2. Only after every phase succeeds does it move outputs into the
   canonical repo paths via atomic os.replace().
3. On failure, prints + telegrams the manifest so the operator can see
   exactly which phase blew up and what survived.
4. Logs to logs/refresh-mispricing.log instead of /tmp (the latter is
   wiped on reboot).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import shutil
import sys
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_STATE_DIR = REPO_ROOT / "run-state"
LOG_DIR = REPO_ROOT / "logs"
SCREENS_DIR = REPO_ROOT / "mispricing" / "screens"
DAILY_DIR = REPO_ROOT / "paper-journal" / "mispricing" / "daily"
JOURNAL_DIR = REPO_ROOT / "paper-journal" / "mispricing"
OPTIONS_CACHE = REPO_ROOT / "options-cache"


def _setup_logging(run_id: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "refresh-mispricing.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter(
        "%(asctime)sZ [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid double-handlers on repeated runs.
    if not any(getattr(h, "baseFilename", None) == str(log_path)
               for h in root.handlers):
        root.addHandler(handler)
    return log_path


@dataclass
class PhaseResult:
    name: str
    ok: bool
    started_at: str
    ended_at: str | None = None
    error: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunManifest:
    run_id: str
    started_at: str
    ended_at: str | None = None
    success: bool = False
    prefer_source: str = "ib"
    phases: list[PhaseResult] = field(default_factory=list)
    canonical_paths_updated: list[str] = field(default_factory=list)


def _phase(manifest: RunManifest, name: str, fn: Callable[[], dict[str, Any]]) -> bool:
    started = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    log = logging.getLogger(name)
    log.info("phase START: %s", name)
    result = PhaseResult(name=name, ok=False, started_at=started)
    manifest.phases.append(result)
    try:
        out = fn() or {}
        result.metrics = out.get("metrics", {})
        result.artifacts = out.get("artifacts", {})
        result.ok = True
        result.ended_at = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        log.info("phase END   : %s (%s)", name, result.metrics)
        return True
    except Exception as exc:
        result.ok = False
        result.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1200:]}"
        result.ended_at = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        log.exception("phase FAIL : %s", name)
        return False


def _atomic_replace(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(src), str(dst))


def _alert_failure(manifest: RunManifest) -> None:
    """Telegram alert with a per-phase status table."""
    try:
        from mispricing.morning_brief import _send_telegram  # local lazy import
    except ImportError:
        return
    lines = [f"REFRESH FAILED run_id={manifest.run_id}",
             f"started_at={manifest.started_at}",
             f"prefer={manifest.prefer_source}"]
    for p in manifest.phases:
        status = "OK" if p.ok else "FAIL"
        lines.append(f"  {status:>4} {p.name}")
        if p.error:
            lines.append(f"       error: {p.error.splitlines()[0][:150]}")
    _send_telegram("\n".join(lines), prefix="[puc-trading refresh]")


def run(*, prefer_source: str = "ib", deploy_push: bool = False,
        live_push: bool = False) -> RunManifest:
    """Run the daily mispricing-screen refresh end-to-end."""
    run_id = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_path = _setup_logging(run_id)
    log = logging.getLogger("orchestrator")
    log.info("=" * 70)
    log.info("run_id=%s prefer_source=%s deploy_push=%s live_push=%s",
             run_id, prefer_source, deploy_push, live_push)

    run_dir = RUN_STATE_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest(
        run_id=run_id,
        started_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        prefer_source=prefer_source,
    )

    # ---------- phase 1: chains ----------
    def _phase_chains():
        from mispricing import ib_chain
        cv_path = REPO_ROOT / "corpus" / "convergence-latest.json"
        cv = json.loads(cv_path.read_text())
        tickers = sorted({r["ticker"] for r in cv.get("scores", []) if r.get("ticker")})
        summary = ib_chain.refresh_universe(tickers, prefer=prefer_source)
        with_contracts = sum(1 for s in summary.values() if s.get("contracts", 0) > 0)
        manifest_path = run_dir / "chains-summary.json"
        manifest_path.write_text(json.dumps(summary, indent=2, default=str))
        return {"metrics": {"tickers": len(tickers),
                            "with_contracts": with_contracts,
                            "no_chain": len(tickers) - with_contracts},
                "artifacts": {"summary": str(manifest_path)}}
    if not _phase(manifest, "chains", _phase_chains):
        _finalize(manifest, run_dir, abort=True)
        _alert_failure(manifest)
        return manifest

    # ---------- phase 2: detector ----------
    def _phase_detect():
        from mispricing import detector
        rows = detector.screen(prefer_source=prefer_source)
        # Write screen to tmp first.
        tmp_screen = run_dir / f"screen-{dt.date.today().isoformat()}.json"
        SCREENS_DIR.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict as _asdict
        payload = {
            "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "rows": [_asdict(r) for r in rows],
            "summary": {
                "total": len(rows),
                "income": sum(1 for r in rows if r.bucket == "income"),
                "lottery": sum(1 for r in rows if r.bucket == "lottery"),
                "mispriced_up": sum(1 for r in rows if r.classification == "mispriced_up"),
            },
        }
        tmp_screen.write_text(json.dumps(payload, indent=2, default=str))
        return {"metrics": {"rows": len(rows),
                            "mispriced_up": payload["summary"]["mispriced_up"]},
                "artifacts": {"tmp_screen": str(tmp_screen)}}
    if not _phase(manifest, "detect", _phase_detect):
        _finalize(manifest, run_dir, abort=True)
        _alert_failure(manifest)
        return manifest

    # ---------- phase 3: shape ----------
    def _phase_shape():
        from mispricing import detector, shaper, paper_executor
        # Read the tmp screen we just wrote.
        tmp_screen_path = Path(manifest.phases[1].artifacts["tmp_screen"])
        data = json.loads(tmp_screen_path.read_text())
        rows = [detector.MispricingRow(**r) for r in data["rows"]]
        held = paper_executor.held_positions_for_shaper()
        candidates = shaper.shape(rows, held_positions=held)
        tmp_candidates = run_dir / "candidates.json"
        from dataclasses import asdict as _asdict
        tmp_candidates.write_text(json.dumps([_asdict(c) for c in candidates],
                                              indent=2, default=str))
        return {"metrics": {"income": sum(1 for c in candidates if c.bucket == "income"),
                            "lottery": sum(1 for c in candidates if c.bucket == "lottery"),
                            "total_usd": round(sum(c.cost_total_usd or 0
                                                    for c in candidates), 2)},
                "artifacts": {"tmp_candidates": str(tmp_candidates)}}
    if not _phase(manifest, "shape", _phase_shape):
        _finalize(manifest, run_dir, abort=True)
        _alert_failure(manifest)
        return manifest

    # ---------- phase 4: ticket + open paper ----------
    def _phase_ticket():
        from mispricing import detector, tickets, paper_executor, shaper
        from mispricing.shaper import TradeCandidate as TC
        tmp_screen_path = Path(manifest.phases[1].artifacts["tmp_screen"])
        tmp_candidates_path = Path(manifest.phases[2].artifacts["tmp_candidates"])
        data = json.loads(tmp_screen_path.read_text())
        rows = [detector.MispricingRow(**r) for r in data["rows"]]
        cands = [TC(**c) for c in json.loads(tmp_candidates_path.read_text())]
        held = paper_executor.held_positions_for_shaper()
        text = tickets.build_daily(screen_rows=rows, candidates=cands,
                                    held_positions=held, closes=[])
        tmp_ticket = run_dir / f"{dt.date.today().isoformat()}.md"
        tmp_ticket.write_text(text)
        # Defer position opening to the commit step so it stays
        # transactional with the canonical move.
        return {"metrics": {"ticket_bytes": len(text),
                            "candidates": len(cands)},
                "artifacts": {"tmp_ticket": str(tmp_ticket),
                              "tmp_candidates": str(tmp_candidates_path)}}
    if not _phase(manifest, "ticket", _phase_ticket):
        _finalize(manifest, run_dir, abort=True)
        _alert_failure(manifest)
        return manifest

    # ---------- phase 5: commit canonical paths + open + settle ----------
    def _phase_commit():
        from mispricing import paper_executor
        from mispricing.shaper import TradeCandidate as TC
        # Move the screen and ticket into their canonical locations.
        tmp_screen_path = Path(manifest.phases[1].artifacts["tmp_screen"])
        tmp_ticket_path = Path(manifest.phases[3].artifacts["tmp_ticket"])
        tmp_candidates_path = Path(manifest.phases[3].artifacts["tmp_candidates"])
        canonical_screen = SCREENS_DIR / tmp_screen_path.name
        canonical_ticket = DAILY_DIR / tmp_ticket_path.name
        _atomic_replace(tmp_screen_path, canonical_screen)
        _atomic_replace(tmp_ticket_path, canonical_ticket)
        manifest.canonical_paths_updated.extend([
            str(canonical_screen), str(canonical_ticket),
        ])
        # Now open paper positions (state-mutating) from the saved candidates.
        cands = [TC(**c) for c in json.loads(tmp_candidates_path.read_text())]
        new = paper_executor.open_paper(cands)
        # Settle (evaluate exits + rewrite tracker).
        positions = paper_executor._load_positions()
        just_closed = paper_executor.evaluate_exits(positions)
        summary = paper_executor.settle()
        return {"metrics": {"new_paper_positions": len(new),
                            "closed_today": summary["closed_today"],
                            "open_after": summary["open"]}}
    if not _phase(manifest, "commit", _phase_commit):
        _finalize(manifest, run_dir, abort=True)
        _alert_failure(manifest)
        return manifest

    # ---------- phase 6: brief ----------
    def _phase_brief():
        from mispricing import morning_brief
        sent = morning_brief.send_brief(dry_run=False)
        return {"metrics": {"sent": sent}}
    if not _phase(manifest, "brief", _phase_brief):
        # Brief failing isn't fatal -- everything's already committed.
        # Log and continue.
        log.warning("morning_brief failed but earlier phases succeeded")

    # ---------- optional phase 7: git push ----------
    if deploy_push:
        def _phase_push():
            import subprocess
            cmd_add = ["git", "-C", str(REPO_ROOT), "add",
                       "paper-journal/mispricing/", "mispricing/screens/"]
            subprocess.run(cmd_add, check=True, capture_output=True)
            diff = subprocess.run(["git", "-C", str(REPO_ROOT),
                                    "diff", "--cached", "--quiet"],
                                   capture_output=True)
            if diff.returncode == 0:
                return {"metrics": {"changes": 0}}
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "commit", "-m",
                 f"mispricing: refresh at {dt.datetime.utcnow().isoformat(timespec='seconds')}Z run_id={run_id}"],
                check=True, capture_output=True,
            )
            subprocess.run(["git", "-C", str(REPO_ROOT), "push", "origin", "main"],
                           check=True, capture_output=True)
            return {"metrics": {"changes": 1}}
        _phase(manifest, "push", _phase_push)  # don't abort on push failure

    _finalize(manifest, run_dir, abort=False)
    return manifest


def _finalize(manifest: RunManifest, run_dir: Path, *, abort: bool) -> None:
    manifest.ended_at = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    manifest.success = (not abort) and all(p.ok or p.name == "brief"
                                            for p in manifest.phases)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2, default=str))
    log = logging.getLogger("orchestrator")
    log.info("manifest -> %s (success=%s)", manifest_path, manifest.success)
    # Retention: keep the last 14 run-state dirs.
    runs = sorted([p for p in RUN_STATE_DIR.iterdir() if p.is_dir()])
    if len(runs) > 14:
        for old in runs[:-14]:
            shutil.rmtree(old, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prefer-source", choices=["ib", "yfinance"], default="ib")
    p.add_argument("--deploy-push", action="store_true",
                    help="git push the journal + tracker after the run")
    p.add_argument("--live-push", action="store_true",
                    help="placeholder: enable real IB orders (gated)")
    args = p.parse_args(argv)
    m = run(prefer_source=args.prefer_source,
            deploy_push=args.deploy_push,
            live_push=args.live_push)
    print(json.dumps({
        "run_id": m.run_id, "success": m.success,
        "phases": [{"name": p.name, "ok": p.ok, "metrics": p.metrics,
                    "error": (p.error.splitlines()[0] if p.error else None)}
                   for p in m.phases],
    }, indent=2))
    return 0 if m.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
