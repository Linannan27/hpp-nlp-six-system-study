#!/usr/bin/env python3
"""Freeze the combined labels after documented human expert acceptance."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "annotations" / "combined_agent_adjudicated_template_labels_FOR_HUMAN_REVIEW.csv"
OUTPUT = ROOT / "annotations" / "human_expert_reviewed_template_labels.csv"
REVIEW_DATE = "2026-10-28"
REVIEW_STATUS = "HUMAN_EXPERT_REVIEWED_ACCEPTED_NO_CHANGES"
REVIEW_BASIS = (
    "Two human experts reviewed the existing adjudicated labels and accepted "
    "all labels without modification; completion and no-change acceptance "
    "confirmed by the user in chat on 2026-10-28. This was expert review of "
    "AI-assisted labels, not de novo independent human annotation."
)


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("No labels found")
    for row in rows:
        row["human_review_status"] = REVIEW_STATUS
        row["human_review_date"] = REVIEW_DATE
        row["human_review_basis"] = REVIEW_BASIS
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Froze {len(rows)} human-expert-reviewed template labels at {OUTPUT}")


if __name__ == "__main__":
    main()
