#!/usr/bin/env python3
"""Build two independently ordered, blinded annotation sheets."""

from __future__ import annotations

import csv
import hashlib
import random
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "derived" / "normalized_payer_records.csv"
OUT = ROOT / "annotations"

ANNOTATION_FIELDS = [
    "primary_method",
    "attr_fee_schedule_reference",
    "attr_case_rate",
    "attr_per_diem",
    "attr_percent_of_charge",
    "attr_fixed_dollar",
    "attr_outlier_stop_loss",
    "attr_lesser_of",
    "attr_bundle_packaging",
    "attr_external_reference",
    "attr_length_of_stay",
    "computability",
    "confidence",
    "annotator_notes",
]


def sample_id(hospital, text):
    digest = hashlib.sha256(f"{hospital}\0{text}".encode("utf-8")).hexdigest()[:12]
    return f"EXP-{digest.upper()}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    with INPUT.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["hospital"] == "West Mercy Hospital" or not row["nlp_text"]:
                continue
            groups[(row["hospital"], row["nlp_text"])].append(row)

    public_rows = []
    key_rows = []
    for (hospital, text), rows in groups.items():
        sid = sample_id(hospital, text)
        descriptions = []
        for value in (r["description"] for r in rows):
            if value and value not in descriptions:
                descriptions.append(value)
            if len(descriptions) == 3:
                break
        settings = sorted({r["setting"] for r in rows if r["setting"]})
        billing = sorted({r["billing_class"] for r in rows if r["billing_class"]})
        public_rows.append({
            "sample_id": sid,
            "hospital": hospital,
            "occurrence_count": len(rows),
            "setting": "|".join(settings),
            "billing_class": "|".join(billing),
            "example_descriptions": " || ".join(descriptions),
            "expression_text": text,
            **{field: "" for field in ANNOTATION_FIELDS},
        })
        key_rows.append({
            "sample_id": sid,
            "hospital": hospital,
            "occurrence_count": len(rows),
            "structured_methodology_counts": "|".join(
                f"{label or 'missing'}:{count}"
                for label, count in sorted(Counter(r["methodology"] for r in rows).items())
            ),
            "expression_text": text,
        })

    fieldnames = list(public_rows[0])
    by_hospital = defaultdict(list)
    for row in public_rows:
        by_hospital[row["hospital"]].append(row)
    pilot_rows = []
    pilot_rng = random.Random(20261030)
    allocations = {
        "Banner Churchill Community Hospital": 8,
        "Berger Hospital": 8,
        "Martha's Vineyard Hospital": 9,
    }
    for hospital, n in allocations.items():
        candidates = list(by_hospital[hospital])
        pilot_rng.shuffle(candidates)
        pilot_rows.extend(candidates[:n])
    pilot_ids = {row["sample_id"] for row in pilot_rows}

    for annotator, seed in (("A", 20261028), ("B", 20261029)):
        ordered = list(public_rows)
        random.Random(seed).shuffle(ordered)
        path = OUT / f"annotation_{annotator}_BLINDED.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ordered)
        pilot_ordered = [row for row in ordered if row["sample_id"] in pilot_ids]
        with (OUT / f"annotation_{annotator}_PILOT25.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(pilot_ordered)

    with (OUT / "pilot_sample_ids.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "hospital"])
        writer.writeheader()
        writer.writerows(
            {"sample_id": row["sample_id"], "hospital": row["hospital"]}
            for row in sorted(pilot_rows, key=lambda r: (r["hospital"], r["sample_id"]))
        )

    with (OUT / "weak_reference_key_DO_NOT_GIVE_ANNOTATORS.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(key_rows[0]))
        writer.writeheader()
        writer.writerows(sorted(key_rows, key=lambda r: r["sample_id"]))

    print(f"Built {len(public_rows)} unique-expression rows for each annotator in {OUT}")


if __name__ == "__main__":
    main()
