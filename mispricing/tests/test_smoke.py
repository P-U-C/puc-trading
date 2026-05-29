"""Smoke tests for the mispricing modules. These exercise the
orchestration shape against a small in-memory fixture; they don't hit
IB Gateway or yfinance."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from mispricing import detector, shaper, tickets, ib_chain, paper_executor, orchestrator
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


def test_shaper_accumulates_same_ticker_exposure_within_run():
    rows = [
        _fake_row(catalyst_id=f"cat_qs_same_ticker_{idx}", atm_straddle_mid=5.0)
        for idx in range(4)
    ]

    cands = shaper.shape(rows)
    qs_total = sum(c.cost_total_usd or 0 for c in cands if c.ticker == "QS")

    assert len([c for c in cands if c.ticker == "QS"]) == 3
    assert qs_total == 450.0
    assert qs_total <= 10000 * 0.05


def test_direction_resolves_from_calendar_theme_directions():
    """cicadas.md: FXA/UNG/SOYB are SHORT, CORN/WEAT are LONG. Unlisted -> long."""
    td = {"cicadas": {"FXA": "short", "UNG": "short", "CORN": "long"}}
    cat = {"id": "cat_x"}
    assert detector._resolve_direction(cat, ["cicadas"], "FXA", td) == "short"
    assert detector._resolve_direction(cat, ["cicadas"], "CORN", td) == "long"
    assert detector._resolve_direction(cat, ["cicadas"], "ZZZ", td) == "long"  # default
    # per-catalyst override beats the theme default
    cat2 = {"id": "cat_y", "ticker_directions": {"CORN": "short"}}
    assert detector._resolve_direction(cat2, ["cicadas"], "CORN", td) == "short"


def test_shaper_picks_puts_for_bearish_thesis():
    """A short-thesis mispriced_up row must be expressed as a put_spread (ATM
    long put + lower short put), not a bullish call spread."""
    bull = _fake_row(ticker="CORN", direction="long")
    bear = _fake_row(ticker="FXA", direction="short", spot=70.0, atm_strike=70.0)
    cands = shaper.shape([bull, bear])
    by_t = {c.ticker: c for c in cands}
    assert by_t["CORN"].structure == "call_spread"
    assert by_t["CORN"].strike_upper > by_t["CORN"].strike      # higher short call
    assert by_t["FXA"].structure == "put_spread"
    assert by_t["FXA"].strike_upper < by_t["FXA"].strike        # lower short put
    assert by_t["FXA"].direction == "short"


def test_remark_put_spread_gains_when_underlying_falls():
    """A bearish put spread must GAIN when the underlying drops (the call-spread
    model would have shown a loss)."""
    from mispricing import remark
    pos = dict(status="open", ticker="FXA", structure="put_spread",
               cost_per_contract_usd=60.0, strike=70.0, strike_upper=63.0,
               entry_date="2026-05-19", expiry="2026-09-18", mark=60.0, pct_pnl=0.0)
    down = remark.remark_position(pos, spot=64.0, today=dt.date(2026, 6, 15))
    up = remark.remark_position(pos, spot=76.0, today=dt.date(2026, 6, 15))
    assert down["pct_pnl"] > 0, down      # AUD fell -> bearish put gains
    assert up["pct_pnl"] < 0, up          # AUD rose -> bearish put loses


def test_shaper_caps_correlated_theme_and_catalyst_exposure():
    """The cicadas blow-up regression: many distinct tickers on the SAME theme +
    catalyst must not stack past the theme/catalyst caps, and no more than
    MAX_TICKERS_PER_CATALYST distinct names get loaded onto one catalyst."""
    from mispricing import (MAX_THEME_EXPOSURE_PCT, MAX_CATALYST_EXPOSURE_PCT,
                            MAX_TICKERS_PER_CATALYST)
    # 6 correlated ag names, all theme=cicadas, all catalyst=NOAA-ENSO, each
    # cheap enough that without caps they'd each take a full per-ticker slug.
    rows = [
        _fake_row(ticker=t, theme_id="cicadas",
                  catalyst_id="cat_noaa_enso_2026_06",
                  event_date="2026-06-11", days_to_event=13,
                  spot=20.0, atm_strike=20.0, atm_straddle_mid=1.0,
                  market_implied_move=0.05, thesis_implied_move=0.13,
                  mispricing_ratio=2.6)
        for t in ("WEAT", "CORN", "DBA", "FXA", "NTR", "CF")
    ]
    cands = shaper.shape(rows)
    theme_total = sum(c.cost_total_usd or 0 for c in cands if c.theme_id == "cicadas")
    cat_total = sum(c.cost_total_usd or 0 for c in cands
                    if c.catalyst_id == "cat_noaa_enso_2026_06")
    distinct = {c.ticker for c in cands if c.catalyst_id == "cat_noaa_enso_2026_06"}
    assert theme_total <= 10000 * MAX_THEME_EXPOSURE_PCT + 0.01, theme_total
    assert cat_total <= 10000 * MAX_CATALYST_EXPOSURE_PCT + 0.01, cat_total
    assert len(distinct) <= MAX_TICKERS_PER_CATALYST, distinct


def test_shaper_correlation_caps_account_for_held_book():
    """Caps must see already-open positions, not just this run's adds. If the
    book already holds the catalyst cap's worth, a new same-catalyst row gets
    nothing."""
    from mispricing import MAX_CATALYST_EXPOSURE_PCT
    held = [
        {"ticker": "WEAT", "theme_id": "cicadas",
         "catalyst_id": "cat_noaa_enso_2026_06",
         "cost_total_usd": 10000 * MAX_CATALYST_EXPOSURE_PCT}
    ]
    rows = [_fake_row(ticker="CORN", theme_id="cicadas",
                      catalyst_id="cat_noaa_enso_2026_06",
                      event_date="2026-06-11", days_to_event=13,
                      spot=20.0, atm_strike=20.0, atm_straddle_mid=1.0,
                      market_implied_move=0.05, thesis_implied_move=0.13,
                      mispricing_ratio=2.6)]
    cands = shaper.shape(rows, held_positions=held)
    assert [c for c in cands if c.catalyst_id == "cat_noaa_enso_2026_06"] == []


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


def test_paper_executor_stats_use_contract_dollars_and_calendar_days():
    pos = paper_executor.PaperPosition(
        id="QS-call-10-2026-06-19-2026-05-01",
        bucket="income",
        ticker="QS",
        theme_id="solid-state-battery",
        catalyst_id="cat_qs",
        event_date="2026-06-01",
        structure="long_call",
        strike=10.0,
        strike_upper=None,
        expiry="2026-06-19",
        quantity_contracts=2,
        cost_per_contract_usd=150.0,
        cost_total_usd=300.0,
        entry_date="2026-05-01",
        entry_rationale="test",
        mark=225.0,
        pct_pnl=50.0,
        status="closed",
        closed_at="2026-05-04",
        close_reason="+50% gain target",
        close_price=225.0,
    )

    stats = paper_executor._compute_stats([], [pos])

    assert stats["income"]["total_pnl_usd"] == 150.0
    assert stats["income"]["mean_pnl_usd"] == 150.0
    assert stats["income"]["median_hold_days"] == 3
    assert stats["income"]["hit_rate_pct"] == 100.0


def test_paper_executor_gate_not_ready_with_no_positions():
    stats = paper_executor._compute_stats([], [])

    assert stats["gate"]["first_open_date"] is None
    assert stats["gate"]["days_elapsed"] is None
    assert stats["gate"]["ready"] is False


def test_orchestrator_publish_replacements_rolls_back_partial_publish(tmp_path, monkeypatch):
    src_ok = tmp_path / "src-ok.txt"
    src_fail = tmp_path / "src-fail.txt"
    dst_ok = tmp_path / "dst-ok.txt"
    dst_fail = tmp_path / "dst-fail.txt"
    src_ok.write_text("new ok")
    src_fail.write_text("new fail")
    dst_ok.write_text("old ok")
    dst_fail.write_text("old fail")

    real_replace = orchestrator._atomic_replace

    def fake_replace(src, dst):
        if Path(dst).name == "dst-fail.txt":
            raise RuntimeError("publish failed")
        return real_replace(src, dst)

    monkeypatch.setattr(orchestrator, "_atomic_replace", fake_replace)

    try:
        orchestrator._publish_replacements(
            [(src_ok, dst_ok), (src_fail, dst_fail)],
            backup_dir=tmp_path / "backup",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("publish failure did not raise")

    assert dst_ok.read_text() == "old ok"
    assert dst_fail.read_text() == "old fail"


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


class _FakeSnap:
    """Minimal snapshot exposing only expiries() for _pick_expiry tests."""
    def __init__(self, expiries):
        self._expiries = list(expiries)

    def expiries(self):
        return sorted(self._expiries)


def test_pick_expiry_skips_when_no_expiry_covers_catalyst():
    """Regression: the first paper book bought near-dated options that
    expired BEFORE their catalyst (20/20 closed trades, all 0%). An income
    trade whose chain cannot reach the event must be SKIPPED, not stuffed
    into the nearest weekly."""
    event = dt.date(2026, 8, 6)
    near_only = _FakeSnap(["2026-05-22", "2026-05-29", "2026-06-18"])
    assert detector._pick_expiry(near_only, event, "income") is None


def test_pick_expiry_covers_catalyst_with_buffer():
    event = dt.date(2026, 8, 6)
    # event + MIN_POST_EVENT_BUFFER_DAYS (45d) = 2026-09-20, so the screen must
    # reach the first expiry on/after that — Oct 16, not the Aug/Sep expiries
    # that die within weeks of the print.
    chain = _FakeSnap(["2026-05-22", "2026-07-17", "2026-08-21", "2026-10-16"])
    assert detector._pick_expiry(chain, event, "income") == "2026-10-16"


def test_pick_expiry_enforces_tenor_floor_not_just_post_event():
    """Regression for the cicadas -32% blow-up: a +1-week expiry after the
    catalyst is pure theta. With a 45d residual floor, a 2026-06-11 catalyst
    must NOT pick the 2026-06-18 monthly even though it technically clears the
    event — it must reach out to a tenor that matches the multi-stage thesis."""
    event = dt.date(2026, 6, 11)
    chain = _FakeSnap(["2026-06-18", "2026-07-17", "2026-10-16", "2027-01-15"])
    picked = detector._pick_expiry(chain, event, "income")
    assert picked == "2026-10-16"  # first expiry >= event + 45d (2026-07-26)
    assert (dt.date.fromisoformat(picked) - event).days >= detector.MIN_POST_EVENT_BUFFER_DAYS


def test_pick_expiry_income_no_event_takes_30d_plus():
    chain = _FakeSnap(["2026-05-22", "2026-06-30", "2026-08-21"])
    today = dt.date.today()
    got = detector._pick_expiry(chain, None, "income")
    assert got is not None and dt.date.fromisoformat(got) >= today


def test_remark_day_one_anchor_no_jump():
    """Re-marking at entry (spot == long strike) must reproduce ~cost: no
    artificial day-1 P&L jump off the model-proxy entry basis."""
    from mispricing import remark
    pos = dict(status="open", ticker="CORN", cost_per_contract_usd=35.0,
               strike=19.0, strike_upper=20.9, entry_date="2026-05-19",
               expiry="2026-06-18", mark=35.0, pct_pnl=0.0)
    upd = remark.remark_position(pos, spot=19.0, today=dt.date(2026, 5, 19))
    assert abs(upd["pct_pnl"]) < 1.0


def test_remark_gains_when_underlying_rallies_and_caps_at_width():
    from mispricing import remark
    pos = dict(status="open", ticker="CORN", cost_per_contract_usd=35.0,
               strike=19.0, strike_upper=20.9, entry_date="2026-05-19",
               expiry="2026-06-18", mark=35.0, pct_pnl=0.0)
    up = remark.remark_position(pos, spot=25.0, today=dt.date(2026, 5, 26))
    base = remark.remark_position(pos, spot=19.0, today=dt.date(2026, 5, 26))
    assert up["mark"] > base["mark"]                 # rally lifts the spread
    assert up["mark"] <= (20.9 - 19.0) * 100 + 0.01  # capped at width × 100


def test_remark_positions_handles_objects_and_dicts():
    from mispricing import remark, paper_executor
    obj = paper_executor.PaperPosition(
        id="x", bucket="income", ticker="CORN", theme_id="t", catalyst_id="c",
        event_date="2026-06-11", structure="call_spread", strike=19.0,
        strike_upper=20.9, expiry="2026-06-18", quantity_contracts=5,
        cost_per_contract_usd=35.0, cost_total_usd=175.0, entry_date="2026-05-19",
        entry_rationale="r", mark=35.0, pct_pnl=0.0, status="open")
    n = remark.remark_positions([obj], lambda t: 25.0, today=dt.date(2026, 5, 26))
    assert n == 1 and obj.mark != 35.0 and obj.pct_pnl > 0


def _open_income(pct_pnl, event_date):
    from mispricing.paper_executor import PaperPosition
    return PaperPosition(
        id="t", bucket="income", ticker="CORN", theme_id="th", catalyst_id="c",
        event_date=event_date, structure="call_spread", strike=19.0,
        strike_upper=20.9, expiry="2026-07-17", quantity_contracts=5,
        cost_per_contract_usd=35.0, cost_total_usd=175.0, entry_date="2026-05-19",
        entry_rationale="r", mark=13.5, pct_pnl=pct_pnl, status="open")


def _isolate_paths(monkeypatch, tmp_path):
    """evaluate_exits persists via _save_positions to module-level paths;
    redirect them to a tmp dir so a test can NEVER touch the real book."""
    from mispricing import paper_executor
    monkeypatch.setattr(paper_executor, "POSITIONS_PATH", tmp_path / "positions.json")
    monkeypatch.setattr(paper_executor, "CLOSED_PATH", tmp_path / "closed.json")
    monkeypatch.setattr(paper_executor, "TRACKER_PATH", tmp_path / "tracker.md")
    monkeypatch.setattr(paper_executor, "JOURNAL_DIR", tmp_path)


def test_loss_stop_suppressed_before_catalyst_fires_after(monkeypatch, tmp_path):
    """Option B: a -60% income trade holds while its catalyst is still
    pending, but stops out once the catalyst has passed."""
    from mispricing import paper_executor
    _isolate_paths(monkeypatch, tmp_path)
    today = dt.date(2026, 5, 26)
    pending = _open_income(-60.0, "2026-06-11")   # catalyst still ahead
    passed = _open_income(-60.0, "2026-05-20")    # catalyst already gone
    closed = paper_executor.evaluate_exits([pending, passed], today=today)
    assert pending.status == "open"               # held through catalyst
    assert passed.status == "closed" and passed in closed
    assert passed.close_reason == "income stop loss (-50%)"


def test_profit_target_still_fires_pre_catalyst(monkeypatch, tmp_path):
    from mispricing import paper_executor
    _isolate_paths(monkeypatch, tmp_path)
    win = _open_income(55.0, "2026-06-11")
    closed = paper_executor.evaluate_exits([win], today=dt.date(2026, 5, 26))
    assert win.status == "closed" and win.close_reason == "+50% gain target"


def test_remark_expired_marks_to_intrinsic_not_stale_timevalue():
    """Codex MEDIUM: at/after expiry a position must mark to intrinsic, not
    retain a day of model time-value."""
    from mispricing import remark
    pos = dict(status="open", ticker="CORN", structure="call_spread",
               cost_per_contract_usd=35.0, strike=19.0, strike_upper=20.9,
               entry_date="2026-05-19", expiry="2026-06-18", mark=35.0, pct_pnl=0.0)
    # Expired, underlying below long strike -> spread worthless (intrinsic 0),
    # not a stale day of model time-value.
    upd = remark.remark_position(pos, spot=17.0, today=dt.date(2026, 6, 18))
    assert upd["mark"] == 0.0
    # Expired deep ITM -> gains vs cost and never exceeds width × 100.
    up = remark.remark_position(pos, spot=30.0, today=dt.date(2026, 6, 18))
    assert up["mark"] > 35.0 and up["mark"] <= (20.9 - 19.0) * 100 + 0.01


def test_remark_rejects_nan_spot_and_unsupported_structure():
    from mispricing import remark
    pos = dict(status="open", ticker="CORN", structure="call_spread",
               cost_per_contract_usd=35.0, strike=19.0, strike_upper=20.9,
               entry_date="2026-05-19", expiry="2026-06-18", mark=35.0, pct_pnl=0.0)
    nan = remark.remark_position(pos, spot=float("nan"), today=dt.date(2026, 5, 26))
    assert nan["mark"] == 35.0 and nan["pct_pnl"] == 0.0  # unchanged
    straddle = dict(pos, structure="straddle", mark=80.0, pct_pnl=0.0)
    out = remark.remark_position(straddle, spot=25.0, today=dt.date(2026, 5, 26))
    assert out["mark"] == 80.0  # unsupported structure left untouched
