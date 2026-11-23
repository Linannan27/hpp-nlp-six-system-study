# 公开医院价格透明数据中支付方式表达的轻量 NLP 规范化：初步概念验证

## 一、这次实际做了什么

本试验使用三家医院官方公开的 CMS v3.0 机器可读文件（MRF），分别来自 Banner Health、OhioHealth 和 Mass General Brigham；另使用 CMS 虚构的 West Mercy Hospital 示例文件检验 JSON 解析器，但不将它纳入真实世界性能指标。

管道同时解析 CSV 和嵌套 JSON，把每条 payer-level 价格统一为医院、payer/plan、场景、价格形式、结构化 methodology、algorithm 和 notes 字段。NLP 规则只读取 algorithm/notes，不把结构化 methodology 作为输入；methodology 仅作为弱参照标签。

## 二、数据规模与字段可用性

| 真实医院 | payer-level 记录 | 有 NLP 文本的记录 | 有标签的独特表达 |
|---|---:|---:|---:|
| Berger Hospital | 81,404 | 28,192 | 28 |
| Banner Churchill Community Hospital | 131,516 | 9,385 | 2 |
| Martha's Vineyard Hospital | 10,452 | 626 | 136 |
| **合计** | **223,372** | **38,203** | **166** |

仅 17.1% 的 payer-level 记录含有可用的 algorithm/notes 文本。更重要的是，38,203 条有文本记录去重后只有 166 个带结构化标签的“医院—表达—方法”组合。若按原始行随机切分训练集和测试集，相同文本很容易同时进入两个集合，从而产生严重的重复泄漏和虚高分数。

## 三、初步规则实验

朴素基线仅检测 `fee schedule`、`case rate`、`per diem` 和费用百分比等字面线索。在排除结构化标签为 `other` 的真实世界子集上：

| 分析口径 | n | 覆盖率 | 已覆盖样本准确率 | Macro-F1（弃权计错） |
|---|---:|---:|---:|---:|
| 独特表达 | 77 | 98.7% | 15.8% | 0.444 |
| 按原始记录频数加权 | 9,457 | 96.7% | 99.2% | 0.519 |

加权准确率看似很高，但独特表达准确率只有 15.8%，原因是 Banner 一条高频百分比表达重复了 9,059 次。这个对比说明，后续论文必须把“独特表达”或“留一医院外”作为主要评估单位，不能仅报告按行加权的 accuracy。

其中最典型的失败是：Martha's Vineyard Hospital 有 64 个独特表达的结构化标签为 `case rate`，但自由文本以 `Fee schedule rate` 开头，后面再描述 inlier reimbursement、outlier threshold 和 stop-loss。朴素关键词规则因此将这 64 个表达全部判为 fee schedule。

为证明组合上下文的价值，又加入一条开发性规则：当文本同时出现 fee-schedule 线索、outlier/stop-loss 与 `inlier reimbursement` 时，归为 case rate。在同一开发数据上，独特表达的已覆盖准确率升至 100%，Macro-F1 升至 0.917。**这不是独立验证结果**，因为规则在同一语料上开发和评估；它只说明“字面关键词→组合条款识别”是值得正式验证的技术路线。

## 四、`other` 类别内部并不单一

在真实数据中，共有 89 个独特文本表达的结构化 methodology 为 `other`。多标签规则识别出：

| 语义属性 | 独特表达数 | 对应原始记录数 |
|---|---:|---:|
| fee schedule/APC/base-rate 线索 | 75 | 12,289 |
| 固定金额线索 | 66 | 870 |
| outlier/stop-loss | 62 | 1,427 |
| 费用百分比 | 21 | 11,210 |
| bundled/packaged | 16 | 160 |
| 两种以上主要支付机制 | 10 | 1,879 |
| lesser-of | 9 | 2,330 |
| 外部规则/网址/政府 pricer 引用 | 6 | 7,106 |
| per diem | 2 | 897 |

这些属性可以同时出现，因此数量不相加。结果支持将任务改写为层级多标签问题：第一层预测主支付方式，第二层识别 outlier、lesser-of、bundling、外部引用、住院天数和缺失参数等属性。

## 五、可以写入论文的初步结论

1. CMS v3.0 结构化 methodology 并没有消除自由文本异质性；`other` 包含多种支付机制和附加条件。
2. 真实 MRF 的文本高度重复。原始行级随机分割会导致泄漏；应按医院或去重表达分割。
3. 朴素关键词无法稳定处理复合条款；需要组合规则、句子级属性抽取和低置信度弃权。
4. 按行加权的 99.2% accuracy 具有误导性；独特表达级结果更能揭示模型对新表达的真实能力。

## 六、当前不能声称的事情

- 不能将结构化 methodology 当作经独立专家确认的 gold standard。
- 不能把同一语料上开发的上下文规则称为“经外部验证的模型”。
- 不能从三家医院推断全美医院的分布。
- 不能声称 NLP 输出等于最终实际支付额，因为许多条款仍缺少外部 fee schedule、病人级信息或合同参数。

## 七、下一步如何升级为正式实验

1. 对 166 个独特表达加上不含文本的分层样本，制定主类别+多标签属性的标注手册。
2. 两位标注者独立标注，报告 Cohen's kappa 和每个属性的一致率。
3. 补充至少 5–10 家来自不同系统的医院，用 leave-one-hospital-out 评估，禁止相同表达跨集合。
4. 比较字面规则、TF-IDF/linear model、sentence embedding 和 hybrid+abstention；报告 Macro-F1、覆盖率、弃权率、跨医院结果及误差类型。
5. 把论文定位为 proof-of-concept/pilot，而非全国验证。
