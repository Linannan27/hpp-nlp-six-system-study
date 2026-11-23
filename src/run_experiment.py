#!/usr/bin/env python3
"""Run a transparent, rule-based proof of concept on normalized MRF records.

The structured CMS methodology field is treated as a weak reference label. The
rules only inspect algorithm/notes text; they never read the reference label.
Exact duplicate expressions are also collapsed to expose pseudo-replication.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "normalized_payer_records.csv"
RESULTS = ROOT / "results"

LABEL_MAP = {
    "fee schedule": "fee_schedule",
    "case rate": "case_rate",
    "per diem": "per_diem",
    "percent of total billed charges": "percent_of_charge",
    "other": "other",
}

PATTERNS = {
    "fee_schedule": re.compile(r"\bfee\s*schedule\b|\bapc\s+price\b|\bbase\s+rate\b", re.I),
    "case_rate": re.compile(r"\bcase\s+rate\b|\bper\s+case\b", re.I),
    "per_diem": re.compile(r"\bper\s+diem\b|\bdaily\s+rate\b", re.I),
    "percent_of_charge": re.compile(
        r"%\s*(?:of\s+)?(?:total\s+)?(?:billed\s+)?charges?|%BC\b|"
        r"\bpercent(?:age)?\s+of\s+(?:total\s+)?(?:billed\s+)?charges?\b",
        re.I,
    ),
    "outlier_stop_loss": re.compile(r"\boutliers?\b|\bstop[ -]?loss\b", re.I),
    "lesser_of": re.compile(r"\blesser\s+(?:of|than)\b", re.I),
    "bundle_packaging": re.compile(r"\bbundl(?:e|ed|ing)\b|\bpackag(?:e|ed|ing)\b", re.I),
    "external_reference": re.compile(
        r"https?://|\breferenceable\b|\bmedicaid\b|\bmedicare\b|\bpricer\b|"
        r"\bsupplier\s+invoice\b",
        re.I,
    ),
    "length_of_stay": re.compile(r"\blength\s+of\s+stay\b|\bcovered\s+days?\b", re.I),
    "fixed_dollar": re.compile(r"\$\s*(?:\d|NUM)|\(\$\s*(?:\d|NUM)|\bmaximum\s+reimbursement\s+(?:\d|NUM)", re.I),
}

PRIMARY = ("case_rate", "per_diem", "percent_of_charge", "fee_schedule")


def flags(text):
    return {name: bool(pattern.search(text or "")) for name, pattern in PATTERNS.items()}


def classify_literal(text):
    found = flags(text)
    main = [name for name in PRIMARY if found[name]]
    if len(main) > 1:
        return "hybrid"
    if main:
        return main[0]
    if found["external_reference"] or found["lesser_of"] or found["fixed_dollar"]:
        return "other"
    return "abstain"


def classify_contextual(text):
    """Add one compositional rule motivated by case-based outlier language.

    This is a development-corpus heuristic, not a held-out validated model.
    """
    found = flags(text)
    if (found["fee_schedule"] and found["outlier_stop_loss"]
            and re.search(r"\binlier\s+reimbursement\b", text, re.I)):
        return "case_rate"
    return classify_literal(text)


def metrics(rows, weighted=False):
    labels = sorted({r["gold"] for r in rows} | {r["prediction"] for r in rows if r["prediction"] != "abstain"})
    total_weight = sum(r["weight"] if weighted else 1 for r in rows)
    covered = [r for r in rows if r["prediction"] != "abstain"]
    covered_weight = sum(r["weight"] if weighted else 1 for r in covered)
    correct_weight = sum(
        r["weight"] if weighted else 1
        for r in covered if r["prediction"] == r["gold"]
    )
    per_class = {}
    f1s = []
    for label in labels:
        tp = sum((r["weight"] if weighted else 1) for r in rows if r["gold"] == label and r["prediction"] == label)
        fp = sum((r["weight"] if weighted else 1) for r in rows if r["gold"] != label and r["prediction"] == label)
        fn = sum((r["weight"] if weighted else 1) for r in rows if r["gold"] == label and r["prediction"] != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
        if tp + fn:
            f1s.append(f1)
    return {
        "n": total_weight,
        "coverage": covered_weight / total_weight if total_weight else 0.0,
        "accuracy_when_covered": correct_weight / covered_weight if covered_weight else 0.0,
        "macro_f1_with_abstentions_as_errors": sum(f1s) / len(f1s) if f1s else 0.0,
        "per_class": per_class,
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    examples = {}
    all_records = []
    with DATA.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            all_records.append(row)
            if row["nlp_text"] and row["methodology"] in LABEL_MAP:
                key = (row["hospital"], row["nlp_text"], LABEL_MAP[row["methodology"]])
                counts[key] += 1
                examples[key] = row

    unique_rows = []
    for (hospital, text, gold), weight in counts.items():
        literal_prediction = classify_literal(text)
        contextual_prediction = classify_contextual(text)
        unique_rows.append({
            "hospital": hospital,
            "gold": gold,
            "prediction": literal_prediction,
            "contextual_prediction": contextual_prediction,
            "weight": weight,
            "text": text,
            **{f"flag_{k}": int(v) for k, v in flags(text).items()},
        })

    with (RESULTS / "unique_expression_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(unique_rows[0]))
        writer.writeheader()
        writer.writerows(sorted(unique_rows, key=lambda r: (r["hospital"], r["gold"], r["text"])))

    non_other = [r for r in unique_rows if r["gold"] != "other"]
    other_rows = [r for r in unique_rows if r["gold"] == "other"]
    other_subtypes = Counter()
    weighted_other_subtypes = Counter()
    for row in other_rows:
        found = flags(row["text"])
        for name, value in found.items():
            if value:
                other_subtypes[name] += 1
                weighted_other_subtypes[name] += row["weight"]
        main_count = sum(found[name] for name in PRIMARY)
        if main_count > 1:
            other_subtypes["hybrid_primary_mechanisms"] += 1
            weighted_other_subtypes["hybrid_primary_mechanisms"] += row["weight"]

    hospital_record_counts = Counter(r["hospital"] for r in all_records)
    hospital_text_counts = Counter(r["hospital"] for r in all_records if r["nlp_text"])
    hospital_unique_counts = Counter(r["hospital"] for r in unique_rows)
    report = {
        "design": {
            "reference_label": "CMS structured methodology field (weak reference; not human gold standard)",
            "model_input": "algorithm + generic notes + payer-specific notes only",
            "unit_for_primary_evaluation": "unique hospital-expression-methodology tuple",
            "important_exclusion": "CMS synthetic example retained for parser checks but excluded from real-world metrics",
        },
        "real_world_corpus": {
            "payer_records": sum(v for k, v in hospital_record_counts.items() if k != "West Mercy Hospital"),
            "records_with_nlp_text": sum(v for k, v in hospital_text_counts.items() if k != "West Mercy Hospital"),
            "unique_labeled_expressions": sum(v for k, v in hospital_unique_counts.items() if k != "West Mercy Hospital"),
            "by_hospital_records": dict(hospital_record_counts),
            "by_hospital_text_records": dict(hospital_text_counts),
            "by_hospital_unique_expressions": dict(hospital_unique_counts),
        },
        "rule_metrics_real_world_non_other": {
            "literal_keyword_rules": {
                "unique_expression_level": metrics([r for r in non_other if r["hospital"] != "West Mercy Hospital"]),
                "record_weighted": metrics([r for r in non_other if r["hospital"] != "West Mercy Hospital"], weighted=True),
            },
            "contextual_development_rule": {
                "unique_expression_level": metrics([
                    {**r, "prediction": r["contextual_prediction"]}
                    for r in non_other if r["hospital"] != "West Mercy Hospital"
                ]),
                "record_weighted": metrics([
                    {**r, "prediction": r["contextual_prediction"]}
                    for r in non_other if r["hospital"] != "West Mercy Hospital"
                ], weighted=True),
                "warning": "Developed and evaluated on the same corpus; descriptive only, not external validation."
            },
        },
        "other_field_refinement_real_world": {
            "unique_expression_flags": dict(other_subtypes),
            "record_weighted_flags": dict(weighted_other_subtypes),
            "note": "Flags are multi-label and therefore do not sum to the number of expressions or records.",
        },
        "all_unique_expression_confusion": {
            f"{gold} -> {pred}": n
            for (gold, pred), n in Counter((r["gold"], r["prediction"]) for r in unique_rows if r["hospital"] != "West Mercy Hospital").items()
        },
    }
    with (RESULTS / "experiment_results.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
