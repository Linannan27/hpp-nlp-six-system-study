#!/usr/bin/env python3
"""Hospital-level holdout evaluation on unique expressions and weak labels."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from run_experiment import classify_contextual, classify_literal


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "results" / "unique_expression_predictions.csv"
OUT_JSON = ROOT / "results" / "leave_one_hospital_out.json"
OUT_CSV = ROOT / "results" / "leave_one_hospital_out_predictions.csv"
LABELS = ("case_rate", "fee_schedule", "other", "per_diem", "percent_of_charge")


def normalize(text):
    text = text.lower()
    text = re.sub(r"https?://\S+", " URL ", text)
    text = re.sub(r"\$?\d[\d,.]*%?", " NUM ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def char_ngrams(text, lower=3, upper=5):
    normalized = f"  {normalize(text)}  "
    counts = Counter()
    for n in range(lower, upper + 1):
        counts.update(normalized[i:i+n] for i in range(len(normalized) - n + 1))
    return counts


class CharNgramNB:
    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, rows):
        self.doc_counts = Counter(r["gold"] for r in rows)
        self.labels = sorted(self.doc_counts)
        self.feature_counts = defaultdict(Counter)
        self.class_totals = Counter()
        self.vocab = set()
        for row in rows:
            feats = char_ngrams(row["text"])
            self.feature_counts[row["gold"]].update(feats)
            self.class_totals[row["gold"]] += sum(feats.values())
            self.vocab.update(feats)
        self.n_docs = len(rows)
        return self

    def predict(self, text):
        feats = char_ngrams(text)
        vocab_size = max(len(self.vocab), 1)
        scores = {}
        # A supervised model cannot predict a class absent from its training set.
        for label in self.labels:
            prior = (self.doc_counts[label] + self.alpha) / (
                self.n_docs + self.alpha * len(self.labels)
            )
            denom = self.class_totals[label] + self.alpha * vocab_size
            score = math.log(prior)
            counts = self.feature_counts[label]
            for feature, n in feats.items():
                score += n * math.log((counts[feature] + self.alpha) / denom)
            scores[label] = score
        return max(scores, key=scores.get)


def rule_to_reference(prediction):
    if prediction == "hybrid":
        return "other"
    return prediction


def metric(rows, pred_field, allowed_labels=None):
    selected = rows if allowed_labels is None else [r for r in rows if r["gold"] in allowed_labels]
    if not selected:
        return {"n": 0, "coverage": None, "accuracy": None, "macro_f1": None}
    covered = [r for r in selected if r[pred_field] != "abstain"]
    accuracy = sum(r[pred_field] == r["gold"] for r in selected) / len(selected)
    f1s = []
    per_class = {}
    for label in LABELS:
        support = sum(r["gold"] == label for r in selected)
        if not support:
            continue
        tp = sum(r["gold"] == label and r[pred_field] == label for r in selected)
        fp = sum(r["gold"] != label and r[pred_field] == label for r in selected)
        fn = sum(r["gold"] == label and r[pred_field] != label for r in selected)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s.append(f1)
        per_class[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
    return {
        "n": len(selected),
        "coverage": len(covered) / len(selected),
        "accuracy": accuracy,
        "macro_f1": sum(f1s) / len(f1s),
        "per_class": per_class,
    }


def main():
    with INPUT.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["hospital"] != "West Mercy Hospital"]

    hospitals = sorted({r["hospital"] for r in rows})
    prediction_rows = []
    folds = {}
    for held_out in hospitals:
        train = [r for r in rows if r["hospital"] != held_out]
        test = [{**r} for r in rows if r["hospital"] == held_out]
        model = CharNgramNB(alpha=1.0).fit(train)
        train_labels = sorted({r["gold"] for r in train})
        test_labels = sorted({r["gold"] for r in test})
        for row in test:
            row["held_out_hospital"] = held_out
            row["literal_rule"] = rule_to_reference(classify_literal(row["text"]))
            row["contextual_rule"] = rule_to_reference(classify_contextual(row["text"]))
            row["char_ngram_nb"] = model.predict(row["text"])
            prediction_rows.append(row)

        shared = set(train_labels)
        folds[held_out] = {
            "train_n": len(train),
            "test_n": len(test),
            "train_labels": train_labels,
            "test_labels": test_labels,
            "unseen_test_labels": sorted(set(test_labels) - shared),
            "literal_rule": metric(test, "literal_rule"),
            "contextual_rule_posthoc_not_validated": metric(test, "contextual_rule"),
            "char_ngram_nb": metric(test, "char_ngram_nb"),
            "shared_label_subset": {
                "labels": sorted(shared),
                "literal_rule": metric(test, "literal_rule", shared),
                "contextual_rule": metric(test, "contextual_rule", shared),
                "char_ngram_nb": metric(test, "char_ngram_nb", shared),
            },
        }

    report = {
        "design": {
            "unit": "unique hospital-expression-methodology tuple",
            "reference": "structured CMS methodology (weak label)",
            "split": "leave one entire hospital/system out",
            "models": ["literal fixed rules", "fixed contextual rules", "character 3-5 gram multinomial naive Bayes"],
            "warning": "Three hospitals have severe label-support imbalance; unseen held-out labels are reported explicitly.",
        },
        "folds": folds,
        "pooled": {
            "literal_rule": metric(prediction_rows, "literal_rule"),
            "contextual_rule": metric(prediction_rows, "contextual_rule"),
            "char_ngram_nb": metric(prediction_rows, "char_ngram_nb"),
        },
    }
    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    fieldnames = list(prediction_rows[0])
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prediction_rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
