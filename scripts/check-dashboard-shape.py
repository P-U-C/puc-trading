#!/usr/bin/env python3
"""Validate the public scanner dashboard JSON shape."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


DEFAULT_PATH = "~/pft-validator/scanner/scan-results.json"

SCAN_META_FIELDS = {
    "scanned_at",
    "tickers_scanned",
    "contracts_fetched",
    "contracts_passed",
    "themes",
}

RESULT_FIELDS = {
    "ticker",
    "theme",
    "strike",
    "expiry",
    "dte",
    "otm_pct",
    "ask",
    "mid",
    "iv",
    "asymmetry_score",
    "convergence",
}

CONVERGENCE_FIELDS = {"ticker", "theme", "score", "tier", "status"}

BOOK_TOP_FIELDS = {"generated_at", "live_unlocked", "go_live_gate", "paper", "live"}
BOOK_SIDE_FIELDS = {"open", "closed", "stats"}
GATE_FIELDS = {"required_closed_trades", "current_closed_trades", "remaining_trades"}

RELATIVE_EDGE_TOP_FIELDS = {"generated_at", "source", "rules", "summary", "baskets"}
RELATIVE_EDGE_SUMMARY_FIELDS = {"baskets", "active", "trigger", "watch"}
RELATIVE_EDGE_BASKET_FIELDS = {
    "basket_id",
    "theme",
    "kind",
    "benchmark",
    "state",
    "phase",
    "phase_label",
    "action",
    "action_priority",
    "timing",
    "tickers",
    "priced_tickers",
    "metrics",
    "leaders",
}
RELATIVE_EDGE_METRIC_FIELDS = {"basket_return", "benchmark_return", "excess_return", "breadth"}
RELATIVE_EDGE_TIMING_FIELDS = {
    "first_trigger_date",
    "first_active_date",
    "trading_days_since_first_trigger",
    "trading_days_since_first_active",
    "first_trigger_age",
    "first_active_age",
}


def require_mapping(value: object, label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: expected object")
        return False
    return True


def require_fields(value: dict, fields: set[str], label: str, errors: list[str]) -> None:
    for field in sorted(fields):
        if field not in value:
            errors.append(f"{label}: missing field {field}")


def validate(payload: object) -> list[str]:
    errors: list[str] = []
    if not require_mapping(payload, "root", errors):
        return errors

    root = payload
    assert isinstance(root, dict)
    require_fields(root, {"scan_meta", "results", "convergence", "book", "relative_edge"}, "root", errors)

    book = root.get("book")
    if require_mapping(book, "book", errors):
        assert isinstance(book, dict)
        require_fields(book, BOOK_TOP_FIELDS, "book", errors)
        gate = book.get("go_live_gate")
        if require_mapping(gate, "book.go_live_gate", errors):
            assert isinstance(gate, dict)
            require_fields(gate, GATE_FIELDS, "book.go_live_gate", errors)
        for side in ("paper", "live"):
            side_val = book.get(side)
            if require_mapping(side_val, f"book.{side}", errors):
                assert isinstance(side_val, dict)
                require_fields(side_val, BOOK_SIDE_FIELDS, f"book.{side}", errors)
                if not isinstance(side_val.get("open"), list):
                    errors.append(f"book.{side}.open: expected list")
                if not isinstance(side_val.get("closed"), list):
                    errors.append(f"book.{side}.closed: expected list")

    scan_meta = root.get("scan_meta")
    if require_mapping(scan_meta, "scan_meta", errors):
        assert isinstance(scan_meta, dict)
        require_fields(scan_meta, SCAN_META_FIELDS, "scan_meta", errors)

    results = root.get("results")
    if not isinstance(results, list):
        errors.append("results: expected list")
    else:
        for idx, item in enumerate(results):
            label = f"results[{idx}]"
            if require_mapping(item, label, errors):
                assert isinstance(item, dict)
                require_fields(item, RESULT_FIELDS, label, errors)

    convergence = root.get("convergence")
    if not isinstance(convergence, list):
        errors.append("convergence: expected list")
    else:
        for idx, item in enumerate(convergence):
            label = f"convergence[{idx}]"
            if require_mapping(item, label, errors):
                assert isinstance(item, dict)
                require_fields(item, CONVERGENCE_FIELDS, label, errors)

    relative_edge = root.get("relative_edge")
    if require_mapping(relative_edge, "relative_edge", errors):
        assert isinstance(relative_edge, dict)
        require_fields(relative_edge, RELATIVE_EDGE_TOP_FIELDS, "relative_edge", errors)
        summary = relative_edge.get("summary")
        if require_mapping(summary, "relative_edge.summary", errors):
            assert isinstance(summary, dict)
            require_fields(summary, RELATIVE_EDGE_SUMMARY_FIELDS, "relative_edge.summary", errors)
        baskets = relative_edge.get("baskets")
        if not isinstance(baskets, list):
            errors.append("relative_edge.baskets: expected list")
        else:
            for idx, item in enumerate(baskets):
                label = f"relative_edge.baskets[{idx}]"
                if require_mapping(item, label, errors):
                    assert isinstance(item, dict)
                    require_fields(item, RELATIVE_EDGE_BASKET_FIELDS, label, errors)
                    if item.get("state") not in {"active", "trigger", "watch"}:
                        errors.append(f"{label}.state: expected active, trigger, or watch")
                    if not isinstance(item.get("phase"), str):
                        errors.append(f"{label}.phase: expected string")
                    if not isinstance(item.get("phase_label"), str):
                        errors.append(f"{label}.phase_label: expected string")
                    if not isinstance(item.get("action"), str):
                        errors.append(f"{label}.action: expected string")
                    if not isinstance(item.get("action_priority"), int):
                        errors.append(f"{label}.action_priority: expected int")
                    timing = item.get("timing")
                    if require_mapping(timing, f"{label}.timing", errors):
                        assert isinstance(timing, dict)
                        require_fields(timing, RELATIVE_EDGE_TIMING_FIELDS, f"{label}.timing", errors)
                    if not isinstance(item.get("tickers"), list):
                        errors.append(f"{label}.tickers: expected list")
                    if not isinstance(item.get("priced_tickers"), list):
                        errors.append(f"{label}.priced_tickers: expected list")
                    metrics = item.get("metrics")
                    if require_mapping(metrics, f"{label}.metrics", errors):
                        assert isinstance(metrics, dict)
                        for window in ("63d", "126d"):
                            metric = metrics.get(window)
                            if require_mapping(metric, f"{label}.metrics.{window}", errors):
                                assert isinstance(metric, dict)
                                require_fields(metric, RELATIVE_EDGE_METRIC_FIELDS, f"{label}.metrics.{window}", errors)
                    if not isinstance(item.get("leaders"), list):
                        errors.append(f"{label}.leaders: expected list")

    return errors


def main() -> int:
    path = Path(os.environ.get("SCAN_RESULTS_PATH", DEFAULT_PATH)).expanduser()
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        print(f"{path}: file not found", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"{path}: invalid JSON: {exc}", file=sys.stderr)
        return 1

    errors = validate(payload)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"{path}: dashboard shape ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
