"""Phase 2: mispricing detector.

For each (ticker, catalyst) pair where the catalyst window is open,
compute:
  - market_implied_move: ATM straddle premium / spot, scaled to the
    catalyst horizon
  - thesis_implied_move: function of convergence_score,
    exposure_strength, event_type-specific multiplier
  - mispricing_ratio: thesis / market

Emit a daily ranked screen JSON.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml

from . import ib_chain

LOG = logging.getLogger("mispricing.detector")

REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERGENCE_PATH = REPO_ROOT / "corpus" / "convergence-latest.json"
CALENDAR_PATH = REPO_ROOT / "calendar" / "catalysts.yaml"
SCREEN_DIR = REPO_ROOT / "mispricing" / "screens"

# Event-type-specific multipliers on the thesis move. The intuition:
# an FDA decision is binary and large; an earnings beat is gradient; an
# M&A close is small-but-near-certain; a regulatory docket update is
# diffuse.
EVENT_MOVE_MULTIPLIER = {
    "fda_decision": 2.0,
    "fda_advisory_committee": 1.5,
    "trial_readout": 1.8,
    "ma_close": 0.5,           # close is mostly priced in; the trade is convergence to deal price
    "ipo": 1.5,                # private mark → public valuation gap
    "earnings": 1.0,
    "fomc": 0.6,
    "rate_decision": 0.6,
    "regulatory_docket": 0.7,
    "budget_appropriation": 0.8,
    "policy_decision": 0.7,
    "conference_launch": 0.6,
    "product_launch": 0.8,
    "data_release": 1.2,
    "industry_milestone": 0.8,
    "structural": 0.5,
}

NEAR_TERM_HORIZON_DAYS = 90
LONG_TERM_HORIZON_DAYS_MIN = 365
LONG_TERM_HORIZON_DAYS_MAX = 730


@dataclass
class MispricingRow:
    ticker: str
    theme_id: str
    catalyst_id: str
    event_date: str | None
    horizon_bucket: str | None
    event_type: str
    days_to_event: int | None
    convergence_score: float
    convergence_tier: str
    exposure_strength: float
    spot: float | None
    expiry_used: str | None
    atm_strike: float | None
    atm_straddle_mid: float | None
    market_implied_move: float | None
    thesis_implied_move: float | None
    mispricing_ratio: float | None
    classification: str       # mispriced_up | fair | mispriced_down | no_chain | no_market
    bucket: str               # income | lottery | excluded
    notes: str = ""


def _load_calendar() -> list[dict[str, Any]]:
    if not CALENDAR_PATH.exists():
        return []
    d = yaml.safe_load(CALENDAR_PATH.read_text()) or {}
    return d.get("events", []) or []


def _load_convergence() -> dict[str, Any]:
    if not CONVERGENCE_PATH.exists():
        return {"scores": [], "themes": []}
    return json.loads(CONVERGENCE_PATH.read_text())


def _parse_event_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    s = str(s).strip()
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _days_to_event(d: dt.date | None, today: dt.date) -> int | None:
    if d is None:
        return None
    return (d - today).days


def _classify_bucket(days_to: int | None, horizon_bucket: str | None,
                     tier: str) -> str:
    """Income (≤90d catalyst) vs lottery (≥365d) vs excluded (in-between or
    LOW tier without a strong horizon signal)."""
    if days_to is not None:
        if 0 <= days_to <= NEAR_TERM_HORIZON_DAYS:
            return "income"
        if days_to >= LONG_TERM_HORIZON_DAYS_MIN:
            return "lottery"
        return "excluded"
    # No explicit date; use horizon_bucket.
    if horizon_bucket == "near_term_0_90d":
        return "income"
    if horizon_bucket in ("long_term_1y_3y", "structural_3y_plus"):
        return "lottery"
    return "excluded"


def _atm_straddle(snapshot: ib_chain.ChainSnapshot, target_expiry: str) -> tuple[float | None, float | None, float | None]:
    """Returns (atm_strike, straddle_mid, market_implied_move) for the
    given expiry. ATM = strike closest to spot."""
    if snapshot.spot is None:
        return None, None, None
    contracts = snapshot.chain_for_expiry(target_expiry)
    if not contracts:
        return None, None, None
    strikes = sorted({c.strike for c in contracts})
    atm = min(strikes, key=lambda k: abs(k - snapshot.spot))
    call = next((c for c in contracts if c.strike == atm and c.right == "C"), None)
    put = next((c for c in contracts if c.strike == atm and c.right == "P"), None)
    if not call or not put:
        return atm, None, None
    cm = call.mid()
    pm = put.mid()
    if cm is None or pm is None:
        return atm, None, None
    straddle = round(cm + pm, 4)
    market_move = round(straddle / snapshot.spot, 4)
    return atm, straddle, market_move


def _pick_expiry(snapshot: ib_chain.ChainSnapshot,
                 target_date: dt.date | None,
                 bucket: str) -> str | None:
    """For income, pick first expiry on/after the event_date.
    For lottery, pick first expiry >= 365 days out."""
    expiries = snapshot.expiries()
    if not expiries:
        return None
    today = dt.date.today()
    if bucket == "lottery":
        cutoff = today + dt.timedelta(days=LONG_TERM_HORIZON_DAYS_MIN)
        candidates = [e for e in expiries if _parse_event_date(e) and _parse_event_date(e) >= cutoff]
        if candidates:
            return candidates[0]
        return expiries[-1]  # furthest available
    # income: first expiry on/after event_date (default to 30d post-today)
    cutoff = target_date or (today + dt.timedelta(days=30))
    candidates = [e for e in expiries if _parse_event_date(e) and _parse_event_date(e) >= cutoff]
    if candidates:
        return candidates[0]
    return expiries[0] if expiries else None


def _thesis_move(*, convergence_score: float, exposure_strength: float,
                 event_type: str) -> float:
    """Heuristic: thesis move = score × exposure × event_multiplier × base.
    Base 10% is the 'typical big-event move' anchor; the multiplier band
    expands/contracts from there."""
    base = 0.10
    em = EVENT_MOVE_MULTIPLIER.get(event_type, 0.7)
    return round(convergence_score * exposure_strength * em * base * 1.5, 4)


def screen(*, today: dt.date | None = None, prefer_source: str = "ib") -> list[MispricingRow]:
    today = today or dt.date.today()
    calendar = _load_calendar()
    convergence = _load_convergence()
    scores_by_pair: dict[tuple[str, str], dict[str, Any]] = {
        (r["theme_id"], r["ticker"]): r for r in convergence.get("scores", [])
    }

    rows: list[MispricingRow] = []
    pulled: dict[str, ib_chain.ChainSnapshot] = {}

    for cat in calendar:
        cat_id = cat.get("id", "")
        event_date = _parse_event_date(cat.get("event_date"))
        days_to = _days_to_event(event_date, today)
        # Skip catalysts that have already passed (more than 5 days ago).
        if days_to is not None and days_to < -5:
            continue
        event_type = cat.get("event_type", "structural")
        horizon_bucket = None  # calendar entries usually have explicit dates
        for ticker in cat.get("tickers") or []:
            theme_ids = cat.get("theme_ids") or []
            # Find convergence row for any (theme_id, ticker) match.
            score_row = None
            for tid in theme_ids:
                if (tid, ticker) in scores_by_pair:
                    score_row = scores_by_pair[(tid, ticker)]
                    break
            if not score_row:
                continue
            score = float(score_row.get("score", 0))
            tier = str(score_row.get("tier", "LOW"))
            exposure_strength = float(
                (score_row.get("score_components") or {}).get("exposure_strength", 0.5)
            )

            bucket = _classify_bucket(days_to, horizon_bucket, tier)
            if bucket == "excluded":
                continue

            # Pull chain (cached per ticker per screen run).
            if ticker not in pulled:
                snap = ib_chain.load_snapshot(ticker, today)
                if snap is None:
                    snap = ib_chain.pull_chain(ticker, prefer=prefer_source)
                    if snap.contracts:
                        ib_chain.save_snapshot(snap)
                pulled[ticker] = snap
            snap = pulled[ticker]

            if not snap.contracts:
                rows.append(MispricingRow(
                    ticker=ticker, theme_id=theme_ids[0] if theme_ids else "?",
                    catalyst_id=cat_id, event_date=cat.get("event_date"),
                    horizon_bucket=horizon_bucket, event_type=event_type,
                    days_to_event=days_to, convergence_score=score,
                    convergence_tier=tier, exposure_strength=exposure_strength,
                    spot=snap.spot, expiry_used=None, atm_strike=None,
                    atm_straddle_mid=None, market_implied_move=None,
                    thesis_implied_move=None, mispricing_ratio=None,
                    classification="no_chain", bucket=bucket,
                    notes=snap.error or "no contracts pulled",
                ))
                continue

            expiry = _pick_expiry(snap, event_date, bucket)
            atm, straddle, market_move = _atm_straddle(snap, expiry) if expiry else (None, None, None)
            thesis_move = _thesis_move(
                convergence_score=score,
                exposure_strength=exposure_strength,
                event_type=event_type,
            )
            if market_move is None or market_move <= 0:
                ratio = None
                classification = "no_market"
            else:
                ratio = round(thesis_move / market_move, 4)
                if ratio >= 1.5:
                    classification = "mispriced_up"
                elif ratio <= 0.67:
                    classification = "mispriced_down"
                else:
                    classification = "fair"

            rows.append(MispricingRow(
                ticker=ticker, theme_id=theme_ids[0] if theme_ids else "?",
                catalyst_id=cat_id, event_date=cat.get("event_date"),
                horizon_bucket=horizon_bucket, event_type=event_type,
                days_to_event=days_to, convergence_score=score,
                convergence_tier=tier, exposure_strength=exposure_strength,
                spot=snap.spot, expiry_used=expiry, atm_strike=atm,
                atm_straddle_mid=straddle, market_implied_move=market_move,
                thesis_implied_move=thesis_move, mispricing_ratio=ratio,
                classification=classification, bucket=bucket,
            ))
    # Sort: mispriced_up first, then by ratio descending.
    def _sort_key(r: MispricingRow):
        cls_rank = {"mispriced_up": 0, "fair": 1, "mispriced_down": 2,
                    "no_market": 3, "no_chain": 4}.get(r.classification, 5)
        ratio = r.mispricing_ratio if r.mispricing_ratio is not None else 0
        return (cls_rank, -ratio)
    rows.sort(key=_sort_key)
    return rows


def write_screen(rows: list[MispricingRow], today: dt.date | None = None) -> Path:
    today = today or dt.date.today()
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    out = SCREEN_DIR / f"screen-{today.isoformat()}.json"
    payload = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "rows": [asdict(r) for r in rows],
        "summary": {
            "total": len(rows),
            "income": sum(1 for r in rows if r.bucket == "income"),
            "lottery": sum(1 for r in rows if r.bucket == "lottery"),
            "mispriced_up": sum(1 for r in rows if r.classification == "mispriced_up"),
            "mispriced_down": sum(1 for r in rows if r.classification == "mispriced_down"),
            "fair": sum(1 for r in rows if r.classification == "fair"),
            "no_chain": sum(1 for r in rows if r.classification == "no_chain"),
        },
    }
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(out)
    return out
