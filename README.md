# Hospital Price Expression NLP Six System Study

**Author:** Nan Li

This folder contains a reproducible six-hospital-system public-data study. The
final 134 mechanism-template labels were produced through independent
dual-agent annotation and adjudication, then reviewed and accepted without
changes by two human experts. This is an expert-reviewed AI-assisted label set,
not de novo independent human double coding. The fictional CMS example file is
used only as a parser fixture.

## Research question

CMS v3.0 already constrains `methodology` to an enumerated category. Can a
lightweight, transparent NLP layer refine records assigned to the broad
`other` category and recover co-occurring reimbursement provisions from the
free-text `algorithm` and notes fields without using methodology as a model
input?

## Data and design

- Real systems: Banner Churchill Community Hospital, Berger Hospital
  (OhioHealth), Martha's Vineyard Hospital, Orlando Health, Stanford Health
  Care Tri-Valley, and South Miami Hospital (Baptist Health South Florida).
- Synthetic parser fixture: CMS fictional West Mercy Hospital. It is excluded
  from real-world performance metrics.
- Final label: AI-assisted adjudication accepted without changes after review
  by two human experts. The structured CMS `methodology` field is used only as
  a weak reference and never as the model input or final gold label.
- Primary unit: unique hospital-system payment-mechanism template after
  amounts, percentages, URLs, and service-code instances are normalized.
- Model input: `standard_charge_algorithm`, generic notes, and payer-specific
  notes. The structured methodology field is never part of the input.
- CMS v3.0 methodology is an enum with valid values `case rate`, `fee
  schedule`, `percent of total billed charges`, `per diem`, and `other`.
  The research gap is the loss of detail within `other`, not the absence of a
  structured methodology field.

Full URLs, retrieval dates, and hashes are in `data/sources.json`.

## Reproduce

From this directory:

```bash
python3 src/audit_mrfs.py
python3 src/run_experiment.py
python3 src/build_annotation_packet.py
python3 src/leave_one_hospital_out.py
python3 src/adjudicate_agent_labels.py
python3 src/leave_one_hospital_out_agent_labels.py
python3 -m unittest discover -s tests -v
```

Prepare the non-destructive Orlando Health expansion packet:

```bash
python3 src/prepare_expansion_annotation.py
python3 src/preannotate_expansion.py
```

The expansion builder streams the 521 MB Baptist Tall CSV instead of loading it
into memory. It normalizes dollar amounts, percentages, revenue/procedure codes,
and modifiers before deduplication. This collapses 828,475 literal South Miami
strings to 32 payment-mechanism templates. Across all three expansion systems,
the human review packet contains 100 templates: Orlando 48, Stanford 20, and
South Miami 32.

`expansion_machine_preannotations_FOR_HUMAN_REVIEW.csv` is a convenience file,
not gold data. Every field is explicitly marked `NOT_HUMAN_REVIEWED` and must be
verified or changed by a human expert before model training or evaluation.
For independent human annotation, use `expansion_annotation_A_BLINDED.csv` and
`expansion_annotation_B_BLINDED.csv`; do not show either annotator the weak
reference or machine-preannotation file until both blinded sheets are complete.

Build the formal NLP baselines and the HPP-NLP hybrid model:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-model.txt
.venv/bin/python src/compare_models.py
```

Freeze the expert-reviewed labels and reproduce the final analyses with:

```bash
python3 src/freeze_human_reviewed_labels.py
HPP_INPUT=annotations/human_expert_reviewed_template_labels.csv \
  HPP_OUTPUT_PREFIX=final_human_reviewed_primary \
  .venv/bin/python src/compare_models.py
.venv/bin/python src/compare_multilabel_attributes.py
.venv/bin/python src/compare_computability.py
.venv/bin/python src/run_end_to_end_stanford_case.py
```

`human_expert_reviewed_template_labels.csv` records the review date, status,
and basis. Files carrying `FOR_HUMAN_REVIEW` are retained as provenance and
must not be used as the final model input.

`hpp_nlp_hybrid_logistic` combines word TF-IDF, character TF-IDF, ten fixed
reimbursement-pattern features, class-balanced logistic regression, and
confidence-based abstention. The script compares it with word/character
logistic regression, character Linear SVM, and fixed literal rules. It reports
both development-only stratified random cross-validation and the stricter
leave-one-hospital/system-out evaluation.

Main outputs:

- `data/derived/field_audit.json`
- `data/derived/normalized_payer_records.csv`
- `results/experiment_results.json`
- `results/unique_expression_predictions.csv`
- `results/PRELIMINARY_REPORT_ZH.md`
- `results/HOLDOUT_REPORT_ZH.md`
- `results/model_comparison_hospital_holdout.json`
- `results/model_comparison_hospital_holdout_predictions.csv`
- `results/MODEL_DEVELOPMENT_REPORT_ZH.md`
- `annotations/expansion_human_review.csv`
- `annotations/expansion_machine_preannotations_FOR_HUMAN_REVIEW.csv`
- `annotations/expansion_annotation_A_BLINDED.csv`
- `annotations/expansion_annotation_B_BLINDED.csv`
- `results/EXPANSION_TWO_SYSTEMS_REPORT_ZH.md`
- `annotations/ANNOTATION_GUIDE_ZH.md`
- `annotations/annotation_A_BLINDED.csv`
- `annotations/annotation_B_BLINDED.csv`
- `annotations/expansion_agent_adjudicated_labels_FOR_HUMAN_REVIEW.csv`
- `annotations/combined_agent_adjudicated_template_labels_FOR_HUMAN_REVIEW.csv`
- `annotations/EXPANSION_HUMAN_REVIEW_PRIORITY.csv`
- `annotations/human_expert_reviewed_template_labels.csv`
- `results/expanded_template_model_comparison.json`
- `results/expanded_multilabel_attribute_holdout.json`
- `results/expanded_computability_holdout.json`
- `results/final_human_reviewed_primary.json`
- `results/final_human_reviewed_multilabel.json`
- `results/final_human_reviewed_computability.json`
- `results/FINAL_HUMAN_REVIEWED_REPORT_ZH.md`
- `results/end_to_end_stanford_summary.json`
- `results/end_to_end_stanford_template_predictions.csv`
- `data/derived/stanford_enriched_text_records.csv`
- `results/END_TO_END_STANFORD_CASE_ZH.md`

After both annotators complete every required field, score agreement with:

```bash
python3 src/score_annotations.py \
  annotations/annotation_A_BLINDED.csv \
  annotations/annotation_B_BLINDED.csv \
  --output-dir results/annotation_scoring
```

## Interpretation guardrails

The contextual rule was developed and evaluated on the same small corpus. Its
score is descriptive and must not be presented as external validation. The
labels originated in two AI-agent annotations and AI adjudication. Two human
experts subsequently reviewed and accepted the labels without changes. The
paper must call them expert-reviewed AI-assisted labels, not two independent
de novo human annotations.

Random expression-level CV mixes institution templates across folds and is
reported only to quantify leakage. Leave-one-hospital/system-out is the primary
generalization design. The six-system study reduces the initial support gaps,
but per diem has only two templates and bundle/direct-computability examples
remain sparse. This is a multi-system development study, not nationwide
external validation.

The Stanford end-to-end case excludes all Stanford templates from training,
parses the official raw JSON, and maps predictions back to all 13,325
text-bearing payer records. Template-level metrics are the inferential result;
record-weighted metrics describe operational reach only because many source
records repeat the same contractual mechanism.
