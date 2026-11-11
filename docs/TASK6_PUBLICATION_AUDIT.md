# Project A — Task 6 publication and release audit

## Scope and decision

This audit covers SBA research only. It does not cover the separate mortgage data pilot. No commit, push, model retraining or rescoring was performed. The Task 6D.1 original outputs and frozen model files remain unchanged. The new as-of sensitivity is aggregate-only and stored outside the repository.

## Verified integrity checks

| Check | Result | Evidence |
|---|---|---|
| Contemporary source checksum | PASS | SHA-256 `b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6`; 403,644 rows, 396 exact duplicates |
| Task 5E.5 independent reference cohort counts | PASS | 322,566 reference records and 21,262 events match expected audit counts; strict cohort 322,564 records, same 21,262 events |
| Historical frozen model artifacts | PASS | Logistic `754906c56945136b9b559aa14f11a76155847f767a3abb67f7d5b7ca1fc9d9`; HGB `fefdcc3268ba8ea8fdfa269df6ca7d026d45500f5c405e4c13a404ab2ef147c9`; hashes match historical freeze manifest |
| Task 6B verified cohort | PASS | Candidate/eligible/excluded 269,122/233,692/35,430; positive/negative 1,349/232,343; yearly rows reconcile |
| README and canonical report headlines | PASS | Historical metrics, Task 6A totals, Task 6B equations, FY2023/FY2024 average precision and severity sensitivity values cross-checked against released aggregate CSVs |
| Task 6C model artifact hashes | PASS | HGB `5cfdc0947fe45755eeb09f5ea6384c4e5e117e7ac65c3c6e096e1c685dfb3231`; logistic `53a7cbfeb26ec64dc679e17b7f8dead3204087bd1b4ff4e11366dea721324e95`; independently recomputed from development output |
| Task 6C development report hashes | PASS | All six files listed in `task6c_manifest.json`, including model artifacts, match computed SHA-256 |
| Curated Task 6C development outputs | PASS | Aggregate metrics, calibration and operating-point reports copied byte-for-byte; release manifest copy links the source manifest hash and omits the row-level prediction output |
| Task 6C evaluation aggregate report hashes | PASS | All five curated aggregate reports match `evaluation_manifest.json` hashes |
| FY2024 unchanged-model evaluation | PASS | Freeze manifest hash is referenced by evaluation manifest; checks record no refit/retune, same eligible observations and FY2024 not used for selection |
| FY2024 cohort | PASS | 60,114 eligible, 417 positive, 59,697 negative; matches Task 6B |
| Malformed FY2024 per-loan predictions | PASS for exclusion; FAIL for artifact validity | SHA-256 matches invalid-artifact manifest entry; marked invalid and excluded from curated aggregate outputs. The malformed archive still exists in the private external folder and must not be published. |
| Task 6D.1 original aggregate output hashes | PASS | All five report hashes match its manifest |
| As-of sensitivity source and reconciliation QA | PASS | New manifest and report checks pass; original output folder was not overwritten |
| Legacy PDF disposition | PASS for exclusion | No renderer available; prior PDF preserved in `docs/archive/`, excluded from release; canonical Markdown requires future PDF regeneration |
| Explicit release allowlist and static validator | PASS | 91 reviewed paths exist; raw/loan-level, private-path, disallowed format and out-of-scope path scans pass; `python tools/validate_release.py` passes |
| Task 6A/5E.5 report hash records | REVIEW HASHES RECORDED | Original manifests lack report hashes; review-time SHA-256 values are listed below. Task 5E.5 loan-level files remain excluded |
| Code license | GAP | No repository code license file was found; do not imply a code reuse license |

FY2024 is described only as a later-year temporal evaluation, not a pristine blind holdout. Freeze evidence states no FY2024 predictive results entered selection; earlier aggregate cohort counts were visible. The malformed file is not one of the evaluation manifest's five curated reports. No raw row-level records or loan-level predictions are included in the proposed release list below.

## Code, paths, and privacy review

Task 6A, 6B, 6C, 6C.2 and 6D.1 analysis scripts accept explicit command-line paths. The reviewed instructions use a sibling `SBA_Project_Data` path, not a hard-coded user-specific absolute path. The official Task 5 scripts retain older workflow interfaces; their manifests identify the actual historical cohort and outputs. `docs/REPRODUCE.md` distinguishes historical model reproduction from the later descriptive and cohort audits and warns not to refit during this review.

No raw FOIA CSV, compressed cohort, `.parquet`, spreadsheet, SQLite database, borrower-level prediction output or local absolute user path is included in the explicit allowlist. The malformed FY2024 prediction artifact and the valid FY2023 row-level prediction artifact remain outside GitHub. The local FY2024 file remains invalid even though aggregate outputs are valid.

Reviewed aggregate-only Task 6A–6D.1 copies are under the task-specific `results/` subdirectories. The verified contemporary HGB and Logistic Regression model files were copied byte-for-byte into `models/` and their hashes match the freeze manifest. The Task 6C validation prediction artifact was not copied.

Review-time hashes for aggregate reports whose original manifests did not record output hashes:

