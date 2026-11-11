#!/usr/bin/env python3
r"""SBA Project A — Task 5D.2: chronological, term-free validation.

Requires the Task 4 enriched FY2010–2014 *strict train* cohort.
Does NOT read FY2015–2016. NO loan-level rows or predictions are exported.
All candidate models exclude term_in_months and derivatives.

Usage:
 python sba_task5d2_term_free_validation.py \
   --input .\sba_cohort_output_v2\strict_train_fy2010_2014.csv.gz \
   --out-dir .\sba_task5d2_term_free_output
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

TRAIN_YEARS=(2010,2011,2012,2013)
VALIDATION_YEAR=2014
EXPECTED={"fit_rows":164628,"val_rows":45888,"fit_events":10856,"val_events":2778}
NUM_CORE=["log_gross_approval","guarantee_share"]
CAT_CORE=["naics_sector","project_state","business_type"]
NUM_EXT=["initial_interest_rate"]
CAT_EXT=["processing_method","revolver_status","fixed_or_variable_interest_ind","collateral_ind"]
CAT_AGE=["business_age"]
# All feature specs omit term. BusinessAge is explicitly exploratory pending provenance.
SPECS={
 "A_core_no_term":(NUM_CORE,CAT_CORE),
 "B_extended_no_term":(NUM_CORE+NUM_EXT,CAT_CORE+CAT_EXT),
 "C_extended_plus_business_age_no_term":(NUM_CORE+NUM_EXT,CAT_CORE+CAT_EXT+CAT_AGE),
}
TARGET="target_chargeoff_within_120m"
REQUIRED={"approval_fy","gross_approval","sba_guaranteed_approval","naics_code",
          "project_state","business_type","initial_interest_rate","processing_method",
          "revolver_status","fixed_or_variable_interest_ind","collateral_ind","business_age",TARGET}
RANDOM_SEED=2026


def write_csv(path:Path,rows:list[dict],cols:list[str]):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore')
        w.writeheader();w.writerows(rows)


def sha256(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def prepare_feature_frame(df:pd.DataFrame)->pd.DataFrame:
    # Use a deliberate feature allowlist; never ingest event dates or outcome-status data.
    out=pd.DataFrame(index=df.index)
    gross=pd.to_numeric(df['gross_approval'],errors='coerce')
    guaranteed=pd.to_numeric(df['sba_guaranteed_approval'],errors='coerce')
    out['log_gross_approval']=np.where(gross>0,np.log1p(gross.clip(lower=0)),np.nan)
    out['guarantee_share']=(guaranteed/gross.where(gross>0)).where(lambda s:s.between(0,1))
    out['initial_interest_rate']=pd.to_numeric(df['initial_interest_rate'],errors='coerce')
    out.loc[~np.isfinite(out['initial_interest_rate']),'initial_interest_rate']=np.nan
    naics=df['naics_code'].astype('string').str.strip().str.extract(r'^(\d{2})',expand=False)
    out['naics_sector']=naics.fillna('__MISSING__').astype(str)
    for c in ['project_state','business_type','processing_method','revolver_status',
              'fixed_or_variable_interest_ind','collateral_ind','business_age']:
        z=df[c].astype('string').str.strip().replace('',pd.NA)
        out[c]=z.fillna('__MISSING__').astype(str)
    return out


def make_model(kind:str,numeric:list[str],categorical:list[str]):
    if kind=='LogisticRegression':
        transformer=ColumnTransformer([
            ('num',Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),
                             ('scale',StandardScaler())]),numeric),
            ('cat',OneHotEncoder(handle_unknown='ignore',min_frequency=30),categorical),
        ],remainder='drop',sparse_threshold=0.3)
        model=LogisticRegression(max_iter=1200,C=1.0,solver='lbfgs',random_state=RANDOM_SEED)
    else:
        transformer=ColumnTransformer([
            ('num',SimpleImputer(strategy='median',keep_empty_features=True),numeric),
            ('cat',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=-1,
                                  encoded_missing_value=-1),categorical),
        ],remainder='drop',sparse_threshold=0)
        model=HistGradientBoostingClassifier(
            learning_rate=0.05,max_iter=130,max_leaf_nodes=15,min_samples_leaf=150,
            l2_regularization=5.0,early_stopping=False,
            categorical_features=([False]*len(numeric)+[True]*len(categorical)),
            random_state=RANDOM_SEED)
    return Pipeline([('preprocess',transformer),('model',model)])


def metrics(y:np.ndarray,p:np.ndarray)->dict:
    p=np.clip(np.asarray(p,dtype=float),1e-12,1-1e-12)
    return {
        'pr_auc_average_precision':round(float(average_precision_score(y,p)),7),
        'roc_auc':round(float(roc_auc_score(y,p)),7) if len(np.unique(y))==2 else None,
        'brier_score':round(float(brier_score_loss(y,p)),7),
        'log_loss':round(float(log_loss(y,p,labels=[0,1])),7),
        'mean_predicted_pct':round(float(p.mean()*100),4),
        'actual_prevalence_pct':round(float(np.asarray(y).mean()*100),4),
    }


def calibration_rows(model_name:str,y:np.ndarray,p:np.ndarray)->list[dict]:
    # Deciles created only within FY2014. Predictions never leave RAM.
    tmp=pd.DataFrame({'p':p,'y':y})
    tmp['decile']=pd.qcut(tmp['p'].rank(method='first'),q=10,labels=False)+1
    out=[]
    for n,g in tmp.groupby('decile',sort=True):
        out.append({'model':model_name,'risk_decile_1_low_10_high':int(n),
                    'n':len(g),'chargeoffs':int(g.y.sum()),
                    'observed_rate_pct':round(float(100*g.y.mean()),4),
                    'mean_predicted_pct':round(float(100*g.p.mean()),4),
                    'absolute_gap_pp':round(float(100*abs(g.y.mean()-g.p.mean())),4)})
    return out


def group_rows(model_name:str,y:np.ndarray,p:np.ndarray,features:pd.DataFrame)->list[dict]:
    out=[]
    for field in ['revolver_status','processing_method','business_age']:
        x=features[field].reset_index(drop=True)
        tmp=pd.DataFrame({'group':x,'y':y,'p':p})
        for grp,sub in tmp.groupby('group',dropna=False):
            if len(sub)<200:continue
            out.append({'model':model_name,'group_field':field,'group_value':str(grp),
                        'n':len(sub),'chargeoffs':int(sub.y.sum()),
                        'observed_rate_pct':round(float(100*sub.y.mean()),4),
                        'mean_predicted_pct':round(float(100*sub.p.mean()),4),
                        'brier_score':round(float(brier_score_loss(sub.y,sub.p)),6)})
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',required=True,type=Path,help='Task 4 enriched strict FY2010–2014 cohort (.csv.gz)')
    ap.add_argument('--out-dir',default='sba_task5d2_term_free_output',type=Path)
    ap.add_argument('--smoke-test',action='store_true',help='Skip fixed expected counts on a synthetic dataset only')
    args=ap.parse_args()
    if not args.input.is_file():raise SystemExit(f'Input not found: {args.input}')
    if 'locked_test' in str(args.input).lower() or 'fy2015' in str(args.input).lower():
        raise SystemExit('REFUSING: input path appears to be a locked-test file.')
    df=pd.read_csv(args.input,compression='infer',low_memory=False)
    missing=REQUIRED-set(df.columns)
    if missing:raise SystemExit(f'Input must be enriched cohort; missing columns: {sorted(missing)}')
    years=pd.to_numeric(df['approval_fy'],errors='coerce')
    observed=set(years.dropna().astype(int))
    if observed - set((*TRAIN_YEARS,VALIDATION_YEAR)) or years.isna().any():
        raise SystemExit(f'REFUSING: out-of-scope fiscal years detected: {sorted(observed)}')
    if 'split' in df.columns and not df['split'].astype(str).str.lower().isin(['train']).all():
        # Previous builders output FY2010-2014 strict_train with split='train'.
        raise SystemExit('REFUSING: input split is not exclusively train. Verify selected file.')
    label=pd.to_numeric(df[TARGET],errors='coerce')
    if label.isna().any() or not label.isin([0,1]).all():
        raise SystemExit('Invalid or missing binary outcome labels.')
    fit_mask=years.isin(TRAIN_YEARS).to_numpy();val_mask=(years==VALIDATION_YEAR).to_numpy()
    counts={'fit_rows':int(fit_mask.sum()),'val_rows':int(val_mask.sum()),
            'fit_events':int(label[fit_mask].sum()),'val_events':int(label[val_mask].sum())}
    checks={k:counts[k]==v for k,v in EXPECTED.items()}
    if not args.smoke_test and not all(checks.values()):
        raise SystemExit('Cohort QA FAILED; no models fitted. Counts: '+json.dumps(counts)+'; expected '+json.dumps(EXPECTED))
    if int(fit_mask.sum())<100 or int(val_mask.sum())<50:
        raise SystemExit('Cohort too small for validation.')
    # Discard everything except the deliberately declared feature set.
    X=prepare_feature_frame(df)
    del df
    Xfit=X.loc[fit_mask].reset_index(drop=True)
    Xval=X.loc[val_mask].reset_index(drop=True)
    yfit=label[fit_mask].astype(int).to_numpy()
    yval=label[val_mask].astype(int).to_numpy()
    rows=[];deciles=[];groups=[]
    for spec,(numeric,categorical) in SPECS.items():
        for kind in ['LogisticRegression','HistGradientBoosting']:
            name=spec+'__'+kind
            print(f'Fitting {name} ...',flush=True)
            m=make_model(kind,numeric,categorical)
            m.fit(Xfit[numeric+categorical],yfit)
            p=m.predict_proba(Xval[numeric+categorical])[:,1]
            result={'model':name,'feature_set':spec,'algorithm':kind,
                    'fit_rows':len(yfit),'fit_events':int(yfit.sum()),
                    'validation_rows':len(yval),'validation_events':int(yval.sum()),
                    'numeric_features':'|'.join(numeric),'categorical_features':'|'.join(categorical),
                    **metrics(yval,p)}
            rows.append(result)
            deciles.extend(calibration_rows(name,yval,p))
            groups.extend(group_rows(name,yval,p,Xval))
            print(f'  FY2014 PR-AUC {result["pr_auc_average_precision"]:.4f}, '
                  f'ROC-AUC {result["roc_auc"]:.4f}, Brier {result["brier_score"]:.4f}',flush=True)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    write_csv(args.out_dir/'task5d2_model_comparison.csv',rows,[
        'model','feature_set','algorithm','fit_rows','fit_events','validation_rows','validation_events',
        'pr_auc_average_precision','roc_auc','brier_score','log_loss','mean_predicted_pct',
        'actual_prevalence_pct','numeric_features','categorical_features'])
    write_csv(args.out_dir/'task5d2_risk_decile_calibration.csv',deciles,[
        'model','risk_decile_1_low_10_high','n','chargeoffs','observed_rate_pct',
        'mean_predicted_pct','absolute_gap_pp'])
    write_csv(args.out_dir/'task5d2_subgroup_calibration.csv',groups,[
        'model','group_field','group_value','n','chargeoffs','observed_rate_pct',
        'mean_predicted_pct','brier_score'])
    manifest={
        'task':'Project A Task 5D.2 Term-free chronological validation',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'input_basename':args.input.name,'input_sha256':sha256(args.input),
        'scope':'Strict FY2010–2014 enriched cohort only',
        'fit_years':list(TRAIN_YEARS),'validation_year':VALIDATION_YEAR,
        'counts':counts,'expected_checks':checks,
        'all_expected_checks_pass':all(checks.values()) if not args.smoke_test else None,
        'smoke_test':bool(args.smoke_test),
        'model_count':len(rows),'model_specifications':{k:{'numerical':n,'categorical':c} for k,(n,c) in SPECS.items()},
        'term_features_in_any_model':False,'business_age_only_in_exploratory_C':True,
        'outcome_dates_as_features':False,'locked_test_rows_read':0,
        'preprocessing_fit_only_on_fy2010_2013':True,
        'python_version':sys.version.split()[0],
        'pandas_version':pd.__version__,'sklearn_version':sklearn.__version__,
        'no_loan_level_predictions_exported':True,
        'interpretation_limits':[
            'Validation is retrospective and conditioned on a strict cohort constructed using eventual outcomes/status.',
            'Term-validity is part of cohort entry even though Term is excluded as a prediction feature.',
            'Approval-time historical provenance of all source features remains to be documented.',
            'BusinessAge is exploratory in specification C only; not approved for deployment.',
            'Do not use FY2015-2016 for model tuning; early baseline previously inspected this period.'
        ]
    }
    (args.out_dir/'task5d2_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('DONE: '+str(args.out_dir),flush=True)
    if not args.smoke_test:
        print('Quality checks passed:',all(checks.values()),flush=True)
    else:
        print('Synthetic smoke test finished; official cohort QA intentionally skipped.',flush=True)

if __name__=='__main__':main()
