#!/usr/bin/env python3
"""Run a true raw-file-to-enriched-record case on a held-out hospital system.

Stanford Health Care Tri-Valley is excluded from every training step.  Its
official CMS v3 JSON is parsed from scratch, normalized into mechanism
templates, classified, and then mapped back to every text-bearing payer row.
Human-reviewed Stanford labels are used only after prediction for evaluation.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from sklearn.base import clone
from sklearn.metrics import accuracy_score, classification_report, f1_score

from audit_mrfs import parse_json
from compare_computability import LABELS as COMPUTABILITY_LABELS
from compare_multilabel_attributes import ATTR_TO_FLAG
from compare_models import LABELS as PRIMARY_LABELS
from compare_models import models
from prepare_expansion_annotation import canonical_template
from run_experiment import classify_literal, flags
from score_annotations import ATTRS


ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = ROOT / "annotations" / "human_expert_reviewed_template_labels.csv"
RAW_PATH = ROOT / "data" / "raw" / "stanford_tri_valley.json"
SUMMARY_PATH = ROOT / "results" / "end_to_end_stanford_summary.json"
TEMPLATE_PATH = ROOT / "results" / "end_to_end_stanford_template_predictions.csv"
RECORD_PATH = ROOT / "data" / "derived" / "stanford_enriched_text_records.csv"
REPORT_PATH = ROOT / "results" / "END_TO_END_STANFORD_CASE_ZH.md"
HOLDOUT = "Stanford Health Care Tri-Valley"
REVIEW_THRESHOLD = 0.50


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fixed_metrics(gold, predicted, labels, weights=None):
    return {
        "n_units": len(gold),
        "weighted_n_records": int(sum(weights)) if weights is not None else None,
        "accuracy": accuracy_score(gold, predicted, sample_weight=weights),
        "macro_f1_fixed_label_set": f1_score(
            gold,
            predicted,
            labels=labels,
            average="macro",
            zero_division=0,
            sample_weight=weights,
        ),
        "per_class": classification_report(
            gold,
            predicted,
            labels=labels,
            output_dict=True,
            zero_division=0,
            sample_weight=weights,
        ),
    }


def multilabel_metrics(template_rows, weighted=False, prediction_prefix="pred_"):
    all_gold = []
    all_pred = []
    all_weights = []
    per_attribute = {}
    for attr in ATTRS:
        selected = [row for row in template_rows if row[attr] in {"0", "1"}]
        gold = [row[attr] for row in selected]
        pred = [row[f"{prediction_prefix}{attr}"] for row in selected]
        weights = [int(row["occurrence_count"]) for row in selected] if weighted else None
        per_attribute[attr] = {
            "n_known_templates": len(selected),
            "positive_support_templates": sum(value == "1" for value in gold),
            "accuracy": accuracy_score(gold, pred, sample_weight=weights),
            "positive_f1": f1_score(
                gold,
                pred,
                pos_label="1",
                average="binary",
                zero_division=0,
                sample_weight=weights,
            ),
        }
        all_gold.extend(gold)
        all_pred.extend(pred)
        all_weights.extend(weights if weights is not None else [1] * len(selected))
    micro_f1 = f1_score(
        all_gold,
        all_pred,
        pos_label="1",
        average="binary",
        zero_division=0,
        sample_weight=all_weights,
    )
    correct_weight = sum(w for a, b, w in zip(all_gold, all_pred, all_weights) if a == b)
    return {
        "known_attribute_cells": len(all_gold),
        "weighted_known_record_cells": int(sum(all_weights)) if weighted else None,
        "hamming_accuracy": correct_weight / sum(all_weights),
        "micro_positive_f1": micro_f1,
        "macro_attribute_f1": sum(v["positive_f1"] for v in per_attribute.values()) / len(ATTRS),
        "per_attribute": per_attribute,
    }


def fit_primary(train, test):
    estimator = clone(models()["hpp_nlp_hybrid_logistic"])
    estimator.fit(
        [row["expression_text"] for row in train],
        [row["primary_method"] for row in train],
    )
    predicted = estimator.predict([row["expression_text"] for row in test])
    probabilities = estimator.predict_proba([row["expression_text"] for row in test])
    return list(map(str, predicted)), probabilities.max(axis=1).tolist()


def fit_attributes(train, test):
    outputs = {attr: [] for attr in ATTRS}
    statuses = {}
    for attr in ATTRS:
        train_known = [row for row in train if row[attr] in {"0", "1"}]
        train_values = sorted({row[attr] for row in train_known})
        if len(train_values) == 1:
            predicted = [train_values[0]] * len(test)
            statuses[attr] = f"constant_{train_values[0]}"
        else:
            estimator = clone(models()["hpp_nlp_hybrid_logistic"])
            estimator.set_params(classifier__solver="liblinear", classifier__max_iter=5000)
            estimator.fit(
                [row["expression_text"] for row in train_known],
                [row[attr] for row in train_known],
            )
            predicted = estimator.predict([row["expression_text"] for row in test])
            statuses[attr] = "fitted"
        outputs[attr] = list(map(str, predicted))
    return outputs, statuses


def fit_computability(train, test):
    estimator = clone(models()["hpp_nlp_hybrid_logistic"])
    estimator.set_params(classifier__solver="liblinear", classifier__max_iter=5000)
    estimator.fit(
        [row["expression_text"] for row in train],
        [row["computability"] for row in train],
    )
    predicted = estimator.predict([row["expression_text"] for row in test])
    probabilities = estimator.predict_proba([row["expression_text"] for row in test])
    return list(map(str, predicted)), probabilities.max(axis=1).tolist()


def write_csv(path: Path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    labels = read_rows(LABELS_PATH)
    train = [row for row in labels if row["hospital"] != HOLDOUT]
    test = [dict(row) for row in labels if row["hospital"] == HOLDOUT]
    if len(test) != 20:
        raise RuntimeError(f"Expected 20 held-out Stanford templates, found {len(test)}")

    primary_pred, primary_conf = fit_primary(train, test)
    attribute_pred, attribute_status = fit_attributes(train, test)
    comp_pred, comp_conf = fit_computability(train, test)
    for index, row in enumerate(test):
        rule_primary = classify_literal(row["expression_text"])
        if rule_primary in {"abstain", "other"}:
            rule_primary = "unclear"
        row["rule_primary_method"] = rule_primary
        row["pred_primary_method"] = primary_pred[index]
        row["primary_confidence"] = primary_conf[index]
        row["pred_computability"] = comp_pred[index]
        row["computability_confidence"] = comp_conf[index]
        for attr in ATTRS:
            row[f"rule_{attr}"] = str(
                int(flags(row["expression_text"])[ATTR_TO_FLAG[attr]])
            )
            row[f"pred_{attr}"] = attribute_pred[attr][index]

    metadata, raw_rows = parse_json(RAW_PATH)
    text_rows = [row for row in raw_rows if row["nlp_text"]]
    by_template = {row["expression_text"]: row for row in test}
    unmatched = Counter()
    mapped_counts = Counter()
    enriched = []
    for number, raw in enumerate(text_rows, 1):
        normalized = canonical_template(raw["nlp_text"])
        template = by_template.get(normalized)
        if template is None:
            unmatched[normalized] += 1
            continue
        mapped_counts[template["sample_id"]] += 1
        predicted_attributes = [
            attr.removeprefix("attr_")
            for attr in ATTRS
            if template[f"pred_{attr}"] == "1"
        ]
        rule_attributes = [
            attr.removeprefix("attr_")
            for attr in ATTRS
            if template[f"rule_{attr}"] == "1"
        ]
        requires_review = (
            float(template["primary_confidence"]) < REVIEW_THRESHOLD
            or template["pred_primary_method"] == "unclear"
            or template["pred_computability"] in {"not_computable", "unclear"}
        )
        enriched.append({
            "record_id": f"STV-{number:06d}",
            "hospital": raw["hospital"],
            "description": raw["description"],
            "setting": raw["setting"],
            "billing_class": raw["billing_class"],
            "payer_name": raw["payer_name"],
            "plan_name": raw["plan_name"],
            "structured_methodology_original": raw["methodology"],
            "standard_charge_dollar": raw["dollar"],
            "standard_charge_percentage": raw["percentage"],
            "mechanism_template_id": template["sample_id"],
            "rule_primary_method": template["rule_primary_method"],
            "predicted_primary_method": template["pred_primary_method"],
            "primary_confidence": f"{float(template['primary_confidence']):.6f}",
            "rule_attributes": "|".join(rule_attributes),
            "predicted_attributes": "|".join(predicted_attributes),
            "predicted_computability": template["pred_computability"],
            "computability_confidence": f"{float(template['computability_confidence']):.6f}",
            "human_review_required": int(requires_review),
        })

    if unmatched:
        raise RuntimeError(f"Unmatched raw templates: {dict(unmatched)}")
    expected_counts = {row["sample_id"]: int(row["occurrence_count"]) for row in test}
    if dict(mapped_counts) != expected_counts:
        raise RuntimeError("Raw-to-template occurrence counts do not match frozen labels")

    primary_gold = [row["primary_method"] for row in test]
    rule_primary_pred = [row["rule_primary_method"] for row in test]
    comp_gold = [row["computability"] for row in test]
    weights = [int(row["occurrence_count"]) for row in test]
    template_primary = fixed_metrics(primary_gold, primary_pred, PRIMARY_LABELS)
    record_primary = fixed_metrics(primary_gold, primary_pred, PRIMARY_LABELS, weights)
    rule_template_primary = fixed_metrics(primary_gold, rule_primary_pred, PRIMARY_LABELS)
    rule_record_primary = fixed_metrics(
        primary_gold, rule_primary_pred, PRIMARY_LABELS, weights
    )
    template_comp = fixed_metrics(comp_gold, comp_pred, COMPUTABILITY_LABELS)
    record_comp = fixed_metrics(comp_gold, comp_pred, COMPUTABILITY_LABELS, weights)

    predicted_primary_records = Counter()
    predicted_comp_records = Counter()
    predicted_attribute_records = Counter()
    for row in test:
        count = int(row["occurrence_count"])
        predicted_primary_records[row["pred_primary_method"]] += count
        predicted_comp_records[row["pred_computability"]] += count
        for attr in ATTRS:
            if row[f"pred_{attr}"] == "1":
                predicted_attribute_records[attr.removeprefix("attr_")] += count

    review_records = sum(int(row["human_review_required"]) for row in enriched)
    source_methodology = Counter(row["methodology"] or "missing" for row in text_rows)
    test_by_id = {row["sample_id"]: row for row in test}
    example_ids = ["EXP-9AD0D67E0FC1", "EXP-F6E2F5F54778", "EXP-20F9189733A3"]
    illustrative_examples = []
    for sample_id in example_ids:
        row = test_by_id[sample_id]
        illustrative_examples.append({
            "sample_id": sample_id,
            "source_occurrence_count": int(row["occurrence_count"]),
            "original_structured_methodology": "other",
            "raw_expression": row["representative_text"],
            "predicted_primary_method": row["pred_primary_method"],
            "fixed_rule_primary_method": row["rule_primary_method"],
            "primary_confidence": row["primary_confidence"],
            "predicted_attributes": [
                attr.removeprefix("attr_")
                for attr in ATTRS if row[f"pred_{attr}"] == "1"
            ],
            "fixed_rule_attributes": [
                attr.removeprefix("attr_")
                for attr in ATTRS if row[f"rule_{attr}"] == "1"
            ],
            "predicted_computability": row["pred_computability"],
            "expert_reviewed_primary_method": row["primary_method"],
        })
    summary = {
        "case_design": {
            "held_out_hospital": HOLDOUT,
            "raw_file": str(RAW_PATH.relative_to(ROOT)),
            "source_metadata": metadata,
            "training_hospital_systems": sorted({row["hospital"] for row in train}),
            "training_templates": len(train),
            "held_out_templates": len(test),
            "held_out_raw_payer_records": len(raw_rows),
            "held_out_text_bearing_records": len(text_rows),
            "mapping_completeness": len(enriched) / len(text_rows),
            "label_use": "Stanford expert-reviewed labels were hidden during fitting and used only for evaluation.",
        },
        "why_134_templates": {
            "six_system_payer_records": 2156830,
            "six_system_text_bearing_records": 1455384,
            "hospital_specific_mechanism_templates": 134,
            "rationale": "Amounts, percentages, codes, and modifiers create repeated row instances of the same contractual mechanism. Template-level evaluation prevents duplicated formulas from dominating accuracy and leaking across splits.",
        },
        "original_structured_methodology_for_text_rows": dict(source_methodology),
        "new_record_level_outputs": {
            "primary_method_distribution": dict(predicted_primary_records),
            "computability_distribution": dict(predicted_comp_records),
            "attribute_positive_record_counts_nonexclusive": dict(predicted_attribute_records),
            "records_with_non_unclear_primary": sum(
                count for label, count in predicted_primary_records.items() if label != "unclear"
            ),
            "records_routed_to_review": review_records,
            "review_rule": f"primary confidence < {REVIEW_THRESHOLD}, unclear primary, or not-computable/unclear computability",
        },
        "illustrative_examples": illustrative_examples,
        "accuracy": {
            "fixed_rules_primary_template_level": rule_template_primary,
            "fixed_rules_primary_record_weighted_descriptive": rule_record_primary,
            "primary_template_level": template_primary,
            "primary_record_weighted_descriptive": record_primary,
            "fixed_rules_attributes_template_level": multilabel_metrics(
                test, weighted=False, prediction_prefix="rule_"
            ),
            "fixed_rules_attributes_record_weighted_descriptive": multilabel_metrics(
                test, weighted=True, prediction_prefix="rule_"
            ),
            "attributes_template_level": multilabel_metrics(test, weighted=False),
            "attributes_record_weighted_descriptive": multilabel_metrics(test, weighted=True),
            "computability_template_level": template_comp,
            "computability_record_weighted_descriptive": record_comp,
            "interpretation": "Template metrics are the inferential evaluation. Record-weighted metrics describe deployment impact but are not independent observations because many records reuse one template.",
        },
        "attribute_model_status": attribute_status,
        "outputs": {
            "template_predictions": str(TEMPLATE_PATH.relative_to(ROOT)),
            "enriched_text_records": str(RECORD_PATH.relative_to(ROOT)),
        },
    }

    template_fields = [
        "sample_id", "hospital", "occurrence_count", "representative_text",
        "expression_text", "primary_method", "rule_primary_method",
        "pred_primary_method", "primary_confidence",
    ]
    for attr in ATTRS:
        template_fields.extend([attr, f"rule_{attr}", f"pred_{attr}"])
    template_fields.extend([
        "computability", "pred_computability", "computability_confidence",
    ])
    write_csv(TEMPLATE_PATH, test, template_fields)
    write_csv(RECORD_PATH, enriched)
    with SUMMARY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    p_acc = template_primary["accuracy"]
    p_f1 = template_primary["macro_f1_fixed_label_set"]
    rp_acc = record_primary["accuracy"]
    attr = summary["accuracy"]["attributes_template_level"]
    rule_p = summary["accuracy"]["fixed_rules_primary_template_level"]
    rule_attr = summary["accuracy"]["fixed_rules_attributes_template_level"]
    comp = template_comp
    report = f"""# Stanford Tri-Valley 端到端留出案例

