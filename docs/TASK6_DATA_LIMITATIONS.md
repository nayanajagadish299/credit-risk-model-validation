# Project A — SBA data and interpretation limitations

## Snapshot and target construction

The source is a retrospective September 30, 2026 SBA 7(a) FOIA snapshot, not a longitudinal servicing ledger. Status, terminal dates, balances and amounts may reflect later revisions or inconsistent records. Task 6B therefore defines a fixed retrospective 24-calendar-month charge-off outcome using approval dates, date consistency, status and follow-up checks. The target is not necessarily equivalent to a regulatory definition of default.

Task 6B selects FY2020–FY2024 candidates, excludes cancelled and committed records under deterministic primary-exclusion rules, and handles paid-in-full outcomes as competing events. The resulting 233,692 eligible loans are a status- and data-quality-selected population. Missing FirstDisbursementDate is reported but is not treated as proof that a loan was never funded. Excluding cancelled/committed and unresolved or inconsistent cases can induce selection bias; the eligible population does not represent all approvals or necessarily all funded loans.

## Predictor timing and leakage

Snapshot fields are not guaranteed to be their approval-time versions. Task 6C excludes loan term and term derivatives, BusinessAge, snapshot status, terminal dates, charge-off amounts, first-disbursement and follow-up/event-time fields from predictors. Several included fields (approval amounts, guarantee share, initial interest rate, NAICS, state, business type, processing method, revolver/fixed-rate/collateral indicators) still have unverified point-in-time provenance. Retrospective availability, coding changes and missingness can create leakage or transportability problems even when explicit outcome fields are excluded.

## Temporal evaluation and calibration

FY2020–FY2022 are training years; FY2023 is development validation; FY2024 is the later-year evaluation. FY2024 outcomes were previously inspected in aggregate during cohort auditing, so FY2024 is not a pristine blind test. Model artifacts were frozen before scoring, and no tuning or recalibration followed. The performance drop between FY2023 and FY2024 is measured; its cause is not identified.

The positive class is rare. Average precision depends on prevalence, and precision at a threshold can remain low despite useful ranking. Quantile calibration is aggregate and bin-dependent; it does not establish subgroup calibration or future calibration. Mean predicted probabilities differ from observed prevalence, particularly on FY2024, and no prospective recalibration evidence is available. Bootstrap intervals quantify sampling uncertainty conditional on the evaluated cohort, not uncertainty about changing populations or outcome recording.

## Severity and financial meaning

GrossChargeOffAmount is a gross balance charged off, not recovery-adjusted net loss. GrossChargeOffAmount divided by GrossApproval is only a gross charge-off-to-approval ratio; approval is not exposure at default, and the ratio is never LGD. SBA source fields do not provide the recovery cashflows, expenses and timing needed for a defensible recovery-adjusted loss model or true EAD. Do not infer exposure from approval amount.

The source contains 18 CHGOFF records with ChargeOffDate after the declared snapshot and 11 without a ChargeOffDate. The strict as-of sensitivity excludes 29 records in total because undated records cannot be confirmed as occurring by the snapshot. The 11 missing-date cases have zero recorded gross charge-off amount. Original severity summaries remain intact; the sensitivity is a separate view. There are also 430 original gross charge-off amounts above GrossApproval (429 in the valid-date as-of population), retained as quality flags rather than corrected.

Approval-vintage differences mix cohort composition, loan age, time at risk, data updates and right-censoring. Charge-off calendar year combines different approval vintages. Neither view alone estimates causal vintage effects. CHGOFF-status selection excludes unresolved and other status classes and can bias severity distributions.

## Reproducibility and privacy

Raw source files, enriched cohorts and all row-level Task 6C outputs remain outside the Git repository. The release candidate contains only reviewed aggregate report copies and verified frozen model artifacts under `results/` and `models/`. The malformed FY2024 prediction serialization is invalid and excluded from the curated release; only aggregate metrics, calibration, operating-point and comparison reports are curated. Source and output checksums are available in Task 6B, Task 6C and Task 6D.1 manifests. Curated release copies are byte-for-byte checked against their source manifests where those manifests provide report hashes; review-time hashes are recorded for earlier outputs whose original manifests had no output hashes. Task 6A and Task 5E.5 manifests do not record per-output SHA-256 values; review-time digests are recorded in `TASK6_PUBLICATION_AUDIT.md` and should be recalculated if those reports are regenerated.

The SBA Open Data portal describes the FOIA resource license as U.S. Government Works. Source attribution and snapshot identification remain required research practice. No third-party code license is present in the repository at this review; select and add a code license before inviting reuse of the analysis code. Do not publish borrower-level source rows, identifiers or predictions.
