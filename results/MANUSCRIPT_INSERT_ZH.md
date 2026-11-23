# 可供论文修订使用的方法与初步结果草稿

> 注：以下文字只能作为“概念验证/开发性试验”。在完成人工双人标注和医院级外部验证前，不应将其写成已验证模型。

## Methods: Data sources and corpus construction

We conducted a public-data proof of concept using CMS template version 3.0 machine-readable files from three hospitals representing three health systems: Banner Churchill Community Hospital (Banner Health), Berger Hospital (OhioHealth), and Martha's Vineyard Hospital (Mass General Brigham). The fictional CMS West Mercy Hospital example was used only as a parser fixture and was excluded from real-world performance calculations. Files were retrieved on October 28, 2026, and source URLs and SHA-256 hashes were retained for reproducibility.

We implemented parsers for both the wide/tall-like CSV representation used by the selected hospitals and the nested JSON representation. Payer-level observations were normalized to a common schema containing hospital, payer, plan, care setting, billing class, negotiated dollar amount, negotiated percentage, structured methodology, algorithm text, generic notes, and payer-specific notes. The structured methodology field was treated as a weak reference label rather than a human-validated gold standard.

## Methods: NLP task and evaluation

The NLP input concatenated algorithm, generic-note, and payer-specific-note fields; the structured methodology field was never included as an input feature. A literal rule baseline detected fee-schedule, case-rate, per-diem, and percentage-of-charge cues. A multi-label attribute layer separately detected outlier/stop-loss, lesser-of, bundling/packaging, external reference, length-of-stay, and fixed-dollar cues. Exact duplicate text was collapsed within hospital and methodology before the primary evaluation to reduce pseudo-replication. Record-weighted metrics were calculated as a secondary analysis to quantify the effect of repeated expressions.

Because one recurrent case-rate expression began with the literal phrase “Fee schedule rate” but subsequently defined inlier reimbursement, an outlier threshold, and stop-loss logic, we added a compositional development rule that classified this conjunction as case rate. This rule was developed and evaluated on the same corpus and was therefore interpreted descriptively rather than as external validation.

## Results: Field availability and duplication

The three real files yielded 223,372 payer-level observations. Algorithm or note text was present in 38,203 observations (17.1%). After collapsing repeated hospital-expression-methodology tuples, only 166 uniquely labeled expressions remained. The reduction was especially pronounced for Banner Churchill Community Hospital, where 9,385 text-bearing observations corresponded to only two unique expressions with non-missing methodology labels. These findings indicate that random row-level train-test splitting would permit identical or near-identical expressions to occur in both partitions and substantially overstate generalization.

## Results: Literal baseline and contextual rule

Among 77 unique real-world expressions with a non-`other` structured methodology, literal keyword rules achieved 98.7% coverage, 15.8% accuracy among covered expressions, and a macro-F1 of 0.444 when abstentions were counted as errors. In contrast, record-frequency weighting produced 99.2% accuracy among covered observations, largely because a correctly classified percentage-of-charge expression was repeated 9,059 times. Thus, row-weighted accuracy obscured poor performance on distinct reimbursement expressions.

The most prominent baseline error involved 64 unique expressions labeled as case rate whose text began with “Fee schedule rate” and then described inlier reimbursement and outlier/stop-loss conditions. The contextual development rule correctly resolved these cases on the development corpus, increasing unique-expression macro-F1 to 0.917. This improvement should be interpreted as evidence supporting compositional clause analysis, not as a validated performance estimate.

## Results: Refining the `other` category

Among 89 unique expressions with structured methodology `other`, the multi-label layer detected fee-schedule/APC/base-rate cues in 75, fixed-dollar cues in 66, outlier/stop-loss provisions in 62, percentage-of-charge language in 21, bundling or packaging in 16, lesser-of provisions in 9, and external rule or pricer references in 6. Ten expressions contained more than one primary payment mechanism. Because attributes were nonexclusive, counts did not sum to 89. These results indicate that `other` is not a homogeneous residual class and support a hierarchical formulation consisting of a primary payment method plus conditional contractual attributes.

## Limitations paragraph

This proof of concept has four important limitations. First, the structured methodology field is a weak reference label and may not correspond to an independently adjudicated economic interpretation. Second, the corpus contains only three hospitals and cannot support national prevalence estimates. Third, the contextual rule was developed and evaluated on the same data. Fourth, an extracted payment mechanism does not necessarily determine the final allowed amount when external fee schedules, patient-level factors, or undisclosed contractual parameters are required. Formal validation should use a prespecified annotation guide, two independent annotators, agreement statistics, and leave-one-hospital-out testing on a larger multi-system corpus.

## Additional holdout result

We subsequently conducted a leave-one-hospital-out analysis at the unique-expression level. The three-hospital corpus exhibited severe class-support mismatch: percentage-of-charge expressions were absent from the training hospitals when Banner Churchill was held out, while case-rate, fee-schedule, and per-diem expressions were absent when Martha's Vineyard Hospital was held out. A character 3–5-gram multinomial naive Bayes classifier achieved pooled accuracy and macro-F1 of 0.000 across the three held-out folds. This negative result indicates that institution-specific language and nonoverlapping label support dominated the small corpus. The result should not be interpreted as evidence that all statistical NLP methods are ineffective; rather, it demonstrates that row-level random splitting is inappropriate and that broader multi-system sampling is required before supervised cross-hospital claims can be made.

## Exploratory two-agent annotation analysis

Two independent AI agents labeled 178 unique real-world expressions using a prespecified hierarchical guide while blinded to one another and to the hospitals' structured methodology fields. Initial disagreements revealed ambiguous definitions for percentage-of-charge attributes and computability. After the guide was revised and the two fields were independently relabeled, agreement for the primary payment method was 95.5% (Cohen's kappa 0.937), and the mean kappa across the primary method, ten attributes, and computability was 0.971. Fifteen expressions required AI adjudication. These labels are development annotations and must not be represented as a human-expert gold standard.

Using the agent-adjudicated development labels, the character n-gram model achieved pooled leave-one-hospital-out accuracy of 0.433 and macro-F1 of 0.283. Case-rate, per-diem, and hybrid F1 remained zero because each category was confined to a single hospital in this pilot. The revised result confirms that improved semantic labeling alone cannot overcome institution-level class-support gaps.
