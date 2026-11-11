#!/usr/bin/env python3
"""Project A Task 5E.1: freeze two term-free B models and verify reload.

Uses ONLY existing FY2010-2014 enriched strict cohort, with FY2010-2013 fit
and FY2014 validation. Previously inspected FY2015-2016 data is not opened.

Requires: numpy, pandas, scipy, scikit-learn, joblib.
Output: serialized model pipelines, aggregate results, manifest, model-card draft.
No loan-level predictions or borrower records are written.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.metrics import brier_score_loss

from sba_task5d2_term_free_validation import (
    EXPECTED, SPECS, TARGET, REQUIRED, make_model, metrics,
    prepare_feature_frame,
)

INPUT_SHA256_5D3='13e721d4936831af585e439a874559a3f8108b5e96c59231d5e9c0805ad884da'
EXPECTED_FY2014={
    'LogisticRegression':{'pr_auc_average_precision':0.1060574,'roc_auc':0.6557371,'brier_score':0.0558695},
    'HistGradientBoosting':{'pr_auc_average_precision':0.1098973,'roc_auc':0.6695365,'brier_score':0.0557123},
}
BANNED=('term','chargeoff','paid_in_full','terminal','liquidation','date','business_age','status')
# 'revolver_status' is deliberately allowed, unlike outcome status.
EXPLICIT_ALLOWLIST=set(SPECS['B_extended_no_term'][0]+SPECS['B_extended_no_term'][1])


def file_sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def csv_write(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


def deciles(y,p,name):
    arr=pd.DataFrame({'y':y,'p':p})
    arr['decile']=pd.qcut(arr['p'].rank(method='first'),10,labels=False)+1
    out=[]
    for d,g in arr.groupby('decile',sort=True):
        out.append({'model':name,'decile':int(d),'n':int(len(g)),
                    'events':int(g.y.sum()),'observed_rate_pct':round(100*float(g.y.mean()),4),
                    'predicted_rate_pct':round(100*float(g.p.mean()),4),
                    'observed_minus_predicted_pp':round(100*(float(g.y.mean())-float(g.p.mean())),4)})
    return out


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--input',type=Path,required=True,help='Existing Task 4 enriched FY2010–2014 strict cohort (.csv.gz)')
    a.add_argument('--out-dir',type=Path,default=Path('sba_task5e1_model_freeze_output'))
    a.add_argument('--smoke-test',action='store_true',help='Synthetic data only; skips pinned official counts and prior metrics')
    args=a.parse_args()
    input_path=args.input.resolve()
    if not input_path.is_file():raise SystemExit(f'Missing input: {input_path}')
    if any(t in str(input_path).lower() for t in ('locked_test','fy2015','fy2016')):
        raise SystemExit('REFUSING: suspected test input path')
    digest=file_sha256(input_path)
    print('Reading enriched strict FY2010–FY2014 cohort...',flush=True)
    df=pd.read_csv(input_path,compression='infer',low_memory=False)
    missing=REQUIRED-set(df.columns)
    if missing:raise SystemExit('Missing enriched columns: '+repr(sorted(missing)))
    years=pd.to_numeric(df['approval_fy'],errors='coerce')
    if years.isna().any() or not years.isin([2010,2011,2012,2013,2014]).all():
        raise SystemExit('REFUSING: data outside FY2010–2014')
    if 'split' in df.columns and not df['split'].astype(str).str.lower().isin(['train']).all():
        raise SystemExit('REFUSING: input contains non-train split rows')
    labels=pd.to_numeric(df[TARGET],errors='coerce')
    if labels.isna().any() or not labels.isin([0,1]).all():raise SystemExit('Missing or invalid labels')
    train=years.isin([2010,2011,2012,2013]).to_numpy()
    val=(years==2014).to_numpy()
    yfit=labels.loc[train].astype(int).to_numpy()
    yval=labels.loc[val].astype(int).to_numpy()
    counts={'fit_rows':int(train.sum()),'val_rows':int(val.sum()),
            'fit_events':int(yfit.sum()),'val_events':int(yval.sum())}
    if not args.smoke_test and counts!=EXPECTED:
        raise SystemExit('Official cohort QA failed; expected '+repr(EXPECTED)+', got '+repr(counts))
    if not args.smoke_test and digest != INPUT_SHA256_5D3:
        raise SystemExit('Input SHA-256 differs from verified Task 5D.3 cohort. Refusing model freeze.')
    if len(yfit)<500 or len(yval)<100 or yfit.sum()<10 or yval.sum()<5:
        raise SystemExit('Too few observations/events to verify fit')
    X=prepare_feature_frame(df)
    del df
    num,cat=SPECS['B_extended_no_term']
    cols=num+cat
    if set(cols)!=EXPLICIT_ALLOWLIST:raise SystemExit('Unexpected feature list')
    if any('term' in c or c=='business_age' or 'chargeoff' in c or 'terminal' in c or 'date' in c for c in cols):
        raise SystemExit('Leakage feature found')
    Xfit=X.loc[train,cols]
    Xval=X.loc[val,cols]
    args.out_dir.mkdir(parents=True,exist_ok=True)
    model_dir=args.out_dir/'model_artifacts'
    model_dir.mkdir(exist_ok=True)
    rows=[];decile_rows=[];artifacts=[]
    reload_checks=[];replication_checks=[]
    for kind in ('LogisticRegression','HistGradientBoosting'):
        print('Fitting B_extended_no_term__'+kind,flush=True)
        model=make_model(kind,num,cat)
        model.fit(Xfit,yfit)
        p=model.predict_proba(Xval)[:,1]
        met=metrics(yval,p)
        name='B_extended_no_term__'+kind
        filename='B_extended_no_term_'+kind+'.joblib'
        model_path=model_dir/filename
        joblib.dump(model,model_path,compress=3)
        check_model=joblib.load(model_path)
        p2=check_model.predict_proba(Xval)[:,1]
        exact=bool(np.array_equal(p,p2))
        maxdiff=float(np.max(np.abs(p-p2)))
        reload_checks.append(exact and maxdiff==0)
        if not args.smoke_test:
            expected=EXPECTED_FY2014[kind]
            repl=all(abs(met[metric]-expected[metric])<0.003 for metric in expected)
        else:repl=True
        replication_checks.append(repl)
        rows.append({'model':name,'fit_years':'FY2010–FY2013','validation_year':'FY2014',
                     'fit_rows':len(yfit),'validation_rows':len(yval),
                     'fit_events':int(yfit.sum()),'validation_events':int(yval.sum()),
                     **met,'artifact_file':filename,'sha256':file_sha256(model_path),
                     'reload_predictions_exact':exact,'max_abs_reload_diff':maxdiff,
                     'replicates_5d3_within_0_003':bool(repl)})
        decile_rows.extend(deciles(yval,p,name))
        artifacts.append({'filename':filename,'sha256':file_sha256(model_path),'bytes':model_path.stat().st_size})
        print('  PR-AUC',met['pr_auc_average_precision'],'ROC-AUC',met['roc_auc'],
              'Brier',met['brier_score'],'reload identical',exact,flush=True)
    csv_write(args.out_dir/'task5e1_frozen_model_metrics.csv',rows)
    csv_write(args.out_dir/'task5e1_validation_risk_deciles.csv',decile_rows)
    approvals=[
      ('log_gross_approval','GrossApproval','Origination-level amount; historical 2026 snapshot, value at decision not proven'),
      ('guarantee_share','SBA guaranteed approval / gross approval','Underwriting field; origination version not independently verified'),
      ('initial_interest_rate','InitialInterestRate','Initial rate by label; point-in-time provenance not independently verified'),
      ('naics_sector','NAICS code','Industry classification; original code vintage/changes not independently verified'),
      ('project_state','ProjectState','Project location; point-in-time version not independently verified'),
      ('business_type','BusinessType','Business category; historical version not independently verified'),
      ('processing_method','ProcessingMethod','Program/processing channel; historical version not independently verified'),
      ('revolver_status','RevolverStatus','Revolving flag; no independent approval-time snapshot verification'),
      ('fixed_or_variable_interest_ind','FixedOrVariableInterestInd','Rate-type indicator; historical version not independently verified'),
      ('collateral_ind','CollateralInd','Collateral indicator; point-in-time status not independently verified'),
    ]
    csv_write(args.out_dir/'task5e1_feature_provenance_register.csv',[
        {'model_feature':f,'raw_field':src,'status':'provisional_not_point_in_time_verified',
         'evidence_or_limitation':note} for f,src,note in approvals])
    qa={
        'only_fy2010_2014_input_read':True,
        'no_fy2015_2016_test_input_read':True,
        'no_term_or_business_age_predictor':True,
        'preprocessing_fit_only_on_fy2010_2013':True,
        'matches_5d3_cohort_sha256':digest==INPUT_SHA256_5D3 if not args.smoke_test else None,
        'expected_cohort_counts':counts==EXPECTED if not args.smoke_test else None,
        'replicates_5d3_validation_metrics':all(replication_checks),
        'model_reload_predictions_bitwise_identical':all(reload_checks),
        'both_model_artifacts_saved':len(artifacts)==2 and all(x['bytes']>0 for x in artifacts),
        'no_loan_level_records_exported':True,
    }
    manifest={
      'task':'Project A Task 5E.1 — reproducible release-candidate freeze',
      'created_utc':datetime.now(timezone.utc).isoformat(),
      'official_run':not args.smoke_test,'input_basename':input_path.name,
      'input_sha256':digest,'counts':counts,'features':cols,
      'models':artifacts,'metrics':rows,'qa_checks':qa,
      'all_expected_checks_pass':all(v is True for v in qa.values()) if not args.smoke_test else None,
      'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,
                  'scikit_learn':sklearn.__version__,'scipy':scipy.__version__,'joblib':joblib.__version__},
      'not_production_ready':True,
      'limits':[
        '2026 FOIA retrospective snapshot; no independent approval-time version of features.',
        'Strict-cohort sample is conditioned on later outcomes and source term validity even when term is excluded from predictors.',
        'FY2013 and FY2014 have been used for development/model choice, so reported scores are not unbiased final generalization claims.',
        'FY2015–FY2016 outcomes were viewed in an earlier baseline; cannot call them pristine holdout.',
        'Observed FY2014 risk exceeds mean prediction; calibration and subgroup calibration remain imperfect.',
        'This is a research portfolio prototype and not a real-world credit decision system.'
      ]
    }
    (args.out_dir/'task5e1_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    card=f'''# SBA 7(a) Term-Free Credit-Risk Research Prototype — Model Card (Draft)

**Status:** frozen release candidate, **NOT production-ready**. Snapshot: 30 September 2026.

## Research question
Can fields observed in the SBA FOIA data be used to rank retrospective 120-month charge-off outcomes on a deliberately defined strict cohort? This is **not** a validated origination-time underwriting score.

## Cohort and design
- Input: `{input_path.name}` (SHA-256 `{digest}`).
- Model fitting: FY2010–FY2013, {counts['fit_rows']:,} loans ({counts['fit_events']:,} events).
- Development validation: FY2014, {counts['val_rows']:,} loans ({counts['val_events']:,} events).
- Models: B Extended Logistic Regression (benchmark); B Extended HistGradientBoosting (provisional champion).
- TermInMonths, term derivatives, BusinessAge, outcome dates, and terminal status not used as predictors.
- Preprocessing fit on FY2010–FY2013 only.

## FY2014 validation
| Model | PR-AUC/AP | ROC-AUC | Brier |
|---|---:|---:|---:|
''' + ''.join(f"| {r['model']} | {r['pr_auc_average_precision']:.4f} | {r['roc_auc']:.4f} | {r['brier_score']:.5f} |\n" for r in rows)+'''
## Significant limitations
1. All predictors are sourced from a retrospective public FOIA extract; approval-time data versions are not independently verified.
2. Eligibility for this strict research cohort depends on final status and term-validity rules, potentially producing selection bias even without term in the model.
3. FY2013/FY2014 results informed model selection; they are development validation, **not** a pristine prospective test.
4. FY2015–FY2016 results were already inspected earlier, so those years must not be described as untouched.
5. The HGB model underpredicts FY2014 overall events, and subgroup gaps exist. The current release is not sufficiently calibrated for operational decision-making.
6. The trained `.joblib` artifacts assume the engineered fields produced by `prepare_feature_frame` in `sba_task5d2_term_free_validation.py` (not raw SBA columns).

## Reproducibility & access
Full output manifest contains cohort hash, feature allowlist, package versions, model hashes, metric replication checks, and bitwise reloaded-prediction agreement. Raw borrower rows/predictions are not exported. Load `joblib` artifacts only from trusted sources.
'''
    (args.out_dir/'MODEL_CARD_DRAFT.md').write_text(card,encoding='utf-8')
    (args.out_dir/'REPRODUCTION_NOTE.md').write_text(
      '''# Model freeze reproduction\n\nOriginal source input: Task 4 enriched FY2010–FY2014 strict cohort.\n\nRun `sba_task5e1_model_freeze.py` from its package alongside `sba_task5d2_term_free_validation.py`.\n\nPipelines accept **engineered** columns, prepared by `prepare_feature_frame` from `sba_task5d2_term_free_validation.py`, not raw FOIA column names.\n\nRead `task5e1_manifest.json` and confirm `all_expected_checks_pass` is true. Do not treat this as approval-time validated or production-ready.\n''',encoding='utf-8')
    print('DONE:',args.out_dir,flush=True)
    print('QC:',manifest['all_expected_checks_pass'],flush=True)
    if not args.smoke_test and not manifest['all_expected_checks_pass']:
        raise SystemExit('QA FAILED: review output manifest before releasing the models')

if __name__=='__main__':main()
