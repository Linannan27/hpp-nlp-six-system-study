#!/usr/bin/env python3
"""Evaluate whether an expression is directly computable under system holdout."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

from sklearn.base import clone
from sklearn.metrics import accuracy_score, classification_report, f1_score

from compare_models import models


ROOT = Path(__file__).resolve().parents[1]
INPUT = Path(os.environ.get(
    "HPP_INPUT",
    ROOT / "annotations" / "human_expert_reviewed_template_labels.csv",
))
OUTPUT_PREFIX = os.environ.get("HPP_OUTPUT_PREFIX", "final_human_reviewed_computability")
OUT_JSON = ROOT / "results" / f"{OUTPUT_PREFIX}.json"
OUT_CSV = ROOT / "results" / f"{OUTPUT_PREFIX}_predictions.csv"
LABELS = ["direct", "conditional_external", "not_computable", "unclear"]


def metrics(gold, predicted):
    return {
        "n": len(gold),
        "accuracy": accuracy_score(gold, predicted),
        "macro_f1_fixed_four_classes": f1_score(
            gold, predicted, labels=LABELS, average="macro", zero_division=0
        ),
        "per_class": classification_report(
            gold, predicted, labels=LABELS, output_dict=True, zero_division=0
        ),
    }


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    hospitals = sorted({row["hospital"] for row in source})
    majority_rows = []
    model_rows = []
    folds = {}
    for held_out in hospitals:
        train = [row for row in source if row["hospital"] != held_out]
        test = [row for row in source if row["hospital"] == held_out]
        train_counts = Counter(row["computability"] for row in train)
        majority = train_counts.most_common(1)[0][0]
        train_labels = sorted(train_counts)
        unseen = sorted({row["computability"] for row in test} - set(train_labels))

        estimator = clone(models()["hpp_nlp_hybrid_logistic"])
        estimator.set_params(classifier__solver="liblinear", classifier__max_iter=5000)
        estimator.fit(
            [row["expression_text"] for row in train],
            [row["computability"] for row in train],
        )
        predicted = estimator.predict([row["expression_text"] for row in test])
        confidence = estimator.predict_proba(
            [row["expression_text"] for row in test]
        ).max(axis=1)
        fold_rows = []
        for row, pred, conf in zip(test, predicted, confidence):
            base = {
                "sample_id": row["sample_id"],
                "held_out_hospital": held_out,
                "gold": row["computability"],
                "expression_text": row["expression_text"],
            }
            majority_rows.append({**base, "prediction": majority})
            item = {**base, "prediction": str(pred), "confidence": float(conf)}
            model_rows.append(item)
            fold_rows.append(item)
        folds[held_out] = {
            "train_n": len(train),
            "test_n": len(test),
            "train_class_support": dict(train_counts),
            "unseen_test_labels": unseen,
            "metrics": metrics(
                [row["gold"] for row in fold_rows],
                [row["prediction"] for row in fold_rows],
            ),
        }

    report = {
        "design": {
            "unit": "unique hospital-system mechanism template",
            "split": "leave one entire hospital/system out",
            "labels": "AI-assisted adjudicated labels accepted without changes after review by two human experts",
            "fixed_label_set": LABELS,
        },
        "class_support": dict(Counter(row["computability"] for row in source)),
        "training_fold_majority_baseline": metrics(
            [row["gold"] for row in majority_rows],
            [row["prediction"] for row in majority_rows],
        ),
        "hpp_nlp_computability": {
            "folds": folds,
            "pooled": metrics(
                [row["gold"] for row in model_rows],
                [row["prediction"] for row in model_rows],
            ),
        },
    }
    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "sample_id", "held_out_hospital", "gold", "prediction",
            "confidence", "expression_text",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(model_rows)
    print(json.dumps({
        "majority_baseline": report["training_fold_majority_baseline"],
        "hpp_nlp": report["hpp_nlp_computability"]["pooled"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
