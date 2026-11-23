# 两个独立医院系统扩展报告

## 新增系统

本阶段新增两个与既有开发集及 Orlando Health 相互独立的医院系统：

1. Stanford Health Care Tri-Valley：CMS v3.0 JSON，文件内日期 2026-04-01，43,065,577 bytes；
2. South Miami Hospital（Baptist Health South Florida）：CMS v3.0 Tall CSV，文件内日期 2026-03-30，ZIP 24,143,862 bytes、解压后 520,665,559 bytes。

来源 URL、抓取日期和 SHA-256 均记录在 `data/sources.json`。原始 MRF 只作为可复现研究输入；GitHub 仓库应发布来源清单、下载说明和哈希，不直接提交大文件。

## 字段审计

| 扩展系统 | payer-level 记录 | 非空 algorithm/notes | 原文字面唯一数 | 机制模板数 |
|---|---:|---:|---:|---:|
| Orlando Health | 340,815 | 77,353 | 75 | 48 |
| Stanford Tri-Valley | 69,094 | 13,325 | 23 | 20 |
| South Miami Hospital | 1,523,549 | 1,326,503 | 828,475 | 32 |
| 合计 | 1,933,458 | 1,417,181 | 828,573 | 100 |

South Miami 的字面唯一数异常大，不代表存在 82.8 万种合同机制。同一公式会按收费金额、revenue code、procedure code 和 modifier 重复实例化。研究因此增加 `canonical_template()`：依次替换 URL、Rev/Proc/Modifier、美元金额、百分比数值和其他数值，再压缩空格。该步骤将 828,475 个 South Miami 字符串压缩为 32 个机制模板。

## 类别覆盖初筛

固定规则只用于选择和工作量评估，不作为 gold label：

- Orlando：48 个模板，29 个 hybrid 候选、18 个含 case-rate、11 个含 per-diem、13 个含 outlier/stop-loss；
- Stanford：20 个模板，13 个 hybrid 候选、8 个含 case-rate、8 个含 per-diem、7 个含 outlier/stop-loss；
- South Miami：32 个模板，6 个 case-rate 候选、5 个 percent-of-charge 候选，另有多条 claim-limit/EAPG 文本需要专家判断。

新增系统能够为原来只存在于单一开发医院的 case-rate、per-diem 和 hybrid 类别提供跨系统支持，但正式分布必须以人类专家标注为准。

## 人类标注包

- `annotations/expansion_annotation_A_BLINDED.csv`：专家 A，随机顺序；
- `annotations/expansion_annotation_B_BLINDED.csv`：专家 B，另一随机顺序；
- `annotations/expansion_weak_reference_DO_NOT_GIVE_ANNOTATORS.csv`：医院结构化 methodology，只供最终裁决参考；
- `annotations/expansion_machine_preannotations_FOR_HUMAN_REVIEW.csv`：机器建议，只能在两位专家完成独立标注后用于加速冲突复核。

两位专家应使用冻结的 `ANNOTATION_GUIDE_ZH.md` v1.1 独立填写全部字段，不交流个别样本，也不查看弱标签或机器建议。完成后运行：

```bash
python3 src/score_annotations.py \
  annotations/expansion_annotation_A_BLINDED.csv \
  annotations/expansion_annotation_B_BLINDED.csv \
  --output-dir results/expansion_human_annotation_scoring
```

在 κ、原始一致率和冲突裁决完成之前，这 100 条不得并入 gold training set，也不得用于报告正式模型性能。
