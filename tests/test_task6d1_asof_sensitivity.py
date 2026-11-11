import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sba_task6d1_asof_sensitivity as sensitivity


class TestAsOfSensitivity(unittest.TestCase):
    def test_future_rows_removed_and_date_quality_flags_remain_visible(self):
        rows = [
            {"amount": 100.0, "ratio": .5, "date": sensitivity.date(2026, 9, 30), "flags": []},
            {"amount": 300.0, "ratio": 1.5, "date": sensitivity.date(2026, 10, 1), "flags": ["chargeoff_after_snapshot"]},
            {"amount": 50.0, "ratio": .25, "date": None, "flags": ["missing_chargeoff_date"]},
        ]
        metrics, flags, counts = sensitivity.build_populations(rows)
        self.assertEqual(counts, {"original_task6d1": 3, "future_dated_excluded_only": 2, "strict_asof_snapshot": 1})
        self.assertEqual(metrics[0]["gross_chargeoff_total"], 450.0)
        self.assertEqual(metrics[1]["gross_chargeoff_total"], 150.0)
        self.assertEqual(metrics[2]["gross_chargeoff_total"], 100.0)
        flag_map = {(r["population"], r["quality_flag"]): r["records"] for r in flags}
        self.assertEqual(flag_map[("original_task6d1", "chargeoff_after_snapshot")], 1)
        self.assertEqual(flag_map[("strict_asof_snapshot", "chargeoff_after_snapshot")], 0)
        self.assertEqual(flag_map[("original_task6d1", "missing_chargeoff_date")], 1)

    def test_ratio_is_not_inferred_without_positive_approval(self):
        result = sensitivity.chargeoff_metrics([{"amount": 5.0, "ratio": None}])
        self.assertEqual(result["valid_ratio_n"], 0)
        self.assertEqual(result["invalid_ratio_n"], 1)


if __name__ == "__main__":
    unittest.main()
