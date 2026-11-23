import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from leave_one_hospital_out import CharNgramNB  # noqa: E402
from prepare_expansion_annotation import canonical_template  # noqa: E402
from score_annotations import kappa  # noqa: E402


class ValidationTests(unittest.TestCase):
    def test_kappa_perfect(self):
        self.assertEqual(kappa(["a", "b", "a"], ["a", "b", "a"]), 1.0)

    def test_nb_cannot_predict_unseen_class(self):
        model = CharNgramNB().fit([
            {"gold": "fee_schedule", "text": "fee schedule rate"},
            {"gold": "other", "text": "supplier invoice"},
        ])
        prediction = model.predict("per diem rate")
        self.assertIn(prediction, {"fee_schedule", "other"})
        self.assertNotEqual(prediction, "per_diem")

    def test_mechanism_template_collapses_codes_and_amounts(self):
        a = "100% of $12.34 in Billed Charges for Rev 272 Proc C1757 Mod Q1"
        b = "88% of $99.00 in Billed Charges for Rev 278 Proc A4648 Mod 59"
        self.assertEqual(canonical_template(a), canonical_template(b))


if __name__ == "__main__":
    unittest.main()
