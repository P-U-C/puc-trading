import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "merge-relative-edge-into-scan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("merge_relative_edge_into_scan", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def path(total_return, periods=180):
    idx = pd.bdate_range("2025-01-02", periods=periods)
    vals = [100.0 * ((1.0 + total_return) ** (i / (periods - 1))) for i in range(periods)]
    return pd.Series(vals, index=idx)


class RelativeEdgeTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_classifies_active_only_when_excess_and_breadth_are_strong(self):
        metrics = {
            "63d": {"excess_return": 0.16, "breadth": 0.67},
            "126d": {"excess_return": 0.26},
        }
        self.assertEqual(self.module.classify_state(metrics, priced_count=3), "active")

    def test_classifies_trigger_before_active_thresholds(self):
        metrics = {
            "63d": {"excess_return": 0.11, "breadth": 0.67},
            "126d": {"excess_return": 0.10},
        }
        self.assertEqual(self.module.classify_state(metrics, priced_count=3), "trigger")

    def test_classifies_fresh_trigger_phase(self):
        phase = self.module.classify_phase(
            "trigger",
            {"63d": {"excess_return": 0.12, "breadth": 0.67}, "126d": {"excess_return": 0.10}},
            {
                "trading_days_since_first_trigger": 21,
                "trading_days_since_first_active": None,
            },
        )
        self.assertEqual(phase["phase"], "fresh_trigger")
        self.assertEqual(phase["action_priority"], 2)

    def test_classifies_old_trigger_as_re_accelerating(self):
        phase = self.module.classify_phase(
            "trigger",
            {"63d": {"excess_return": 0.12, "breadth": 0.67}, "126d": {"excess_return": -0.02}},
            {
                "trading_days_since_first_trigger": 600,
                "trading_days_since_first_active": 540,
            },
        )
        self.assertEqual(phase["phase"], "re_accelerating")

    def test_classifies_stale_watch_as_no_trade(self):
        phase = self.module.classify_phase(
            "watch",
            {"63d": {"excess_return": -0.06, "breadth": 0.20}, "126d": {"excess_return": 0.18}},
            {
                "trading_days_since_first_trigger": 500,
                "trading_days_since_first_active": 300,
            },
        )
        self.assertEqual(phase["phase"], "fading_watch")
        self.assertGreaterEqual(phase["action_priority"], 5)

    def test_requires_minimum_priced_breadth(self):
        metrics = {
            "63d": {"excess_return": 0.30, "breadth": 1.0},
            "126d": {"excess_return": 0.50},
        }
        self.assertEqual(self.module.classify_state(metrics, priced_count=2), "watch")

    def test_analyzes_equal_weight_basket_against_benchmark(self):
        prices = pd.DataFrame(
            {
                "AAA": path(1.20),
                "BBB": path(1.00),
                "CCC": path(0.90),
                "DDD": path(0.70),
                "SPY": path(0.12),
            }
        )
        basket = {
            "basket_id": "test-basket",
            "theme": "Test Basket",
            "kind": "curated",
            "benchmark": "SPY",
            "tickers": ["AAA", "BBB", "CCC", "DDD", "MISSING"],
        }

        row = self.module.analyze_basket(basket, prices)

        self.assertEqual(row["state"], "active")
        self.assertEqual(row["benchmark"], "SPY")
        self.assertEqual(row["priced_count"], 4)
        self.assertEqual(row["missing_tickers"], ["MISSING"])
        self.assertEqual(row["phase"], "early_active")
        self.assertIn("Best entry", row["action"])
        self.assertIsNotNone(row["timing"]["first_active_age"])
        self.assertGreater(row["metrics"]["63d"]["excess_return"], 0.15)
        self.assertGreaterEqual(row["metrics"]["63d"]["breadth"], 0.75)
        self.assertIsNotNone(row["first_active_date"])
        self.assertEqual(row["leaders"][0]["ticker"], "AAA")

    def test_build_baskets_excludes_private_themes_and_adds_curated(self):
        artifact = {
            "themes": [
                {"theme_id": "ai-infrastructure", "theme_name": "AI Infrastructure"},
                {"theme_id": "cicadas", "theme_name": "Cicadas"},
            ],
            "scores": [
                {"theme_id": "ai-infrastructure", "theme": "AI Infrastructure", "ticker": "NVDA", "score": 0.9},
                {"theme_id": "ai-infrastructure", "theme": "AI Infrastructure", "ticker": "AVGO", "score": 0.8},
                {"theme_id": "cicadas", "theme": "Cicadas", "ticker": "CORN", "score": 1.0},
            ],
        }

        baskets = self.module.build_baskets(artifact)
        ids = {basket["basket_id"] for basket in baskets}

        self.assertIn("ai-core-compute", ids)
        self.assertIn("theme-ai-infrastructure", ids)
        self.assertNotIn("theme-cicadas", ids)

    def test_shape_checker_requires_relative_edge_contract(self):
        checker_path = ROOT / "scripts" / "check-dashboard-shape.py"
        spec = importlib.util.spec_from_file_location("check_dashboard_shape", checker_path)
        checker = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(checker)

        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "scan-results.json"
            payload = json.loads(Path("~/pft-validator/scanner/scan-results.json").expanduser().read_text())
            payload["relative_edge"] = {
                "generated_at": "2026-09-23T00:00:00Z",
                "source": "test",
                "rules": {},
                "summary": {"baskets": 1, "active": 1, "trigger": 0, "watch": 0},
                "baskets": [
                    {
                        "basket_id": "x",
                        "theme": "X",
                        "kind": "curated",
                        "benchmark": "SPY",
                        "state": "active",
                        "phase": "early_active",
                        "phase_label": "Early active",
                        "action": "Best entry/add window.",
                        "action_priority": 1,
                        "timing": {
                            "first_trigger_date": "2026-01-01",
                            "first_active_date": "2026-01-08",
                            "trading_days_since_first_trigger": 10,
                            "trading_days_since_first_active": 5,
                            "first_trigger_age": "10d",
                            "first_active_age": "5d",
                        },
                        "tickers": ["AAA", "BBB", "CCC"],
                        "priced_tickers": ["AAA", "BBB", "CCC"],
                        "metrics": {
                            "63d": {"basket_return": 0.2, "benchmark_return": 0.0, "excess_return": 0.2, "breadth": 1.0},
                            "126d": {"basket_return": 0.3, "benchmark_return": 0.0, "excess_return": 0.3, "breadth": 1.0},
                        },
                        "leaders": [],
                    }
                ],
            }
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(checker.validate(payload), [])


if __name__ == "__main__":
    unittest.main()
