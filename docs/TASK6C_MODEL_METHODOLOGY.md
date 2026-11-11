# Task 6C.1: contemporary 24-month charge-off model development

## Cohort and evaluation design

The script reuses `sba_task6b_24m_cohort_audit.classify` and requires exact reconciliation to the verified Task 6B counts before any fit: 269,122 candidates; 233,692 eligible; 1,349 positive; 232,343 negative. It writes a minimized, compressed model input outside the repository. Direct identifiers, event dates, statuses, and other excluded fields are not copied into that model input.

FY2020–2022 form training data. FY2023 is development validation. FY2024 is included only in the local minimized cohort table to preserve Task 6B's exact population counts; its outcomes are not selected, fit, tuned, feature engineered, loaded for scoring, or reported in this stage. FY2024 had already been inspected during cohort work and would not be a pristine blind holdout. The run stops before FY2024 evaluation.

## Features and leakage controls

The candidate allowlist is log gross approval; guaranteed-to-gross approval share; initial interest rate; two-digit NAICS; project state; business type; processing method; revolver status; fixed/variable indicator; and collateral indicator. These attributes can still be retrospectively updated, and their exact approval-time values are not independently verified. Results are therefore exploratory associations, not validated point-in-time underwriting predictions.

Term and term derivatives, BusinessAge, snapshot status, charge-off and paid-in-full dates, gross charge-off amount, first-disbursement date, follow-up/event time, JobsSupported, identifiers, and all other target-derived fields are excluded. First-disbursement and outcome fields are used only in Task 6B cohort construction, never as model predictors. Amount ratio/log transformations are deterministic and applied before fitting; missing-value imputers, scalers, and category encoders are inside sklearn pipelines fit only to FY2020–2022.

## Models

The baseline predicts the FY2020–2022 event prevalence for every FY2023 record. Regularized logistic regression uses L2 regularization (C=0.1), median/mode imputation, numeric standardization, and one-hot categories. The conservative HistGradientBoosting model uses the same train-fitted imputations/one-hot encoding, 100 iterations, at most seven leaves, 0.05 learning rate, L2=5, and minimum leaf size 80. No class weighting or oversampling is used. Random seed is 20261112. No hyperparameter search is performed.

## Evaluation and uncertainty

FY2023 reports average precision (PR-AUC), ROC-AUC, Brier score, log loss, mean predicted probability versus observed event prevalence, decile-style quantile calibration, and precision/recall at fixed thresholds 0.5%, 1%, 2%, and 5%. A 300-replicate bootstrap over FY2023 observations provides a descriptive 95% interval for average precision for fitted models. It measures sampling uncertainty in the selected FY2023 cohort; it does not establish significance or future transportability. Compare models against the prevalence baseline and avoid claims of material improvement without evidence.

## Selection and interpretation limits

Retrospective eligibility based on terminal status/date consistency and exclusion of cancelled/committed loans can induce selection bias. Missing first-disbursement dates are not treated as proof of no funding. The target is retrospective charge-off within 24 calendar months, not necessarily regulatory default. Calibration and ranking describe only this status-selected sample. There is no causal or prospective interpretation.

Artifacts, minimized input, and loan-level validation probabilities remain outside GitHub in `SBA_Project_Data\sba_task6c_development_output`; aggregate metrics and manifest are the review outputs. Do not evaluate FY2024 until model selection is reviewed and frozen.

## Task 6C.2 freeze and later-year evaluation

The provisional primary is the existing conservative HistGradientBoosting pipeline; the existing regularized Logistic Regression is the benchmark, and constant training prevalence is the reference. This decision uses FY2023 PR-AUC, Brier score and log loss only. Artifacts are hash-checked and captured in a freeze manifest before FY2024 labels are read for scoring. The evaluator never refits, tunes, recalibrates, or changes these artifacts. It confirms FY2024 has 60,114 eligible loans and 417 events, then scores all three approaches on that same set. FY2024 outcomes were previously inspected in aggregate during cohort audit; this is a later-year temporal evaluation, not a pristine blind test. Paired bootstrap intervals resample matched observations for the HGB-minus-logistic average precision difference; individual model intervals are not used as a difference test. Evaluation outputs, including loan-level scores, remain outside the repository.

Observed event prevalence rose from 0.3697% in training to 0.9475% in FY2023, then was 0.6937% in FY2024. The paired HGB-minus-logistic average-precision difference was 0.00432 (FY2023 paired 95% interval 0.00072 to 0.00932; 1,000 replicates, seed 20261113) and -0.00099 in FY2024 (paired interval -0.00243 to 0.00075). FY2024 AP was 0.01441 for HGB and 0.01540 for logistic; ranking performance declined from FY2023. HGB had lower FY2024 Brier/log loss than logistic, but its mean predicted prevalence (1.0315%) exceeded observed 0.6937%; logistic overpredicted more (2.3362%). The constant baseline predicts the training prevalence (0.3697%) and therefore underpredicts FY2024 prevalence. These later-year results are descriptive, not evidence of production suitability.

### Task 6C.3 prediction artifact disposition

Inspection found that `fy2024_predictions_local.csv.gz` held only three records, with NumPy arrays serialized inside individual CSV cells and truncated with ellipses. No aligned per-loan prediction arrays were retained in another verified artifact. The file is marked invalid in the evaluation manifest and excluded from curated outputs; it must not be used or published. The aggregate metrics, calibration, operating-point and paired-bootstrap reports and frozen model hashes remain unchanged. A regression test now rejects array-string prediction cells. The serializer has been corrected for any future run, but this cleanup did not rescore FY2024 or reconstruct predictions.
