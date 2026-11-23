# Stanford Tri-Valley 端到端留出案例

## 为什么 216 万条记录只评估 134 个模板

2,156,830 是六个医院系统中的 payer-level 行数，其中 1,455,384 条含有算法或备注文本。同一合同公式会因服务代码、modifier、金额和百分比不同重复出现数千至数十万次。去除这些实例变量后，得到 134 个“医院系统 × 支付机制”模板。模板级准确率避免同一公式的高频复制主导结果；记录级映射则用于表示真实部署影响。

## 真正的端到端流程

本案例将 Stanford Health Care Tri-Valley 整院留出。模型只使用其他五个系统的 114 个模板训练，然后从 Stanford 官方 CMS v3 JSON 重新解析 69,094 条 payer-level 记录。其中 13,325 条含文本，完整映射到 20 个未见模板；Stanford 的人类专家复核标签只在预测完成后用于评估。

原始 CMS `methodology` 对这 13,325 条全部只标为 `other`，无法区分支付机制。NLP 为每条记录新增：六类主机制、10 个可并存合同属性、可计算性、信心度和人工复核标记。预测主机制分布为 {'fee_schedule': 1914, 'hybrid': 9842, 'percent_of_charge': 544, 'unclear': 136, 'case_rate': 889}；可计算性分布为 {'conditional_external': 13189, 'not_computable': 136}。

## 准确性

- 主机制 fixed rules：20 个模板正确 19 个，accuracy 0.950，固定六类 macro-F1 0.637。
- 主机制 HPP-NLP：20 个模板正确 18 个，accuracy 0.900，固定六类 macro-F1 0.630。因此该案例不支持 HPP-NLP 在主类别上超过规则。
- 10 个属性 fixed rules：Hamming 0.853，micro-F1 0.833，macro 属性 F1 0.673。
- 10 个属性 HPP-NLP：Hamming 0.958，micro-F1 0.960，macro 属性 F1 0.868。HPP-NLP 的增量价值主要在多标签属性层。
- 可计算性：模板级准确率 1.000，固定四类 macro-F1 0.500。
- 如按原始记录频数加权，主机制准确率为 0.923。这只表示部署中覆盖的记录比例，不是 13,325 个相互独立的测试样本。

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

结果文件中，模板表保留了原始表达、专家标签与预测的并排比较；记录表展示如何将模板预测回写到全部 13,325 条原始文本价格记录。
