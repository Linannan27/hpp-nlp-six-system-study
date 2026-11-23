#!/usr/bin/env python3
"""Compare reproducible NLP baselines under hospital-level holdout.

Run with the project virtual environment because this module uses
scikit-learn. The primary experimental unit is one unique expression, and an
entire hospital is held out at a time.
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from run_experiment import PATTERNS, classify_literal


ROOT = Path(__file__).resolve().parents[1]
INPUT = Path(os.environ.get(
    "HPP_INPUT",
    ROOT / "annotations" / "agent_adjudicated_development_labels.csv",
))
OUTPUT_PREFIX = os.environ.get("HPP_OUTPUT_PREFIX", "model_comparison_hospital_holdout")
OUT_JSON = ROOT / "results" / f"{OUTPUT_PREFIX}.json"
OUT_CSV = ROOT / "results" / f"{OUTPUT_PREFIX}_predictions.csv"
LABELS = [
    "case_rate",
    "fee_schedule",
    "hybrid",
    "per_diem",
    "percent_of_charge",
    "unclear",
]
THRESHOLDS = [0.40, 0.50, 0.60, 0.70, 0.80, 0.90]


class RuleFeatureTransformer(BaseEstimator, TransformerMixin):
    """Turn the fixed domain patterns into binary model features."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        matrix = [
            [int(bool(pattern.search(text or ""))) for pattern in PATTERNS.values()]
            for text in X
        ]
        return sparse.csr_matrix(np.asarray(matrix, dtype=np.float64))


def models():
    balanced_lr = lambda: LogisticRegression(
        max_iter=3000,
        class_weight="balanced",
        random_state=20261028,
    )
    return {
        "word_tfidf_logistic": Pipeline([
            ("features", TfidfVectorizer(
                lowercase=True, ngram_range=(1, 2), min_df=1,
                sublinear_tf=True, max_features=30000,
            )),
            ("classifier", balanced_lr()),
        ]),
        "char_tfidf_logistic": Pipeline([
            ("features", TfidfVectorizer(
                analyzer="char_wb", lowercase=True, ngram_range=(3, 5),
                min_df=1, sublinear_tf=True, max_features=50000,
            )),
            ("classifier", balanced_lr()),
        ]),
        "char_tfidf_linear_svm": Pipeline([
            ("features", TfidfVectorizer(
                analyzer="char_wb", lowercase=True, ngram_range=(3, 5),
                min_df=1, sublinear_tf=True, max_features=50000,
            )),
            ("classifier", LinearSVC(
                class_weight="balanced", random_state=20261028,
            )),
        ]),
        "hpp_nlp_hybrid_logistic": Pipeline([
            ("features", FeatureUnion([
                ("word", TfidfVectorizer(
                    lowercase=True, ngram_range=(1, 2), min_df=1,
                    sublinear_tf=True, max_features=30000,
                )),
                ("char", TfidfVectorizer(
                    analyzer="char_wb", lowercase=True, ngram_range=(3, 5),
                    min_df=1, sublinear_tf=True, max_features=50000,
                )),
                ("rules", RuleFeatureTransformer()),
            ])),
            ("classifier", balanced_lr()),
        ]),
    }


def metrics(gold, predicted):
    return {
        "n": len(gold),
        "accuracy": accuracy_score(gold, predicted),
        "macro_f1_all_six_classes": f1_score(
            gold, predicted, labels=LABELS, average="macro", zero_division=0
        ),
        "per_class": classification_report(
            gold, predicted, labels=LABELS, output_dict=True, zero_division=0
        ),
    }


