#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
GENERATOR = {"name": "merge_convergence", "version": "0.1.0", "mode": "merge"}
DEFAULT_LLM = "~/puc-trading/corpus/convergence-latest.json"
DEFAULT_OPP = "~/trend-intel-private/themes/peptides/artifacts/opportunity-rows.json"
REQUIRED_ROW_FIELDS = {"ticker", "theme_id", "theme", "score", "tier", "status"}
SCORE_COMPONENT_KEYS = {
    "evidence_strength",
    "freshness_weight",
    "exposure_strength",
    "catalyst_weight",
    "tradability_weight",
    "data_quality_weight",
}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_artifact(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        return {"themes": [], "scores": []}
    with p.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{p}: artifact root must be an object")
    payload.setdefault("themes", [])
    payload.setdefault("scores", [])
    if not isinstance(payload["scores"], list):
        raise ValueError(f"{p}: scores must be a list")
    return payload


def tier_for(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


def normalize_row(row: dict[str, Any], origin: str, idx: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"{origin} row {idx}: expected object")
    out = dict(row)
    missing = sorted(field for field in REQUIRED_ROW_FIELDS if field not in out)
    if missing:
        raise ValueError(f"{origin} row {idx}: missing required fields: {', '.join(missing)}")
    if origin == "llm":
        out.setdefault("row_sources", ["llm_survey"])
        out.setdefault("source_claim_ids", [])
        out.setdefault("source_capture_ids", out.get("capture_ids", []))
    else:
        out.setdefault("row_sources", ["theme_opportunity_generator"])
        out.setdefault("source_claim_ids", [])
        out.setdefault("source_capture_ids", [])
        if "score_components" not in out:
            raise ValueError(f"{origin} row {idx}: missing required fields: score_components")
    out["ticker"] = str(out["ticker"]).upper()
    out["score"] = round(float(out["score"]), 4)
    out["tier"] = str(out["tier"]).upper()
    if out["tier"] not in {"HIGH", "MEDIUM", "LOW"}:
        raise ValueError(f"{origin} row {idx}: invalid tier")
    if not isinstance(out["row_sources"], list):
        raise ValueError(f"{origin} row {idx}: row_sources must be a list")
    if not isinstance(out["source_claim_ids"], list):
        raise ValueError(f"{origin} row {idx}: source_claim_ids must be a list")
    if not isinstance(out["source_capture_ids"], list):
        raise ValueError(f"{origin} row {idx}: source_capture_ids must be a list")
    if "score_components" in out:
        missing_components = SCORE_COMPONENT_KEYS - set(out["score_components"])
        if missing_components:
            raise ValueError(f"{origin} row {idx}: score_components missing {', '.join(sorted(missing_components))}")
    return out


def normalize_rows(rows: list[dict[str, Any]], origin: str) -> list[dict[str, Any]]:
    return [normalize_row(row, origin, idx) for idx, row in enumerate(rows)]


def union_list(*items: list[Any]) -> list[Any]:
    out = []
    seen = set()
    for values in items:
        for value in values or []:
            key = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            if key not in seen:
                seen.add(key)
                out.append(value)
    return out


def merge_pair(llm: dict[str, Any] | None, opp: dict[str, Any] | None) -> dict[str, Any]:
    if llm is None and opp is None:
        raise ValueError("cannot merge empty pair")
    if llm is None:
        assert opp is not None
        out = dict(opp)
        out["row_sources"] = union_list(out.get("row_sources", []), ["theme_opportunity_generator"])
        return out
    if opp is None:
        out = dict(llm)
        out["row_sources"] = union_list(out.get("row_sources", []), ["llm_survey"])
        return out

    score = max(float(llm["score"]), float(opp["score"]))
    out = dict(opp)
    out.update({k: v for k, v in llm.items() if v not in (None, "", [])})
    out["score"] = round(score, 4)
    out["tier"] = tier_for(score)
    out["row_sources"] = union_list(llm.get("row_sources", []), opp.get("row_sources", []))
    out["source_claim_ids"] = union_list(llm.get("source_claim_ids", []), opp.get("source_claim_ids", []))
    out["source_capture_ids"] = union_list(llm.get("source_capture_ids", []), opp.get("source_capture_ids", []))
    components = dict(opp.get("score_components") or {})
    components["llm_score"] = float(llm["score"])
    out["score_components"] = components
    if "convergence_score" in llm:
        out["convergence_score"] = llm["convergence_score"]
    if "convergence_tier" in llm:
        out["convergence_tier"] = llm["convergence_tier"]
    return out


def theme_key(theme: dict[str, Any]) -> tuple[str, str]:
    return (str(theme.get("theme_id", "")), str(theme.get("theme_name") or theme.get("theme") or ""))


def themes_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {}
    for row in rows:
        seen.setdefault(row["theme_id"], {"theme_id": row["theme_id"], "theme_name": row["theme"], "status": row["status"]})
    return list(seen.values())


def merge_artifacts(llm_payload: dict[str, Any], opp_payload: dict[str, Any], generated_at: dt.datetime | None = None) -> dict[str, Any]:
    llm_rows = normalize_rows(llm_payload.get("scores", []), "llm")
    opp_rows = normalize_rows(opp_payload.get("scores", []), "opportunity")
    if not llm_rows and not opp_rows:
        raise ValueError("no scores to merge")

    groups: dict[tuple[str, str], dict[str, dict[str, Any] | None]] = {}
    for row in llm_rows:
        groups.setdefault((row["theme_id"], row["ticker"]), {"llm": None, "opp": None})["llm"] = row
    for row in opp_rows:
        groups.setdefault((row["theme_id"], row["ticker"]), {"llm": None, "opp": None})["opp"] = row

    merged = [merge_pair(pair.get("llm"), pair.get("opp")) for pair in groups.values()]
    merged.sort(key=lambda row: (-float(row["score"]), row["ticker"]))

    theme_union: dict[str, dict[str, Any]] = {}
    for payload in (llm_payload, opp_payload):
        for theme in payload.get("themes", []) or []:
            if isinstance(theme, dict) and theme.get("theme_id"):
                theme_union[str(theme["theme_id"])] = dict(theme)
    for theme in themes_from_rows(merged):
        theme_union.setdefault(theme["theme_id"], theme)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso(generated_at or now_utc()),
        "generator": GENERATOR,
        "themes": sorted(theme_union.values(), key=lambda theme: str(theme.get("theme_id", ""))),
        "scores": merged,
    }


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-source", default=DEFAULT_LLM)
    parser.add_argument("--opportunity-source", default=DEFAULT_OPP)
    parser.add_argument("--out", default=DEFAULT_LLM)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        llm_payload = load_artifact(args.llm_source)
        opp_payload = load_artifact(args.opportunity_source)
        merged = merge_artifacts(llm_payload, opp_payload)
    except Exception as exc:
        print(f"merge failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(merged, indent=2, sort_keys=True))
    else:
        write_atomic(Path(args.out).expanduser(), merged)
        print(f"merged {len(merged['scores'])} scores into {Path(args.out).expanduser()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