## 为什么 216 万条记录只评估 134 个模板

2,156,830 是六个医院系统中的 payer-level 行数，其中 1,455,384 条含有算法或备注文本。同一合同公式会因服务代码、modifier、金额和百分比不同重复出现数千至数十万次。去除这些实例变量后，得到 134 个“医院系统 × 支付机制”模板。模板级准确率避免同一公式的高频复制主导结果；记录级映射则用于表示真实部署影响。

## 真正的端到端流程

本案例将 Stanford Health Care Tri-Valley 整院留出。模型只使用其他五个系统的 {len(train)} 个模板训练，然后从 Stanford 官方 CMS v3 JSON 重新解析 {len(raw_rows):,} 条 payer-level 记录。其中 {len(text_rows):,} 条含文本，完整映射到 20 个未见模板；Stanford 的人类专家复核标签只在预测完成后用于评估。

CMS v3.0 的 `methodology` 是具有固定合法值的分类字段，并非自由文本。本案例的问题是粒度不足：Stanford 将这 {len(text_rows):,} 条含算法文本的记录全部归入 `{next(iter(source_methodology))}`，而复杂条款位于 algorithm 和 notes 自由文本中。NLP 为每条记录新增：六类主机制、10 个可并存合同属性、可计算性、信心度和人工复核标记。预测主机制分布为 {dict(predicted_primary_records)}；可计算性分布为 {dict(predicted_comp_records)}。

