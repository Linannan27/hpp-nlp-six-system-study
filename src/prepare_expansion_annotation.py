#!/usr/bin/env python3
"""Stream new hospital systems into one non-destructive annotation packet."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_mrfs import clean, parse_json
from build_annotation_packet import ANNOTATION_FIELDS, sample_id


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INPUTS = [
    (RAW / "orlando_regional_medical_center.json", "json"),
    (RAW / "stanford_tri_valley.json", "json"),
    (RAW / "590872594_south-miami-hospital_standardcharges.csv", "csv"),
]
OUT_ANNOTATION = ROOT / "annotations" / "expansion_human_review.csv"
OUT_A = ROOT / "annotations" / "expansion_annotation_A_BLINDED.csv"
OUT_B = ROOT / "annotations" / "expansion_annotation_B_BLINDED.csv"
OUT_KEY = ROOT / "annotations" / "expansion_weak_reference_DO_NOT_GIVE_ANNOTATORS.csv"
OUT_AUDIT = ROOT / "data" / "derived" / "expansion_field_audit.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fresh_stats():
    return {
        "payer_records": 0,
        "methodology_counts": Counter(),
        "nonempty_algorithm": 0,
        "nonempty_generic_notes": 0,
        "nonempty_payer_notes": 0,
        "nonempty_nlp_text": 0,
        "unique_mechanism_templates": 0,
    }


def canonical_template(text):
    """Collapse code/amount substitutions while preserving payment semantics."""
    value = clean(text)
    value = re.sub(r"https?://\S+", " URL ", value, flags=re.I)
    value = re.sub(r"\bRev(?:enue)?\s+[A-Z0-9.-]+", "Rev CODE", value, flags=re.I)
    value = re.sub(r"\bProc(?:edure)?\s+[A-Z0-9.-]+", "Proc CODE", value, flags=re.I)
    value = re.sub(r"\bMod(?:ifier)?\s+[A-Z0-9.-]+", "Mod CODE", value, flags=re.I)
    value = re.sub(r"\$\s*[0-9][0-9,]*(?:\.\d+)?", "$NUM", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\s*%", "NUM%", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def add_group(groups, hospital, text, row):
    if not text:
        return
    template = canonical_template(text)
    group = groups[(hospital, template)]
    group["count"] += 1
    if not group["representative_text"]:
        group["representative_text"] = text
    group["methodologies"][clean(row.get("methodology")).lower()] += 1
    for field, target in (("description", "descriptions"), ("setting", "settings"),
                          ("billing_class", "billing_classes")):
        value = clean(row.get(field))
        if value and value not in group[target]:
            group[target].append(value)


def process_json(path, groups, by_hospital):
    metadata, records = parse_json(path)
    hospital = metadata["hospital_name"]
    stats = by_hospital[hospital]
    for row in records:
        stats["payer_records"] += 1
        stats["methodology_counts"][row["methodology"] or "missing"] += 1
        stats["nonempty_algorithm"] += int(bool(row["algorithm"]))
        stats["nonempty_generic_notes"] += int(bool(row["generic_notes"]))
        stats["nonempty_payer_notes"] += int(bool(row["payer_notes"]))
        stats["nonempty_nlp_text"] += int(bool(row["nlp_text"]))
        add_group(groups, hospital, row["nlp_text"], row)
    return {
        **metadata,
        "source_format": "json",
        "local_file": path.name,
        "file_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "payer_records_extracted": len(records),
    }


def process_tall_csv(path, groups, by_hospital):
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        meta_headers = next(csv.reader(handle))
        meta_values = next(csv.reader(handle))
        metadata = dict(zip(meta_headers, meta_values))
        hospital = metadata.get("hospital_name", path.stem)
        stats = by_hospital[hospital]
        reader = csv.DictReader(handle)
        for raw in reader:
            if not clean(raw.get("payer_name")) and not clean(raw.get("standard_charge|methodology")):
                continue
            methodology = clean(raw.get("standard_charge|methodology")).lower()
            algorithm = clean(raw.get("standard_charge|negotiated_algorithm"))
            generic_notes = clean(raw.get("additional_generic_notes"))
            payer_notes = clean(raw.get("additional_payer_specific_notes"))
            text = " | ".join(v for v in (algorithm, generic_notes, payer_notes) if v)
            row = {
                "description": raw.get("description"),
                "setting": raw.get("setting"),
                "billing_class": raw.get("billing_class"),
                "methodology": methodology,
            }
            stats["payer_records"] += 1
            stats["methodology_counts"][methodology or "missing"] += 1
            stats["nonempty_algorithm"] += int(bool(algorithm))
            stats["nonempty_generic_notes"] += int(bool(generic_notes))
            stats["nonempty_payer_notes"] += int(bool(payer_notes))
            stats["nonempty_nlp_text"] += int(bool(text))
            add_group(groups, hospital, text, row)
    return {
        "hospital_name": hospital,
        "last_updated_on": metadata.get("last_updated_on", ""),
        "version": metadata.get("version", ""),
        "source_format": "csv",
        "local_file": path.name,
        "file_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "payer_records_extracted": stats["payer_records"],
    }


def main():
    groups = defaultdict(lambda: {
        "count": 0,
        "representative_text": "",
        "methodologies": Counter(),
        "descriptions": [],
        "settings": [],
        "billing_classes": [],
    })
    by_hospital = defaultdict(fresh_stats)
    sources = []
    for path, source_format in INPUTS:
        if source_format == "json":
            sources.append(process_json(path, groups, by_hospital))
        else:
            sources.append(process_tall_csv(path, groups, by_hospital))

    annotation_rows = []
    key_rows = []
    for (hospital, template), group in sorted(groups.items()):
        text = group["representative_text"]
        sid = sample_id(hospital, template)
        annotation_rows.append({
            "sample_id": sid,
            "hospital": hospital,
            "occurrence_count": group["count"],
            "setting": "|".join(sorted(group["settings"])),
            "billing_class": "|".join(sorted(group["billing_classes"])),
            "example_descriptions": " || ".join(group["descriptions"][:3]),
            "normalized_template": template,
            "expression_text": text,
            **{field: "" for field in ANNOTATION_FIELDS},
        })
        key_rows.append({
            "sample_id": sid,
            "hospital": hospital,
            "occurrence_count": group["count"],
            "structured_methodology_counts": "|".join(
                f"{label or 'missing'}:{count}"
                for label, count in sorted(group["methodologies"].items())
            ),
            "normalized_template": template,
            "expression_text": text,
        })

    OUT_ANNOTATION.parent.mkdir(parents=True, exist_ok=True)
    with OUT_ANNOTATION.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(annotation_rows[0]))
        writer.writeheader()
        writer.writerows(annotation_rows)
    for path, seed in ((OUT_A, 20261101), (OUT_B, 20261102)):
        randomized = list(annotation_rows)
        random.Random(seed).shuffle(randomized)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(randomized[0]))
            writer.writeheader()
            writer.writerows(randomized)
    with OUT_KEY.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(key_rows[0]))
        writer.writeheader()
        writer.writerows(key_rows)

    overall_methodology = Counter()
    for hospital, stats in by_hospital.items():
        stats["unique_mechanism_templates"] = sum(1 for h, _ in groups if h == hospital)
        overall_methodology.update(stats["methodology_counts"])
    serializable_hospitals = {
        hospital: {**stats, "methodology_counts": dict(stats["methodology_counts"])}
        for hospital, stats in sorted(by_hospital.items())
    }
    report = {
        "sources": sources,
        "total_payer_records": sum(s["payer_records"] for s in by_hospital.values()),
        "overall_methodology_counts": dict(overall_methodology),
        "by_hospital": serializable_hospitals,
        "annotation_packet": {
            "hospital_systems": len(by_hospital),
            "unique_expression_rows": len(annotation_rows),
            "path": str(OUT_ANNOTATION.relative_to(ROOT)),
            "annotator_A_path": str(OUT_A.relative_to(ROOT)),
            "annotator_B_path": str(OUT_B.relative_to(ROOT)),
            "weak_reference_path": str(OUT_KEY.relative_to(ROOT)),
        },
    }
    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with OUT_AUDIT.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
