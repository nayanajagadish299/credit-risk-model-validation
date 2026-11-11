# SBA 7(a) Credit-Risk Analytics and Model Validation

**Canonical technical report | Project A | 12 November 2026**
**Status:** Retrospective research prototype. The Markdown file is the canonical report. The prior PDF has been archived as a legacy copy and is not part of the release candidate; PDF regeneration is pending a renderer. No model is approved for lending decisions.

## Executive summary

Project A contains two distinct experiments on SBA 7(a) public FOIA data. The historical experiment studies retrospective charge-off within 120 months in a selected FY2010–FY2014 cohort. The contemporary experiment describes FY2020–FY2026 approvals and constructs a separate retrospective 24-calendar-month charge-off cohort for FY2020–FY2024, followed by frozen-model development and later-year evaluation. Their populations, horizons, source windows and metrics must not be combined.

The historical source-lineage work found a strong unexplained association between recorded term patterns and the historical outcome. Term and term-derived predictors were excluded from the frozen pipelines. Historical FY2014 average precision was 0.109897 for HGB and 0.106057 for Logistic Regression. The paired HGB-minus-logistic FY2014 average-precision interval included zero, so evidence for a PR-AUC advantage was uncertain.

In the contemporary study, the September 30, 2026 source contained 403,644 rows; exact-row deduplication left 403,248. Task 6B selected 233,692 eligible FY2020–FY2024 loans from 269,122 candidates, with 1,349 positives and 232,343 negatives. HGB was selected provisionally using FY2023 development results. On FY2024, Logistic Regression had slightly higher average precision and ROC-AUC, while HGB had lower Brier score and log loss. The paired FY2024 average-precision difference interval includes zero. This ranking change is descriptive; its cause is not established. FY2024 is a later-year temporal evaluation, not a pristine blind holdout, because its aggregate cohort counts had been reviewed earlier.

The severity study measured gross charge-off amounts, not net losses. The strict as-of sensitivity excludes 18 charge-offs dated after the snapshot and 11 charge-offs with no usable date. It therefore contains 8,173 records, compared with 8,202 in the original severity population. Gross charge-off divided by gross approval is only a descriptive ratio and is not LGD.

All research uses retrospective records. Eligibility depends on later status/date fields; feature values lack independently verified approval-time versions; positive outcomes are rare; and calibration and temporal performance are imperfect. The models are not regulatory estimates of default probability and should not be used for approval, denial, pricing or other lending decisions.

## 1. Research questions and data

The project asks:

1. How do data cleaning, target definitions and eligibility rules change the observed SBA charge-off population?
2. In a defined historical cohort, do non-term features rank later recorded charge-offs, and how stable are the results across forward fiscal years?
3. In the contemporary FY2020–FY2024 cohort, how do frozen Logistic Regression and HistGradientBoosting models compare on FY2023 development and FY2024 later-year evaluation?
4. What can the snapshot support about gross charge-off severity, and how sensitive are summaries to records dated after or not dated by the September 30, 2026 snapshot?