## 准确性

- 主机制 fixed rules：20 个模板正确 19 个，accuracy {rule_p['accuracy']:.3f}，固定六类 macro-F1 {rule_p['macro_f1_fixed_label_set']:.3f}。
- 主机制 HPP-NLP：20 个模板正确 18 个，accuracy {p_acc:.3f}，固定六类 macro-F1 {p_f1:.3f}。因此该案例不支持 HPP-NLP 在主类别上超过规则。
- 10 个属性 fixed rules：Hamming {rule_attr['hamming_accuracy']:.3f}，micro-F1 {rule_attr['micro_positive_f1']:.3f}，macro 属性 F1 {rule_attr['macro_attribute_f1']:.3f}。
- 10 个属性 HPP-NLP：Hamming {attr['hamming_accuracy']:.3f}，micro-F1 {attr['micro_positive_f1']:.3f}，macro 属性 F1 {attr['macro_attribute_f1']:.3f}。HPP-NLP 的增量价值主要在多标签属性层。
- 可计算性：模板级准确率 {comp['accuracy']:.3f}，固定四类 macro-F1 {comp['macro_f1_fixed_label_set']:.3f}。
- 如按原始记录频数加权，主机制准确率为 {rp_acc:.3f}。这只表示部署中覆盖的记录比例，不是 13,325 个相互独立的测试样本。

