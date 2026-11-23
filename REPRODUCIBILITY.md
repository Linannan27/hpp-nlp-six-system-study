# Reproducibility protocol

## What the parser is

The parser is deterministic Python code, not a generative model or an external AI service. It reads the CMS v3 JSON and Tall CSV layouts and emits one aligned record for each hospital-payer-plan-item standard charge. The aligned schema contains hospital, source format, item description, setting, billing class, payer, plan, structured methodology, dollar amount, percentage, algorithm, generic notes, payer-specific notes, and a concatenated NLP text field.

For JSON, `src/audit_mrfs.py::parse_json` iterates in source order through `standard_charge_information`, `standard_charges`, and `payers_information`. For CSV, `src/audit_mrfs.py::parse_csv` reads the two metadata rows and then processes each data row with `csv.DictReader`. The model text is always assembled in the fixed order `algorithm | generic notes | payer-specific notes`. The structured methodology value is retained for descriptive comparison but excluded from model features.

## Deterministic mechanism templates

`src/prepare_expansion_annotation.py::canonical_template` applies the following ordered regular-expression replacements:

1. HTTP or HTTPS URLs become `URL`.
2. Revenue, procedure, and modifier identifiers become `Rev CODE`, `Proc CODE`, and `Mod CODE`.
3. Dollar amounts become `$NUM`.
4. Percentages become `NUM%`.
5. Remaining standalone numbers become `NUM`.
6. Repeated whitespace is collapsed.

Hospital identity remains part of the grouping key. Thus, repeated instances within one hospital collapse to a template, but identical text from different hospital systems remains separate for hospital-level holdout.

## Environment

- Python 3.9.6
- Dependency lock: `requirements-reproducible.txt`
- Model random seed: `20261028`
- Word TF-IDF: 1-2 grams, maximum 30,000 features, sublinear TF
- Character TF-IDF: character-within-word 3-5 grams, maximum 50,000 features, sublinear TF
- Classifier: class-balanced logistic regression, maximum 3,000 iterations for the primary comparison and 5,000 where specified for one-versus-rest tasks

## Inputs and integrity

`data/sources.json` records the public source URL, retrieval date, and SHA-256 hash for every analyzed file. The fictional CMS West Mercy file is marked as a parser fixture and is excluded from real-hospital performance estimates. Before reproduction, download each source to the local filename expected by the scripts and verify its hash. If a hospital has replaced the live file, use an archived copy matching the recorded hash or report the new version as a separate replication cohort.

## Minimal reproduction

From `nlp_price_poc`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-reproducible.txt
.venv/bin/python src/audit_mrfs.py
.venv/bin/python src/run_experiment.py
.venv/bin/python src/prepare_expansion_annotation.py
HPP_INPUT=annotations/human_expert_reviewed_template_labels.csv HPP_OUTPUT_PREFIX=final_human_reviewed_primary .venv/bin/python src/compare_models.py
.venv/bin/python src/compare_multilabel_attributes.py
.venv/bin/python src/compare_computability.py
.venv/bin/python src/run_end_to_end_stanford_case.py
.venv/bin/python -m unittest discover -s tests -v
```

The reproduction is successful only if the scripts finish without an unmatched-template or occurrence-count exception, the Stanford mapping completeness is 100%, and all seven tests pass.

## Principal outputs

- `data/derived/field_audit.json`
- `data/derived/normalized_payer_records.csv`
- `annotations/human_expert_reviewed_template_labels.csv`
- `results/final_human_reviewed_primary.json`
- `results/final_human_reviewed_multilabel.json`
- `results/final_human_reviewed_computability.json`
- `results/end_to_end_stanford_summary.json`
- `results/end_to_end_stanford_template_predictions.csv`
- `data/derived/stanford_enriched_text_records.csv`

## Verification anchors

The following SHA-256 values identify the core implementation and frozen label file used for the manuscript:

- `src/audit_mrfs.py`: `4e6373c5f5995f4a960dd99e99e459573687e84bf6984164539c8ab0108d22f2`
- `src/prepare_expansion_annotation.py`: `28468a8b16ef0c3520b7cd3595413a3ed94fb7c28a313120a241e35ec0a70bde`
- `src/compare_models.py`: `4a3dcc50e25f1c2eecf822acca25d0860e2564556398bb7e53e0fbc986a01cfb`
- `src/run_end_to_end_stanford_case.py`: `c73ae4d626c08b4db444ac0bfa10b0ad36265bfb9e7b9b2c89906cc091b04a12`
- `annotations/human_expert_reviewed_template_labels.csv`: `8d7cb7edd852176320d2fdbd70e2618cd7793bf5eaafc1173ee9a1c26128b8b7`

If any of these files changes, record a new hash and treat the run as a new analysis version.
