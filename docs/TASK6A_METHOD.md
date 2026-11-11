# Task 6A — Contemporary SBA 7(a) approvals, FY2020–FY2026

## Purpose
Document original descriptive research on recent approvals from the September 30, 2026 SBA 7(a) FOIA source. This does **not** change or re-fit the historical frozen FY2010–2014 models.

## Inputs and safeguards
- Requires the **exact FY2020–Present as-of 2026-09-30 CSV** verified in the original audit by SHA-256.
- Reads original loan-level data locally and writes **aggregate-only** summaries into a separate output folder outside GitHub.
- Removes exact within-file duplicate rows, checks the snapshot date, reconciles the expected source row count, and reports invalid amounts/guarantees and fiscal-year/date discrepancies.
- Produces: `yearly_summary.csv`, `status_by_fy.csv`, `state_by_fy.csv`, `naics2_by_fy.csv`, `missingness_by_fy.csv`, and `task6a_manifest.json`.
- Status, state and sector group tables suppress cells with fewer than 10 loans; suppression may cause their displayed subtotals to be less than yearly totals.

## Interpretation
- **FY means SBA approval fiscal year**, not calendar year. FY2026 runs through September 30, 2026. Data are as of September 30, 2026; subsequent adjustments are not represented.
- `approved_total_usd` sums **GrossApproval** from positive, parsable amounts. It is not outstanding exposure or realised loss.
- `guaranteed_total_usd` sums SBA guaranteed approval for records with internally consistent positive approval/guaranteed amounts.
- `mean_guarantee_share` is the *unweighted* average of loan-level guarantee-share values among valid loans, not an amount-weighted ratio.
- Loan status is the **retrospective September 2026 snapshot status**; snapshot proportions are **not** default or 24-month charge-off rates. Follow-up is unequally mature across approval years.
- FY2025–FY2026 cannot be called fully observed 24-month outcome cohorts in September 2026.
- NAICS2 extracts the first two digits of the reported NAICS code; missing and invalid values are grouped.
- Point-in-time feature versions, changes in SBA programme policy, origination mix and record updates require separate review before causal or predictive interpretation.

## Next scientific stage
Task 6B will define a properly matured and audited shorter-horizon charge-off label (with event-date and competing-event treatment) and pre-register chronological training/evaluation splits. It must not reuse these snapshot status proportions as an outcome label.

Task 6C will separately audit whether actual recovery cash flows and default-date exposure balances are obtainable. Without them, direct LGD and EAD targets cannot be claimed.
