import csv
import tempfile
import unittest
from pathlib import Path

from vision_classifier.scripts import train


class TrainSearchTests(unittest.TestCase):
    def test_mlp_search_space_contains_notebook_baseline_and_reasonable_variants(self):
        candidates = train.build_mlp_search_candidates(random_state=7)

        self.assertGreaterEqual(len(candidates), 8)
        self.assertIn(
            {
                "hidden_layer_sizes": (512, 256, 64),
                "alpha": 1e-5,
                "learning_rate_init": 0.001,
                "random_state": 7,
            },
            candidates,
        )

    def test_write_search_results_orders_best_auc_first(self):
        rows = [
            {"rank": 2, "mean_test_roc_auc": 0.75, "params": {"alpha": 0.001}},
            {"rank": 1, "mean_test_roc_auc": 0.82, "params": {"alpha": 1e-05}},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results.csv"
            train.write_search_results(rows, out)

            with out.open(newline="") as f:
                result_rows = list(csv.DictReader(f))

        self.assertEqual(result_rows[0]["rank"], "1")
        self.assertEqual(result_rows[0]["mean_test_roc_auc"], "0.82")
        self.assertIn("alpha", result_rows[0]["params"])


if __name__ == "__main__":
    unittest.main()
