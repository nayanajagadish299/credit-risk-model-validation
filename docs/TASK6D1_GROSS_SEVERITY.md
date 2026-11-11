# Task 6D.1 — retrospective gross charge-off severity

## Purpose and interpretation

This study describes `GrossChargeOffAmount` for exact-row-deduplicated records whose September 30, 2026 snapshot status is CHGOFF. SBA's official [7(a)/504 FOIA dataset](https://data.sba.gov/dataset/7a-504-foia) links the [FOIA Data Dictionary workbook](https://data.sba.gov/sites/default/files/uploaded_resources/7a_504_foia_data_dictionary.xlsx). The dictionary describes GrossChargeOffAmount as total loan balance charged off, including guaranteed and non-guaranteed portions. It is a gross charge-off observation, not net loss, recovery-adjusted LGD, or EAD.

`GrossChargeOffAmount / GrossApproval` is named only the **gross charge-off-to-approval ratio**. Approval is not default-date exposure; this ratio is not LGD and must not be labeled or interpreted as LGD. The distribution reports count, sum, mean, median, quartiles and p90/p95/p99. Zero, negative, missing, invalid and above-approval amounts are explicitly counted; nothing is capped or silently removed. Distribution denominators distinguish all CHGOFF rows from records with observed finite amounts. Ratio denominators require finite nonnegative charge-off amount and positive finite approval amount.

## Comparisons

Severity is summarized by approval fiscal-year vintage, charge-off calendar year, two-digit NAICS, project state, and original gross approval bands (<$50k, $50k–<$150k, $150k–<$350k, and >=$350k). Groups below 30 CHGOFF records are suppressed from comparison tables; overall totals remain. The `vintage_by_chargeoff_calendar_year.csv` cross-tab keeps origination vintage separate from event calendar year. Approval-year counts do not represent equal follow-up exposure: recent vintages have younger loans and more right-censoring. Charge-off calendar year aggregates different vintages and loan ages.

## Data validation

The script verifies the expected source SHA-256, source row count and exact full-row deduplication rule used by the preceding project audits. It reconciles deduplicated CHGOFF rows and missing dates with previously observed totals. Date and amount checks include missing/invalid dates, charge-off before approval, charge-off after snapshot, reported approval FY versus approval-date mismatch, nonpositive/missing approval, negative/zero charge-off amount, guarantee outside its approval bounds, and gross charge-off amount above gross approval. Quality flags overlap and are not additive exclusions. Abnormal values remain visible in the aggregate flags and finite-value distributions.

## Bias and limitations

The source is a retrospective status snapshot, not a loan-level servicing panel or recovery history. CHGOFF-status selection conditions the analysis on a recorded terminal status and may omit unresolved records or loans hidden under other statuses. Amounts can be revised, and date completeness is imperfect. Recoveries, liquidation costs, guaranty claims/payments and cashflow timing are absent. Consequently the analysis cannot estimate net economic loss, LGD, EAD or expected loss. No borrower/lender identifiers or loan-level rows are written to outputs.

## Reproduction

Run tests with `python -m unittest discover -s tests -p 'test_task6d1_gross_severity.py' -v`. Run the audit using `python scripts/sba_task6d1_gross_severity.py --source <raw CSV> --out-dir <external output folder>`. Reports and manifest are aggregate-only; manifest contains source and report hashes, expected-count checks, group suppression counts and quality flags.

## Executed snapshot findings

For the September 30, 2026 source, checksum validation passed. The file contained 403,644 rows; exact-row deduplication removed 396, leaving 403,248 unique rows and 8,202 CHGOFF statuses. There were 11 missing charge-off dates. A finite gross charge-off amount was present in all 8,202 CHGOFF rows. Total gross amount was $1,099,161,613.40; mean $134,011.41; median $49,951.60; Q1 $22,026.08; Q3 $141,493.33; p90 $293,077.75; p95 $447,404.53; p99 $1,423,856.41.

All 8,202 had a valid descriptive gross charge-off-to-approval ratio under the stated denominator. Its mean was 0.86145. This is emphatically not LGD. Quality flags found 430 gross charge-off amounts above gross approval, 12 zero amounts, and 18 charge-off dates later than the snapshot date; values were retained and not winsorized or dropped. The 18 future-dated entries should be investigated against subsequent source revisions.

Approval-vintage median gross amounts were $69,134.69 (FY2020, n=1,590), $63,401.12 (FY2021, n=1,447), $48,815.10 (FY2022, n=1,953), $48,037.88 (FY2023, n=2,150), and $39,991.06 (FY2024, n=882); FY2025 had n=177. These differences are descriptive: newer cohorts have shorter time at risk, and the snapshot is right-censored. The separate event-calendar-year table must be used to inspect calendar timing; it is not interchangeable with approval vintage.

The verified aggregate run is stored outside the repository in `SBA_Project_Data\sba_task6d1_severity_output`. All manifest checks passed, and independently recomputed SHA-256 values matched every report hash. Four synthetic tests passed. Amounts above approval and future charge-off dates remain explicit quality concerns, not grounds for silent correction.
