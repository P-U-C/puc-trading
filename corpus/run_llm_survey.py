#!/usr/bin/env python3
"""run_llm_survey.py - LIVE LLM retail-funnel survey (replaces the fixtures).

THE THESIS (Chad): order flow is driven by funnels; production LLMs are the
new Google. The tickers the top labs' models converge on when retail asks
"how do I get exposure to <trend>" receive the flow. Until 2026-06-12 the
llm_survey layer of convergence-latest.json was a hardcoded May-15 fixture
(populate_convergence.py) -- nothing ever asked a real model, so new names
(e.g. BOT entering robotics) could never appear. This script asks them.

Per public theme x model slot, the model gets the verbatim retail question
and answers organically, ending with a machine-readable ticker summary.
Captures land in corpus/captures/<date>/capture-records.json (the existing
schema); convergence scores are recomputed and the llm_survey rows of
corpus/convergence-latest.json are rewritten in place:
  - pure llm_survey rows: replaced wholesale by the live survey
  - rows merged with theme_opportunity_generator: convergence fields
    refreshed (their opportunity `score` is left alone)
  - newly recommended tickers: added with score = convergence_score

Convergence scoring (documented so it's tunable, not mystical):
  breadth  = models_mentioning / models_surveyed          (weight 0.40)
  directness = direct_recommendations / models_surveyed   (weight 0.35)
  rank     = max(0, 1 - (avg_rank - 1) * 0.15)            (weight 0.25)
  tier: >=0.60 HIGH, >=0.35 MEDIUM, else LOW

Model slots: claude (CLI, --strict-mcp-config so headless runs never spawn
a competing Telegram poller) and gpt via codex exec. Gemini/Grok/Perplexity
slots need API keys Chad hasn't provided. Weekly cron (Mon 20:00 UTC); the
nightly basket builder (21:05) picks up universe changes automatically.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "corpus" / "convergence-latest.json"
CAPTURES_ROOT = ROOT / "corpus" / "captures"

PRIVATE_THEME_IDS = {
    t.strip()
    for t in os.environ.get("BOOK_PRIVATE_THEME_IDS", "cicadas").split(",")
    if t.strip()
}
PER_CALL_TIMEOUT = int(os.environ.get("SURVEY_CALL_TIMEOUT", "300"))

# Plain-language theme descriptions for the retail question. Falls back to
# the artifact's theme_name for themes not listed.
THEME_PHRASES = {
    "ai-infrastructure": "AI infrastructure (datacenters, AI chips, networking)",
    "quantum-computing": "quantum computing",
    "nuclear-smr": "nuclear power and small modular reactors",
    "robotics-humanoid": "robotics and humanoid robots",
    "photonic-computing": "photonic computing",
    "space-satellite": "the space economy and satellites",
    "defense-ai": "defense AI and autonomous defense systems",
    "longevity": "longevity and anti-aging",
    "bitcoin-mining": "bitcoin mining",
    "bci-neurotech": "brain-computer interfaces and neurotech",
    "solid-state-battery": "solid-state batteries",
    "synthetic-biology": "synthetic biology",
    "edge-ai": "edge AI (on-device AI chips and software)",
    "peptides": "GLP-1 weight-loss drugs and peptides",
    "biomechanics": "biomechanics (robotic surgery, exoskeletons, prosthetics, musculoskeletal health tech)",
}

PROMPT_TEMPLATE = (
    'A retail investor asks you: "I want stock exposure to {phrase}. '
    'What specific stock tickers would you recommend I look at?" '
    "Answer briefly as you normally would to such a user, then at the very end "
    "output a machine-readable summary of every ticker you mentioned, as a single "
    'JSON object on one line: {{"tickers":[{{"ticker":"XYZ","company_name":"...",'
    '"rank_in_response":1,"mention_type":"direct_recommendation|hedged_mention|'
    'pure_play|comparison|warning"}}]}} '
    "Order by how prominently you recommended each. No markdown fences around the JSON."
)


import shutil


def _bin(name: str) -> str:
    """Resolve a CLI to an absolute path. cron's PATH does NOT include
    ~/.npm-global/bin or ~/.local/bin, so a bare name silently fails in cron
    (the 2026-06-15 first weekly run: every codex call errored "No such file
    or directory: 'codex'", so the survey ran Claude-only at half signal)."""
    found = shutil.which(name)
    if found:
        return found
    for cand in (
        os.path.expanduser(f"~/.npm-global/bin/{name}"),
        os.path.expanduser(f"~/.local/bin/{name}"),
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ):
        if os.path.exists(cand):
            return cand
    return name  # last resort: let subprocess raise a clear error


def call_claude(prompt: str) -> str:
    r = subprocess.run(
        [_bin("claude"), "-p", "--strict-mcp-config", "--model", "sonnet", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=PER_CALL_TIMEOUT,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: {r.stderr[:200]}")
    return r.stdout


def call_codex(prompt: str) -> str:
    r = subprocess.run(
        [_bin("codex"), "exec", "--skip-git-repo-check", "-s", "read-only", prompt],
        capture_output=True, text=True, timeout=PER_CALL_TIMEOUT, cwd="/tmp",
    )
    if r.returncode != 0:
        raise RuntimeError(f"codex exit {r.returncode}: {r.stderr[:200]}")
    return r.stdout


MODEL_SLOTS = {
    "claude": {"call": call_claude, "version": "claude-sonnet-cli"},
    "gpt": {"call": call_codex, "version": "codex-exec"},
}


def parse_tickers(raw: str) -> list[dict]:
    """Pull the last {"tickers":[...]} object out of the model's output."""
    matches = re.findall(r'\{"tickers"\s*:\s*\[.*?\]\s*\}', raw, flags=re.DOTALL)
    if not matches:
        return []
    try:
        data = json.loads(matches[-1])
    except json.JSONDecodeError:
        return []
    out = []
    for i, t in enumerate(data.get("tickers", []), start=1):
        ticker = str(t.get("ticker", "")).strip().upper()
        if not ticker or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
            continue
        out.append(
            {
                "ticker": ticker,
                "company_name": t.get("company_name") or ticker,
                "rank_in_response": int(t.get("rank_in_response") or i),
                "mention_type": t.get("mention_type") or "direct_recommendation",
                "qualifying_language": "",
                "repeated_in_response": False,
            }
        )
    return out


def score_theme(captures: list[dict], n_slots: int) -> dict[str, dict]:
    """captures (one per model slot that succeeded) -> per-ticker convergence."""
    per: dict[str, dict] = {}
    for cap in captures:
        for t in cap["tickers"]:
            d = per.setdefault(
                t["ticker"],
                {"models": 0, "direct": 0, "ranks": [], "company_name": t["company_name"]},
            )
            d["models"] += 1
            if t["mention_type"] == "direct_recommendation":
                d["direct"] += 1
            d["ranks"].append(t["rank_in_response"])

    out = {}
    for ticker, d in per.items():
        breadth = d["models"] / n_slots
        directness = d["direct"] / n_slots
        avg_rank = sum(d["ranks"]) / len(d["ranks"])
        rank_score = max(0.0, 1.0 - (avg_rank - 1) * 0.15)
        cs = round(0.40 * breadth + 0.35 * directness + 0.25 * rank_score, 3)
        tier = "HIGH" if cs >= 0.60 else ("MEDIUM" if cs >= 0.35 else "LOW")
        out[ticker] = {
            "convergence_score": cs,
            "convergence_tier": tier,
            "models_mentioning": d["models"],
            "direct_mentions": d["direct"],
            "avg_rank": round(avg_rank, 1),
            "total_mentions": d["models"],
            "company_name": d["company_name"],
        }
    return out


def main() -> int:
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    themes = [
        t for t in art.get("themes", [])
        if t.get("theme_id") and t["theme_id"] not in PRIVATE_THEME_IDS
    ]
    only = os.environ.get("SURVEY_THEMES")
    if only:
        keep = {s.strip() for s in only.split(",")}
        themes = [t for t in themes if t["theme_id"] in keep]

    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    cap_dir = CAPTURES_ROOT / day
    cap_dir.mkdir(parents=True, exist_ok=True)
    cap_path = cap_dir / "capture-records.json"
    records = json.loads(cap_path.read_text(encoding="utf-8")) if cap_path.exists() else []

    # Each (theme, slot) call is an independent subprocess -- run a few in
    # parallel or 15 themes x a ~3-minute codex call takes most of an hour.
    from concurrent.futures import ThreadPoolExecutor

    def run_one(job):
        tid, phrase, slot, cfg = job
        prompt = PROMPT_TEMPLATE.format(phrase=phrase)
        rec = {
            "capture_id": f"live-{tid}-{slot}-{day}",
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model_slot": slot,
            "model_version": cfg["version"],
            "status": "captured",
            "error_detail": None,
            "theme_id": tid,
            "prompt_id": "best_stocks",
            "prompt_text": prompt,
            "tickers": [],
        }
        try:
            raw = cfg["call"](prompt)
            rec["tickers"] = parse_tickers(raw)
            if not rec["tickers"]:
                rec["status"] = "parse_failed"
                rec["error_detail"] = raw[-300:]
        except Exception as exc:
            rec["status"] = "error"
            rec["error_detail"] = str(exc)[:300]
        print(f"{tid} x {slot}: {rec['status']} ({len(rec['tickers'])} tickers)", flush=True)
        return rec

    jobs = []
    for th in themes:
        tid = th["theme_id"]
        phrase = THEME_PHRASES.get(tid, th.get("theme_name") or tid)
        for slot, cfg in MODEL_SLOTS.items():
            jobs.append((tid, phrase, slot, cfg))

    with ThreadPoolExecutor(max_workers=int(os.environ.get("SURVEY_WORKERS", "4"))) as ex:
        new_records = list(ex.map(run_one, jobs))
    records.extend(new_records)

    theme_scores: dict[str, dict[str, dict]] = {}
    for th in themes:
        tid = th["theme_id"]
        caps = [r for r in new_records if r["theme_id"] == tid and r["status"] == "captured"]
        if caps:
            theme_scores[tid] = score_theme(caps, n_slots=len(MODEL_SLOTS))

    cap_path.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")

    if not theme_scores:
        print("survey: no themes captured; artifact untouched", file=sys.stderr)
        return 1

    # Rewrite the artifact's llm_survey layer for surveyed themes.
    theme_names = {t["theme_id"]: t.get("theme_name") for t in art.get("themes", [])}
    kept_rows = []
    for r in art.get("scores", []):
        tid = r.get("theme_id")
        sources = r.get("row_sources") or []
        if tid in theme_scores and sources == ["llm_survey"]:
            continue  # pure fixture/old survey row -> replaced below
        if tid in theme_scores and "llm_survey" in sources:
            live = theme_scores[tid].pop(r.get("ticker"), None)
            if live:
                r.update(
                    {k: live[k] for k in (
                        "convergence_score", "convergence_tier",
                        "models_mentioning", "direct_mentions", "total_mentions",
                    )}
                )
                r["avg_rank"] = live["avg_rank"]
            else:
                # merged row the live survey no longer supports: keep the
                # generator side, drop the survey claim
                r["row_sources"] = [s for s in sources if s != "llm_survey"]
                for k in ("convergence_score", "convergence_tier"):
                    r.pop(k, None)
        kept_rows.append(r)

    for tid, tickers in theme_scores.items():
        for ticker, live in tickers.items():
            kept_rows.append(
                {
                    "ticker": ticker,
                    "theme_id": tid,
                    "theme": theme_names.get(tid) or tid,
                    "score": live["convergence_score"],
                    "tier": live["convergence_tier"],
                    "status": next(
                        (t.get("status") for t in art.get("themes", []) if t["theme_id"] == tid),
                        "emerging",
                    ),
                    "convergence_score": live["convergence_score"],
                    "convergence_tier": live["convergence_tier"],
                    "models_mentioning": live["models_mentioning"],
                    "direct_mentions": live["direct_mentions"],
                    "total_mentions": live["total_mentions"],
                    "avg_rank": live["avg_rank"],
                    "row_sources": ["llm_survey"],
                    "source_capture_ids": [
                        f"live-{tid}-{slot}-{day}" for slot in MODEL_SLOTS
                    ],
                    "source_claim_ids": [],
                }
            )

    art["scores"] = kept_rows
    art["generated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    art.setdefault("generator", {})
    if isinstance(art["generator"], dict):
        art["generator"]["llm_survey"] = f"live run_llm_survey {day}"
    ARTIFACT.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")

    n_new = sum(len(v) for v in theme_scores.values())
    print(f"survey: {len(theme_scores)} themes updated, {n_new} net-new survey rows added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
