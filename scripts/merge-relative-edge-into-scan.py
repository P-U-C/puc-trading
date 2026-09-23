#!/usr/bin/env python3
"""Merge benchmark-relative edge diagnostics into the scanner dashboard JSON.

The convergence corpus says which narratives and tickers the LLM funnel is
talking about. This layer asks the market question Chad actually needs before
treating a theme as tradeable: is the basket separating from an appropriate
benchmark, and is the move broad enough to be more than one crowded winner?
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


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

PRICE_START = os.environ.get("RELATIVE_EDGE_PRICE_START", "2021-01-01")
PRICE_END = os.environ.get("RELATIVE_EDGE_PRICE_END") or None
THEME_MAX_TICKERS = int(os.environ.get("RELATIVE_EDGE_THEME_MAX_TICKERS", "12"))
MIN_PRICED_TICKERS = int(os.environ.get("RELATIVE_EDGE_MIN_PRICED_TICKERS", "3"))
WINDOWS = (21, 63, 126)
FALLBACK_BENCHMARK = "SPY"

ACTIVE_63D_EXCESS = 0.15
ACTIVE_126D_EXCESS = 0.25
ACTIVE_BREADTH = 0.60
TRIGGER_63D_EXCESS = 0.10
TRIGGER_126D_EXCESS = 0.15
TRIGGER_BREADTH = 0.50
EARLY_ACTIVE_MAX_TRADING_DAYS = 126
FRESH_TRIGGER_MAX_TRADING_DAYS = 63

# Private theses must not leak to the public scanner. This mirrors
# merge-convergence-into-scan.py.
EXCLUDE_THEME_IDS = {
    t.strip()
    for t in os.environ.get("SCANNER_EXCLUDE_THEME_IDS", "cicadas").split(",")
    if t.strip()
}

CURATED_BASKETS: list[dict[str, Any]] = [
    {
        "basket_id": "ai-core-compute",
        "theme": "AI Core Compute",
        "kind": "curated",
        "benchmark": "SMH",
        "tickers": ["NVDA", "AVGO", "AMD", "SMCI", "VRT", "ANET", "DELL"],
        "why": "core AI compute names that led the 2023-2026 AI trade",
    },
    {
        "basket_id": "memory-bandwidth",
        "theme": "Memory / Bandwidth",
        "kind": "curated",
        "benchmark": "SOXX",
        "tickers": ["MU", "WDC", "STX", "LRCX", "AMAT"],
        "why": "HBM, NAND, storage and semiconductor equipment beneficiaries",
    },
    {
        "basket_id": "ai-power-grid",
        "theme": "AI Power / Grid",
        "kind": "curated",
        "benchmark": "QQQ",
        "tickers": ["VST", "CEG", "ETN", "GEV", "VRT", "PWR"],
        "why": "AI electricity, cooling and grid buildout beneficiaries",
    },
]

THEME_BENCHMARKS = {
    "ai-infrastructure": "SMH",
    "edge-ai": "SMH",
    "photonic-computing": "SMH",
    "quantum-computing": "QQQ",
    "robotics-humanoid": "BOTZ",
    "nuclear-smr": "XLU",
    "defense-ai": "ITA",
    "space-satellite": "ARKX",
    "peptides": "XBI",
    "synthetic-biology": "XBI",
    "longevity": "XBI",
    "biomechanics": "IHI",
    "bci-neurotech": "IHI",
    "solid-state-battery": "LIT",
    "bitcoin-mining": "IBIT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_symbol(value: object) -> str | None:
    if value is None:
        return None
    symbol = str(value).strip().upper().lstrip("$")
    if not symbol:
        return None
    return symbol.replace("/", "-")


def clean_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, 4)


def clean_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_json(path: Path) -> Any:
    return json.loads(path.expanduser().read_text(encoding="utf-8"))


def canonical_theme_names(artifact: dict[str, Any]) -> dict[str, str]:
    return {
        str(t.get("theme_id")): str(t.get("theme_name"))
        for t in artifact.get("themes", [])
        if t.get("theme_id") and t.get("theme_name")
    }


def build_baskets(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    baskets = [dict(row) for row in CURATED_BASKETS]
    names = canonical_theme_names(artifact)
    by_theme: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for row in artifact.get("scores", []):
        theme_id = row.get("theme_id")
        if not theme_id or theme_id in EXCLUDE_THEME_IDS:
            continue
        ticker = clean_symbol(row.get("ticker"))
        if not ticker:
            continue
        score = row.get("score", row.get("convergence_score", 0.0))
        existing = by_theme[str(theme_id)].get(ticker)
        if existing is None or float(score or 0.0) > float(existing.get("score") or 0.0):
            by_theme[str(theme_id)][ticker] = {
                "ticker": ticker,
                "score": float(score or 0.0),
                "tier": row.get("tier") or row.get("convergence_tier"),
            }

    for theme_id, rows_by_ticker in sorted(by_theme.items()):
        rows = sorted(rows_by_ticker.values(), key=lambda r: (-r["score"], r["ticker"]))
        tickers = [r["ticker"] for r in rows[:THEME_MAX_TICKERS]]
        if len(tickers) < 2:
            continue
        baskets.append(
            {
                "basket_id": f"theme-{theme_id}",
                "theme_id": theme_id,
                "theme": names.get(theme_id) or theme_id,
                "kind": "corpus_theme",
                "benchmark": THEME_BENCHMARKS.get(theme_id, FALLBACK_BENCHMARK),
                "tickers": tickers,
                "source_score_count": len(rows_by_ticker),
                "source_top_tickers": rows[: min(5, len(rows))],
            }
        )

    return baskets


def symbols_for_download(baskets: list[dict[str, Any]]) -> list[str]:
    symbols: set[str] = {FALLBACK_BENCHMARK}
    for basket in baskets:
        symbols.update(str(t) for t in basket.get("tickers", []))
        symbols.add(str(basket.get("benchmark") or FALLBACK_BENCHMARK))
    return sorted(symbols)


def fetch_prices(symbols: list[str]) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is required for relative edge merge") from exc

    data = yf.download(
        symbols,
        start=PRICE_START,
        end=PRICE_END,
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            prices = data["Close"]
        elif "Adj Close" in data.columns.get_level_values(0):
            prices = data["Adj Close"]
        else:
            return pd.DataFrame()
    else:
        close_col = "Close" if "Close" in data.columns else "Adj Close"
        if close_col not in data.columns:
            return pd.DataFrame()
        if len(symbols) == 1:
            prices = data[[close_col]].rename(columns={close_col: symbols[0]})
        else:
            prices = data[[close_col]]

    prices = prices.apply(pd.to_numeric, errors="coerce")
    prices = prices.dropna(axis=1, how="all")
    prices.columns = [str(c).upper() for c in prices.columns]
    return prices.sort_index()


def usable_series(prices: pd.DataFrame, symbol: str) -> pd.Series | None:
    symbol = symbol.upper()
    if symbol not in prices.columns:
        return None
    series = pd.to_numeric(prices[symbol], errors="coerce").dropna()
    if series.empty:
        return None
    return series


def normalized_basket(prices: pd.DataFrame, tickers: list[str]) -> tuple[pd.Series, list[str], list[str]]:
    frames: dict[str, pd.Series] = {}
    missing: list[str] = []
    for ticker in tickers:
        series = usable_series(prices, ticker)
        if series is None:
            missing.append(ticker)
            continue
        base = float(series.iloc[0])
        if base <= 0:
            missing.append(ticker)
            continue
        frames[ticker] = series / base

    if not frames:
        return pd.Series(dtype=float), [], missing

    frame = pd.DataFrame(frames).sort_index()
    basket = frame.mean(axis=1, skipna=True).dropna()
    return basket, sorted(frames), missing


def window_return(series: pd.Series, end_date: pd.Timestamp, window: int) -> float | None:
    sample = series.loc[:end_date].dropna()
    if len(sample) <= window:
        return None
    start = float(sample.iloc[-window - 1])
    end = float(sample.iloc[-1])
    if start <= 0:
        return None
    return end / start - 1.0


def breadth_for_window(
    prices: pd.DataFrame,
    tickers: list[str],
    benchmark: pd.Series,
    end_date: pd.Timestamp,
    window: int,
) -> float | None:
    bench_return = window_return(benchmark, end_date, window)
    if bench_return is None:
        return None

    winners = 0
    counted = 0
    for ticker in tickers:
        series = usable_series(prices, ticker)
        if series is None:
            continue
        ticker_return = window_return(series, end_date, window)
        if ticker_return is None:
            continue
        counted += 1
        if ticker_return > bench_return:
            winners += 1

    if counted == 0:
        return None
    return winners / counted


def compute_metrics_at(
    prices: pd.DataFrame,
    basket: pd.Series,
    tickers: list[str],
    benchmark: pd.Series,
    end_date: pd.Timestamp,
) -> dict[str, dict[str, float | None]]:
    metrics: dict[str, dict[str, float | None]] = {}
    for window in WINDOWS:
        basket_return = window_return(basket, end_date, window)
        benchmark_return = window_return(benchmark, end_date, window)
        excess = None
        if basket_return is not None and benchmark_return is not None:
            excess = basket_return - benchmark_return
        metrics[f"{window}d"] = {
            "basket_return": clean_float(basket_return),
            "benchmark_return": clean_float(benchmark_return),
            "excess_return": clean_float(excess),
            "breadth": clean_float(breadth_for_window(prices, tickers, benchmark, end_date, window)),
        }
    return metrics


def classify_state(metrics: dict[str, dict[str, float | None]], priced_count: int) -> str:
    if priced_count < MIN_PRICED_TICKERS:
        return "watch"

    m63 = metrics.get("63d", {})
    m126 = metrics.get("126d", {})
    excess_63 = m63.get("excess_return")
    excess_126 = m126.get("excess_return")
    breadth_63 = m63.get("breadth")

    if excess_63 is None or excess_126 is None or breadth_63 is None:
        return "watch"

    if (
        excess_63 >= ACTIVE_63D_EXCESS
        and excess_126 >= ACTIVE_126D_EXCESS
        and breadth_63 >= ACTIVE_BREADTH
    ):
        return "active"

    if (
        (excess_63 >= TRIGGER_63D_EXCESS and breadth_63 >= TRIGGER_BREADTH)
        or (excess_126 >= TRIGGER_126D_EXCESS and breadth_63 >= TRIGGER_BREADTH)
    ):
        return "trigger"

    return "watch"


def trading_days_since(date_str: str | None, index: pd.Index, end_date: pd.Timestamp) -> int | None:
    if not date_str:
        return None
    start = pd.Timestamp(date_str)
    dates = pd.DatetimeIndex(index)
    sample = dates[(dates >= start) & (dates <= end_date)]
    if len(sample) == 0:
        return None
    return max(0, len(sample) - 1)


def age_label(trading_days: int | None) -> str | None:
    if trading_days is None:
        return None
    if trading_days < 21:
        return f"{trading_days}d"
    months = trading_days / 21
    if months < 18:
        return f"{months:.1f}mo"
    return f"{trading_days / 252:.1f}y"


def timing_payload(
    first_trigger_date: str | None,
    first_active_date: str | None,
    index: pd.Index,
    end_date: pd.Timestamp,
) -> dict[str, Any]:
    trigger_days = trading_days_since(first_trigger_date, index, end_date)
    active_days = trading_days_since(first_active_date, index, end_date)
    return {
        "first_trigger_date": first_trigger_date,
        "first_active_date": first_active_date,
        "trading_days_since_first_trigger": clean_int(trigger_days),
        "trading_days_since_first_active": clean_int(active_days),
        "first_trigger_age": age_label(trigger_days),
        "first_active_age": age_label(active_days),
    }


def classify_phase(state: str, metrics: dict[str, dict[str, float | None]], timing: dict[str, Any]) -> dict[str, Any]:
    m63 = metrics.get("63d", {})
    m126 = metrics.get("126d", {})
    excess_63 = m63.get("excess_return") or 0.0
    excess_126 = m126.get("excess_return") or 0.0
    breadth_63 = m63.get("breadth") or 0.0
    active_days = timing.get("trading_days_since_first_active")
    trigger_days = timing.get("trading_days_since_first_trigger")

    if state == "active":
        if active_days is not None and active_days <= EARLY_ACTIVE_MAX_TRADING_DAYS:
            return {
                "phase": "early_active",
                "phase_label": "Early active",
                "action": "Best entry/add window; size only while 63d, 126d and breadth stay above thresholds.",
                "action_priority": 1,
            }
        return {
            "phase": "mature_active",
            "phase_label": "Mature active",
            "action": "Hold or trail existing exposure; avoid fresh chase unless it resets and re-accelerates.",
            "action_priority": 3,
        }

    if state == "trigger":
        if active_days is None and trigger_days is not None and trigger_days <= FRESH_TRIGGER_MAX_TRADING_DAYS:
            return {
                "phase": "fresh_trigger",
                "phase_label": "Fresh trigger",
                "action": "Research queue or starter only; wait for active confirmation before sizing.",
                "action_priority": 2,
            }
        return {
            "phase": "re_accelerating",
            "phase_label": "Re-accelerating",
            "action": "Second-impulse candidate; wait for 126d confirmation or a pullback that preserves breadth.",
            "action_priority": 2,
        }

    if state == "watch" and (active_days is not None or trigger_days is not None):
        if excess_63 > 0 and excess_126 > 0 and breadth_63 >= 0.40:
            return {
                "phase": "reset_watch",
                "phase_label": "Reset watch",
                "action": "No new trade yet; watch for renewed trigger/active status after the reset.",
                "action_priority": 4,
            }
        return {
            "phase": "fading_watch",
            "phase_label": "Fading watch",
            "action": "No new trade; prior edge is stale or losing benchmark-relative breadth.",
            "action_priority": 5,
        }

    return {
        "phase": "insufficient_data",
        "phase_label": "Insufficient data",
        "action": "No trade; price history, benchmark history, or breadth is insufficient.",
        "action_priority": 6,
    }


def first_date_for_state(
    state: str,
    prices: pd.DataFrame,
    basket: pd.Series,
    tickers: list[str],
    benchmark: pd.Series,
) -> str | None:
    combined = pd.concat([basket.rename("basket"), benchmark.rename("benchmark")], axis=1).dropna()
    if len(combined) <= max(WINDOWS):
        return None

    for end_date in combined.index[max(WINDOWS) :]:
        metrics = compute_metrics_at(prices, basket, tickers, benchmark, end_date)
        if classify_state(metrics, len(tickers)) == state:
            return pd.Timestamp(end_date).strftime("%Y-%m-%d")
    return None


def latest_leaders(
    prices: pd.DataFrame,
    tickers: list[str],
    benchmark: pd.Series,
    end_date: pd.Timestamp,
    window: int = 63,
) -> list[dict[str, Any]]:
    bench_return = window_return(benchmark, end_date, window)
    if bench_return is None:
        return []

    leaders = []
    for ticker in tickers:
        series = usable_series(prices, ticker)
        if series is None:
            continue
        ticker_return = window_return(series, end_date, window)
        if ticker_return is None:
            continue
        leaders.append(
            {
                "ticker": ticker,
                f"return_{window}d": clean_float(ticker_return),
                f"excess_{window}d": clean_float(ticker_return - bench_return),
            }
        )

    leaders.sort(key=lambda row: (row.get(f"excess_{window}d") is None, -(row.get(f"excess_{window}d") or -999), row["ticker"]))
    return leaders[:5]


def benchmark_series(prices: pd.DataFrame, requested: str) -> tuple[str, str | None, pd.Series | None]:
    requested = (requested or FALLBACK_BENCHMARK).upper()
    series = usable_series(prices, requested)
    if series is not None and len(series) > max(WINDOWS):
        return requested, None, series
    if requested != FALLBACK_BENCHMARK:
        fallback = usable_series(prices, FALLBACK_BENCHMARK)
        if fallback is not None and len(fallback) > max(WINDOWS):
            return FALLBACK_BENCHMARK, requested, fallback
    return requested, None, series


def analyze_basket(basket_def: dict[str, Any], prices: pd.DataFrame) -> dict[str, Any]:
    tickers = [clean_symbol(t) for t in basket_def.get("tickers", [])]
    tickers = sorted({t for t in tickers if t})
    basket, priced_tickers, missing_tickers = normalized_basket(prices, tickers)
    benchmark_symbol, fallback_from, benchmark = benchmark_series(
        prices, str(basket_def.get("benchmark") or FALLBACK_BENCHMARK)
    )

    result: dict[str, Any] = {
        "basket_id": basket_def["basket_id"],
        "theme": basket_def.get("theme"),
        "theme_id": basket_def.get("theme_id"),
        "kind": basket_def.get("kind"),
        "benchmark": benchmark_symbol,
        "benchmark_requested": fallback_from or benchmark_symbol,
        "tickers": tickers,
        "priced_tickers": priced_tickers,
        "missing_tickers": sorted(missing_tickers),
        "priced_count": len(priced_tickers),
        "state": "watch",
        "phase": "insufficient_data",
        "phase_label": "Insufficient data",
        "action": "No trade; price history, benchmark history, or breadth is insufficient.",
        "action_priority": 6,
        "timing": {
            "first_trigger_date": None,
            "first_active_date": None,
            "trading_days_since_first_trigger": None,
            "trading_days_since_first_active": None,
            "first_trigger_age": None,
            "first_active_age": None,
        },
        "metrics": {f"{window}d": {"basket_return": None, "benchmark_return": None, "excess_return": None, "breadth": None} for window in WINDOWS},
        "first_trigger_date": None,
        "first_active_date": None,
        "leaders": [],
    }

    if basket.empty or benchmark is None or benchmark.empty:
        return result

    combined = pd.concat([basket.rename("basket"), benchmark.rename("benchmark")], axis=1).dropna()
    if combined.empty:
        return result

    end_date = pd.Timestamp(combined.index[-1])
    metrics = compute_metrics_at(prices, basket, priced_tickers, benchmark, end_date)
    state = classify_state(metrics, len(priced_tickers))
    first_trigger_date = first_date_for_state("trigger", prices, basket, priced_tickers, benchmark)
    first_active_date = first_date_for_state("active", prices, basket, priced_tickers, benchmark)
    timing = timing_payload(first_trigger_date, first_active_date, combined.index, end_date)
    phase = classify_phase(state, metrics, timing)

    result.update(
        {
            "state": state,
            **phase,
            "as_of_date": end_date.strftime("%Y-%m-%d"),
            "metrics": metrics,
            "first_trigger_date": first_trigger_date,
            "first_active_date": first_active_date,
            "timing": timing,
            "leaders": latest_leaders(prices, priced_tickers, benchmark, end_date),
        }
    )
    return result


def state_sort_key(row: dict[str, Any]) -> tuple[int, float, float, str]:
    phase_rank = row.get("action_priority") or 9
    state_rank = {"active": 0, "trigger": 1, "watch": 2}.get(row.get("state"), 3)
    m126 = ((row.get("metrics") or {}).get("126d") or {}).get("excess_return")
    m63 = ((row.get("metrics") or {}).get("63d") or {}).get("excess_return")
    return (phase_rank, state_rank, -(m126 or -999), -(m63 or -999), str(row.get("theme") or ""))


def build_relative_edge(artifact: dict[str, Any]) -> dict[str, Any]:
    baskets = build_baskets(artifact)
    prices = fetch_prices(symbols_for_download(baskets))
    rows = [analyze_basket(basket, prices) for basket in baskets]
    rows.sort(key=state_sort_key)
    counts = Counter(row["state"] for row in rows)
    phase_counts = Counter(row["phase"] for row in rows)
    latest_dates = [row.get("as_of_date") for row in rows if row.get("as_of_date")]

    return {
        "generated_at": utc_now(),
        "source": "Yahoo Finance adjusted close via yfinance",
        "price_start": PRICE_START,
        "price_end": PRICE_END,
        "as_of_date": max(latest_dates) if latest_dates else None,
        "rules": {
            "basket_construction": f"equal-weight adjusted-close baskets; corpus themes use top {THEME_MAX_TICKERS} tickers by score",
            "history_note": "first_trigger_date and first_active_date are retrospective for the published basket membership; corpus availability must be audited separately",
            "phase_note": "trade timing comes from current state plus signal age; old first-active dates are not fresh entries",
            "min_priced_tickers": MIN_PRICED_TICKERS,
            "fresh_trigger_max_trading_days": FRESH_TRIGGER_MAX_TRADING_DAYS,
            "early_active_max_trading_days": EARLY_ACTIVE_MAX_TRADING_DAYS,
            "active": {
                "excess_63d_gte": ACTIVE_63D_EXCESS,
                "excess_126d_gte": ACTIVE_126D_EXCESS,
                "breadth_63d_gte": ACTIVE_BREADTH,
            },
            "trigger": {
                "excess_63d_gte": TRIGGER_63D_EXCESS,
                "excess_126d_gte": TRIGGER_126D_EXCESS,
                "breadth_63d_gte": TRIGGER_BREADTH,
            },
            "windows_trading_days": list(WINDOWS),
        },
        "summary": {
            "baskets": len(rows),
            "active": counts.get("active", 0),
            "trigger": counts.get("trigger", 0),
            "watch": counts.get("watch", 0),
            "entry_window": phase_counts.get("early_active", 0),
            "research_queue": phase_counts.get("fresh_trigger", 0) + phase_counts.get("re_accelerating", 0),
            "no_trade": phase_counts.get("reset_watch", 0)
            + phase_counts.get("fading_watch", 0)
            + phase_counts.get("insufficient_data", 0),
            "phase_counts": dict(sorted(phase_counts.items())),
        },
        "baskets": rows,
    }


def main() -> int:
    if not ARTIFACT.exists():
        print(f"merge-relative-edge: artifact missing: {ARTIFACT}", file=sys.stderr)
        return 1
    if not SCAN_PATH.exists():
        print(f"merge-relative-edge: scan results missing: {SCAN_PATH}", file=sys.stderr)
        return 1

    artifact = load_json(ARTIFACT)
    payload = load_json(SCAN_PATH)
    if not isinstance(artifact, dict) or not isinstance(payload, dict):
        print("merge-relative-edge: expected object JSON roots", file=sys.stderr)
        return 1

    edge = build_relative_edge(artifact)
    payload["relative_edge"] = edge
    payload.setdefault("scan_meta", {})["relative_edge_refreshed_at"] = edge["generated_at"]
    SCAN_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    summary = edge["summary"]
    print(
        "merge-relative-edge: "
        f"{summary['active']} active, {summary['trigger']} trigger, "
        f"{summary['watch']} watch across {summary['baskets']} baskets"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
