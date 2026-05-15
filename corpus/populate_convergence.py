#!/usr/bin/env python3
"""Generate a deterministic fixture convergence artifact and capture records."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "corpus" / "convergence-latest.json"
CAPTURES_ROOT = ROOT / "corpus" / "captures"

MODELS = ["gpt5", "claude", "gemini", "perplexity", "grok"]
PROMPTS = ["best_stocks", "how_to_invest", "pure_plays", "top_5", "etf_or_stock"]
MENTION_TYPES = ["hedged_mention", "pure_play", "comparison", "warning"]

FIXTURE_SEED = [
    {"ticker": "NVDA", "theme": "AI Infrastructure", "score": 0.800, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "AVGO", "theme": "AI Infrastructure", "score": 0.620, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "VRT", "theme": "AI Infrastructure", "score": 0.496, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "ANET", "theme": "AI Infrastructure", "score": 0.269, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "MU", "theme": "AI Infrastructure", "score": 0.260, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "TSM", "theme": "AI Infrastructure", "score": 0.250, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "DELL", "theme": "AI Infrastructure", "score": 0.200, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "LLY", "theme": "GLP-1 / Peptides", "score": 0.800, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "NVO", "theme": "GLP-1 / Peptides", "score": 0.680, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "VKTX", "theme": "GLP-1 / Peptides", "score": 0.509, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "AMGN", "theme": "GLP-1 / Peptides", "score": 0.350, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "GPCR", "theme": "GLP-1 / Peptides", "score": 0.250, "tier": "LOW", "status": "growing"},
    {"ticker": "IONQ", "theme": "Quantum Computing", "score": 0.733, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "QBTS", "theme": "Quantum Computing", "score": 0.600, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "RGTI", "theme": "Quantum Computing", "score": 0.589, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "BWXT", "theme": "Nuclear / SMR", "score": 0.600, "tier": "HIGH", "status": "growing"},
    {"ticker": "OKLO", "theme": "Nuclear / SMR", "score": 0.541, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "SMR", "theme": "Nuclear / SMR", "score": 0.514, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "GEV", "theme": "Nuclear / SMR", "score": 0.465, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "CEG", "theme": "Nuclear / SMR", "score": 0.400, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "CCJ", "theme": "Nuclear / SMR", "score": 0.300, "tier": "LOW", "status": "growing"},
    {"ticker": "LEU", "theme": "Nuclear / SMR", "score": 0.250, "tier": "LOW", "status": "growing"},
    {"ticker": "TSLA", "theme": "Robotics / Humanoid", "score": 0.500, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "ISRG", "theme": "Robotics / Humanoid", "score": 0.400, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "SYM", "theme": "Robotics / Humanoid", "score": 0.350, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "SERV", "theme": "Robotics / Humanoid", "score": 0.250, "tier": "LOW", "status": "growing"},
    {"ticker": "LITE", "theme": "Photonic Computing", "score": 0.400, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "COHR", "theme": "Photonic Computing", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "IIVI", "theme": "Photonic Computing", "score": 0.300, "tier": "LOW", "status": "emerging"},
    {"ticker": "RKLB", "theme": "Space / Satellite", "score": 0.500, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "ASTS", "theme": "Space / Satellite", "score": 0.400, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "PL", "theme": "Space / Satellite", "score": 0.300, "tier": "LOW", "status": "growing"},
    {"ticker": "LUNR", "theme": "Space / Satellite", "score": 0.250, "tier": "LOW", "status": "emerging"},
    {"ticker": "PLTR", "theme": "Defense AI", "score": 0.600, "tier": "HIGH", "status": "growing"},
    {"ticker": "LDOS", "theme": "Defense AI", "score": 0.350, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "BWXT", "theme": "Defense AI", "score": 0.300, "tier": "LOW", "status": "growing"},
    {"ticker": "ABBV", "theme": "Longevity", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "CELH", "theme": "Longevity", "score": 0.250, "tier": "LOW", "status": "emerging"},
    {"ticker": "MARA", "theme": "Bitcoin Mining", "score": 0.500, "tier": "MEDIUM", "status": "post_peak"},
    {"ticker": "RIOT", "theme": "Bitcoin Mining", "score": 0.450, "tier": "MEDIUM", "status": "post_peak"},
    {"ticker": "CLSK", "theme": "Bitcoin Mining", "score": 0.350, "tier": "MEDIUM", "status": "post_peak"},
    {"ticker": "BFLY", "theme": "BCI / Neurotech", "score": 0.500, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "QSI", "theme": "BCI / Neurotech", "score": 0.400, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "QS", "theme": "Solid-State Battery", "score": 0.550, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "SLDP", "theme": "Solid-State Battery", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "CRBU", "theme": "Synthetic Biology", "score": 0.400, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "TWST", "theme": "Synthetic Biology", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "PACB", "theme": "Synthetic Biology", "score": 0.300, "tier": "LOW", "status": "emerging"},
    {"ticker": "AMBA", "theme": "Edge AI", "score": 0.500, "tier": "MEDIUM", "status": "emerging"},
]


def theme_id(theme):
    return re.sub(r"[^a-z0-9]+", "_", theme.lower()).strip("_")


def tier_for(score):
    if score >= 0.6:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"


def score_for(models_mentioning, avg_rank, direct_mentions, total_mentions):
    direct_ratio = direct_mentions / total_mentions if total_mentions else 0
    score = (models_mentioning / 5) * 0.5 + (1 / max(avg_rank, 1)) * 0.3 + direct_ratio * 0.2
    return round(score, 3)


def choose_plan(target_score, target_tier):
    best = None
    for models_mentioning in range(1, 6):
        total_mentions = models_mentioning
        for rank in range(1, 13):
            for direct_mentions in range(total_mentions + 1):
                score = score_for(models_mentioning, rank, direct_mentions, total_mentions)
                if tier_for(score) != target_tier:
                    continue
                distance = abs(score - target_score)
                candidate = (distance, models_mentioning, rank, direct_mentions, score)
                if best is None or candidate < best:
                    best = candidate
    if best is None:
        raise ValueError(f"cannot synthesize {target_tier} score near {target_score}")
    _, models_mentioning, rank, direct_mentions, _ = best
    return {
        "models_mentioning": models_mentioning,
        "rank": rank,
        "direct_mentions": direct_mentions,
    }


def compute_convergence(records, selected_theme_id):
    ticker_map = {}
    for record in records:
        if record["theme_id"] != selected_theme_id or record["status"] != "captured":
            continue
        for mention in record["tickers"]:
            ticker = mention["ticker"].upper()
            entry = ticker_map.setdefault(
                ticker,
                {
                    "company": mention["company_name"],
                    "models": set(),
                    "total_mentions": 0,
                    "ranks": [],
                    "direct_count": 0,
                    "hedged_count": 0,
                    "capture_ids": [],
                },
            )
            entry["models"].add(record["model_slot"])
            entry["total_mentions"] += 1
            entry["ranks"].append(mention["rank_in_response"])
            entry["capture_ids"].append(record["capture_id"])
            if mention["mention_type"] == "direct_recommendation":
                entry["direct_count"] += 1
            if mention["mention_type"] == "hedged_mention":
                entry["hedged_count"] += 1

    results = []
    for ticker, data in ticker_map.items():
        avg_rank = sum(data["ranks"]) / len(data["ranks"])
        score = score_for(len(data["models"]), avg_rank, data["direct_count"], data["total_mentions"])
        results.append(
            {
                "ticker": ticker,
                "company_name": data["company"],
                "theme_id": selected_theme_id,
                "models_mentioning": len(data["models"]),
                "total_mentions": data["total_mentions"],
                "avg_rank": round(avg_rank, 1),
                "direct_recommendation_count": data["direct_count"],
                "hedged_mention_count": data["hedged_count"],
                "convergence_score": score,
                "convergence_tier": tier_for(score).lower(),
                "source_capture_ids": sorted(set(data["capture_ids"])),
            }
        )
    return sorted(results, key=lambda row: (-row["convergence_score"], row["ticker"]))


def build_capture_records(generated_at):
    themes = {}
    for row in FIXTURE_SEED:
        themes.setdefault(row["theme"], row["status"])

    records_by_theme_model = {}
    for theme_index, (theme_name, status) in enumerate(themes.items()):
        tid = theme_id(theme_name)
        for model_index, model in enumerate(MODELS):
            capture_id = f"fixture-{tid}-{model}"
            records_by_theme_model[(tid, model)] = {
                "capture_id": capture_id,
                "timestamp_utc": generated_at,
                "model_slot": model,
                "model_version": f"{model}-fixture-0.1.0",
                "status": "captured",
                "error_detail": None,
                "theme_id": tid,
                "prompt_id": PROMPTS[model_index % len(PROMPTS)],
                "prompt_text": f"Fixture prompt for {theme_name}",
                "tickers": [],
                "response_excerpt": f"Synthetic fixture capture for {theme_name} ({status}).",
            }

        theme_rows = [row for row in FIXTURE_SEED if row["theme"] == theme_name]
        for ticker_index, row in enumerate(theme_rows):
            plan = choose_plan(row["score"], row["tier"])
            start = (ticker_index + theme_index) % len(MODELS)
            selected_models = [MODELS[(start + offset) % len(MODELS)] for offset in range(plan["models_mentioning"])]
            for mention_index, model in enumerate(selected_models):
                mention_type = (
                    "direct_recommendation"
                    if mention_index < plan["direct_mentions"]
                    else MENTION_TYPES[(ticker_index + mention_index) % len(MENTION_TYPES)]
                )
                records_by_theme_model[(tid, model)]["tickers"].append(
                    {
                        "ticker": row["ticker"],
                        "company_name": f"{row['ticker']} Corp",
                        "rank_in_response": plan["rank"],
                        "mention_type": mention_type,
                        "qualifying_language": f"fixture {mention_type.replace('_', ' ')}",
                        "repeated_in_response": mention_index == 0 and plan["models_mentioning"] > 3,
                    }
                )

    return list(records_by_theme_model.values())


def build_artifact(records, generated_at):
    seed_by_key = {(row["ticker"], theme_id(row["theme"])): row for row in FIXTURE_SEED}
    themes = [
        {"theme_id": theme_id(theme), "theme_name": theme, "status": status}
        for theme, status in dict((row["theme"], row["status"]) for row in FIXTURE_SEED).items()
    ]
    scores = []
    for theme in themes:
        for score in compute_convergence(records, theme["theme_id"]):
            seed = seed_by_key[(score["ticker"], theme["theme_id"])]
            tier = score["convergence_tier"].upper()
            scores.append(
                {
                    "ticker": score["ticker"],
                    "theme_id": theme["theme_id"],
                    "theme": theme["theme_name"],
                    "convergence_score": score["convergence_score"],
                    "score": score["convergence_score"],
                    "convergence_tier": tier,
                    "tier": tier,
                    "status": seed["status"],
                    "models_mentioning": score["models_mentioning"],
                    "avg_rank": score["avg_rank"],
                    "direct_mentions": score["direct_recommendation_count"],
                    "total_mentions": score["total_mentions"],
                    "source_capture_ids": score["source_capture_ids"],
                }
            )

    return {
        "schema_version": "0.1.0",
        "generated_at": generated_at,
        "generator": {"name": "llm-convergence-populator", "version": "0.1.0", "mode": "fixture"},
        "themes": themes,
        "scores": scores,
    }


def main():
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    records = build_capture_records(generated_at)
    artifact = build_artifact(records, generated_at)

    capture_dir = CAPTURES_ROOT / generated_at[:10]
    capture_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(ARTIFACT_PATH, "w") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")

    capture_path = capture_dir / "capture-records.json"
    with open(capture_path, "w") as f:
        json.dump(records, f, indent=2)
        f.write("\n")

    print(f"wrote {ARTIFACT_PATH}")
    print(f"wrote {capture_path}")


if __name__ == "__main__":
    main()