| Output | SHA-256 |
|---|---|
| Task 6A `yearly_summary.csv` | `437cda83a0eee451ac873e232c097b11f46e50e276a86fa6b4778fd3a8c8837d` |
| Task 6A `status_by_fy.csv` | `8d97c26ef8645680d59f4175826a16e9ef231e947440643620f1bd4efae62aba` |
| Task 6A `state_by_fy.csv` | `62d0648cf69e7fe89e26472e17d87f981826c2ccc1d6120e3cebf702faf81fc0` |
| Task 6A `naics2_by_fy.csv` | `0e385ea92aeb64815b7f4a1fca269c5a122ffe5f5a075b5c6100e8d54ca63e31` |
| Task 6A `missingness_by_fy.csv` | `c8d3e5dbdf0583af747c96173aaf5f553f6829a74df0fc7e5204c83d6030b299` |
| Task 5E.5 `cohort_counts_by_fy.csv` | `fcb795cb3296565f70703f8ee4ed7de305523d82c5c62493b284372d7e7ab2d4` |
| Task 5E.5 `quality_flags.csv` | `88c09d39045e37593563d508948523d465b922f107e0fe6cba4a9bdc81eca5b9` |

No PDF renderer was available (`pandoc`, `quarto`, `wkhtmltopdf`, `prince`, `typst`, WeasyPrint, Markdown, ReportLab and pypandoc were unavailable). The old `docs/TECHNICAL_REPORT.pdf` was moved without changing SHA-256 `5332997677ddf5cc7f1341d4698e991d99d097b9e198503094ac842a27441e34` to `docs/archive/TECHNICAL_REPORT_legacy_2026-11-11.pdf`; it is excluded from the release allowlist and must not be presented as the current report. The canonical report is Markdown; a matching PDF still requires regeneration.

`RELEASE_MANIFEST.json` was refreshed from [`tools/sba_release_allowlist.txt`](../tools/sba_release_allowlist.txt), not a directory-wide sweep that could add out-of-scope files. `tools/refresh_release_manifest.py` requires an explicit allowlist and rejects common raw/loan-level file patterns. The 91-entry allowlist includes aggregate copies for Tasks 6A–6D.1 and two contemporary frozen model files; it excludes all row-level predictions and source records. The manifest hash checks and static release validation passed.

## Final consistency review findings

The README and canonical report were checked against the curated Task 5D.2/5E.1, Task 6A, verified Task 6B, Task 6C and Task 6D.1 aggregate tables and manifests. The reported FY2014 model metrics and top-decile figures, contemporary yearly/cohort counts, FY2023/FY2024 model metrics, paired bootstrap intervals, severity summaries and sensitivity counts match those aggregate files.

Two historical forensic numerical claims previously present in the draft canonical report could not be independently checked against an aggregate table in the curated package: the exact approval-date versus first-disbursement-date target disagreement count, and term-pattern event rates / near-term timing percentages. Those figures have been removed from the canonical report. The report retains only a qualitative description of the documented lineage concern and explicitly states that its detailed diagnostic is not in the release package. This is a traceability limitation, not a failed model-hash or cohort-count check. No other unsupported headline numerical claim was identified in the README or canonical report during this review.

The FY2023/FY2024 ranking shift is reported descriptively. FY2023 HGB has higher average precision; FY2024 Logistic Regression has slightly higher average precision and ROC-AUC, while HGB has better Brier score and log loss. The FY2024 paired average-precision interval includes zero. Prevalence changed across training, development and evaluation populations; composition shift, changing predictor/outcome relationships and sampling variation are plausible explanations, but none is causally identified. Low prevalence limits precision because the non-event population is very large relative to positives. Neither frozen model is suitable for lending decisions: retrospective selection, unverified approval-time feature provenance, temporal metric changes, imperfect calibration, absence of prospective validation and lack of decision-utility/fairness review all remain.

The 18 future-dated charge-off records cannot be represented as having occurred by the September 30, 2026 snapshot. The 11 undated records cannot be assigned an as-of event date, even though they have zero recorded gross charge-off amounts. Both groups remain visible in original Task 6D.1 results and are separately handled in the strict dated-by-snapshot sensitivity; the original results were not rewritten. The gross charge-off-to-approval ratio is descriptive and is not LGD.

## Proposed GitHub release allowlist

Only the following reviewed paths are proposed for the SBA release. Include directories by listed files only; do not sweep whole folders.

