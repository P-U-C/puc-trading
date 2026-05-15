import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from corpus import merge_convergence


ROOT = Path(__file__).resolve().parents[1]


def llm_row(ticker="NVDA", score=0.7, theme_id="ai_infrastructure", theme="AI Infrastructure"):
    tier = "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.55 else "LOW"
    return {
        "ticker": ticker,
        "theme_id": theme_id,
        "theme": theme,
        "convergence_score": score,
        "score": score,
        "convergence_tier": tier,
        "tier": tier,
        "status": "peak_hype",
        "models_mentioning": 3,
        "avg_rank": 1.0,
        "direct_mentions": 3,
        "total_mentions": 3,
        "source_capture_ids": ["cap1"],
    }


def opp_row(ticker="BANB", score=0.62, theme_id="peptides", theme="Peptides"):
    tier = "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.55 else "LOW"
    return {
        "ticker": ticker,
        "theme_id": theme_id,
        "theme": theme,
        "score": score,
        "tier": tier,
        "status": "peak_hype",
        "row_sources": ["theme_opportunity_generator"],
        "source_claim_ids": ["clm_1"],
        "source_capture_ids": [],
        "score_components": {
            "evidence_strength": 0.8,
            "freshness_weight": 0.9,
            "exposure_strength": 0.7,
            "catalyst_weight": 0.5,
            "tradability_weight": 1.0,
            "data_quality_weight": 1.0,
        },
    }


def artifact(rows):
    themes = {}
    for row in rows:
        themes[row["theme_id"]] = {"theme_id": row["theme_id"], "theme_name": row["theme"], "status": row["status"]}
    return {
        "schema_version": "0.1.0",
        "generated_at": "2026-05-15T00:00:00Z",
        "generator": {"name": "test", "version": "0.1.0"},
        "themes": list(themes.values()),
        "scores": rows,
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


class MergeConvergenceTests(unittest.TestCase):
    def test_two_empty_sources_fail(self):
        with self.assertRaisesRegex(ValueError, "no scores to merge"):
            merge_convergence.merge_artifacts({"themes": [], "scores": []}, {"themes": [], "scores": []})

    def test_only_llm_source_fills_row_sources(self):
        merged = merge_convergence.merge_artifacts(artifact([llm_row()]), {"themes": [], "scores": []})
        self.assertEqual(len(merged["scores"]), 1)
        self.assertEqual(merged["scores"][0]["ticker"], "NVDA")
        self.assertEqual(merged["scores"][0]["row_sources"], ["llm_survey"])

    def test_only_opportunity_source_keeps_generator_source(self):
        merged = merge_convergence.merge_artifacts({"themes": [], "scores": []}, artifact([opp_row()]))
        self.assertEqual(len(merged["scores"]), 1)
        self.assertEqual(merged["scores"][0]["ticker"], "BANB")
        self.assertEqual(merged["scores"][0]["row_sources"], ["theme_opportunity_generator"])

    def test_same_ticker_merges_sources_and_claims(self):
        merged = merge_convergence.merge_artifacts(
            artifact([llm_row(score=0.7)]),
            artifact([opp_row(ticker="NVDA", score=0.8, theme_id="ai_infrastructure", theme="AI Infrastructure")]),
        )
        row = merged["scores"][0]
        self.assertEqual(len(merged["scores"]), 1)
        self.assertEqual(set(row["row_sources"]), {"llm_survey", "theme_opportunity_generator"})
        self.assertEqual(row["score"], 0.8)
        self.assertEqual(row["source_claim_ids"], ["clm_1"])
        self.assertEqual(row["score_components"]["llm_score"], 0.7)

    def test_different_tickers_sort_by_score_desc(self):
        merged = merge_convergence.merge_artifacts(artifact([llm_row("NVDA", 0.6)]), artifact([opp_row("BANB", 0.8)]))
        self.assertEqual([row["ticker"] for row in merged["scores"]], ["BANB", "NVDA"])

    def test_cli_refuses_two_missing_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing1 = Path(tmp) / "missing1.json"
            missing2 = Path(tmp) / "missing2.json"
            out = Path(tmp) / "out.json"
            code = merge_convergence.main(["--llm-source", str(missing1), "--opportunity-source", str(missing2), "--out", str(out)])
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())

    def test_cli_writes_merged_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = Path(tmp) / "llm.json"
            opp = Path(tmp) / "opp.json"
            out = Path(tmp) / "out.json"
            write_json(llm, artifact([llm_row()]))
            write_json(opp, artifact([opp_row()]))
            code = merge_convergence.main(["--llm-source", str(llm), "--opportunity-source", str(opp), "--out", str(out)])
            self.assertEqual(code, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["scores"]), 2)

    def test_dashboard_shape_checker_still_accepts_current_dashboard_fixture(self):
        checker_path = ROOT / "scripts" / "check-dashboard-shape.py"
        spec = importlib.util.spec_from_file_location("check_dashboard_shape", checker_path)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)
        dashboard_path = Path("~/pft-validator/scanner/scan-results.json").expanduser()
        payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
        self.assertEqual(module.validate(payload), [])


if __name__ == "__main__":
    unittest.main()
