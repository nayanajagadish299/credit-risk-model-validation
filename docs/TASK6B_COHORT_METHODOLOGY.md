# Task 6B: retrospective 24-month cohort audit

## Target and population

The audit uses the September 30, 2026 FY2020-present SBA FOIA snapshot and considers approval fiscal years 2020–2024. The fiscal year reported by SBA must equal the year derived from `ApprovalDate` (October through September). A loan is mature only when its approval date plus 24 calendar months, with end-of-month dates clipped to the last valid day, is on or before September 30, 2026.

Among mature, internally consistent records, a dated `CHGOFF` is positive if its charge-off date is on or before the 24-month horizon and negative if later. A `PIF` with a valid date is treated as a competing event and as no charge-off by 24 months. `EXEMPT` with no terminal date is treated as event-free through the snapshot after maturity. Missing `ChargeOffDate` is not itself evidence of missing event data: it is expected for non-charge-off records. A charge-off status without a valid charge-off date, PIF without a valid paid date, both dates present, dates before approval/after snapshot, status/date contradictions, invalid/mismatched approval dates, and immature records are excluded and reported.

Cancelled and committed records, unknown/current statuses, and records without resolved terminal status are excluded and separately counted. The source is exact-row deduplicated for aggregate counting. FY-specific eligible, positive, negative, prevalence, exclusion, event-date consistency and candidate predictor missingness tables are written. Outputs contain aggregates only; no identifiers, rows, dates, or row hashes are emitted.

## Predictors and governance

Potential fields are approval amount, SBA guaranteed amount, initial interest rate, NAICS, project state, business type, processing method, revolver status, fixed/variable indicator, and collateral indicator. This is a missingness inventory only, not a model feature recommendation. The available retrospective snapshot does not independently establish that any value is the value known at approval. Loan term, BusinessAge, snapshot status, event dates, loss amounts, and all other outcome-derived fields are not predictors. Dates and status are used only for eligibility and outcome construction.

## Limitations

This is an approval-level retrospective snapshot, not a servicing panel. Status/date fields and predictor values may have been updated after origination; the resulting cohort and labels cannot establish prospective performance or point-in-time predictor availability. PIF creates a competing-event outcome rather than ordinary censoring for the binary cumulative-incidence target. `EXEMPT` records with no terminal event are only known to be event-free through the snapshot. Exclusions and source selection can induce bias. No model is trained in Task 6B.

Run from the repository with `python -m unittest tests/test_task6b_24m_cohort_audit.py`, then run the script with explicit `--input` and `--out-dir` paths. The script refuses a source checksum mismatch before producing outputs. Its expected checksum is the checksum previously recorded for the September 2026 snapshot; QA status is recorded in `task6b_manifest.json`.

## Final QA implementation

The audit emits `exclusions_by_fy.csv` with exactly one primary reason per excluded candidate. The deterministic precedence is: CANCLD; COMMIT; invalid approval date; invalid approval FY; reported/derived FY mismatch; outside candidate FY range; insufficient 24-month maturity; both terminal dates; invalid terminal date; terminal date before approval; terminal date after snapshot; CHGOFF without valid date; PIF without valid date; EXEMPT with terminal date; unresolved or unrecognized status. Overlapping issues are separately tabulated in `quality_flag_overlaps.csv` and are not summed as exclusions. Reconciliation tables assert candidates = eligible + excluded and eligible = positives + negatives by FY.

`FirstDisbursementDate` is reported by FY and snapshot status with missing, invalid, valid, before-approval, and after-snapshot counts. Its absence does not itself exclude a loan and is not proof that no disbursement occurred. Cancelled and committed records are excluded by status; this status-based selection may omit approvals and potentially undisbursed loans, so results describe a retrospectively selected status-defined cohort, not all approvals or verified funded exposure. No feature is independently proven to have its recorded value at approval; terminal dates/statuses, losses, term, and BusinessAge are not predictors. All emitted output is aggregate-only.
