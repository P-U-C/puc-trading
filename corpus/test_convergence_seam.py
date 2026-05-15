import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus import populate_convergence
from scanner import run_live_scan


def write_json(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f)


def valid_artifact(generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": "0.1.0",
        "generated_at": generated_at,
        "generator": {"name": "test", "version": "0.1.0", "mode": "fixture"},
        "themes": [{"theme_id": "ai_infra", "theme_name": "AI Infrastructure", "status": "peak_hype"}],
        "scores": [
            {
                "ticker": "NVDA",
                "theme_id": "ai_infra",
                "theme": "AI Infrastructure",
                "convergence_score": 0.8,
                "score": 0.8,
                "convergence_tier": "HIGH",
                "tier": "HIGH",
                "status": "peak_hype",
                "models_mentioning": 5,
                "avg_rank": 1.0,
                "direct_mentions": 5,
                "total_mentions": 5,
                "source_capture_ids": ["fixture-ai_infra-gpt5"],
            }
        ],
    }


class ConvergenceSeamTests(unittest.TestCase):
    def test_missing_artifact_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            with self.assertRaisesRegex(run_live_scan.ConvergenceLoadError, "missing"):
                run_live_scan.validate_convergence_artifact(missing)

    def test_malformed_json_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json")
            with self.assertRaisesRegex(run_live_scan.ConvergenceLoadError, "malformed JSON"):
                run_live_scan.validate_convergence_artifact(path)

    def test_missing_generated_at_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            artifact = valid_artifact()
            artifact.pop("generated_at")
            write_json(path, artifact)
            with self.assertRaisesRegex(run_live_scan.ConvergenceLoadError, "generated_at"):
                run_live_scan.validate_convergence_artifact(path)

    def test_stale_artifact_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            old = datetime.now(timezone.utc) - timedelta(days=30)
            write_json(path, valid_artifact(old.isoformat()))
            with self.assertRaisesRegex(run_live_scan.ConvergenceLoadError, "stale.*threshold=14"):
                run_live_scan.validate_convergence_artifact(path, max_age_days=14)

    def test_empty_scores_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            artifact = valid_artifact()
            artifact["scores"] = []
            write_json(path, artifact)
            with self.assertRaisesRegex(run_live_scan.ConvergenceLoadError, "non-empty"):
                run_live_scan.validate_convergence_artifact(path)

    def test_missing_required_score_field_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            artifact = valid_artifact()
            artifact["scores"][0].pop("theme")
            write_json(path, artifact)
            with self.assertRaisesRegex(run_live_scan.ConvergenceLoadError, "missing required fields: theme"):
                run_live_scan.validate_convergence_artifact(path)

    def test_valid_artifact_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            write_json(path, valid_artifact())
            loaded = run_live_scan.load_convergence(path)
            self.assertEqual(
                loaded,
                [{"ticker": "NVDA", "theme": "AI Infrastructure", "score": 0.8, "tier": "HIGH", "status": "peak_hype"}],
            )

    def test_fixture_populator_output_validates(self):
        populate_convergence.main()
        artifact = run_live_scan.validate_convergence_artifact(populate_convergence.ARTIFACT_PATH)
        capture_path = (
            populate_convergence.CAPTURES_ROOT
            / artifact["generated_at"][:10]
            / "capture-records.json"
        )
        self.assertTrue(capture_path.exists())
        self.assertEqual(len(artifact["scores"]), len(populate_convergence.FIXTURE_SEED))
        self.assertEqual(artifact["generator"]["mode"], "fixture")

    def test_compatibility_mapping_into_scanner_input(self):
        mapped = run_live_scan.map_convergence_scores(valid_artifact())
        self.assertEqual(set(mapped[0]), {"ticker", "theme", "score", "tier", "status"})
        self.assertIsInstance(mapped[0]["score"], float)
        self.assertEqual(mapped[0]["ticker"], "NVDA")


if __name__ == "__main__":
    unittest.main()
