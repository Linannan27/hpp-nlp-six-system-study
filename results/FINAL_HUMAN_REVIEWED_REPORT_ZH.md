# HPP NLP 人类专家复核后最终结果

## 标签冻结状态

两位人类专家已复核现有 AI 双标与裁决结果，并确认全部接受、没有修改。最终标签文件包含六个医院系统的 134 个机制模板。该过程应表述为“AI-assisted labels reviewed and accepted by two human experts”，不能表述为“两位人类专家从头独立双标”。

## 最终医院系统级留出结果

| 主支付方式模型 | Accuracy | 固定六类 Macro-F1 |
|---|---:|---:|
| 固定字面规则 | **0.746** | **0.773** |
| Word TF-IDF Logistic | 0.493 | 0.372 |
| Character TF-IDF Logistic | 0.478 | 0.358 |
| Character Linear SVM | 0.522 | 0.403 |
| HPP-NLP hybrid | 0.672 | 0.551 |
| Rule-model cascade | 0.709 | 0.735 |

HPP-NLP 是最强的纯学习模型，但固定规则在主类别上仍然最好。论文不能声称学习模型全面超过规则。

| 层级任务 | 基线 | HPP-NLP |
|---|---:|---:|
| 十属性 Hamming accuracy | 0.854 | **0.891** |
| 十属性 micro positive F1 | 0.773 | **0.856** |
| 十属性 macro attribute F1 | 0.731 | **0.793** |
| 可计算性 Accuracy | 0.701 | **0.739** |
| 可计算性 Macro-F1 | 0.206 | **0.321** |

多标签属性识别是当前最有力的模型贡献。HPP-NLP 对 external reference 和 length of stay 的识别明显优于固定规则。Bundle/packaging、per diem、direct computability 和 unclear computability 的样本仍然不足。

## 可发表结论

最终产出不是单一黑箱分类器，而是一个可复现的层级混合管道：机制模板规范化、固定规则、词和字符 NLP 特征、多标签属性模型、可计算性模型、置信度拒识和人工复核。论文最稳健的创新是证明原始金额和服务代码会制造伪重复，并用医院系统级留出显示随机模板切分会高估泛化。

## 对外发布边界

GitHub 可以发布代码、134 条专家复核机制模板、来源 URL、文件哈希、下载说明、结果 JSON 和预测表。`data/raw/`、`.venv/` 和大型医院原始文件已通过 `.gitignore` 排除。正式发布前仍需由作者选择许可证，并确认期刊对数据与预印本仓库的要求。
