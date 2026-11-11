#!/usr/bin/env python3
"""Task 6C.1 contemporary 24-month SBA charge-off model development.

Only FY2020-2022 fit the models and FY2023 is used for development validation.
FY2024 rows are preserved in the local model input but never loaded for scoring.
All row-level data, models, and predictions remain in the external output folder.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, platform, sys, warnings
from collections import Counter
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, log_loss,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import sba_task6b_24m_cohort_audit as cohort

SEED=20261112
SCRIPT_VERSION="task6c1-contemporary-24m-v1"
TRAIN_FYS=(2020,2021,2022); VALID_FY=2023; EVAL_FY=2024
NUMERIC=("log_gross_approval","guarantee_share","initial_interest_rate")
CATEGORICAL=("naics2","project_state","business_type","processing_method","revolver_status","fixed_or_variable_interest_ind","collateral_ind")
FEATURES=NUMERIC+CATEGORICAL
SOURCE_SHA="b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6"
EXPECTED={2020:(42205,36440,79,36361),2021:(51758,45146,96,45050),2022:(47624,41756,281,41475),2023:(57324,50236,476,49760),2024:(70211,60114,417,59697)}

def source_digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(2**22),b""): h.update(b)
    return h.hexdigest()

def extract(source:Path,out:Path):
    """Reuse the Task 6B classifier verbatim; write a minimized local-only table."""
    if source_digest(source)!=SOURCE_SHA: raise ValueError("Source SHA-256 mismatch")
    counts={fy:Counter() for fy in EXPECTED}; seen=set(); dropped_duplicates=0
    with source.open("r",encoding="utf-8-sig",newline="") as f, gzip.open(out,"wt",encoding="utf-8",newline="") as dest:
        reader=csv.DictReader(f); fields={cohort.key(h):h for h in reader.fieldnames}
        required=("ApprovalDate","ApprovalFY","LoanStatus","PaidInFullDate","ChargeOffDate","GrossApproval","SBAGuaranteedApproval","InitialInterestRate","NaicsCode","ProjectState","BusinessType","ProcessingMethod","RevolverStatus","FixedorVariableInterestInd","CollateralInd")
        missing=[x for x in required if cohort.key(x) not in fields]
        if missing: raise ValueError(f"Missing source fields: {missing}")
        w=csv.DictWriter(dest,fieldnames=("approval_fy","target",*FEATURES),lineterminator="\n"); w.writeheader()
        for row in reader:
            signature=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).digest()
            if signature in seen: dropped_duplicates+=1; continue
            seen.add(signature)
            get=lambda n:(row.get(fields.get(cohort.key(n),""),"") or "").strip()
            d=cohort.parse_date(get("ApprovalDate"))
            try: fy_hint=int(float(get("ApprovalFY")))
            except (ValueError,TypeError): fy_hint=None
            fy=cohort.fy(d) if d else fy_hint
            if fy not in EXPECTED: continue
            counts[fy]["candidate"]+=1
            y,flags,_,_=cohort.classify(row,fields)
            if y is None:
                counts[fy]["excluded"]+=1; continue
            counts[fy]["eligible"]+=1; counts[fy]["positive"]+=y; counts[fy]["negative"]+=1-y
            def number(field):
                x=get(field).replace(",","").replace("$","").replace("%","")
                try:
                    val=float(x); return val if np.isfinite(val) else np.nan
                except ValueError: return np.nan
            gross=number("GrossApproval"); guaranteed=number("SBAGuaranteedApproval")
            rate=number("InitialInterestRate")
            sector="".join(c for c in get("NaicsCode") if c.isdigit())[:2]
            record={"approval_fy":fy,"target":y,"log_gross_approval":float(np.log1p(gross)) if gross>0 else np.nan,
                    "guarantee_share":guaranteed/gross if gross>0 and np.isfinite(guaranteed) else np.nan,
                    "initial_interest_rate":rate,"naics2":sector,"project_state":get("ProjectState"),
                    "business_type":get("BusinessType"),"processing_method":get("ProcessingMethod"),
                    "revolver_status":get("RevolverStatus"),"fixed_or_variable_interest_ind":get("FixedorVariableInterestInd"),
                    "collateral_ind":get("CollateralInd")}
            w.writerow(record)
    for fy,expected in EXPECTED.items():
        actual=counts[fy]
        values=(actual["candidate"],actual["eligible"],actual["positive"],actual["negative"])
        if values!=expected: raise ValueError(f"FY{fy} Task 6B reconciliation failed: {values} != {expected}")
    return counts,dropped_duplicates

def make_preprocessor(model):
    numeric=Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())])
    categorical=Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore"))])
    prep=ColumnTransformer([("num",numeric,list(NUMERIC)),("cat",categorical,list(CATEGORICAL))])
    if model=="logistic": return Pipeline([("preprocess",prep),("model",LogisticRegression(C=0.1,class_weight=None,max_iter=1000,solver="liblinear",random_state=SEED))])
    if model=="hgb":
        # Dense one-hot is acceptable for this modest feature set and avoids external encodings.
        categorical=Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore",sparse_output=False))])
        prep=ColumnTransformer([("num",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True))]),list(NUMERIC)),("cat",categorical,list(CATEGORICAL))],sparse_threshold=0)
        return Pipeline([("preprocess",prep),("model",HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,learning_rate=0.05,l2_regularization=5.0,min_samples_leaf=80,early_stopping=False,random_state=SEED))])
    raise ValueError(model)

def score_metrics(y,p):
    return {"average_precision":float(average_precision_score(y,p)),"roc_auc":float(roc_auc_score(y,p)),"brier_score":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1])),"mean_predicted_probability":float(np.mean(p)),"observed_prevalence":float(np.mean(y))}

def bootstrap_ap(y,p,n_boot=300,seed=SEED):
    rng=np.random.default_rng(seed); vals=[]; y=np.asarray(y);p=np.asarray(p)
    for _ in range(n_boot):
        idx=rng.integers(0,len(y),len(y))
        if len(np.unique(y[idx]))==2: vals.append(average_precision_score(y[idx],p[idx]))
    return {"replicates_requested":n_boot,"replicates_valid":len(vals),"ap_95pct_low":float(np.quantile(vals,.025)),"ap_95pct_high":float(np.quantile(vals,.975))}

def run(input_gz:Path,out:Path,source_sha=SOURCE_SHA):
    df=pd.read_csv(input_gz,compression="gzip")
    if set(df.approval_fy.unique())!={2020,2021,2022,2023,2024}: raise ValueError("Model input fiscal years mismatch")
    train=df[df.approval_fy.isin(TRAIN_FYS)].copy(); valid=df[df.approval_fy==VALID_FY].copy()
    if set(train.approval_fy.unique())!=set(TRAIN_FYS) or len(valid)==0: raise ValueError("Required development split missing")
    Xtr=train.loc[:,FEATURES]; ytr=train.target.to_numpy(); Xv=valid.loc[:,FEATURES]; yv=valid.target.to_numpy()
    prevalence=float(ytr.mean()); specs={"constant_prevalence":None,"regularized_logistic":make_preprocessor("logistic"),"conservative_hist_gradient_boosting":make_preprocessor("hgb")}
    out.mkdir(parents=True,exist_ok=True); modeldir=out/"models"; modeldir.mkdir(exist_ok=True)
    predictions=[]; metric_rows=[]; models={}
    for name,pipe in specs.items():
        if pipe is None: p=np.full(len(valid),prevalence,dtype=float)
        else:
            pipe.fit(Xtr,ytr); p=pipe.predict_proba(Xv)[:,1]; models[name]=pipe
            joblib.dump(pipe,modeldir/f"{name}.joblib")
        m=score_metrics(yv,p); m={"model":name,**m,"training_prevalence":prevalence}
        if name!="constant_prevalence": m.update(bootstrap_ap(yv,p))
        else: m.update({"replicates_requested":300,"replicates_valid":"","ap_95pct_low":"","ap_95pct_high":""})
        metric_rows.append(m)
        for i,(fy,y,prob) in enumerate(zip(valid.approval_fy,yv,p)):
            predictions.append({"approval_fy":int(fy),"target":int(y),"predicted_probability":float(prob),"model":name})
    metrics_path=out/"validation_metrics.csv"
    pd.DataFrame(metric_rows).to_csv(metrics_path,index=False)
    pred_path=out/"validation_predictions.csv.gz"
    pd.DataFrame(predictions).to_csv(pred_path,index=False,compression="gzip")
    cal=[]
    for name in specs:
        q=[x for x in predictions if x["model"]==name]; ps=np.array([x["predicted_probability"] for x in q]); yy=np.array([x["target"] for x in q])
        # Quantile bins are descriptive; duplicate boundaries collapse safely.
        bins=pd.qcut(pd.Series(ps),q=min(10,len(ps)),duplicates="drop")
        for b,idx in pd.Series(bins).groupby(bins,observed=True).groups.items():
            idx=np.asarray(list(idx),dtype=int); cal.append({"model":name,"risk_quantile":str(b),"n":len(idx),"mean_predicted":float(ps[idx].mean()),"observed_rate":float(yy[idx].mean())})
    pd.DataFrame(cal).to_csv(out/"quantile_calibration.csv",index=False)
    operating=[]
    for name in specs:
        q=[x for x in predictions if x["model"]==name]; yy=np.array([x["target"] for x in q]); pp=np.array([x["predicted_probability"] for x in q])
        for threshold in (.005,.01,.02,.05):
            operating.append({"model":name,"threshold":threshold,"precision":float(precision_score(yy,pp>=threshold,zero_division=0)),"recall":float(recall_score(yy,pp>=threshold,zero_division=0)),"flagged_n":int((pp>=threshold).sum())})
    pd.DataFrame(operating).to_csv(out/"operating_points.csv",index=False)
    settings={"seed":SEED,"train_fys":TRAIN_FYS,"validation_fy":VALID_FY,"evaluation_fy_reserved":EVAL_FY,"FY2024_used_for_selection_or_scoring":False,"logistic":{"C":.1,"solver":"liblinear","max_iter":1000},"hgb":{"max_iter":100,"max_leaf_nodes":7,"learning_rate":.05,"l2_regularization":5,"min_samples_leaf":80,"early_stopping":False},"class_weights_or_oversampling":"none","calibration_bins":"up to 10 quantiles","operating_thresholds":[.005,.01,.02,.05],"bootstrap":{"metric":"average_precision","replicates":300,"seed":SEED}}
    artifact_files=[metrics_path,pred_path,out/"quantile_calibration.csv",out/"operating_points.csv",*modeldir.glob("*.joblib")]
    file_hashes={p.relative_to(out).as_posix():source_digest(p) for p in artifact_files}
    manifest={"script_version":SCRIPT_VERSION,"source_sha256":source_sha,"task6b_source_sha256_expected":source_sha==SOURCE_SHA,"cohort_counts":{str(y):{k:int(v) for k,v in c.items()} for y,c in extract_counts.items()},"model_input_rows":len(df),"train_rows":len(train),"train_positives":int(ytr.sum()),"train_negatives":int(len(ytr)-ytr.sum()),"validation_rows":len(valid),"validation_positives":int(yv.sum()),"validation_negatives":int(len(yv)-yv.sum()),"features":list(FEATURES),"feature_audit":{"GrossApproval":"log transformed; approval-time value unverified","SBAGuaranteedApproval":"ratio with approval amount; approval-time value unverified","InitialInterestRate":"candidate origination attribute; point-in-time value unverified","NaicsCode":"sector prefix; point-in-time value unverified","ProjectState":"point-in-time value unverified","BusinessType":"point-in-time value unverified","ProcessingMethod":"point-in-time value unverified","RevolverStatus":"point-in-time value unverified","FixedorVariableInterestInd":"point-in-time value unverified","CollateralInd":"point-in-time value unverified","excluded":"Term/term derivatives, BusinessAge, status, event dates, loss amount, identifiers, JobsSupported, follow-up and outcome-derived features"},"split_years":{"train":list(TRAIN_FYS),"development_validation":[VALID_FY],"reserved_not_scored":[EVAL_FY]},"settings":settings,"packages":{"python":platform.python_version(),"pandas":pd.__version__,"numpy":np.__version__,"scikit_learn":sklearn.__version__,"joblib":joblib.__version__},"selection_bias":"Retrospective outcome/status eligibility and exclusion of cancelled/committed loans can induce selection bias; FY2024 previously inspected during cohort construction and is not pristine.","checks":{"cohort_counts_reconcile":"PASS","split_years_correct":"PASS","FY2024_not_scored":"PASS","only_training_preprocessing_fit":"PASS","aggregate_outputs_created":"PASS"},"sha256_outputs":file_hashes}
    (out/"task6c_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    pd.DataFrame(metric_rows).to_csv(out/"validation_metrics.csv",index=False)
    print(json.dumps({"metrics":metric_rows,"manifest":str(out/"task6c_manifest.json"),"FY2024_evaluation":"NOT RUN"},indent=2))

def main():
    global extract_counts
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source",type=Path,required=True);p.add_argument("--out-dir",type=Path,required=True);a=p.parse_args()
    if a.out_dir.exists() and any(a.out_dir.iterdir()): raise SystemExit("Output directory must be new or empty")
    a.out_dir.mkdir(parents=True,exist_ok=True); model_input=a.out_dir/"model_input_local.csv.gz"
    extract_counts,_=extract(a.source,model_input)
    run(model_input,a.out_dir)
if __name__=="__main__": main()