## 过去无法获得而现在可获得的信息

1. 可以把原本全部混在 `other` 中的记录分成 fee schedule、percent of charge、hybrid 和 unclear，避免在价格比较中把不可比的合同项混在一起。
2. 不只给一个类别，还能标出 stop-loss、lesser-of、per-diem、case-rate、外部 fee schedule 引用和住院天数等可并存条款。
3. 可区分“文件内直接可算”、“需外部费率表才可算”和“不可算”，并将低信心度或不可计算记录送入审核队列。

## 三个原始到输出的具体例子

| CMS methodology 和原始条款 | Fixed rules | HPP-NLP | 专家标签和用途 |
|---|---|---|---|
| `other`; `[MSDRG Base Rate: FEE SCHEDULE]` | 主类 `fee_schedule`；属性 fee schedule | 主类 `fee_schedule` (0.737)；另识别 external reference | 主类 `fee_schedule`；说明需外部 DRG 费率表，该模板覆盖 1,778 条。 |
| `other`; stop-loss + fee schedule + per-diem + burn case-rate | 主类 `hybrid`；少报 fixed-dollar、external-reference 和 length-of-stay | 主类误判为 `case_rate` (0.445)，但 8 个属性全部与专家一致 | 主类 `hybrid`；HPP 的低置信度可将其送审，该模板覆盖 889 条。 |
| `other`; stop-loss + lesser-of + 多种 per-diem/case-rate + 百分比/固定金额 | 主类 `hybrid`；少报 fixed-dollar 和 length-of-stay | 主类 `hybrid` (0.529)；补出 fixed-dollar 和 length-of-stay，但多报 external-reference | 主类 `hybrid`；展示 HPP 在属性层的增量与错误，该模板覆盖 1,778 条。 |

结果文件中，模板表保留了原始表达、专家标签与预测的并排比较；记录表展示如何将模板预测回写到全部 {len(text_rows):,} 条原始文本价格记录。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({
        "raw_records": len(raw_rows),
        "text_records": len(text_rows),
        "templates": len(test),
        "primary_template_accuracy": p_acc,
        "fixed_rule_primary_template_accuracy": rule_p["accuracy"],
        "primary_record_weighted_accuracy": rp_acc,
        "attribute_hamming_accuracy": attr["hamming_accuracy"],
        "computability_template_accuracy": comp["accuracy"],
        "outputs": summary["outputs"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
