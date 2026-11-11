# SBA 7(a) Credit-Risk Analytics and Model Validation

**Status:** Retrospective research prototype. Historical FY2010–2014 and contemporary FY2020–FY2024 modelling are separate experiments. The canonical final report is [docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md). Not approved for lending decisions. Raw FOIA records and loan-level cohorts/predictions are kept outside this repository.

## Research scope

Project A studies SBA 7(a) public FOIA data from a September 30, 2026 retrospective snapshot. It combines source and cohort audits, a historical fixed 120-month charge-off analysis, contemporary lending summaries, a separately constructed 24-calendar-month charge-off cohort, temporal model evaluation and gross charge-off severity descriptions.

The outcome is a retrospective recorded charge-off under each experiment’s documented eligibility rules. It is not necessarily regulatory default. Feature values in the administrative snapshot are not independently verified as the values available at loan approval. The models are not regulatory estimates of default probability, production scores or approved underwriting tools.

## Headline findings

### Historical FY2010–FY2014 experiment

The strict historical cohort contains 210,516 loans, with 13,634 charge-off events. Models fit FY2010–FY2013 (164,628 loans; 10,856 events) and validate on FY2014 (45,888 loans; 2,778 events; 6.0539% prevalence).

| FY2014 model | Average precision | ROC-AUC | Brier score |
|---|---:|---:|---:|
| Extended Logistic Regression | 0.106057 | 0.655737 | 0.055870 |
| Extended HistGradientBoosting | 0.109897 | 0.669537 | 0.055712 |

The paired FY2014 HGB-minus-logistic average-precision interval includes zero. A suspicious historical term association led to excluding term and term-derived features. FY2015–FY2016 outcomes were seen in earlier work, so they are not an untouched holdout.

### Contemporary SBA analysis

Task 6A verified 403,644 raw rows, 396 exact duplicates and 403,248 unique FY2020–FY2026 records. Total nominal approved amounts were $213,015,593,018. These are approval amounts, not disbursement, exposure or losses.

Task 6B’s FY2020–FY2024 24-month cohort reconciles 269,122 candidates to 233,692 eligible, 35,430 excluded, 1,349 positives and 232,343 negatives. FY2024 has 60,114 eligible loans and 417 positives. Charge-offs after the 24-month horizon are negatives for this fixed-horizon target. Cancelled, committed and unresolved records are subject to documented selection rules; the resulting eligible sample is not all SBA approvals or necessarily all funded exposure.

| Frozen model | FY | Average precision | ROC-AUC | Brier score | Mean predicted | Observed prevalence |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 2023 | 0.027965 | 0.789528 | 0.009443 | 0.014260 | 0.009475 |
| HistGradientBoosting | 2023 | 0.032280 | 0.788597 | 0.009271 | 0.008751 | 0.009475 |
| Logistic Regression | 2024 | 0.015398 | 0.760143 | 0.008191 | 0.023362 | 0.006937 |
| HistGradientBoosting | 2024 | 0.014408 | 0.735401 | 0.006925 | 0.010315 | 0.006937 |

HGB was selected provisionally on FY2023 development results. Logistic average precision was slightly higher on FY2024, while HGB had lower Brier and log loss. The paired FY2024 average-precision difference interval includes zero. FY2024 is a later-year temporal evaluation, **not a pristine blind holdout**, because aggregate FY2024 cohort counts had been reviewed earlier. Ranking changed across years; the cause is not identified. Rare positives, prevalence changes and population/feature drift limit precision, calibration and generalization.

Task 6D.1 found 8,202 CHGOFF records with total gross charge-off amount $1,099,161,613.40 (mean $134,011.41; median $49,951.60). The separate strict as-of set contains 8,173 records after excluding 18 future-dated and 11 undated records. The gross charge-off-to-approval ratio is descriptive only and **is not LGD**. Full statistics and QA evidence are in the canonical report.

## Leakage, calibration and use limits

Term and term derivatives, BusinessAge, snapshot status, outcome dates, gross charge-off amounts, identifiers and follow-up/event-time information are excluded from contemporary predictors. Imputers, scalers and encoders were fitted only on FY2020–FY2022. The remaining features do not have independently verified approval-time values. Retrospective selection, rare outcomes, temporal metric shifts, imperfect calibration and the malformed local FY2024 prediction serialization preclude individual lending use. That malformed archive is marked invalid and excluded from the curated release; do not use or publish it.

## Repository contents and reproduction

- `scripts/`: reviewed SBA audits and historical workflows.
- `tests/`: synthetic tests for cohort, model-output and release-integrity logic.
- `models/`: validated historical and contemporary frozen pipelines; load `.joblib` files only from trusted sources.
- `results/`: aggregate historical and curated Task 6A–6D.1 reports/manifests. Authoritative original runs remain under the sibling `SBA_Project_Data` directory; only reviewed aggregate copies and verified frozen model artifacts are included here.
- `docs/TECHNICAL_REPORT.md`: canonical consolidated report and local manifest/output references.
- `tools/sba_release_allowlist.txt`: explicit candidate release list; excludes raw data, row-level outputs and out-of-scope files.

Run `docs/REPRODUCE.md` for synthetic checks and safe aggregate reproduction instructions. No model retraining or rescoring is needed to review the completed analyses. The old PDF was archived because no PDF renderer is available; it is not a final copy of the canonical Markdown report.

SBA source attribution: [7(a) & 504 FOIA dataset](https://data.sba.gov/dataset/7a-504-foia), which identifies the resource as a U.S. Government Work. No repository code license has been selected; reuse terms remain unresolved.
