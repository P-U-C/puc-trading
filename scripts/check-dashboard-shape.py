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
    require_fields(root, {"scan_meta", "results", "convergence"}, "root", errors)

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

