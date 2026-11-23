#!/usr/bin/env python3
"""Adjudicate expansion A/B labels under frozen guide v1.1."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from score_annotations import FIELDS


ROOT = Path(__file__).resolve().parents[1]
A_PATH = ROOT / "annotations" / "expansion_annotation_A_BLINDED.csv"
B_PATH = ROOT / "annotations" / "expansion_annotation_B_BLINDED.csv"
OUT = ROOT / "annotations" / "expansion_agent_adjudicated_labels_FOR_HUMAN_REVIEW.csv"


PRIMARY_DECISIONS = {
    "EXP-0560834B0B61": ("fee_schedule", "ASG rate is primary; billed-charge limit is a cap, not a second primary method."),
    "EXP-16050E718BF3": ("case_rate", "The stated payment unit is an inclusive episode of care."),
    "EXP-28A2BAA406D0": ("fee_schedule", "ASG rate is primary; billed-charge limit is a cap."),
    "EXP-2AB07139B772": ("case_rate", "DRG and obstetric case rates are case-based; stop-loss is secondary."),
    "EXP-35B4E5B71034": ("case_rate", "Explicit case rate remains primary; billed-charge limit is a cap."),
    "EXP-3C37D92A7EE5": ("case_rate", "Bariatric case-rate/DRG language identifies a case-based unit."),
    "EXP-4898CD2031DB": ("fee_schedule", "ASG rate is primary; billed-charge limit is a cap."),
    "EXP-897605E7AAE1": ("case_rate", "DRG/BMT case rates are case-based; stop-loss is secondary."),
    "EXP-BA1EC5EE44FA": ("case_rate", "Explicit case rate remains primary; billed-charge limit is a cap."),
    "EXP-E7618BEDE0D9": ("fee_schedule", "ASG rate is primary; billed-charge limit is a cap."),
}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["sample_id"]: row for row in csv.DictReader(handle)}


def decide(sid, field, a_value, b_value):
    if field == "primary_method":
        return PRIMARY_DECISIONS[sid]
    if field == "attr_bundle_packaging":
        return "0", "Guide requires explicit bundle/packaged language; case/episode structure alone is insufficient."
    if field == "computability":
        if sid == "EXP-F815D01DF2B9":
            return "conditional_external", "Text is an example using average billed charges; actual claim inputs are still required."
        return "not_computable", "MSR reduction may apply but its trigger/formula is absent, so final payment is not unique."
    if field == "attr_fixed_dollar":
        return "0", "Displayed dollars are charge-derived examples, not an independent fixed contractual amount/cap."
    if field == "attr_outlier_stop_loss":
        return "0", "Maximum reimbursement is a cap; no outlier or stop-loss mechanism is stated."
    if field == "attr_percent_of_charge":
        return "1", "Billed charges explicitly determine the payment cap."
    if field == "attr_lesser_of":
        return "1", "Maximum reimbursement implements a lower-of percentage amount and cap."
    if field == "attr_length_of_stay":
        return "0", "Observation per hour is not inpatient length-of-stay dependence."
    raise KeyError((sid, field, a_value, b_value))


def conservative_confidence(a, b):
    rank = {"low": 0, "medium": 1, "high": 2}
    return min((a, b), key=lambda value: rank[value])


def main():
    a, b = read(A_PATH), read(B_PATH)
    if set(a) != set(b):
        raise SystemExit("A/B sample IDs do not match")
    rows = []
    for sid in sorted(a):
        base_fields = [
            "sample_id", "hospital", "occurrence_count", "setting", "billing_class",
            "example_descriptions", "normalized_template", "expression_text",
        ]
        output = {field: a[sid][field] for field in base_fields}
        rationales = []
        for field in FIELDS:
            av, bv = a[sid][field].strip(), b[sid][field].strip()
            if av == bv:
                output[field] = av
            else:
                output[field], rationale = decide(sid, field, av, bv)
                rationales.append(f"{field}: {rationale}")
        output["confidence"] = conservative_confidence(a[sid]["confidence"], b[sid]["confidence"])
        output["agreement_status"] = "adjudicated" if rationales else "agreed"
        output["adjudication_rationale"] = " | ".join(rationales)
        output["adjudicated_by"] = "root AI agent; requires subsequent human expert review"
        output["human_review_status"] = "PENDING"
        for field in FIELDS:
            output[f"A_{field}"] = a[sid][field]
            output[f"B_{field}"] = b[sid][field]
        rows.append(output)
    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")
    print("Primary distribution:", dict(Counter(r["primary_method"] for r in rows)))
    print("Adjudicated rows:", sum(r["agreement_status"] == "adjudicated" for r in rows))


if __name__ == "__main__":
    main()
