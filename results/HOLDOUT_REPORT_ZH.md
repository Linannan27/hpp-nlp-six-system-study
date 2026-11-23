# 双人标注准备与医院级留出评估报告

## 一、双人标注包

已从三家真实医院的 algorithm/notes 中生成 178 个去重的“医院—文本表达”样本。该数量高于前一轮的 166，因为标注包保留了结构化 methodology 缺失的表达，以免受原标签可用性偏差影响。

已生成 A/B 两份不同随机顺序的盲标表、标注手册、隔离保存的弱标签对照表，以及一致性计算和冲突裁决脚本。主类别包括 `fee_schedule`、`case_rate`、`per_diem`、`percent_of_charge`、`hybrid`、`other_clear` 和 `unclear`；附加属性包括 outlier/stop-loss、lesser-of、bundling、external reference、length of stay 等。

目前表格为空白盲标状态。必须由两位真实标注者独立完成后，才能报告双人一致性。不应用同一模型或同一规则填充 A/B 两表。

## 二、留一医院外评估设计

每次将一家医院的全部独特表达作为测试集，其余两家医院作为训练集。评估单位为独特的“医院—表达—methodology”组合，不按原始重复行加权。本轮仍使用结构化 methodology 作弱参照标签，因为人工金标尚未完成。

对比固定字面规则、开发后的组合上下文规则，以及字符 3–5 gram 多项式朴素贝叶模型。组合规则曾查看整体语料，因此不是严格外部验证，只作参考。监督模型不允许预测训练集中没有出现的类别。

## 三、数据支持断裂

| 测试医院 | 训练 n | 测试 n | 测试集中训练时未出现的类别 |
|---|---:|---:|---|
| Banner Churchill | 164 | 2 | percent_of_charge |
| Berger Hospital | 138 | 28 | 无 |
| Martha's Vineyard | 30 | 136 | case_rate, fee_schedule, per_diem |

现有三院数据不足以进行公平的五类跨医院监督学习比较。Banner 的有标签独特文本只有 2 条，而 Martha's Vineyard 中三个关键类别在其他两院的训练文本中完全缺失。

## 四、医院级留出结果

| 方法 | 汇总准确率 | 汇总 Macro-F1 | 解读 |
|---|---:|---:|---|
| 字面规则 | 0.151 | 0.280 | 对 per diem 相对稳定，但对 case rate 和 `other` 失败 |
| 组合上下文规则 | 0.536 | 0.490 | 曾查看全部语料，不得当作外部验证结果 |
| 字符 n-gram 朴素贝叶 | 0.000 | 0.000 | 在医院级 domain shift 和类别断裂下完全失败 |

朴素贝叶的失败不是因为原始行数太少，而是因为去重后的语义样本少、医院之间语言模板差异大，并且类别支持不重叠。留出 Berger 时，28 条测试表达的弱标签全是 `other`，模型却将它们判为 percent-of-charge、fee schedule 或 per diem。留出 Martha's Vineyard 时，训练集只有 `other` 和 percent-of-charge，所以无法学习其他三类。

## 五、对论文的含义

不应写成“模型已证明可跨医院推广”。目前可被数据支持的表述是：

> Row-level performance substantially overstated generalization. In leave-one-hospital-out evaluation, a character n-gram classifier failed under severe institution-specific template shift and class-support mismatch, demonstrating the need for hospital-grouped validation, broader multi-system sampling, and human-adjudicated hierarchical labels.

这是一个有价值的负面结果：仅使用某一医院或某一系统的重复文本训练模型，很可能只是学会了发布者模板，而非通用的支付机制。

## 六、下一轮的最小充分条件

1. 两位标注者完成 178 条盲标并裁决冲突。
2. 补充至少 3–7 个新医院系统，并优先选择能为每个主类别提供至少两个训练医院的数据。
3. 正式分析使用裁决后的层级人工标签，不再把 CMS methodology 作为 gold standard。
4. 主指标报告 leave-one-system-out Macro-F1、属性级 F1、弃权率和 accuracy-coverage curve。
