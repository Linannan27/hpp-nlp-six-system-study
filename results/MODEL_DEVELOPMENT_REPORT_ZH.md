# HPP-NLP 正式模型开发：第一阶段结果

## 模型定义

本阶段将概念性框架落实为可运行的 `HPP-NLP` 混合分类器。模型将三组特征并联：

1. 词级 1–2 gram TF-IDF；
2. 字符级 3–5 gram TF-IDF；
3. 十个固定领域特征，包括 fee schedule、case rate、per diem、percentage of charge、outlier/stop-loss、lesser-of、bundling、外部引用、住院天数和固定金额。

三组特征输入类别平衡的多项逻辑回归。模型输出六类主支付方式的概率，并支持按置信度阈值拒识，将低置信度表达送交人工复核。比较模型包括词级逻辑回归、字符级逻辑回归、字符级 Linear SVM 和固定字面规则。

## 数据和评价设计

- 开发集：178 条独特医院—表达记录。
- 当前类别：case rate 68、fee schedule 64、unclear 16、percent of charge 11、hybrid 11、per diem 8。
- 内部开发评价：五折分层随机表达交叉验证。该设计会混合医院模板，只用于观察模型在同分布下能否学习，不作为外部验证。
- 主要评价：leave-one-hospital/system-out。每次将一家医院的全部表达留出，禁止同院模板进入训练集。
- 主指标：固定六类别 Macro-F1；同时报告 accuracy、各类别 F1、训练集中未出现的留出类别以及选择性预测 coverage–accuracy。

## 结果

| 模型 | 随机表达 CV Accuracy | 随机表达 CV Macro-F1 | 医院级留出 Accuracy | 医院级留出 Macro-F1 |
|---|---:|---:|---:|---:|
| 词级 TF-IDF + Logistic | 0.938 | 0.884 | 0.017 | 0.006 |
| 字符级 TF-IDF + Logistic | 0.938 | 0.873 | 0.017 | 0.006 |
| 字符级 TF-IDF + Linear SVM | 0.944 | 0.891 | 0.017 | 0.006 |
| **HPP-NLP 混合模型** | **0.972** | **0.957** | **0.022** | **0.035** |
| 固定字面规则 | 不适用 | 不适用 | 0.612 | 0.767 |

固定规则的 Macro-F1 较高不能理解为全面性能良好：它对 case rate 的 F1 为 0，但对五个较小类别接近完全识别；类别不平衡使 accuracy 只有 0.612。其价值在于显示明确术语可跨医院迁移，而统计模型主要学习了医院特定模板。

HPP-NLP 在随机表达交叉验证中达到 0.972 accuracy 和 0.957 Macro-F1，但医院级留出降至 0.022 和 0.035。即使只看训练医院已经出现的标签，留出 accuracy 也只有 0.044。这表明性能下降不仅来自未见类别，也来自强烈的机构模板/domain shift。选择性预测在置信度 0.70 时对 3 条样本达到 100% accuracy，但 coverage 仅 1.7%，尚无实用价值。

## 新增公开数据

从 Orlando Health 官方价格透明页面取得 Orlando Health, Inc. CMS v3.0 JSON MRF：

- 文件内更新时间：2026-04-01；
- 340,815 条 payer-level 记录；
- 77,353 条含 algorithm 文本；
- 75 条逐字独特表达，经机制模板规范化后为 48 条；
- 原始结构化方法字段为 fee schedule 249,599、percent of total billed charges 13,863、other 77,353。

在 Orlando Health 之外，本阶段又增加两个独立医院系统：Stanford Health Care Tri-Valley 和 Baptist Health South Florida 的 South Miami Hospital。三套扩展数据合计 1,933,458 条 payer-level 记录，其中 Stanford 有 69,094 条、South Miami 有 1,523,549 条。

South Miami 的 1,326,503 条非空文本若按原文逐字去重会产生 828,475 个“唯一表达”，原因是同一支付公式反复替换收费金额、Rev code、procedure code 和 modifier。为避免伪样本，本研究新增机制模板规范化步骤：将金额、百分比数值及代码替换为占位符后再去重。由此 South Miami 从 828,475 个字面字符串压缩为 32 个支付机制模板。

最终扩展人工复核包为 100 个模板：Orlando 48、Stanford 20、South Miami 32。初步规则筛查显示 Orlando 有 29 个 hybrid 候选，Stanford 有 13 个 hybrid 候选并包含 per-diem/case-rate，South Miami 有 6 个明确 case-rate 候选及大量 percent-of-charge/claim-limit 文本。这些模板已经写入 `annotations/expansion_human_review.csv`；另有明确标记为非 gold 的机器预标注文件供人类加速审核。

## 可发表的贡献

当前结果支持一个比“高分分类器”更可靠的贡献：本研究给出一个开源的分层混合模型，并实证证明同一医院模板混入训练和测试会将 Macro-F1 从接近 0.96 虚高到远高于真正跨医院泛化水平。医院级留出和未见类别审计因此应成为医院价格透明 NLP 的最低评价标准。

在完成 Orlando、Stanford 和 South Miami 三套扩展模板的专家标注前，不能将 HPP-NLP 称为已验证模型。准确表述应为“developed and evaluated in a multi-hospital proof-of-concept”。