def selective_curve(rows):
    result = []
    for threshold in THRESHOLDS:
        covered = [r for r in rows if r["confidence"] >= threshold]
        result.append({
            "threshold": threshold,
            "coverage": len(covered) / len(rows) if rows else 0.0,
            "covered_n": len(covered),
            "accuracy_when_covered": (
                sum(r["gold"] == r["prediction"] for r in covered) / len(covered)
                if covered else None
            ),
            "macro_f1_when_covered": (
                f1_score(
                    [r["gold"] for r in covered],
                    [r["prediction"] for r in covered],
                    labels=LABELS,
                    average="macro",
                    zero_division=0,
                ) if covered else None
            ),
        })
    return result


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))

    hospitals = sorted({r["hospital"] for r in source})
    all_predictions = []
    report_models = {}

    # Fixed literal rules are included as a transparent reference baseline.
    rule_rows = []
    for row in source:
        prediction = classify_literal(row["expression_text"])
        if prediction in {"abstain", "other"}:
            prediction = "unclear"
        item = {
            "sample_id": row["sample_id"],
            "held_out_hospital": row["hospital"],
            "model": "literal_rule_baseline",
            "split_type": "fixed_rule_no_training",
            "gold": row["primary_method"],
            "prediction": prediction,
            "confidence": "",
            "train_labels": "not_applicable",
            "unseen_gold_label": "0",
            "expression_text": row["expression_text"],
        }
        rule_rows.append(item)
        all_predictions.append(item)
    report_models["literal_rule_baseline"] = {
        "pooled": metrics(
            [r["gold"] for r in rule_rows],
            [r["prediction"] for r in rule_rows],
        ),
        "note": "Fixed rules do not train on the held-out data; abstain/other maps to unclear.",
    }

    for model_name, prototype in models().items():
        model_rows = []
        folds = {}
        for held_out in hospitals:
            train = [r for r in source if r["hospital"] != held_out]
            test = [r for r in source if r["hospital"] == held_out]
            train_labels = sorted({r["primary_method"] for r in train})
            unseen_labels = sorted({r["primary_method"] for r in test} - set(train_labels))
            prototype.fit(
                [r["expression_text"] for r in train],
                [r["primary_method"] for r in train],
            )
            predicted = prototype.predict([r["expression_text"] for r in test])
            if hasattr(prototype, "predict_proba"):
                confidence = prototype.predict_proba(
                    [r["expression_text"] for r in test]
                ).max(axis=1)
            else:
                confidence = [None] * len(test)

            fold_rows = []
            for row, pred, conf in zip(test, predicted, confidence):
                item = {
                    "sample_id": row["sample_id"],
                    "held_out_hospital": held_out,
                    "model": model_name,
                    "split_type": "leave_one_hospital_out",
                    "gold": row["primary_method"],
                    "prediction": str(pred),
                    "confidence": "" if conf is None else float(conf),
                    "train_labels": "|".join(train_labels),
                    "unseen_gold_label": str(int(row["primary_method"] in unseen_labels)),
                    "expression_text": row["expression_text"],
                }
                fold_rows.append(item)
                model_rows.append(item)
                all_predictions.append(item)
            folds[held_out] = {
                "train_n": len(train),
                "test_n": len(test),
                "train_labels": train_labels,
                "unseen_test_labels": unseen_labels,
                "metrics": metrics(
                    [r["gold"] for r in fold_rows],
                    [r["prediction"] for r in fold_rows],
                ),
            }

        entry = {
            "folds": folds,
            "pooled": metrics(
                [r["gold"] for r in model_rows],
                [r["prediction"] for r in model_rows],
            ),
        }
        seen_rows = [r for r in model_rows if r["unseen_gold_label"] == "0"]
        entry["pooled_seen_label_subset"] = metrics(
            [r["gold"] for r in seen_rows],
            [r["prediction"] for r in seen_rows],
        )
        probabilistic = [r for r in model_rows if r["confidence"] != ""]
        if probabilistic:
            entry["selective_prediction"] = selective_curve(probabilistic)
        report_models[model_name] = entry

    # Development-only comparison: stratified folds mix hospitals and therefore
    # quantify how much easier the task looks when institution templates leak
    # across train/test. These are not external-validation results.
    texts = [r["expression_text"] for r in source]
    gold = [r["primary_method"] for r in source]
    cv_splits = min(5, min(Counter(gold).values()))
    cv = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=20261028)
    for model_name, prototype in models().items():
        cv_rows = []
        for fold_number, (train_idx, test_idx) in enumerate(cv.split(texts, gold), 1):
            estimator = clone(prototype)
            estimator.fit([texts[i] for i in train_idx], [gold[i] for i in train_idx])
            fold_texts = [texts[i] for i in test_idx]
            predicted = estimator.predict(fold_texts)
            if hasattr(estimator, "predict_proba"):
                confidence = estimator.predict_proba(fold_texts).max(axis=1)
            else:
                confidence = [None] * len(test_idx)
            for i, pred, conf in zip(test_idx, predicted, confidence):
                item = {
                    "sample_id": source[i]["sample_id"],
                    "held_out_hospital": source[i]["hospital"],
                    "model": model_name,
                    "split_type": "stratified_random_expression_cv",
                    "gold": gold[i],
                    "prediction": str(pred),
                    "confidence": "" if conf is None else float(conf),
                    "train_labels": "|".join(sorted(set(gold))),
                    "unseen_gold_label": "0",
                    "expression_text": texts[i],
                }
                cv_rows.append(item)
                all_predictions.append(item)
        report_models[model_name]["development_stratified_random_cv"] = {
            "warning": "Hospitals are mixed across folds; use only to quantify template leakage, not external validity.",
            "pooled": metrics(
                [r["gold"] for r in cv_rows],
                [r["prediction"] for r in cv_rows],
            ),
        }

    # Final transparent cascade: trust an explicit fixed-rule class, and use
    # the learned hybrid model only when the rule cannot determine a class.
    # This policy is specified before looking at fold outcomes and requires no
    # tuning on held-out hospitals.
    cascade_rows = []
    base_rows = [r for r in all_predictions if r["model"] == "hpp_nlp_hybrid_logistic"]
    for row in base_rows:
        rule_prediction = classify_literal(row["expression_text"])
        if rule_prediction in {"abstain", "other"}:
            rule_prediction = "unclear"
        prediction = rule_prediction if rule_prediction != "unclear" else row["prediction"]
        item = {
            **row,
            "model": "hpp_nlp_rule_model_cascade",
            "prediction": prediction,
            "confidence": "",
        }
        cascade_rows.append(item)
        all_predictions.append(item)
    cascade_loho = [r for r in cascade_rows if r["split_type"] == "leave_one_hospital_out"]
    cascade_random = [r for r in cascade_rows if r["split_type"] == "stratified_random_expression_cv"]
    cascade_folds = {}
    for held_out in hospitals:
        fold_rows = [r for r in cascade_loho if r["held_out_hospital"] == held_out]
        cascade_folds[held_out] = {
            "test_n": len(fold_rows),
            "metrics": metrics(
                [r["gold"] for r in fold_rows],
                [r["prediction"] for r in fold_rows],
            ),
        }
    cascade_seen = [r for r in cascade_loho if r["unseen_gold_label"] == "0"]
    report_models["hpp_nlp_rule_model_cascade"] = {
        "policy": "Use fixed literal rule when it returns a substantive class; otherwise use HPP-NLP hybrid logistic prediction.",
        "folds": cascade_folds,
        "pooled": metrics(
            [r["gold"] for r in cascade_loho],
            [r["prediction"] for r in cascade_loho],
        ),
        "pooled_seen_label_subset": metrics(
            [r["gold"] for r in cascade_seen],
            [r["prediction"] for r in cascade_seen],
        ),
        "development_stratified_random_cv": {
            "warning": "Hospitals are mixed across folds; development-only.",
            "pooled": metrics(
                [r["gold"] for r in cascade_random],
                [r["prediction"] for r in cascade_random],
            ),
        },
    }

    report = {
        "design": {
            "unit": "unique hospital-system mechanism template",
            "split": "leave one entire hospital/system out",
            "labels": (
                f"{len(source)} AI-assisted adjudicated labels from {INPUT.name}; "
                + (
                    "all labels were accepted without changes after review by two human experts"
                    if source and all(
                        row.get("human_review_status") == "HUMAN_EXPERT_REVIEWED_ACCEPTED_NO_CHANGES"
                        for row in source
                    )
                    else "human expert review status must be documented separately"
                )
            ),
            "class_set": LABELS,
            "primary_metric": "macro-F1 across a fixed six-class label set",
            "paired_evaluations": [
                f"{cv_splits}-fold stratified random expression CV (development-only)",
                "leave-one-hospital/system-out (primary external design)",
            ],
            "warning": "Some held-out classes are absent from training hospitals; these support failures are reported rather than hidden.",
            "software": "scikit-learn 1.6.1",
        },
        "models": report_models,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_predictions[0]))
        writer.writeheader()
        writer.writerows(all_predictions)
    print(json.dumps({
        name: values["pooled"] for name, values in report_models.items()
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
