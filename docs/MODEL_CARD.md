# Model card — SBA 7(a) retrospective research prototype

**Status:** frozen development release candidate; **not production-ready**.
**Data snapshot:** September 30, 2026 public SBA FOIA extract.

## Intended use
Educational research in historical charge-off risk ranking, data quality, temporal validation, and model-governance methods. **Not intended for approval, denial, pricing, adverse-action, or other real-world credit decisions.**

## Training and selection
The final benchmark is Extended Logistic Regression; the primary model is Extended HistGradientBoosting. Fitting uses FY2010–2013 and development validation uses FY2014. A separate FY2013 forward-validation window was used during selection. FY2015–FY2016 is not untouched. Full details in `METHODOLOGY.md`.

| Metric | Logistic | HGB |
|---|---:|---:|
| FY2014 PR-AUC | 0.1061 | 0.1099 |
| FY2014 ROC-AUC | 0.6557 | 0.6695 |
| FY2014 Brier score | 0.0558695 | 0.0557123 |
| FY2014 predicted prevalence | 5.7275% | 5.6254% |
| FY2014 observed prevalence | 6.0539% | 6.0539% |

## Notable restrictions
Loan term, term derivatives, BusinessAge and outcome/status/date variables are absent from both fitted models. All included inputs have provisionally unverified approval-time versions. The cohort definition itself uses retrospective status/term logic; excluding the term predictor does not remove selection bias. The score is not calibrated sufficiently for loan-level decisions. See `OPEN_QUESTIONS.md`.

## Audit trail
See `results/task5e1_manifest.json` for input SHA-256, package versions, QA checks and model hashes, and `results/task5d3_paired_bootstrap.csv` for forward-year comparison uncertainty. The model artifacts are provided for reproducibility only. Never load an untrusted `.joblib`.
