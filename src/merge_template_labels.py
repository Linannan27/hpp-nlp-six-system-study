#!/usr/bin/env python3
"""Merge original and expansion adjudications at mechanism-template level."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from build_annotation_packet import sample_id
from prepare_expansion_annotation import canonical_template
from score_annotations import FIELDS


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "annotations" / "agent_adjudicated_development_labels.csv"
EXPANSION = ROOT / "annotations" / "expansion_agent_adjudicated_labels_FOR_HUMAN_REVIEW.csv"
OUT = ROOT / "annotations" / "combined_agent_adjudicated_template_labels_FOR_HUMAN_REVIEW.csv"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    groups = defaultdict(list)
    for row in read(ORIGINAL):
        template = canonical_template(row["expression_text"])
        groups[(row["hospital"], template)].append({**row, "source_set": "original_178"})
    for row in read(EXPANSION):
        template = row["normalized_template"]
        groups[(row["hospital"], template)].append({**row, "source_set": "expansion_100"})

    output_rows = []
    for (hospital, template), rows in sorted(groups.items()):
        for field in FIELDS:
            values = {row[field] for row in rows}
            if len(values) != 1:
                raise SystemExit(f"Conflicting {field} for {hospital}/{template}: {values}")
        output_rows.append({
            "sample_id": sample_id(hospital, template),
            "hospital": hospital,
            "source_set": "|".join(sorted({r["source_set"] for r in rows})),
            "source_sample_ids": "|".join(sorted(r["sample_id"] for r in rows)),
            "occurrence_count": sum(int(r.get("occurrence_count") or 0) for r in rows),
            "expression_text": template,
            "representative_text": rows[0]["expression_text"],
            **{field: rows[0][field] for field in FIELDS},
            "confidence": min(
                (r["confidence"] for r in rows),
                key=lambda value: {"low": 0, "medium": 1, "high": 2}[value],
            ),
            "human_review_status": (
                "PENDING_EXPANSION_REVIEW" if any(r["source_set"] == "expansion_100" for r in rows)
                else "USER_REPORTED_REVIEWED_SCOPE_UNDOCUMENTED"
            ),
        })

    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} template rows to {OUT}")
    print("By hospital:", dict(Counter(r["hospital"] for r in output_rows)))
    print("Primary:", dict(Counter(r["primary_method"] for r in output_rows)))


if __name__ == "__main__":
    main()
