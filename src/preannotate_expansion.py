#!/usr/bin/env python3
"""Create clearly marked machine suggestions for human expansion review."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from run_experiment import classify_literal, flags


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "annotations" / "expansion_human_review.csv"
OUTPUT = ROOT / "annotations" / "expansion_machine_preannotations_FOR_HUMAN_REVIEW.csv"


ATTR_MAP = {
    "attr_fee_schedule_reference": "fee_schedule",
    "attr_case_rate": "case_rate",
    "attr_per_diem": "per_diem",
    "attr_percent_of_charge": "percent_of_charge",
    "attr_fixed_dollar": "fixed_dollar",
    "attr_outlier_stop_loss": "outlier_stop_loss",
    "attr_lesser_of": "lesser_of",
    "attr_bundle_packaging": "bundle_packaging",
    "attr_external_reference": "external_reference",
    "attr_length_of_stay": "length_of_stay",
}


def suggested_computability(text, found):
    lower = text.lower()
    if "no services for payer" in lower or "estimated allowed amount" == lower.strip(" .|"):
        return "unclear"
    formula_signal = bool(re.search(
        r"%|\$|lesser|rate|per diem|case rate|billed charges|threshold|equals|=",
        text,
        re.I,
    ))
    if found["external_reference"] and not formula_signal:
        return "not_computable"
    return "conditional_external"


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output_rows = []
    for row in rows:
        text = row["normalized_template"] or row["expression_text"]
        found = flags(text)
        primary = classify_literal(text)
        if primary in {"abstain", "other"}:
            primary = "unclear"
        suggested = {
            **row,
            "primary_method": primary,
            **{field: str(int(found[flag_name])) for field, flag_name in ATTR_MAP.items()},
            "computability": suggested_computability(text, found),
            "confidence": "medium",
            "annotator_notes": "MACHINE PREANNOTATION — human must verify/edit every field before use as gold label.",
            "review_status": "NOT_HUMAN_REVIEWED",
        }
        output_rows.append(suggested)
    fieldnames = list(output_rows[0])
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} machine-preannotated rows to {OUTPUT}")


if __name__ == "__main__":
    main()