The source is SBA’s [7(a) & 504 FOIA dataset](https://data.sba.gov/dataset/7a-504-foia) and associated [data dictionary](https://data.sba.gov/sites/default/files/uploaded_resources/7a_504_foia_data_dictionary.xlsx). The contemporary file used here is `FOIA_7a_FY2020_Present_asof_260930.csv`, with SHA-256 `b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6`. SBA identifies the dataset as a U.S. Government Work and updates it periodically. The data are an administrative retrospective snapshot, not an immutable origination-time or servicing history.

## 2. Source audits and historical cohort construction

### 2.1 Historical FY2010–FY2014 experiment

The historical source audit covered 243,525 FY2010–FY2014 rows. It removed 799 exact duplicate excess rows, leaving 242,726 unique records. The strict historical modeling cohort contained 210,516 loans and 13,634 charge-offs under the fixed 120-month target. The model split is FY2010–FY2013 training (164,628 loans; 10,856 events) and FY2014 development validation (45,888 loans; 2,778 events, 6.0539% prevalence).

Task 5E.5 independently rebuilt the historical cohort outputs from the four source files and reconciled the reference population to 322,566 records and 21,262 charge-offs. The strict comparison cohort had 322,564 records with the same 21,262 charge-offs. This verifies cohort count reconciliation; it does not establish byte-for-byte raw-source-to-model reproducibility or fix the point-in-time provenance limitation. A separate source-lineage analysis compared approval-date and first-disbursement-date origins. Its detailed aggregate output is not included in the curated release package, so this report makes no numerical claim about the extent of label disagreement; the exercise nevertheless motivates explicit target-origin documentation.

### 2.2 Term anomaly investigation and leakage controls

A historical forensic review identified a large, unexplained association between recorded loan-term patterns and the retrospective outcome. The supporting loan-level diagnostic tables are not part of the curated aggregate release, so this report does not publish the unverified subgroup rates or event-timing percentages. The anomaly was treated as a leakage and source-lineage warning, not as evidence of a causal relationship or proof that the recorded term was fixed at origination.

The frozen historical models therefore omit `TermInMonths`, derived term indicators, and `BusinessAge`, as well as terminal status and outcome dates. The ten historical features are log gross approval, guarantee share, initial interest rate, two-digit NAICS, project state, business type, processing method, revolver status, fixed/variable indicator and collateral indicator. Their exact approval-time values are not independently verified. This conservative exclusion policy reduces direct leakage risk but does not establish all retained fields as valid point-in-time predictors.

## 3. Historical FY2010–FY2014 model results

The historical comparison used Logistic Regression as a benchmark and HistGradientBoosting as a flexible alternative. On FY2014:

| Model | Average precision | ROC-AUC | Brier score | Log loss | Mean predicted | Observed prevalence |
|---|---:|---:|---:|---:|---:|---:|
| Extended Logistic Regression | 0.106057 | 0.655737 | 0.055870 | 0.219973 | 5.7275% | 6.0539% |
| Extended HistGradientBoosting | 0.109897 | 0.669537 | 0.055712 | 0.218361 | 5.6254% | 6.0539% |

A paired bootstrap with 150 replicates estimated the FY2014 HGB-minus-logistic average-precision difference at 0.003508 (95% interval -0.000433 to 0.007467), which includes zero. The ROC-AUC difference was 0.013865 (95% interval 0.008808 to 0.018604); the Brier difference was -0.000153 (95% interval -0.000221 to -0.000066). These resampling intervals describe uncertainty within the selected validation sample only.

The historical HGB top-decile prediction averaged about 11.88%, compared with about 12.90% observed. FY2013 and FY2014 were development years used in model selection; FY2015–FY2016 outcomes were viewed in earlier baseline work. None is a pristine confirmatory test. The source data and selection process also preclude interpreting these scores as prospective, calibrated probabilities for applicants.

## 4. Contemporary FY2020–FY2026 descriptive audit (Task 6A)

Task 6A verified 403,644 source rows, 396 exact duplicate excess rows and 403,248 unique records across FY2020–FY2026. Total nominal approved amount in the yearly summary was **$213,015,593,018**. FY2020–FY2026 record counts were 42,205; 51,758; 47,624; 57,324; 70,211; 78,025; and 56,101. FY2025–FY2026 loans had less than 24 months of possible follow-up at the snapshot boundary, so these approval and status summaries are not fixed-horizon charge-off rates. Gross approval sums are not disbursement, outstanding balance, loss or EAD.

## 5. Task 6B: retrospective 24-month cohort

The Task 6B target is a recorded charge-off within **24 calendar months** after approval, assessed from the September 30, 2026 retrospective snapshot. Approval fiscal years are reconciled to approval dates; only cohorts with the required calendar follow-up are eligible. Paid-in-full is treated as a competing terminal event. Charge-off dates, paid-in-full dates and status fields are used for eligibility and outcome construction only. Cancelled, committed, unresolved and inconsistent records are handled under the manifest’s mutually exclusive exclusion priority. Missing FirstDisbursementDate is reported but is not, by itself, an exclusion.

This is a retrospective charge-off outcome, not necessarily a regulatory definition of default. Charge-offs after the 24-month horizon are negative for this fixed-horizon label; 6,645 later charge-offs were accounted for as negatives. FY2020–FY2024 counts reconcile as follows:

| Approval FY | Candidate | Eligible | Positive | Negative | 24-month prevalence |
|---:|---:|---:|---:|---:|---:|
| 2020 | 42,205 | 36,440 | 79 | 36,361 | 0.2168% |
| 2021 | 51,758 | 45,146 | 96 | 45,050 | 0.2126% |
| 2022 | 47,624 | 41,756 | 281 | 41,475 | 0.6730% |
| 2023 | 57,324 | 50,236 | 476 | 49,760 | 0.9475% |
| 2024 | 70,211 | 60,114 | 417 | 59,697 | 0.6937% |
| **Total** | **269,122** | **233,692** | **1,349** | **232,343** | **0.5773%** |

The candidate pool differs from the raw 403,248 unique FY2020–Present rows because it is limited to the FY2020–FY2024 approval candidate cohorts. Of 35,430 candidate exclusions, 35,399 are CANCLD or COMMIT exclusions; the remainder are other date, maturity, status and consistency exclusions. This eligibility definition induces selection: excluded cancelled/committed and unresolved loans can differ systematically from eligible loans, and eligible status does not prove a funded or outstanding exposure.

## 6. Task 6C: contemporary model development and FY2024 evaluation

### 6.1 Development design and leakage prevention

FY2020–FY2022 were training years (123,342 eligible observations; 456 positives; 0.3697% prevalence), FY2023 was development validation (50,236; 476 positives; 0.9475%), and FY2024 was reserved for later-year evaluation (60,114; 417 positives; 0.6937%). The fitted pipelines and preprocessing were frozen before FY2024 scoring. FY2024 cohort counts had previously been inspected; FY2024 is therefore not a pristine blind holdout.

The feature allowlist contains log gross approval, guaranteed-to-gross approval share, initial interest rate, NAICS-2, project state, business type, processing method, revolver status, fixed/variable indicator and collateral indicator. Term, term-derived fields, BusinessAge, snapshot status, charge-off and paid-in-full dates, gross charge-off amount, first-disbursement and follow-up/event-time information, identifiers and other outcome-derived variables are excluded. Imputers, scalers and encoders were fitted only on FY2020–FY2022. The Task 6C manifest flags every retained predictor as lacking independently verified approval-time provenance.

The prespecified comparison uses a constant training-prevalence reference, L2 Logistic Regression (C=0.1) and conservative HistGradientBoosting (100 iterations, at most 7 leaves, learning rate 0.05, L2=5, minimum leaf size 80); no oversampling or class weights were used. The existing HGB was selected provisionally using FY2023 average precision, Brier score and log loss; the existing Logistic Regression remained the benchmark. No post-freeze refit, retuning, recalibration or rescore was performed for this report.

### 6.2 Development and temporal evaluation metrics

| Model | FY | Average precision | ROC-AUC | Brier | Log loss | Mean predicted | Observed prevalence |
|---|---:|---:|---:|---:|---:|---:|---:|
| Constant training prevalence | 2023 | 0.009475 | 0.500000 | 0.009419 | 0.056732 | 0.003697 | 0.009475 |
| Logistic Regression | 2023 | 0.027965 | 0.789528 | 0.009443 | 0.049701 | 0.014260 | 0.009475 |
| HistGradientBoosting | 2023 | 0.032280 | 0.788597 | 0.009271 | 0.048441 | 0.008751 | 0.009475 |
| Constant training prevalence | 2024 | 0.006937 | 0.500000 | 0.006899 | 0.042526 | 0.003697 | 0.006937 |
| Logistic Regression | 2024 | 0.015398 | 0.760143 | 0.008191 | 0.048098 | 0.023362 | 0.006937 |
| HistGradientBoosting | 2024 | 0.014408 | 0.735401 | 0.006925 | 0.039990 | 0.010315 | 0.006937 |

In FY2023, HGB had higher average precision and slightly better Brier/log loss than Logistic Regression; ROC-AUC was nearly tied and slightly favored logistic. The paired FY2023 HGB-minus-logistic average-precision difference was 0.004315 (95% interval 0.000716 to 0.009324; 1,000 matched-observation bootstrap replicates, seed 20261113). In FY2024, Logistic Regression’s average precision exceeded HGB by 0.000989, while HGB had better Brier and log loss. The paired HGB-minus-logistic FY2024 difference was -0.000989 (95% interval -0.002428 to 0.000747; 1,000 replicates, same seed), which includes zero.

The ranking change has no established single cause. Observed prevalence changed from 0.3697% in training to 0.9475% in FY2023 and 0.6937% in FY2024. Cohort composition, changing feature/outcome relationships, and sampling variation among rare positives are plausible contributors; this analysis does not identify their separate effects. Average precision is prevalence-sensitive. At these event rates, even a model that ranks some positives toward the top can produce many false positives and low precision. In FY2024, HGB’s top quantile averaged 3.568% predicted versus 1.676% observed; logistic’s top quantile averaged 10.969% versus 1.863% observed. At the 1% score cutoff, FY2024 precision/recall was 1.36%/66.19% for HGB and 1.21%/90.17% for logistic. These are descriptive operating-point summaries, not recommended lending thresholds.

The HGB and logistic models must not be used for lending decisions. Their training targets are retrospective snapshot outcomes, eligibility conditions on future status and consistency, and candidate features lack independent point-in-time versions. Validation is limited to one development year and one later year in a selected sample, performance shifted between those years, calibration is imperfect, and no prospective, causal, fairness or regulatory validation was conducted. The fixed-horizon charge-off target is not a regulatory definition of default probability.

### 6.3 Prediction artifact publication status

The FY2024 loan-level prediction archive contains three rows of truncated NumPy array strings, not aligned scalar predictions. The evaluation manifest marks it invalid and excluded from curated outputs. No individual predictions are reconstructed or published. The curated outputs are aggregate model metrics, quantile calibration, operating points, paired bootstrap and FY2023/FY2024 comparison tables.

## 7. Task 6D.1: gross charge-off severity

The original severity audit includes 8,202 exact-row-deduplicated CHGOFF-status loans. All 8,202 have valid nonnegative GrossChargeOffAmount and valid descriptive gross charge-off-to-approval ratios. SBA's data dictionary describes GrossChargeOffAmount as the loan balance charged off, including guaranteed and non-guaranteed portions; it is not recovery-adjusted economic loss.

| Gross charge-off amount statistic | Original population |
|---|---:|
| Total | $1,099,161,613.40 |
| Mean | $134,011.41 |
| Median | $49,951.60 |
| Q1 / Q3 | $22,026.08 / $141,493.33 |
| P90 / P95 / P99 | $293,077.75 / $447,404.53 / $1,423,856.41 |
| Mean gross charge-off-to-approval ratio | 0.86145 |

The original audit flagged 430 charge-off amounts above GrossApproval, 12 zero amounts, 11 missing charge-off dates and 18 dates after the declared snapshot. Values were retained, not capped. Task 6D.1 outputs also stratify by approval fiscal year, charge-off calendar year, NAICS-2, project state and original approval-size band; small comparison groups are suppressed at the documented minimum n. Approval-vintage severity reflects unequal time at risk and right-censoring. GrossChargeOffAmount is not recovery-adjusted net loss. GrossApproval is not exposure at default, and their ratio is **not LGD**.

### 7.1 Separate strict as-of sensitivity

The sensitivity uses the same source and deduplication rule but separately reports (a) the original Task 6D.1 population, (b) a bridge removing only the 18 future dates, and (c) a strict as-of population with valid ChargeOffDate no later than 2026-09-30. The 11 missing-date loans cannot be proven to fall within the snapshot window, so the strict set excludes them as well.

| Population | N | Total | Mean | Median | Q1 | Q3 | P90 | P95 | P99 | Mean ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Original Task 6D.1 | 8,202 | $1,099,161,613.40 | $134,011.41 | $49,951.60 | $22,026.08 | $141,493.33 | $293,077.75 | $447,404.53 | $1,423,856.41 | 0.86145 |
| Remove only 18 future dates | 8,184 | $1,095,771,542.93 | $133,891.93 | $49,951.13 | $22,023.37 | $141,515.23 | $293,056.56 | $446,910.36 | $1,420,436.90 | 0.86142 |
| Strict as-of, valid date ≤ 2026-09-30 | 8,173 | $1,095,771,542.93 | $134,072.13 | $49,967.51 | $22,112.18 | $141,704.41 | $293,392.03 | $447,165.99 | $1,420,895.62 | 0.86258 |

Removing the future-dated records reduces gross amount total by $3,390,070.47. The 11 undated records have zero recorded gross charge-off amounts, verified by the sensitivity QA; removing them therefore reduces the denominator from 8,184 to 8,173 without changing the total, increasing the amount mean and mean ratio. The original severity results remain unchanged. The strict subset retains 429 above-approval amounts and one zero amount. This sensitivity is a data-boundary analysis, not a correction of the original report.

## 8. Limitations and financial interpretation

- **Retrospective selection:** Task 6B eligibility uses future status/date information; cancellation, commitment and unresolved-record exclusions can change the population. Findings do not generalize automatically to all SBA approvals or funded loans.
- **Feature provenance:** recorded administrative features are not proven to be the values available at approval. Excluding obvious post-outcome fields prevents direct leakage but does not establish point-in-time validity of the remaining predictors.
- **Rare outcomes and temporal instability:** only 1,349 of 233,692 eligible contemporary loans are positive (0.5773% overall). Precision is constrained by low prevalence, uncertainty is substantial for relatively small event counts, and performance changed from FY2023 to FY2024.
- **Calibration and transportability:** aggregate quantile bins and bootstrap intervals are sample-conditional. They do not validate subgroup calibration, future calibration or deployment suitability.
- **Gross severity is not loss given default:** recovery cash flows, their timing, expenses and default-date balance are not established by these source fields. This report makes no LGD, EAD, expected-loss or causal estimate.
- **Snapshot anomalies:** future-dated and missing terminal dates require separate reporting. They are not silently imputed or removed from the original published summaries.
- **Reproducibility:** manifests verify selected source and report hashes, and Task 5E.5 reproduces cohort counts. An end-to-end raw-source-to-historical-model performance reproduction is not fully established; compressed gzip metadata can prevent byte-identical cohort hashes even when decoded rows match.

## 9. Contributions and further research

The project’s contributions are an auditable checksum and deduplication workflow; independent cohort count reconciliation; explicit competing-event and fixed-horizon target rules; temporal model splitting; paired comparison uncertainty; leakage controls; disclosure of approval-time provenance gaps; separate accounting for outcome timing versus approval vintage; and financial interpretation that keeps gross charge-off amounts separate from exposure and recovery-adjusted loss concepts. These are methodological contributions; claims about predictive usefulness remain conditional on this retrospective sample.

Next research should prioritize genuinely historical approval-time feature snapshots, an independently sourced and mature temporal cohort, a transparent accounting of cancelled/committed/undisbursed selection, and an external prospective validation design. Do not respond to current uncertainty by tuning on FY2024 or altering frozen artifacts. The contemporaneous reports do not test causality, regulatory default, fairness, or operational utility.

## 10. Reproducibility and audit trail

Raw FOIA data, enriched cohorts and loan-level predictions remain outside the repository. The authoritative aggregate runs are under `..\SBA_Project_Data`; reviewed aggregate-only copies and verified contemporary frozen model artifacts are in this release candidate under `results/` and `models/`. Reproduction instructions are in [`REPRODUCE.md`](REPRODUCE.md):

| Experiment | Verified external output | Curated repository copy |
|---|---|---|
| Historical model freeze | `sba_task5e1_model_freeze_output\task5e1_manifest.json` | `results/task5e1_manifest.json`; `results/task5e1_frozen_model_metrics.csv` |
| Independent Task 5E.5 cohort reconciliation | `sba_cohort_output_v2_rebuild_5e5\cohort_manifest.json`; `cohort_counts_by_fy.csv`; `quality_flags.csv` | Historical count evidence is summarized above; loan-level cohorts stay outside the release |
| Task 6A descriptive audit | `sba_task6a_output\task6a_manifest.json`; yearly/status/state/NAICS/missingness CSVs | `results/task6a/` |
| Task 6B cohort QA | `sba_task6b_audit_output_verified\task6b_manifest.json`; outcome, exclusion, quality-flag and disbursement CSVs | `results/task6b_verified/` |
| Task 6C development | `sba_task6c_development_output\task6c_manifest.json`; metrics, calibration and operating-point CSVs | `results/task6c_development/`; sanitized aggregate manifest excludes loan-level prediction-file hash |
| Task 6C freeze and FY2024 evaluation | `sba_task6c_fy2024_evaluation\model_freeze_manifest.json`; `evaluation_manifest.json`; comparison, calibration, operating-point and bootstrap reports | `results/task6c_fy2024_evaluation/`; invalid prediction artifact not copied |
| Task 6D.1 severity | `sba_task6d1_severity_output\task6d1_manifest.json`; distribution, ratio, vintage/calendar, reconciliation and quality CSVs | `results/task6d1_severity/` |
| Task 6D.1 strict as-of sensitivity | `sba_task6d1_asof_sensitivity\task6d1_asof_sensitivity_manifest.json`; comparison and quality CSVs | `results/task6d1_asof_sensitivity/` |

The SBA’s public data attribution is linked above. Repository source-code licensing has not been selected. No new PDF is supplied: no Markdown-to-PDF renderer was available in the reviewed environment. The old PDF is archived under `docs/archive/` and must not be presented as matching this report.
