# 双 AI Agent 独立标注、手册修订与裁决报告

## 定位声明

本次标注由两个相互独立的 AI agent 完成，不是两位人类专家。两个 agent 只能查看共同标注手册、各自的盲标表和表内上下文；禁止查看对方结果、医院原始 methodology 对照表或先前的模型预测。因此，本结果可用于开发标签体系和发现歧义，但不能在论文中冒充人类专家 gold standard。

## 标注范围

- 样本：178 个去重的真实医院支付方式表达。
- 主类别：fee schedule、case rate、per diem、percent of charge、hybrid、other clear、unclear。
- 属性：fee-schedule reference、case rate、per diem、percent of charge、fixed dollar、outlier/stop-loss、lesser-of、bundle/packaging、external reference、length of stay。
- 附加判断：computability 和 confidence。

## 第一轮一致性与手册修订

第一轮标注的主类别一致率为 95.5%，Cohen's kappa 为 0.937。但出现两个系统性歧义：

- `attr_percent_of_charge`：一个 agent 只把主支付或附加支付直接按收费百分比计算视为阳性；另一个 agent 还将 `billed amount × cost-to-charge ratio` 影响 outlier 支付的情形视为阳性。初始 kappa 仅 0.086。
- `computability`：一个 agent 将“公式完整但需 billed amount/LOS”视为 direct，另一个视为 conditional。初始 kappa 为 0.040。

手册 v1.1 采用以下冻结口径：

1. 只要收费额或 cost-to-charge ratio 会影响基础支付、上限、outlier 触发或 outlier 金额，`attr_percent_of_charge=1`。
2. 只有使用当前表达和同一 MRF 价格行已有字段就能得到唯一金额时，computability 才是 direct；需 billed amount、LOS、quantity、同日服务或外部 pricer 时为 conditional_external。

两个 agent 根据 v1.1 分别重标这两个字段。

## v1.1 一致性

| 字段 | 原始一致率 | Cohen's kappa |
|---|---:|---:|
| 主支付方式 | 0.955 | 0.937 |
| fee-schedule reference | 0.989 | 0.965 |
| case-rate attribute | 0.978 | 0.955 |
| per-diem attribute | 1.000 | 1.000 |
| percent-of-charge attribute | 1.000 | 1.000 |
| fixed-dollar attribute | 1.000 | 1.000 |
| outlier/stop-loss | 0.994 | 0.986 |
| lesser-of | 0.994 | 0.954 |
| bundle/packaging | 0.989 | 0.945 |
| external reference | 0.994 | 0.974 |
| length-of-stay | 1.000 | 1.000 |
| computability | 0.994 | 0.935 |

十二个评分字段的平均 kappa 为 0.971。剩余 15 个样本存在至少一项冲突，主要是 inpatient fee-schedule rate 与 case rate 的边界、MS-DRG base rate 的主类别、以及 lesser-of/cap 是否构成 hybrid。

## 裁决后开发标签

由根 agent 按冻结手册裁决 15 个冲突样本，最终主类别分布为：

| 主类别 | n |
|---|---:|
| case rate | 68 |
| fee schedule | 64 |
| unclear | 16 |
| percent of charge | 11 |
| hybrid | 11 |
| per diem | 8 |

该数据集应称为 `agent-adjudicated development labels`，不应称为 human gold standard。

## 使用裁决标签的医院级留出

字符 3–5 gram 朴素贝叶在 178 个裁决标签上的 leave-one-hospital-out 结果为：

- pooled accuracy: 0.433
- pooled Macro-F1: 0.283
- fee schedule F1: 0.600
- percent of charge F1: 0.513
- unclear F1: 0.583
- case rate、hybrid 和 per diem F1: 0

失败的根本原因是类别按医院集中：Martha's Vineyard 包含全部 68 个 case-rate 和 8 个 per-diem 表达；Berger 包含全部 11 个 hybrid 表达。当对应医院被留出时，训练数据中没有该类别。

因此，双-agent标注改善了语义标签，但没有解决研究设计中的跨医院类别支持问题。下一轮应按“医院系统 × 主类别”主动补样，而不是继续增加同一医院内的重复记录。
