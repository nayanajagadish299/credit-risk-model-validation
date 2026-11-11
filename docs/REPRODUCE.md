# Reproduce the model from the existing VS Code project

Run commands in **PowerShell** with the existing `SBA_Project_Data` folder open. They assume the enriched cohort already exists in `sba_cohort_output_v2`. Do **not** point the script to the older `sba_cohort_output` because it lacks required underwriting fields.

```powershell
# From SBA_Project_Data, with this release candidate extracted to .\Project_A_5E2_GitHub_Release_Candidate
python -m pip install -r .\Project_A_5E2_GitHub_Release_Candidate\requirements.txt

# Refit the frozen models (does not open FY2015–2016)
$cohort = Resolve-Path ".\sba_cohort_output_v2\strict_train_fy2010_2014.csv.gz"
python .\Project_A_5E2_GitHub_Release_Candidate\scripts\sba_task5e1_model_freeze.py --input $cohort.Path --out-dir ".\sba_task5e1_reproduction_output"

# Verify the resulting manifest
(Get-Content .\sba_task5e1_reproduction_output\task5e1_manifest.json -Raw | ConvertFrom-Json).all_expected_checks_pass
```

The run trains Logistic Regression and HistGradientBoosting on FY2010–FY2013, then tests FY2014. Since the scripts live in one folder, `sba_task5e1_model_freeze.py` can import `prepare_feature_frame` and model definitions from `sba_task5d2_term_free_validation.py`.

### Environment
Official successful run: Python 3.10.2, numpy 2.2.6, pandas 2.3.3, scipy 1.15.3, scikit-learn 1.7.2, joblib 1.4.2. Exact dependency versions appear in `requirements.txt`. The exact cohort SHA-256 appears in `results/task5e1_manifest.json`.

### Privacy and data management
Never commit the raw FOIA CSVs, enriched train/test cohort, personal paths, per-loan predictions or borrower-level features. This repository includes only synthetic-independent aggregate results and curated model artifacts. Do not load serialized models from untrusted sources because joblib can execute code during deserialization.
