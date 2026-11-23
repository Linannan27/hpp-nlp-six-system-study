#!/usr/bin/env python3
"""Create a development label set by adjudicating two independent AI agents.

This output is for pipeline development only and must not be described as a
human-expert gold standard.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from score_annotations import ATTRS, FIELDS


ROOT = Path(__file__).resolve().parents[1]
A_PATH = ROOT / "annotations" / "annotation_A_BLINDED.csv"
B_PATH = ROOT / "annotations" / "annotation_B_BLINDED.csv"
OUT = ROOT / "annotations" / "agent_adjudicated_development_labels.csv"

# Frozen-guide v1.1 decisions for every remaining A/B disagreement.
DECISIONS = {
    ("EXP-02715B04B71B", "attr_external_reference"): ("1", "Multiple-surgery guidelines are an external rule affecting payment."),
    ("EXP-06B700BFE933", "attr_bundle_packaging"): ("1", "Text explicitly states the procedure can be bundled."),
    ("EXP-083C29FD579E", "primary_method"): ("case_rate", "Inpatient condition-level fixed rate includes all outliers."),
    ("EXP-083C29FD579E", "attr_case_rate"): ("1", "Inpatient condition-level fixed rate is case based."),
    ("EXP-1B933BB72F10", "primary_method"): ("case_rate", "Inpatient condition-level fixed rate includes all outliers."),
    ("EXP-1B933BB72F10", "attr_case_rate"): ("1", "Inpatient condition-level fixed rate is case based."),
    ("EXP-2BCA1AF8E875", "primary_method"): ("case_rate", "Inpatient condition-level fixed rate includes all outliers."),
    ("EXP-2BCA1AF8E875", "attr_case_rate"): ("1", "Inpatient condition-level fixed rate is case based."),
    ("EXP-4628F148992D", "attr_bundle_packaging"): ("1", "Text explicitly states the procedure can be bundled."),
    ("EXP-49D39A1AE2B8", "attr_fee_schedule_reference"): ("U", "Allowable amount is named but its source is not identified."),
    ("EXP-6A7EFB151A35", "attr_fee_schedule_reference"): ("1", "OPPS/APC and adjusted APC rate are explicit fee-schedule references."),
    ("EXP-6A7EFB151A35", "attr_outlier_stop_loss"): ("1", "Text explicitly defines an outlier threshold and payment."),
    ("EXP-84E688102EC0", "primary_method"): ("hybrid", "Expression combines fixed ambulance dollar amounts with an APC fee schedule."),
    ("EXP-958CD37BE699", "computability"): ("unclear", "No-claims note contains no payment mechanism to assess."),
    ("EXP-DBA983B935E1", "primary_method"): ("case_rate", "Inpatient condition-level fixed rate includes all outliers."),
    ("EXP-DBA983B935E1", "attr_case_rate"): ("1", "Inpatient condition-level fixed rate is case based."),
    ("EXP-DE0A69737BDA", "primary_method"): ("fee_schedule", "APC fee schedule is primary; percent-of-charge is a lesser-of condition."),
    ("EXP-ED3D8DEF8986", "primary_method"): ("fee_schedule", "Guide defines DRG base-rate references as fee schedule absent case-rate language."),
    ("EXP-F171C01896EC", "primary_method"): ("fee_schedule", "MS-DRG fee schedule is primary; charge percentage is a lesser-of condition."),
    ("EXP-FC9CCF9701B9", "attr_lesser_of"): ("1", "Not-to-exceed wording implements a minimum-of/cap rule."),
}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["sample_id"]: row for row in csv.DictReader(handle)}


def conservative_confidence(a, b):
    rank = {"low": 0, "medium": 1, "high": 2}
    return min((a, b), key=lambda value: rank[value])


def main():
    a, b = read(A_PATH), read(B_PATH)
    if set(a) != set(b):
        raise SystemExit("A/B sample IDs do not match")
    observed_conflicts = {
        (sid, field)
        for sid in a for field in FIELDS
        if a[sid][field] != b[sid][field]
    }
    if observed_conflicts != set(DECISIONS):
        raise SystemExit(
            f"Adjudication table mismatch. Missing={observed_conflicts - set(DECISIONS)}; "
            f"stale={set(DECISIONS) - observed_conflicts}"
        )

    rows = []
    base_fields = [
        "sample_id", "hospital", "occurrence_count", "setting", "billing_class",
        "example_descriptions", "expression_text",
    ]
    for sid in sorted(a):
        output = {field: a[sid][field] for field in base_fields}
        rationales = []
        for field in FIELDS:
            if a[sid][field] == b[sid][field]:
                output[field] = a[sid][field]
            else:
                output[field], rationale = DECISIONS[(sid, field)]
                rationales.append(f"{field}: {rationale}")
        output["confidence"] = conservative_confidence(a[sid]["confidence"], b[sid]["confidence"])
        output["agreement_status"] = "adjudicated" if rationales else "agreed"
        output["adjudication_rationale"] = " | ".join(rationales)
        output["adjudicated_by"] = "root AI agent; development-only, not human expert"
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
