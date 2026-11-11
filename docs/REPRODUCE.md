# Reproduction guide — Windows / VS Code (PowerShell)

## What has actually been verified

The frozen Logistic Regression and HistGradientBoosting pipelines were trained using the existing **Task 4 enriched strict FY2010–2014 cohort**, and their FY2014 metrics and serialized model checksums were verified. This is **frozen-input reproducibility**, not proof of independently reproducible performance starting from the four original public SBA CSV files. FY2015–FY2016 results were inspected earlier and are not an untouched confirmatory test set.

The original loan-level CSVs and enriched loan-level data are kept outside this repository and excluded by `.gitignore`.

## 1. Check the published repository (no loan-level inputs needed)

Run from the cloned repository folder `credit-risk-model-validation`:

```powershell
python .\tools\validate_release.py
python -m compileall -q .\scripts .\tools
```

## 2. Refit the models with the *existing verified cohort* (optional)

The following commands assume a sibling analysis folder named `SBA_Project_Data`, as used during this project. Adjust only if your paths differ.

```powershell
python -m pip install -r .\requirements.txt
$cohort = Resolve-Path '..\SBA_Project_Data\sba_cohort_output_v2\strict_train_fy2010_2014.csv.gz'
python .\scripts\sba_task5e1_model_freeze.py --input $cohort.Path --out-dir '..\SBA_Project_Data\sba_task5e1_reproduction_output'
(Get-Content '..\SBA_Project_Data\sba_task5e1_reproduction_output\task5e1_manifest.json' -Raw | ConvertFrom-Json).all_expected_checks_pass
```

This *refits* the models and may take substantial compute time. **It is not necessary for a documentation-only update.** If your older `sba_cohort_output` exists, do **not** substitute that file: it lacks the required Task 4 underwriting fields.

## 3. Rebuild the enriched cohort from the source (documented, not independently revalidated)

Use the official September 30, 2026 SBA 7(a) FOIA snapshot. The original successful builder expects these **four** unmodified files in the analysis directory:

- `FOIA_7a_FY1991_FY1999_asof_260930.csv`
- `FOIA_7a_FY2000_FY2009_asof_260930.csv`
- `FOIA_7a_FY2010_FY2019_asof_260930.csv`
- `FOIA_7a_FY2020_Present_asof_260930.csv`

The original source SHA-256 values, expected row counts and cohort rules are recorded in `scripts/build_sba_cohort_enriched.py` and its generated `cohort_manifest.json`. This command would regenerate cohorts **outside the Git repository** and should only be run intentionally, not as part of the current release-documentation task:

```powershell
python .\scripts\build_sba_cohort_enriched.py --input-dir '..\SBA_Project_Data' --out-dir '..\SBA_Project_Data\sba_cohort_output_v2_rebuild'
```

Inspect the resulting `cohort_manifest.json`, cohort counts and original source SHA-256 values before accepting any rebuilt cohort. The script also emits later-year cohorts, but those are **not** needed for the FY2010–2014 model refit; do not open later-year outcome files for feature tuning.

### Important limitation: gzip byte-for-byte reproducibility

The cohort builder uses `gzip.open`, which may put creation-time metadata into `.csv.gz` files. Thus a fresh rebuild might contain logically identical table rows while yielding a different **compressed-file SHA-256**. The official `sba_task5e1_model_freeze.py` script *requires* the originally verified compressed-file SHA-256, so a freshly rebuilt cohort may be rejected even if the data are otherwise equivalent. **Do not bypass that check or claim end-to-end replication.** A future reproducibility pass should establish a deterministic gzip pipeline or compare canonical uncompressed data hashes, then separately assess the model metrics.

### Environment

The successful frozen-model run reported Python 3.10.2, numpy 2.2.6, pandas 2.3.3, scipy 1.15.3, scikit-learn 1.7.2 and joblib 1.4.2. Exact pinned package versions are in `requirements.txt`. The original validated cohort checksum is recorded in `results/task5e1_manifest.json`.

### Responsible release

Never commit raw FOIA source CSVs, enriched cohorts, per-loan predictions or private local paths. Only publish curated aggregate analyses and reviewed models. Load `.joblib` model files **only from trusted sources**, since deserialization can execute code.