- Root: `.gitignore`, `README.md`, `requirements.txt`
- Core historical docs: `docs/METHODOLOGY.md`, `docs/MODEL_CARD.md`, `docs/REPRODUCE.md`, `docs/FREEZE_REPRODUCTION_NOTE.md`, `docs/TECHNICAL_REPORT.md`, `docs/OPEN_QUESTIONS.md`
- SBA Task 6 docs: `docs/TASK6A_METHOD.md`, `docs/TASK6B_COHORT_METHODOLOGY.md`, `docs/TASK6C_MODEL_METHODOLOGY.md`, `docs/TASK6D1_GROSS_SEVERITY.md`, `docs/TASK6_FINAL_RESEARCH_FINDINGS.md`, `docs/TASK6_DATA_LIMITATIONS.md`, `docs/TASK6_PUBLICATION_AUDIT.md`
- Scripts: `scripts/build_sba_cohort_enriched.py`, `scripts/sba_task5d1_term_forensics.py`, `scripts/sba_task5d2_term_free_validation.py`, `scripts/sba_task5d3_temporal_stability.py`, `scripts/sba_task5d_source_lineage_audit.py`, `scripts/sba_task5e1_model_freeze.py`, `scripts/sba_task6a_contemporary_audit.py`, `scripts/sba_task6b_24m_cohort_audit.py`, `scripts/sba_task6c_24m_model_validation.py`, `scripts/sba_task6c2_freeze_evaluate.py`, `scripts/sba_task6d1_gross_severity.py`, `scripts/sba_task6d1_asof_sensitivity.py`
- Tests: `tests/test_task6a_audit.py`, `tests/test_task6b_24m_cohort_audit.py`, `tests/test_task6c_24m_model_validation.py`, `tests/test_task6c2_freeze_evaluate.py`, `tests/test_task6d1_gross_severity.py`, `tests/test_task6d1_asof_sensitivity.py`, `tests/test_release_manifest.py`
- Validated frozen models: historical `models/B_extended_no_term_LogisticRegression.joblib`, `models/B_extended_no_term_HistGradientBoosting.joblib`; contemporary `models/conservative_hist_gradient_boosting.joblib`, `models/regularized_logistic.joblib`
- Existing aggregate historical results: `results/task5d2_manifest.json`, `results/task5d2_model_comparison.csv`, `results/task5d2_risk_decile_calibration.csv`, `results/task5d2_subgroup_calibration.csv`, all `results/task5d3_*.csv` and `results/task5d3_manifest.json`, and all `results/task5e1_*.csv` and `results/task5e1_manifest.json`
- Contemporary aggregate reports/manifests: all explicitly listed files under `results/task6a/`, `results/task6b_verified/`, `results/task6c_development/`, `results/task6c_fy2024_evaluation/`, `results/task6d1_severity/` and `results/task6d1_asof_sensitivity/`; the Task 6C development release manifest omits the private validation prediction artifact
- Figures: `figures/term_free_pr_auc_by_year.png`, `figures/fy2014_hgb_calibration.png`
- Tools: `tools/validate_release.py`, `tools/refresh_release_manifest.py`, `tools/sba_release_allowlist.txt`

Exclude raw or loan-level files, all files under `SBA_Project_Data`, the malformed FY2024 prediction file, the valid FY2023 loan-level predictions, historical cohort CSVs, draft/original model card, `docs/archive/TECHNICAL_REPORT_legacy_2026-11-11.pdf`, `docs/TASK6D_LGD_EAD_FEASIBILITY.md`, all Freddie Mac/mortgage Task 6D.2 files, private paths, caches and temporary files. No Task 6C predictions are included. The allowlist is a proposal for review, not a commit or release action.

## Final pre-publication validation

- Synthetic tests: 29 passed across the seven applicable SBA/release test files (Task 6A, Task 6B, Task 6C, Task 6C.2, Task 6D.1 severity, Task 6D.1 sensitivity and release manifest). Mortgage/Task 6D.2 tests were excluded as out of scope.
- Syntax: 22 SBA scripts, tests and release tools compiled successfully.
- Release manifest: refreshed from the explicit 91-path allowlist; independent allowlist-to-manifest comparison, file sizes and SHA-256 checks passed.
- Static validator: `python .\tools\validate_release.py` passed. It confirms the historical frozen artifacts and curated release hashes; it explicitly does not claim independent end-to-end reproduction.
- Report scan: headline counts/metrics in README and canonical report were checked against curated aggregate files; safeguards on FY2024, lending-use, regulatory-default and LGD interpretation passed. Unverifiable historical forensic subgroup figures were removed and are disclosed above.
- `git diff --check` and final `git status --short` are recorded in the review response; nothing was committed or pushed.

## Code license recommendation (not applied)

MIT is a reasonable choice for **original project-authored source code and synthetic tests** if the repository owner confirms the right to license those contributions. It is short and permits reuse with attribution and the license notice. Limit its stated scope to project code under `scripts/`, `tests/` and `tools/`; do not imply it covers the SBA source dataset, third-party software, serialized model artifacts, or research figures and report text. SBA identifies its FOIA resource as a U.S. Government Work, while the pinned dependencies remain under their own licenses/notices. Installed metadata for joblib 1.4.2, pandas 2.3.3 and scikit-learn 1.7.2 reports BSD 3-Clause; NumPy and SciPy distributions carry their own bundled notices, including third-party components. The four frozen joblib model artifacts (two historical and two contemporary) are separately governed research outputs and should not be assumed covered by a code license without reviewing their training-data and distribution terms. No `LICENSE` file has been added; approval and rights confirmation are needed first.

## Remaining release blockers

1. Select an explicit license for repository code; none was found.
2. Conduct the requested human scientific and publication review before Project A is called complete.
