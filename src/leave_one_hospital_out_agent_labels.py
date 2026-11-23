#!/usr/bin/env python3
"""Hospital holdout using two-agent adjudicated development labels."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from leave_one_hospital_out import CharNgramNB


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "annotations" / "agent_adjudicated_development_labels.csv"
OUT_JSON = ROOT / "results" / "leave_one_hospital_out_agent_labels.json"
OUT_CSV = ROOT / "results" / "leave_one_hospital_out_agent_predictions.csv"


def metric(rows):
    if not rows:
        return {"n": 0, "accuracy": None, "macro_f1": None, "per_class": {}}
    labels = sorted({r["gold"] for r in rows} | {r["prediction"] for r in rows})
    per_class = {}
    f1s = []
    for label in labels:
        support = sum(r["gold"] == label for r in rows)
        if not support:
            continue
        tp = sum(r["gold"] == label and r["prediction"] == label for r in rows)
        fp = sum(r["gold"] != label and r["prediction"] == label for r in rows)
        fn = sum(r["gold"] == label and r["prediction"] != label for r in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
        f1s.append(f1)
    return {
        "n": len(rows),
        "accuracy": sum(r["gold"] == r["prediction"] for r in rows) / len(rows),
        "macro_f1": sum(f1s) / len(f1s),
        "per_class": per_class,
    }


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    hospitals = sorted({r["hospital"] for r in source})
    predictions = []
    folds = {}
    for held_out in hospitals:
        train = [
            {"gold": r["primary_method"], "text": r["expression_text"]}
            for r in source if r["hospital"] != held_out
        ]
        test_source = [r for r in source if r["hospital"] == held_out]
        model = CharNgramNB(alpha=1.0).fit(train)
        fold_rows = []
        for row in test_source:
            predicted = model.predict(row["expression_text"])
            item = {
                "sample_id": row["sample_id"],
                "held_out_hospital": held_out,
                "gold": row["primary_method"],
                "prediction": predicted,
                "expression_text": row["expression_text"],
            }
            fold_rows.append(item)
            predictions.append(item)
        train_labels = sorted({r["gold"] for r in train})
        test_labels = sorted({r["gold"] for r in fold_rows})
        folds[held_out] = {
            "train_n": len(train),
            "test_n": len(fold_rows),
            "train_labels": train_labels,
            "test_labels": test_labels,
            "unseen_test_labels": sorted(set(test_labels) - set(train_labels)),
            "metrics": metric(fold_rows),
        }
    report = {
        "design": {
            "labels": "two independent AI agents, guide v1.1, root AI adjudication",
            "warning": "Development labels are not human-expert gold standard.",
            "split": "leave one hospital/system out; unique expressions only",
            "model": "character 3-5 gram multinomial naive Bayes",
        },
        "folds": folds,
        "pooled": metric(predictions),
    }
    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
