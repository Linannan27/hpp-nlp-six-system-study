#!/usr/bin/env python3
"""Build a compact human-review queue from the expansion adjudication sheet."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "annotations" / "expansion_agent_adjudicated_labels_FOR_HUMAN_REVIEW.csv"
OUTPUT = ROOT / "annotations" / "EXPANSION_HUMAN_REVIEW_PRIORITY.csv"
ATTRS = [
    "attr_fee_schedule_reference", "attr_case_rate", "attr_per_diem",
    "attr_percent_of_charge", "attr_fixed_dollar", "attr_outlier_stop_loss",
    "attr_lesser_of", "attr_bundle_packaging", "attr_external_reference",
    "attr_length_of_stay",
]


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    priority = []
    for row in rows:
        if row["agreement_status"] != "agreed" or row["confidence"] != "high":
            reasons = []
            if row["agreement_status"] != "agreed":
                reasons.append("A/B conflict adjudicated by root AI")
            if row["confidence"] in {"medium", "low"}:
                reasons.append(f"confidence={row['confidence']}")
            item = {
                "review_priority": "1" if row["agreement_status"] != "agreed" else "2",
                "sample_id": row["sample_id"],
                "hospital": row["hospital"],
                "expression_text": row["expression_text"],
                "proposed_primary_method": row["primary_method"],
                "proposed_computability": row["computability"],
                "A_primary_method": row["A_primary_method"],
                "B_primary_method": row["B_primary_method"],
                "A_computability": row["A_computability"],
                "B_computability": row["B_computability"],
                "adjudication_rationale": row["adjudication_rationale"],
                "review_reason": "; ".join(reasons),
                "reviewed_primary_method": "",
                "reviewed_computability": "",
                "human_notes": "",
                "reviewer": "",
                "review_date": "",
            }
            for attr in ATTRS:
                item[f"proposed_{attr}"] = row[attr]
                item[f"reviewed_{attr}"] = ""
            priority.append(item)
    priority.sort(key=lambda row: (row["review_priority"], row["hospital"], row["sample_id"]))
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(priority[0]))
        writer.writeheader()
        writer.writerows(priority)
    print(f"wrote {len(priority)} priority review rows to {OUTPUT}")


if __name__ == "__main__":
    main()
