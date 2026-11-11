# Methodology summary

## Data and target
The underlying dataset is a **30 September 2026 retrospective SBA FOIA snapshot**. The project uses a strict FY2010–2014 modeling cohort with a fixed 120-month charge-off label (`target_chargeoff_within_120m`). This label is retrospective and depends on definition-specific follow-up conditions. The strict sample selection is **not a representative origination-time loan population**.

The source-lineage audit and term-forensics investigation found a large difference in retrospective charge-off frequencies by term pattern, but an elapsed-time-to-charge-off matching hypothesis did not explain that difference. Loan term and all derived term features are excluded from the models retained here. This conservative choice avoids presenting the unexplained term signal as an approved origination predictor.

## Chronological development
- Model selection was informed by forward validation with FY2013 and FY2014.
- Frozen models fit FY2010–FY2013 (**164,628** loans, **10,856** charge-off events).
- Frozen models evaluate on FY2014 (**45,888** loans, **2,778** charge-off events).
- Transformations and imputers fit only on the corresponding training period, not the validation year.
- FY2015–FY2016 was inspected earlier during baseline work; it is **not** a pristine confirmatory set.

## Features in the frozen model
1. `log_gross_approval` (log-transformed GrossApproval)
2. `guarantee_share` (guaranteed approval / gross approval)
3. `initial_interest_rate`
4. `naics_sector` (2-digit NAICS prefix)
5. `project_state`
6. `business_type`
7. `processing_method`
8. `revolver_status`
9. `fixed_or_variable_interest_ind`
10. `collateral_ind`

Each of these retains **provisional** point-in-time provenance: a historical version of its value at loan decision has not been independently verified. The frozen models are therefore research prototypes, not validated underwriting predictors.

## Model comparison
Logistic Regression supplies the interpretable benchmark; HistGradientBoosting is the provisional primary candidate. The comparison uses ROC-AUC, average precision, Brier score, log loss and risk-decile calibration. In FY2014 the HGB PR-AUC advantage over Logistic Regression has a paired-bootstrap 95% interval spanning zero (150 replicates), while its ROC-AUC and Brier differences do not. A bootstrap based on validation observations only quantifies sampling uncertainty within this selected cohort.

## Calibration and limitations
The HGB predicted 5.6254% mean charge-off probability versus 6.0539% observed in FY2014; top-decile risk was 11.8829% predicted versus 12.9004% observed. Subgroup gaps remain. Scores should **not** be used for loan pricing, eligibility or regulatory decision-making.

## Reproducibility
Stored manifests contain input SHA-256 and environment versions; stored model files were verified against manifest SHA-256, and the official freeze run recorded bitwise-identical predictions after reloading. See `REPRODUCE.md` for the executable path.
