# HPP-NLP 六医院系统扩展实验报告

## 1. 这次实际完成了什么

本阶段将三个开发医院与三个独立扩展系统合并为六医院系统、134 个去重支付机制模板的开发语料。新增的 100 个扩展模板由两个相互隔离的 AI agent 按同一冻结手册独立标注，再由根 agent 仅依据手册裁决冲突。所有新增标签仍标记为 `PENDING`，等待人类专家逐条复核；因此以下分数是模型开发结果，不是最终人类 gold-standard 结果。

研究产出已经不仅是方法论，而是一个可运行的层级 NLP 原型：

1. 主支付方式六分类；
2. 十种可并存支付条款的多标签识别；
3. 最终金额可计算性四分类；
4. 置信度拒识和人工复核队列；
5. 医院系统级留出评估与可复现脚本。

## 2. 数据与模板单位

六个系统共形成 134 个“医院系统—机制模板”：Banner 7、Berger 16、Martha's Vineyard 11、Orlando 48、South Miami 32、Stanford Tri-Valley 20。主类别分布为 hybrid 44、fee schedule 39、case rate 19、percent of charge 17、unclear 13、per diem 2。

扩展数据原始共有 1,933,458 条 payer-level records，其中 1,417,181 条含算法或备注文本。South Miami 的金额、服务代码和 modifier 使同一公式产生 828,475 个逐字不同字符串；规范化金额、百分比、Rev/Proc/Modifier 和 URL 后，仅剩 32 个机制模板。由此，论文的一个重要技术贡献是把评价单位从高重复的原始记录改为支付机制模板，避免同一公式实例泄漏到训练集和测试集。

## 3. 双 agent 标注结果

两个 agent 各自完成 100 条扩展模板的主类别、十属性和可计算性标注。主类别原始一致率为 0.900，Cohen's kappa 为 0.862。十个属性与可计算性的平均 kappa 为 0.884；fee-schedule、case-rate、per-diem 和 external-reference 的 kappa 为 1.000。

主要系统性分歧是 `bundle_packaging`（kappa 0.355）：Agent A 将部分 case/episode 结构视为 bundle，Agent B 要求文本明确出现 bundle/packaged。按冻结手册采用后者，即不能仅从 case rate 推断 bundling。共有 51 条在至少一个字段上发生分歧并经根 agent 裁决。

供人类复核的优先队列包含 79 条：51 条 agent 冲突记录，以及无冲突但置信度为 medium/low 的记录。完整 100 条裁决表仍保留，便于全量审阅。

## 4. 主支付方式模型

主评价采用 leave-one-hospital/system-out：每次完整留出一个医院系统，禁止同一系统模板出现在训练侧。固定六类 Macro-F1 如下：

| 方法 | Accuracy | Macro-F1 |
|---|---:|---:|
| 固定字面规则 | 0.746 | 0.773 |
| Word TF-IDF + Logistic | 0.493 | 0.372 |
| Char TF-IDF + Logistic | 0.478 | 0.358 |
| Char TF-IDF + Linear SVM | 0.522 | 0.403 |
| HPP-NLP hybrid | 0.672 | 0.551 |
| 固定规则→HPP-NLP cascade | 0.709 | 0.735 |

结论必须如实表述：HPP-NLP 明显优于全部纯统计学习基线，但在主类别总体指标上尚未超过专家设计的固定规则。级联模型接近规则基线，但也没有反超。这不是失败；它说明当前 134 个模板仍适合以“规则保证高精度、NLP 处理长尾和拒识”为产品架构，而不能声称端到端模型已经全面取代规则。

HPP-NLP 的置信度具有实用价值：阈值 0.50 时覆盖 68.7%，覆盖样本准确率 84.8%；阈值 0.80 时覆盖 21.6%，准确率 96.6%；阈值 0.90 时覆盖 4.5%，准确率 100%。这些数值只用于当前开发集的工作流设计，需在人类复核标签上重算。

## 5. 十属性多标签模型

对每个属性分别排除 `U`，仍采用医院系统级留出。结果如下：

| 方法 | Hamming accuracy | Micro positive F1 | Macro attribute F1 |
|---|---:|---:|---:|
| 固定属性规则 | 0.854 | 0.773 | 0.731 |
| HPP-NLP multi-label | **0.891** | **0.856** | **0.793** |

这是当前最有说服力的模型结果：HPP-NLP 在多标签机制属性上超过规则基线，尤其改善了 external reference（F1 0.228→0.848）和 length of stay（0.174→0.933）。但 bundle/packaging 的模型 F1 为 0，说明正例只有 11 条且语义边界仍不稳定；该属性必须优先人工复核并继续补样本。

## 6. 可计算性模型

可计算性分布为 conditional external 94、not computable 29、direct 8、unclear 3。医院系统级留出结果：

| 方法 | Accuracy | 固定四类 Macro-F1 |
|---|---:|---:|
| 训练折多数类 | 0.701 | 0.206 |
| HPP-NLP computability | **0.739** | **0.321** |

模型能够识别一部分 `not_computable`（F1 0.444），但 direct 和 unclear 的 F1 仍为 0。当前结果只支持“可计算性有可学习信号”，不支持宣称已可靠区分全部四类。

## 7. 论文可主张的贡献

在完成专家复核后，论文可以把贡献写成四点：

1. 提出 hospital price transparency payment expression 的机制模板规范化方法，减少金额/代码实例造成的伪重复与评价泄漏。
2. 将任务定义为“主支付方式 + 可并存条款 + 可计算性”的层级 NLP，而不是把 CMS methodology 当作完整语义标签。
3. 提供规则、词/字符 TF-IDF、SVM、HPP-NLP hybrid 和 cascade 的医院系统级外推比较，并公开负面结果。
4. 提供置信度拒识和 human-in-the-loop 审阅机制，使模型能作为实际数据质量管道，而非黑箱分类器。

目前不应写“validated across U.S. hospitals”或“human expert gold standard”。更准确的表述是：`six-system public-data development study with independent dual-agent annotation and pending human expert review`。待人类复核并重跑后，再决定是否升级为 `expert-reviewed`。

## 8. 下一步复核与冻结顺序

1. 先审阅 `EXPANSION_HUMAN_REVIEW_PRIORITY.csv` 的 79 条，优先级 1 是 51 条冲突记录。
2. 对其余 21 条高置信、无冲突记录作快速全量确认，保证 100 条都留下可追溯的人类结论。
3. 将人类修订合并为冻结标签，重跑三个任务和置信度曲线。
4. 报告复核前后标签变化率、各字段人机一致率，并据此决定能否称为 expert-reviewed gold set。
5. 最终 GitHub 仓库只发布脚本、小型派生模板、来源 URL/日期/哈希和下载说明；不提交 521 MB 原始 CSV。
