#!/usr/bin/env python3
"""Validate two completed annotation sheets and calculate agreement."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


PRIMARY = {
    "fee_schedule", "case_rate", "per_diem", "percent_of_charge",
    "hybrid", "other_clear", "unclear",
}
BINARY = {"0", "1", "U"}
COMPUTABILITY = {"direct", "conditional_external", "not_computable", "unclear"}
CONFIDENCE = {"high", "medium", "low"}
ATTRS = [
    "attr_fee_schedule_reference", "attr_case_rate", "attr_per_diem",
    "attr_percent_of_charge", "attr_fixed_dollar", "attr_outlier_stop_loss",
    "attr_lesser_of", "attr_bundle_packaging", "attr_external_reference",
    "attr_length_of_stay",
]
FIELDS = ["primary_method", *ATTRS, "computability"]


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["sample_id"]: row for row in rows}


def kappa(a_values, b_values):
    n = len(a_values)
    if not n:
        return None
    observed = sum(a == b for a, b in zip(a_values, b_values)) / n
    a_counts, b_counts = Counter(a_values), Counter(b_values)
    labels = set(a_counts) | set(b_counts)
    expected = sum((a_counts[x] / n) * (b_counts[x] / n) for x in labels)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def validate(row, label):
    errors = []
    if row.get("primary_method", "").strip() not in PRIMARY:
        errors.append(f"{label}: invalid/blank primary_method")
    for field in ATTRS:
        if row.get(field, "").strip() not in BINARY:
            errors.append(f"{label}: invalid/blank {field}")
    if row.get("computability", "").strip() not in COMPUTABILITY:
        errors.append(f"{label}: invalid/blank computability")
    if row.get("confidence", "").strip() not in CONFIDENCE:
        errors.append(f"{label}: invalid/blank confidence")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotator_a", type=Path)
    parser.add_argument("annotator_b", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("annotation_scoring"))
    args = parser.parse_args()

    a, b = read_rows(args.annotator_a), read_rows(args.annotator_b)
    if set(a) != set(b):
        missing_a = sorted(set(b) - set(a))
        missing_b = sorted(set(a) - set(b))
        raise SystemExit(f"Sample-ID mismatch. Missing A={missing_a}; missing B={missing_b}")

    validation_errors = []
    for sid in sorted(a):
        validation_errors.extend(validate(a[sid], f"A/{sid}"))
        validation_errors.extend(validate(b[sid], f"B/{sid}"))
    if validation_errors:
        preview = "\n".join(validation_errors[:30])
        raise SystemExit(f"Complete/fix annotations before scoring ({len(validation_errors)} errors):\n{preview}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"n": len(a), "fields": {}}
    conflicts = []
    for field in FIELDS:
        av = [a[sid][field].strip() for sid in sorted(a)]
        bv = [b[sid][field].strip() for sid in sorted(a)]
        agreement = sum(x == y for x, y in zip(av, bv)) / len(av)
        report["fields"][field] = {"raw_agreement": agreement, "cohen_kappa": kappa(av, bv)}

    for sid in sorted(a):
        differing = [field for field in FIELDS if a[sid][field].strip() != b[sid][field].strip()]
        if differing:
            conflicts.append({
                "sample_id": sid,
                "hospital": a[sid]["hospital"],
                "expression_text": a[sid]["expression_text"],
                "differing_fields": "|".join(differing),
                **{f"A_{field}": a[sid][field] for field in FIELDS},
                **{f"B_{field}": b[sid][field] for field in FIELDS},
                "adjudicated_primary_method": "",
                "adjudication_notes": "",
            })

    kappas = [v["cohen_kappa"] for v in report["fields"].values() if v["cohen_kappa"] is not None]
    report["macro_mean_kappa"] = sum(kappas) / len(kappas) if kappas else None
    report["conflict_rows"] = len(conflicts)
    with (args.output_dir / "agreement_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    if conflicts:
        with (args.output_dir / "adjudication_conflicts.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(conflicts[0]))
            writer.writeheader()
            writer.writerows(conflicts)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
