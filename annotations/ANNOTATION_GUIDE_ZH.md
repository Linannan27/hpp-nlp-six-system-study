# 支付方式表达双人标注手册 v1.1

## 标注原则

两位标注者先分别使用 `annotation_A_PILOT25.csv` 和
`annotation_B_PILOT25.csv` 完成同一组 25 条分层试标，只讨论标注规则并修订手册。手册冻结后，重新独立使用 `annotation_A_BLINDED.csv` 和 `annotation_B_BLINDED.csv` 标注全部样本。全程不讨论个别样本，不查看 `weak_reference_key_DO_NOT_GIVE_ANNOTATORS.csv`。

标注的对象是文本所表达的支付机制，不是医院原始结构化标签，也不是对合同最终支付额的法律或财务认定。

## `primary_method`

只填写下列一个值：

- `fee_schedule`：根据费用表、APC、DRG 权重/基础费率或其他预定表计算。
- `case_rate`：一次住院、病例或整个 episode 以固定或可计算的打包金额支付。可带 outlier。
- `per_diem`：按住院天数或每日费率支付。
- `percent_of_charge`：主要金额是总收费、账单收费或指定收费的百分比。
- `hybrid`：同一条表达中有两种以上主要方式，且无法视为单一方式的普通附加条件。
- `other_clear`：支付逻辑清楚，但不属于上述类别，例如单纯成本加成。
- `unclear`：文本只有理赔缺失说明、修饰符调整，或信息不足以确定主方式。

判定优先级：先看计价单位（每例/每日/收费百分比），再看基准表。`outlier`、`lesser-of` 和 `stop-loss` 通常是附加属性，不单独改变主方式。

## 属性字段

每个 `attr_*` 填 `1`（明确存在）、`0`（明确不存在）或 `U`（无法确定）。

- `attr_fee_schedule_reference`：引用 fee schedule、APC、DRG/base rate 等。
- `attr_case_rate`：存在每例/每次住院支付。
- `attr_per_diem`：存在每日费率。
- `attr_percent_of_charge`：若文本明确使用 billed charges、total charges 或收费额乘以百分比/成本收费比，且该计算会决定基础支付、支付上限、outlier 是否触发或 outlier 金额，标 `1`。因此 `billed amount × cost-to-charge ratio` 只要进入 outlier 支付算法也标 `1`。仅对未说明性质的 allowable/payment/fee-schedule amount 作百分比调整时标 `0`；无法判断百分比分母时标 `U`。
- `attr_fixed_dollar`：文本给出明确固定美元金额或上限。
- `attr_outlier_stop_loss`：存在 outlier、stop-loss 或超阈值附加支付。
- `attr_lesser_of`：存在 lesser-of/取较低值逻辑。
- `attr_bundle_packaging`：服务可能打包、packaged 或 conditional packaging。
- `attr_external_reference`：需要外部网址、政府 pricer、Medicare/Medicaid 规则或供应商发票。
- `attr_length_of_stay`：金额受住院天数/covered days 影响。

## `computability`

- `direct`：仅使用 `expression_text` 中的常数和同一 MRF 价格行已明确提供的字段，即可得到唯一的最终支付金额；不需要患者/理赔层面的收费额、LOS、数量、同日其他服务，也不需要查询其他费率表、网页或 pricer。
- `conditional_external`：支付公式和分支逻辑已足够清楚，但要得到最终金额，至少还需要一个当前 MRF 价格行未提供的运行时输入，例如 billed charges、LOS、服务数量、同日服务组合、最高费率状态，或外部 fee schedule/pricer 数值。取得这些输入后，公式原则上可执行。
- `not_computable`：当前文本缺少关键公式、参数或分支规则；即使允许补充通常可获得的外部输入，也不能唯一、稳定地推导支付金额。仅写“参见某网站/支付方法”而未提供操作公式时归入此类。
- `unclear`：连可计算性都无法从文本判断。

## `confidence`

填 `high`、`medium` 或 `low`。置信度不参与 kappa 的主统计，用于排定 adjudication 优先级。

## 边界例子

- `Fee schedule rate ... inlier reimbursement ... outlier threshold`：若文本明确整例 inlier 支付，标 `case_rate`；同时将 fee-schedule reference 和 outlier 标为 1。
- `96% of billed charges, capped at workers' compensation maximum`：主类别为 `percent_of_charge`；若上限需外部法定表，external reference 标 1。
- `There were no paid claims ...`：主类别为 `unclear`，computability 通常为 `unclear`。
- `lesser of $24,000 and 80% of charges`：主类别为 `hybrid`或 `percent_of_charge` 需看研究口径；v1.0 统一标为 `hybrid`，并将 fixed-dollar、percent-of-charge 和 lesser-of 标 1。
