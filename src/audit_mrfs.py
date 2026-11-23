#!/usr/bin/env python3
"""Normalize selected CMS v3.0 hospital MRFs and summarize usable NLP fields."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def emit_record(hospital, source_format, description, setting, billing_class,
                payer_name, plan_name, methodology, dollar, percentage,
                algorithm, generic_notes, payer_notes):
    text_parts = [clean(algorithm), clean(generic_notes), clean(payer_notes)]
    return {
        "hospital": hospital,
        "source_format": source_format,
        "description": clean(description),
        "setting": clean(setting),
        "billing_class": clean(billing_class),
        "payer_name": clean(payer_name),
        "plan_name": clean(plan_name),
        "methodology": clean(methodology).lower(),
        "dollar": clean(dollar),
        "percentage": clean(percentage),
        "algorithm": clean(algorithm),
        "generic_notes": clean(generic_notes),
        "payer_notes": clean(payer_notes),
        "nlp_text": " | ".join(part for part in text_parts if part),
    }


def parse_csv(path):
    records = []
    # Some nominally UTF-8 hospital files contain isolated Windows-1252 bytes.
    # Replacement preserves row structure while making the anomaly explicit.
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        meta_headers = next(csv.reader(handle))
        meta_values = next(csv.reader(handle))
        metadata = dict(zip(meta_headers, meta_values))
        reader = csv.DictReader(handle)
        hospital = metadata.get("hospital_name", path.stem)
        for row in reader:
            if not clean(row.get("payer_name")) and not clean(row.get("standard_charge|methodology")):
                continue
            records.append(emit_record(
                hospital=hospital,
                source_format="csv",
                description=row.get("description"),
                setting=row.get("setting"),
                billing_class=row.get("billing_class"),
                payer_name=row.get("payer_name"),
                plan_name=row.get("plan_name"),
                methodology=row.get("standard_charge|methodology"),
                dollar=row.get("standard_charge|negotiated_dollar"),
                percentage=row.get("standard_charge|negotiated_percentage"),
                algorithm=row.get("standard_charge|negotiated_algorithm"),
                generic_notes=row.get("additional_generic_notes"),
                payer_notes=row.get("additional_payer_specific_notes"),
            ))
    return metadata, records


def parse_json(path):
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    hospital = payload.get("hospital_name", path.stem)
    records = []
    for service in payload.get("standard_charge_information", []):
        for charge in service.get("standard_charges", []):
            generic_notes = charge.get("additional_generic_notes")
            for payer in charge.get("payers_information", []):
                records.append(emit_record(
                    hospital=hospital,
                    source_format="json",
                    description=service.get("description"),
                    setting=charge.get("setting"),
                    billing_class=charge.get("billing_class"),
                    payer_name=payer.get("payer_name"),
                    plan_name=payer.get("plan_name"),
                    methodology=payer.get("methodology"),
                    dollar=payer.get("standard_charge_dollar"),
                    percentage=payer.get("standard_charge_percentage"),
                    algorithm=payer.get("standard_charge_algorithm"),
                    generic_notes=generic_notes,
                    payer_notes=payer.get("additional_payer_specific_notes"),
                ))
    metadata = {
        "hospital_name": hospital,
        "last_updated_on": payload.get("last_updated_on", ""),
        "version": payload.get("version", ""),
    }
    return metadata, records


def summarize(records):
    by_hospital = {}
    for hospital in sorted({r["hospital"] for r in records}):
        subset = [r for r in records if r["hospital"] == hospital]
        by_hospital[hospital] = {
            "payer_records": len(subset),
            "methodology_counts": dict(Counter(r["methodology"] or "missing" for r in subset)),
            "nonempty_algorithm": sum(bool(r["algorithm"]) for r in subset),
            "nonempty_generic_notes": sum(bool(r["generic_notes"]) for r in subset),
            "nonempty_payer_notes": sum(bool(r["payer_notes"]) for r in subset),
            "nonempty_nlp_text": sum(bool(r["nlp_text"]) for r in subset),
            "unique_nlp_text": len({r["nlp_text"] for r in subset if r["nlp_text"]}),
        }
    return {
        "total_payer_records": len(records),
        "overall_methodology_counts": dict(Counter(r["methodology"] or "missing" for r in records)),
        "by_hospital": by_hospital,
    }


def main():
    inputs = [
        (RAW / "cms_v3_example.json", parse_json),
        (RAW / "ohiohealth_berger.json", parse_json),
        (RAW / "banner_churchill.csv", parse_csv),
        (RAW / "042104691_Marthas-Vineyard-Hospital_StandardCharges.csv", parse_csv),
    ]
    DERIVED.mkdir(parents=True, exist_ok=True)
    all_records = []
    metadata = []
    for path, parser in inputs:
        meta, records = parser(path)
        meta["local_file"] = path.name
        meta["payer_records_extracted"] = len(records)
        metadata.append(meta)
        all_records.extend(records)

    fieldnames = list(all_records[0])
    with (DERIVED / "normalized_payer_records.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    report = {"sources": metadata, **summarize(all_records)}
    with (DERIVED / "field_audit.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
