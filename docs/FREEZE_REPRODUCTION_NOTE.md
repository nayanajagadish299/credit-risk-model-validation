# Model freeze reproduction

Original source input: Task 4 enriched FY2010–FY2014 strict cohort.

Run `sba_task5e1_model_freeze.py` from its package alongside `sba_task5d2_term_free_validation.py`.

Pipelines accept **engineered** columns, prepared by `prepare_feature_frame` from `sba_task5d2_term_free_validation.py`, not raw FOIA column names.

Read `task5e1_manifest.json` and confirm `all_expected_checks_pass` is true. Do not treat this as approval-time validated or production-ready.
