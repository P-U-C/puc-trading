"""Smoke tests for the mispricing modules. These exercise the
orchestration shape against a small in-memory fixture; they don't hit
IB Gateway or yfinance."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from mispricing import detector, shaper, tickets, ib_chain, paper_executor
from mispricing.detector import MispricingRow
from mispricing.shaper import TradeCandidate


def _fake_row(**overrides) -> MispricingRow:
    base = dict(
        ticker="QS", theme_id="solid-state-battery",
        catalyst_id="cat_qs_q3_2026_earnings",
        event_date="2026-10-29", horizon_bucket=None,
        event_type="earnings", days_to_event=160,
        convergence_score=0.91, convergence_tier="HIGH",
        exposure_strength=0.9, spot=8.0, expiry_used="2026-11-15",
        atm_strike=8.0, atm_straddle_mid=1.8,
        market_implied_move=0.225, thesis_implied_move=0.40,
        mispricing_ratio=1.78, classification="mispriced_up",
        bucket="income",
    )
    base.update(overrides)
    return MispricingRow(**base)


def test_event_move_multiplier_lookup_coverage():
    """Every event_type used in the calendar must have a multiplier."""
    import yaml
    cal_path = Path(__file__).resolve().parents[2] / "calendar" / "catalysts.yaml"
    if not cal_path.exists():
        return
    cal = yaml.safe_load(cal_path.read_text()) or {}
    used_types = {e["event_type"] for e in cal.get("events", [])}
    for t in used_types:
        assert t in detector.EVENT_MOVE_MULTIPLIER, f"missing multiplier for {t}"


def test_thesis_move_monotonic_in_score():
    a = detector._thesis_move(convergence_score=0.5, exposure_strength=0.8,
                              event_type="earnings")
    b = detector._thesis_move(convergence_score=0.9, exposure_strength=0.8,
                              event_type="earnings")
    assert b > a


def test_classify_bucket_buckets():
    assert detector._classify_bucket(30, None, "HIGH") == "income"
    assert detector._classify_bucket(400, None, "HIGH") == "lottery"
    assert detector._classify_bucket(180, None, "HIGH") == "excluded"
    assert detector._classify_bucket(None, "near_term_0_90d", "HIGH") == "income"
    assert detector._classify_bucket(None, "long_term_1y_3y", "HIGH") == "lottery"


def test_shaper_respects_budgets():
    rows = [
        _fake_row(),
        _fake_row(ticker="LITE", theme_id="photonic-computing",
                  catalyst_id="cat_lite_q3_2026_earnings", spot=110.0,
                  atm_strike=110.0, atm_straddle_mid=18.0,
                  market_implied_move=0.164, thesis_implied_move=0.31,
                  mispricing_ratio=1.89),
        # Lottery row
        _fake_row(ticker="BIOA", theme_id="longevity",
                  catalyst_id="cat_bioage_apj_ind",
                  event_date="2027-06-15", days_to_event=395,
                  spot=4.5, atm_strike=4.5, atm_straddle_mid=1.2,
                  market_implied_move=0.267, thesis_implied_move=0.40,
                  mispricing_ratio=1.5, classification="fair",
                  bucket="lottery"),
    ]
    cands = shaper.shape(rows)
    income = [c for c in cands if c.bucket == "income"]
    lottery = [c for c in cands if c.bucket == "lottery"]
    summary = shaper.candidates_summary(cands)
    # Income trades must not exceed 60% of book
    assert summary["income_total_usd"] <= 10000 * 0.60 + 0.01
    # Lottery trades must not exceed 40% of book
    assert summary["lottery_total_usd"] <= 10000 * 0.40 + 0.01
    # Per-ticker cap (5% = $500)
    by_ticker_total = {}
    for c in cands:
        by_ticker_total[c.ticker] = by_ticker_total.get(c.ticker, 0) + (c.cost_total_usd or 0)
    for t, total in by_ticker_total.items():
        assert total <= 10000 * 0.05 + 0.01, f"{t} over per-ticker cap: {total}"


def test_ticket_markdown_round_trip(tmp_path, monkeypatch):
    """Just verify the writer produces non-empty markdown with all sections."""
    monkeypatch.setattr(tickets, "DAILY_DIR", tmp_path)
    rows = [_fake_row()]
    cands = shaper.shape(rows)
    text = tickets.build_daily(today=dt.date(2026, 5, 18),
                                screen_rows=rows, candidates=cands)
    out = tickets.write_daily(text, today=dt.date(2026, 5, 18))
    body = out.read_text()
    assert "NEW INCOME" in body
    assert "NEW LOTTERY" in body
    assert "CLOSE" in body
    assert "HOLD" in body
    assert "SCREEN SUMMARY" in body


def test_paper_executor_open_close_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_executor, "POSITIONS_PATH",
                        tmp_path / "positions.json")
    monkeypatch.setattr(paper_executor, "CLOSED_PATH",
                        tmp_path / "closed.json")
    monkeypatch.setattr(paper_executor, "TRACKER_PATH",
                        tmp_path / "tracker.md")
    monkeypatch.setattr(paper_executor, "JOURNAL_DIR", tmp_path)

    rows = [_fake_row()]
    cands = shaper.shape(rows)
    assert cands
    new_positions = paper_executor.open_paper(cands)
    assert len(new_positions) == len(cands)
    # Force a profit-target exit
    pos_list = paper_executor._load_positions()
    pos_list[0].mark = pos_list[0].cost_per_contract_usd * 1.6
    pos_list[0].pct_pnl = 60.0
    paper_executor._save_positions(pos_list)
    closed_now = paper_executor.evaluate_exits(paper_executor._load_positions())
    assert len(closed_now) == 1
    summary = paper_executor.settle()
    assert summary["closed_today"] == 1
    assert summary["open"] == 0


def test_chain_snapshot_dataclasses_serialize():
    snap = ib_chain.ChainSnapshot(
        ticker="TEST", snapshot_at="2026-05-18T00:00:00Z",
        spot=10.0, source="test", contracts=[
            ib_chain.ChainContract(strike=10.0, expiry="2026-06-19",
                                    right="C", bid=0.5, ask=0.6, last=0.55,
                                    iv=0.6, delta=0.5, gamma=0.1,
                                    theta=-0.01, vega=0.05,
                                    open_interest=100, volume=50)
        ],
    )
    c = snap.chain_for_expiry("2026-06-19")[0]
    assert c.mid() == 0.55
