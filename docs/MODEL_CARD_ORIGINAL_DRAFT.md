# SBA 7(a) Term-Free Credit-Risk Research Prototype — Model Card (Draft)

**Status:** frozen release candidate, **NOT production-ready**. Snapshot: 30 September 2026.

## Research question
Can fields observed in the SBA FOIA data be used to rank retrospective 120-month charge-off outcomes on a deliberately defined strict cohort? This is **not** a validated origination-time underwriting score.

## Cohort and design
- Input: `strict_train_fy2010_2014.csv.gz` (SHA-256 `13e721d4936831af585e439a874559a3f8108b5e96c59231d5e9c0805ad884da`).
- Model fitting: FY2010–FY2013, 164,628 loans (10,856 events).
- Development validation: FY2014, 45,888 loans (2,778 events).
- Models: B Extended Logistic Regression (benchmark); B Extended HistGradientBoosting (provisional champion).
- TermInMonths, term derivatives, BusinessAge, outcome dates, and terminal status not used as predictors.
- Preprocessing fit on FY2010–FY2013 only.

## FY2014 validation
| Model | PR-AUC/AP | ROC-AUC | Brier |
|---|---:|---:|---:|
| B_extended_no_term__LogisticRegression | 0.1061 | 0.6557 | 0.05587 |
| B_extended_no_term__HistGradientBoosting | 0.1099 | 0.6695 | 0.05571 |

## Significant limitations
1. All predictors are sourced from a retrospective public FOIA extract; approval-time data versions are not independently verified.
2. Eligibility for this strict research cohort depends on final status and term-validity rules, potentially producing selection bias even without term in the model.
3. FY2013/FY2014 results informed model selection; they are development validation, **not** a pristine prospective test.
4. FY2015–FY2016 results were already inspected earlier, so those years must not be described as untouched.
5. The HGB model underpredicts FY2014 overall events, and subgroup gaps exist. The current release is not sufficiently calibrated for operational decision-making.
6. The trained `.joblib` artifacts assume the engineered fields produced by `prepare_feature_frame` in `sba_task5d2_term_free_validation.py` (not raw SBA columns).

## Reproducibility & access
Full output manifest contains cohort hash, feature allowlist, package versions, model hashes, metric replication checks, and bitwise reloaded-prediction agreement. Raw borrower rows/predictions are not exported. Load `joblib` artifacts only from trusted sources.
