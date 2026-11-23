#!/usr/bin/env python3
"""Evaluate ten payment attributes with hospital-system holdout."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

from sklearn.base import clone
from sklearn.metrics import precision_recall_fscore_support

from compare_models import models
from run_experiment import flags
from score_annotations import ATTRS


ROOT = Path(__file__).resolve().parents[1]
INPUT = Path(os.environ.get(
    "HPP_INPUT",
    ROOT / "annotations" / "human_expert_reviewed_template_labels.csv",
))
OUTPUT_PREFIX = os.environ.get("HPP_OUTPUT_PREFIX", "final_human_reviewed_multilabel")
OUT_JSON = ROOT / "results" / f"{OUTPUT_PREFIX}.json"
OUT_CSV = ROOT / "results" / f"{OUTPUT_PREFIX}_predictions.csv"

ATTR_TO_FLAG = {
    "attr_fee_schedule_reference": "fee_schedule",
    "attr_case_rate": "case_rate",
    "attr_per_diem": "per_diem",
    "attr_percent_of_charge": "percent_of_charge",
    "attr_fixed_dollar": "fixed_dollar",
    "attr_outlier_stop_loss": "outlier_stop_loss",
    "attr_lesser_of": "lesser_of",
    "attr_bundle_packaging": "bundle_packaging",
    "attr_external_reference": "external_reference",
    "attr_length_of_stay": "length_of_stay",
}


def summarize(rows, prediction_field):
    per_attribute = {}
    all_gold, all_pred = [], []
    for attr in ATTRS:
        selected = [r for r in rows if r["attribute"] == attr]
        gold = [r["gold"] for r in selected]
        pred = [r[prediction_field] for r in selected]
        precision, recall, f1, _ = precision_recall_fscore_support(
            gold, pred, pos_label="1", average="binary", zero_division=0
        )
        per_attribute[attr] = {
            "n_known": len(selected),
            "positive_support": sum(v == "1" for v in gold),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "accuracy": sum(a == b for a, b in zip(gold, pred)) / len(gold),
        }
        all_gold.extend(gold)
        all_pred.extend(pred)
    micro = precision_recall_fscore_support(
        all_gold, all_pred, pos_label="1", average="binary", zero_division=0
    )
    return {
        "known_attribute_cells": len(all_gold),
        "hamming_accuracy": sum(a == b for a, b in zip(all_gold, all_pred)) / len(all_gold),
        "micro_positive_precision": micro[0],
        "micro_positive_recall": micro[1],
        "micro_positive_f1": micro[2],
        "macro_attribute_f1": sum(v["f1"] for v in per_attribute.values()) / len(per_attribute),
        "per_attribute": per_attribute,
    }


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    hospitals = sorted({r["hospital"] for r in source})
    predictions = []
    fold_support = {}
    for held_out in hospitals:
        train_rows = [r for r in source if r["hospital"] != held_out]
        test_rows = [r for r in source if r["hospital"] == held_out]
        fold_support[held_out] = {}
        for attr in ATTRS:
            train = [r for r in train_rows if r[attr] in {"0", "1"}]
            test = [r for r in test_rows if r[attr] in {"0", "1"}]
            train_values = sorted({r[attr] for r in train})
            if len(train_values) == 1:
                model_predictions = [train_values[0]] * len(test)
                model_status = f"constant_{train_values[0]}"
            else:
                estimator = clone(models()["hpp_nlp_hybrid_logistic"])
                estimator.set_params(
                    classifier__solver="liblinear",
                    classifier__max_iter=5000,
                )
                estimator.fit(
                    [r["expression_text"] for r in train],
                    [r[attr] for r in train],
                )
                model_predictions = estimator.predict(
                    [r["expression_text"] for r in test]
                )
                model_status = "fitted"
            fold_support[held_out][attr] = {
                "train_n_known": len(train),
                "train_values": train_values,
                "test_n_known": len(test),
                "model_status": model_status,
            }
            for row, model_prediction in zip(test, model_predictions):
                rule_prediction = str(int(flags(row["expression_text"])[ATTR_TO_FLAG[attr]]))
                predictions.append({
                    "sample_id": row["sample_id"],
                    "held_out_hospital": held_out,
                    "attribute": attr,
                    "gold": row[attr],
                    "rule_prediction": rule_prediction,
                    "hpp_nlp_prediction": str(model_prediction),
                    "expression_text": row["expression_text"],
                })
    report = {
        "design": {
            "unit": "unique hospital-system mechanism template",
            "split": "leave one entire hospital/system out",
            "unknown_labels": "U cells excluded attribute-by-attribute",
            "labels": "AI-assisted adjudicated labels accepted without changes after review by two human experts",
        },
        "class_support": {
            attr: dict(Counter(r[attr] for r in source)) for attr in ATTRS
        },
        "fold_support": fold_support,
        "literal_rule_baseline": summarize(predictions, "rule_prediction"),
        "hpp_nlp_multilabel": summarize(predictions, "hpp_nlp_prediction"),
    }
    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    print(json.dumps({
        "literal_rule_baseline": {k: v for k, v in report["literal_rule_baseline"].items() if k != "per_attribute"},
        "hpp_nlp_multilabel": {k: v for k, v in report["hpp_nlp_multilabel"].items() if k != "per_attribute"},
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
