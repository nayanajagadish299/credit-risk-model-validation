#!/usr/bin/env python3
"""Project A Task 5D.3: term-free temporal robustness and calibration.

Inputs: existing Task 4 enriched strict FY2010-2014 training cohort only.
The FY2015-FY2016 locked-test cohort is never opened. All candidates omit term
and BusinessAge. BusinessAge is used only as a descriptive subgroup for auditing.
Predictions are not written to disk.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sba_task5d2_term_free_validation import (
    prepare_feature_frame, make_model, metrics, SPECS, TARGET,
    REQUIRED as SOURCE_REQUIRED,
)

FOLDS=[(2013,[2010,2011,2012]), (2014,[2010,2011,2012,2013])]
MODELS=[("A_core_no_term","LogisticRegression"),
        ("A_core_no_term","HistGradientBoosting"),
        ("B_extended_no_term","LogisticRegression"),
        ("B_extended_no_term","HistGradientBoosting")]
EXPECTED_2014={"train_rows":164628,"train_events":10856,"validation_rows":45888,"validation_events":2778}
PINNED_5D2_SHA256="13e721d4936831af585e439a874559a3f8108b5e96c59231d5e9c0805ad884da"
KNOWN_5D2_B={
    "LogisticRegression":{"pr_auc_average_precision":0.1060574,"roc_auc":0.6557371},
    "HistGradientBoosting":{"pr_auc_average_precision":0.1098973,"roc_auc":0.6695365},
}
BOOTSTRAP_SEED=2026


def csv_write(path, data):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        if not data:
            f.write('no_records_meeting_suppression_threshold\n')
            return
        w=csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader();w.writerows(data)


def file_hash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def decile_summary(y,p,model,year):
    t=pd.DataFrame({'y':y,'p':p})
    t['decile']=pd.qcut(t.p.rank(method='first'),q=10,labels=False)+1
    rows=[]
    for dec,g in t.groupby('decile'):
        rows.append({'validation_year':year,'model':model,'decile':int(dec),'n':len(g),
                     'events':int(g.y.sum()),
                     'observed_event_rate_pct':round(100*g.y.mean(),4),
                     'predicted_event_rate_pct':round(100*g.p.mean(),4),
                     'captured_fraction_all_events_pct':round(100*g.y.sum()/len(y[y==1]),4)})
    return rows


def subgroup_summary(y,p,x,model,year):
    rows=[]
    for field in ['revolver_status','processing_method','business_age']:
        t=pd.DataFrame({'group':x[field].to_numpy(),'y':y,'p':p})
        for name, g in t.groupby('group',dropna=False):
            # Avoid unstable/sensitive small-group reporting.
            if len(g)<300 or int(g.y.sum())<10: continue
            obs=100*g.y.mean();pred=100*g.p.mean()
            rows.append({'validation_year':year,'model':model,'field':field,
                         'group':str(name),'n':len(g),'events':int(g.y.sum()),
                         'observed_rate_pct':round(obs,4),
                         'predicted_rate_pct':round(pred,4),
                         'observed_minus_predicted_pp':round(obs-pred,4)})
    return rows


def paired_bootstrap(y,p_a,p_b,year,reps=150):
    """Paired bootstrap CI for AP/ROC/Brier difference: B HGB minus B Logistic."""
    rng=np.random.default_rng(BOOTSTRAP_SEED+year)
    indices=np.arange(len(y))
    deltas={"pr_auc":[],"roc_auc":[],"brier":[]}
    for _ in range(reps):
        ix=rng.choice(indices,size=len(indices),replace=True)
        yy=y[ix]
        if int(yy.sum())==0 or int(yy.sum())==len(yy):continue
        aa=p_a[ix];bb=p_b[ix]
        deltas['pr_auc'].append(average_precision_score(yy,bb)-average_precision_score(yy,aa))
        deltas['roc_auc'].append(roc_auc_score(yy,bb)-roc_auc_score(yy,aa))
        deltas['brier'].append(brier_score_loss(yy,bb)-brier_score_loss(yy,aa))
    out=[]
    for metric, vals in deltas.items():
        if not vals: continue
        lo,med,hi=np.quantile(vals,[0.025,0.5,0.975])
        out.append({'validation_year':year,'metric':metric,'comparison':'B_HGB_minus_B_Logistic',
                    'n_replicates':len(vals), 'median_difference':round(float(med),7),
                    'ci95_low':round(float(lo),7),'ci95_high':round(float(hi),7),
                    'ci_includes_zero':bool(lo<=0<=hi)})
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True,
        help='Enriched Task 4 strict FY2010-2014 cohort (.csv.gz), NOT older base cohort')
    ap.add_argument('--out-dir',type=Path,default=Path('sba_task5d3_temporal_output'))
    ap.add_argument('--bootstrap-reps',type=int,default=150,
        help='Number of paired bootstrap repeats (default 150)')
    ap.add_argument('--smoke-test',action='store_true',
        help='For synthetic test data only; skips official cohort count checks')
    args=ap.parse_args()
    if not args.input.is_file():raise SystemExit(f'Input missing: {args.input}')
    if args.bootstrap_reps < 10 or args.bootstrap_reps > 1000:
        raise SystemExit('--bootstrap-reps should be between 10 and 1000')
    if any(v in str(args.input).lower() for v in ('locked_test','fy2015','fy2016')):
        raise SystemExit('REFUSING: filename suggests a held-out test set')
    df=pd.read_csv(args.input,compression='infer',low_memory=False)
    miss=SOURCE_REQUIRED-set(df.columns)
    if miss:raise SystemExit('Enriched cohort missing required columns: '+', '.join(sorted(miss)))
    years=pd.to_numeric(df['approval_fy'],errors='coerce')
    if years.isna().any() or not years.isin([2010,2011,2012,2013,2014]).all():
        raise SystemExit('REFUSING: input includes out-of-scope fiscal years')
    if 'split' in df.columns and not df['split'].astype(str).str.lower().isin(['train']).all():
        raise SystemExit('REFUSING: split column includes non-train rows')
    label=pd.to_numeric(df[TARGET],errors='coerce')
    if label.isna().any() or not label.isin([0,1]).all():
        raise SystemExit('Expected complete binary outcome')
    sha=file_hash(args.input)
    X=prepare_feature_frame(df)
    y=label.astype(int).to_numpy()
    yrs=years.to_numpy()
    del df
    results=[];deciles=[];subgroups=[];bootstrap=[];fold_meta=[]
    qa={"no_test_files_read":True,"no_term_features_in_models":True,
        "no_business_age_predictor":True,"preprocessing_fit_only_in_fold":True,
        "expected_2014_counts":False,"reproduces_5d2_2014_b_within_0_003":False}
    yr14metrics={}
    for val_year, fit_years in FOLDS:
        imask=np.isin(yrs,fit_years);vmask=(yrs==val_year)
        yy=y[vmask];yf=y[imask]
        counts={'train_rows':int(imask.sum()),'train_events':int(yf.sum()),
                'validation_rows':int(vmask.sum()),'validation_events':int(yy.sum())}
        print('Validation FY',val_year,'train FY',fit_years,'counts',counts,flush=True)
        if val_year==2014:
            qa['expected_2014_counts']=(counts==EXPECTED_2014)
            if not args.smoke_test and not qa['expected_2014_counts']:
                raise SystemExit('Official FY2014 cohort QA failed. '+str(counts))
        if len(yy)<100 or len(yf)<500 or int(yy.sum())<5 or int(yf.sum())<5:
            raise SystemExit('Insufficient cohort for annual evaluation '+str(val_year))
        fold_meta.append({'validation_year':val_year,'train_years':fit_years,**counts})
        predictions={}
        for spec,algorithm in MODELS:
            num,cat=SPECS[spec]
            assert 'term_in_months' not in num+cat and 'business_age' not in num+cat
            name=spec+'__'+algorithm
            print('  fitting',name,flush=True)
            m=make_model(algorithm,num,cat)
            m.fit(X.loc[imask,num+cat], yf)
            p=m.predict_proba(X.loc[vmask,num+cat])[:,1]
            met=metrics(yy,p)
            results.append({'validation_year':val_year,'fit_years':'|'.join(map(str,fit_years)),
                'model':name,'train_n':int(imask.sum()),'validation_n':len(yy),
                'events':int(yy.sum()), **met})
            deciles.extend(decile_summary(yy,p,name,val_year))
            subgroups.extend(subgroup_summary(yy,p,X.loc[vmask],name,val_year))
            predictions[name]=p
            if val_year==2014 and spec=='B_extended_no_term':yr14metrics[algorithm]=met
            print('    AP',met['pr_auc_average_precision'],'ROC',met['roc_auc'],flush=True)
        bootstrap.extend(paired_bootstrap(yy,
            predictions['B_extended_no_term__LogisticRegression'],
            predictions['B_extended_no_term__HistGradientBoosting'],
            val_year,args.bootstrap_reps))
    if not args.smoke_test:
        qa['reproduces_5d2_2014_b_within_0_003']=all(
          abs(yr14metrics[k][metric]-ref)<0.003
          for k,vals in KNOWN_5D2_B.items() for metric,ref in vals.items())
    feature_missing=[]
    for year in sorted(set(int(a) for a in yrs)):
        rows=(yrs==year)
        for column in ['log_gross_approval','guarantee_share','initial_interest_rate',
                       'naics_sector','project_state','business_type','processing_method',
                       'revolver_status','fixed_or_variable_interest_ind','collateral_ind','business_age']:
            series=X.loc[rows,column]
            if pd.api.types.is_numeric_dtype(series):count=int(series.isna().sum())
            else:count=int((series=='__MISSING__').sum())
            feature_missing.append({'approval_fy':year,'field':column,'n':len(series),
              'missing_count':count,'missing_pct':round(100*count/len(series),4)})
    args.out_dir.mkdir(parents=True,exist_ok=True)
    for filename,rows in [
        ('task5d3_temporal_comparison.csv',results),
        ('task5d3_risk_decile_calibration.csv',deciles),
        ('task5d3_subgroup_calibration.csv',subgroups),
        ('task5d3_paired_bootstrap.csv',bootstrap),
        ('task5d3_feature_missingness_by_fy.csv',feature_missing)]:
        csv_write(args.out_dir/filename,rows)
    if args.smoke_test:
        qa['expected_2014_counts']=None
        qa['reproduces_5d2_2014_b_within_0_003']=None
    manifest={'task':'Project A 5D.3: FY2013/FY2014 term-free forward robustness',
              'created_utc':datetime.now(timezone.utc).isoformat(),
              'input_file':args.input.name,'input_sha256':sha,
              'matches_5d2_input_sha256':sha==PINNED_5D2_SHA256,
              'fit_validation_folds':fold_meta,'candidate_models':len(MODELS),
              'bootstrap_reps':args.bootstrap_reps,'qa_checks':qa,
              'all_expected_checks_pass':(all(v is True for v in qa.values()) and sha==PINNED_5D2_SHA256)
                        if not args.smoke_test else None,
              'smoke_test':bool(args.smoke_test),'python_version':sys.version.split()[0],
              'pandas_version':pd.__version__,'sklearn_version':sklearn.__version__,
              'no_loan_level_outputs_saved':True,
              'notes':['BusinessAge is examined as subgroup but not used by candidates.',
                'Strict source cohort is conditioned on retrospective statuses and term validity.',
                'Approval-time provenance and cohort selection must be disclosed before repository release.',
                'FY2015-2016 was viewed during an earlier baseline; not a virgin holdout.']}
    (args.out_dir/'task5d3_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('DONE:',args.out_dir,flush=True)
    print('QC:',manifest['all_expected_checks_pass'],flush=True)

if __name__=='__main__':main()
