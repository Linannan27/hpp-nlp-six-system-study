import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_experiment import classify_contextual, classify_literal, flags  # noqa: E402


class RuleTests(unittest.TestCase):
    def test_literal_per_diem(self):
        self.assertEqual(classify_literal("Paid at a per diem of $6,512"), "per_diem")

    def test_literal_hybrid(self):
        text = "40% of charges, then a $200,000 case rate"
        self.assertEqual(classify_literal(text), "hybrid")

    def test_contextual_case_outlier(self):
        text = (
            "Fee schedule rate ($15,108.11). If estimated cost exceeds an "
            "outlier threshold defined as inlier reimbursement plus stop loss."
        )
        self.assertEqual(classify_literal(text), "fee_schedule")
        self.assertEqual(classify_contextual(text), "case_rate")

    def test_multilabel_flags(self):
        found = flags("The lesser of $24,000 and 80% of total billed charges")
        self.assertTrue(found["lesser_of"])
        self.assertTrue(found["fixed_dollar"])
        self.assertTrue(found["percent_of_charge"])


if __name__ == "__main__":
    unittest.main()
