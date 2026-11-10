# SBA 7(a) Credit-Risk Analytics & Model Validation

**An independent financial data science project using publicly released SBA 7(a) FOIA data.**

The project studies portfolio outcomes, temporal cohort construction, credit-risk model experiments, feature provenance and an unusual loan-term/product pattern. The goal is a reproducible, carefully interpreted validation workflow—not a production lending model or a claim of causal effects.

## Data and evaluation design

- **Source:** Public SBA 7(a) FOIA loan data.
- **Snapshot used locally:** September 30, 2026.
- **Development split:** FY2010–FY2013 fit; FY2014 forward validation.
- **Locked test:** FY2015–FY2016 is intentionally unopened while feature and model decisions remain in development.
- Raw source files are maintained separately; this repository landing page does not distribute borrower-level data.

## Project status — 10 November 2026

### Completed analytical work

1. Public-data profiling and data-quality audits.
2. Fixed-horizon cohort construction and temporal split.
3. Baseline HistGradientBoosting model and model interpretation.
4. Task 4 feature enrichment and feature-provenance diagnostics.
5. Task 5A feature-set experiments A–F.
6. Task 5B exact-term/product-group anomaly audit.
7. Initial Task 5C adjusted analysis.

### Current work and next gates

- **Task 5C.1:** Run the corrected analysis. It retains all exact-term groups, uses observed-support term/revolver groups, reports the Unanswered business-age category and full Model C coefficients, and fits imputation statistics on FY2010–FY2013 only.
- **Task 5D:** Investigate product drivers and the Unanswered category; perform term-pattern ablation; compare Logistic Regression with HistGradientBoosting; inspect calibration by group; make final feature decisions.
- Confirm point-in-time availability and source definitions before freezing the feature set.
- Only after the feature/model freeze should the FY2015–FY2016 locked test be considered.

**Important:** The saved first-run Task 5C output is provisional. The corrected analysis package contains the rerun script; corrected results must be generated and checked before any Task 5C result is treated as final.

## Interpretation guardrails

- Odds ratios are not risk ratios.
- Statistical association is not causation.
- A strong term-related signal is a diagnostic finding, not proof of a product rule or data error.
- Do not use off-support predictions or unsupported term/revolver combinations as evidence.
- Point-in-time predictor availability must be confirmed before predictive claims.
- Do not report the locked test as evaluated until it has been deliberately opened after model freeze.

## Reference/reproduction distinction

A related public reference repository was inspected, but it uses a June 30, 2026 SBA snapshot. The local project uses the September 30, 2026 snapshot. The reference repository has not been independently cloned and run end-to-end; this work must not be described as an exact reproduction. Keep reference code separate and attribute any external methodology.

## Planned portfolio deliverables

- Reproducible cohort and analysis scripts.
- Pinned environment and automated tests.
- Model comparison and calibration tables.
- Feature timing/provenance register.
- Model card and technical validation report.
- A compact dashboard or demo after the analytical decisions are frozen.

## Technology

Python, pandas, NumPy, scikit-learn, statsmodels, SciPy, matplotlib, Git and GitHub.

## Author

Nayana Jagadish

**Focus:** Financial Data Science · Credit Risk Analytics · Model Validation · Business Analytics
