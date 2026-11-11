# Reproduction and verification guide — SBA 7(a)

## Canonical report and run policy

[`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md) is the canonical consolidated report. Authoritative Task 6A–6D.1 outputs and manifests are in the sibling `SBA_Project_Data` folder. Reviewed aggregate-only copies and verified contemporary frozen models are in the release candidate under `results/` and `models/`. This guide reproduces synthetic checks and, when explicitly requested, the aggregate Task 6D.1 sensitivity. It does not require model fitting or scoring.

Do **not** refit, retune, recalibrate or rescore the frozen Task 6C models to reproduce the published summary. The verified artifacts/manifests are the evidence. FY2024 is a later-year evaluation, not an untouched blind holdout.

## Data source and checksums

The local source is SBA’s [7(a) & 504 FOIA dataset](https://data.sba.gov/dataset/7a-504-foia), archived as of September 30, 2026. The Task 6A–6D.1 source file is `FOIA_7a_FY2020_Present_asof_260930.csv`, expected SHA-256:

`b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6`

Raw FOIA files and enriched or prediction-level rows must stay outside this repository. Do not export borrower identifiers or loan-level predictions to GitHub.

## What the aggregate manifests verify

- Task 5E.5 rebuilt the historical cohorts from the four FY1991–FY2020 source segments and matched the expected reference count: 322,566 loans / 21,262 charge-offs. The strict cohort count was 322,564 with 21,262 events. This is a cohort-count reproduction; it is not a full raw-source-to-frozen-model reproduction.
- Task 5E.1’s historical FY2010–FY2014 freeze records 164,628 training observations and 45,888 FY2014 validation observations, with model hashes and bitwise-identical reload predictions.
- Task 6A verifies 403,644 source rows, 396 exact duplicates and 403,248 unique FY2020–FY2026 records.
- Verified Task 6B reconciles 269,122 candidates, 233,692 eligible, 35,430 excluded, 1,349 positive and 232,343 negative outcomes. Its per-year cohort counts are in `sba_task6b_audit_output_verified\outcome_reconciliation_by_fy.csv`.
- Task 6C development and FY2024 evaluation manifests record source/model/report hashes, cohort counts and QA. The malformed FY2024 predictions archive is invalid and excluded from curated outputs. Do not read it as predictions or publish it.
- Task 6D.1 records 8,202 CHGOFF loans and the original severity summary. The separate strict as-of sensitivity has 8,173 dated-by-snapshot records; its manifest explains the 18 future-dated and 11 undated exclusions. The gross charge-off-to-approval ratio is not LGD.

See the authoritative output paths and report hashes in `TECHNICAL_REPORT.md` and `TASK6_PUBLICATION_AUDIT.md`; curated copies retain their source filenames inside task-specific `results/` subdirectories.

## Run applicable SBA synthetic tests

From the repository root in PowerShell:

```powershell
python -m unittest discover -s tests -p 'test_task6a_audit.py' -v
python -m unittest discover -s tests -p 'test_task6b_24m_cohort_audit.py' -v
python -m unittest discover -s tests -p 'test_task6c_24m_model_validation.py' -v
python -m unittest discover -s tests -p 'test_task6c2_freeze_evaluate.py' -v
python -m unittest discover -s tests -p 'test_task6d1_gross_severity.py' -v
python -m unittest discover -s tests -p 'test_task6d1_asof_sensitivity.py' -v
python -m unittest discover -s tests -p 'test_release_manifest.py' -v
```

These tests use synthetic data; they do not refit or rescore frozen models. Python syntax checks should compile the SBA scripts explicitly. Avoid a blanket compile/test command that includes out-of-scope workflows.

## Optional: reproduce only the aggregate as-of sensitivity

This command reads the verified source and writes aggregate-only reports to a **new** output directory. It does not alter the original Task 6D.1 output or model results:

```powershell
python .\scripts\sba_task6d1_asof_sensitivity.py `
  --source '..\SBA_Project_Data\FOIA_7a_FY2020_Present_asof_260930.csv' `
  --out-dir '..\SBA_Project_Data\sba_task6d1_asof_sensitivity_reproduction'
```

The script checks source SHA-256, source row count, exact-row deduplication, 8,202 CHGOFF records, 18 future-dated rows, the 11 undated zero-amount rows, nested populations, and output hashes. Review its manifest and CSVs after the command exits.

## Candidate release integrity

The candidate package is restricted by `tools/sba_release_allowlist.txt`. After approved documentation/code changes, refresh only that explicit allowlist and run the release validator:

```powershell
python .\tools\refresh_release_manifest.py --allowlist-file .\tools\sba_release_allowlist.txt
python .\tools\validate_release.py
```

The refresher rejects common raw/loan-level patterns and does not scan whole directories into the release. This step prepares checksums; it does not approve, commit or publish the release. The old report PDF is archived as a legacy file because no PDF renderer was available; it must not be distributed as the current report.

### Portable checksums for aggregate text reports

Scientific run manifests retain their original raw-byte SHA-256 values and provenance. These values are not rewritten to accommodate Git line-ending conversion. `results/portable_report_checksums.json` records those raw hashes alongside a separate portable SHA-256 for each of the 21 Task 6B, Task 6C and Task 6D.1 aggregate reports. The portable calculation replaces CRLF bytes with LF bytes only; all other bytes are hashed unchanged. A report passes after Windows-to-Unix line-ending conversion only when its normalized content matches the recorded portable hash. Any content change still fails verification.

Verify the curated reports with:

```powershell
python .\tools\verify_portable_report_checksums.py
```

Binary files, including frozen `.joblib` model artifacts, continue to use raw-byte SHA-256 checks against their freeze manifests. Do not refresh the portable report index as part of routine verification; regenerate a new reviewed index only when intentionally publishing changed aggregate reports, while preserving the original run evidence.

## Environment and licensing

The historical freeze recorded Python 3.10.2, numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, scipy 1.15.3 and joblib 1.4.2 (see `requirements.txt`). Dependencies keep their own licenses and notices. SBA describes the data resource as a U.S. Government Work. No repository code license has been selected; see the license recommendation in `TASK6_PUBLICATION_AUDIT.md`. Do not treat a future code license as applying to SBA data, third-party packages or trained model files.
