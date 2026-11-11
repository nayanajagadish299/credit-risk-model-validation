#!/usr/bin/env python3
"""Freeze Task 6C.1 artifacts, then score FY2024 once without refitting."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,platform
from pathlib import Path
import joblib,numpy as np,pandas as pd,sklearn
from sklearn.metrics import average_precision_score,roc_auc_score,brier_score_loss,log_loss,precision_score,recall_score
import sba_task6c_24m_model_validation as dev

SEED=20261113; BOOTSTRAPS=1000
HGB="conservative_hist_gradient_boosting"; LR="regularized_logistic"; BASE="constant_prevalence"

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(2**22),b''): h.update(b)
 return h.hexdigest()

def paired_delta_ci(y,a,b,n=BOOTSTRAPS,seed=SEED):
 rng=np.random.default_rng(seed); y=np.asarray(y); a=np.asarray(a); b=np.asarray(b); vals=[]
 for _ in range(n):
  ix=rng.integers(0,len(y),len(y))
  if len(np.unique(y[ix]))==2: vals.append(average_precision_score(y[ix],a[ix])-average_precision_score(y[ix],b[ix]))
 point=average_precision_score(y,a)-average_precision_score(y,b)
 return {"difference_hgb_minus_logistic":float(point),"ci_95_low":float(np.quantile(vals,.025)),"ci_95_high":float(np.quantile(vals,.975)),"replicates_requested":n,"replicates_valid":len(vals),"seed":seed}

def metrics(y,p):
 return {"average_precision":float(average_precision_score(y,p)),"roc_auc":float(roc_auc_score(y,p)),"brier_score":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1])),"observed_prevalence":float(np.mean(y)),"mean_predicted_probability":float(np.mean(p))}

def prediction_file_valid(path):
 """True only for scalar, row-aligned loan/model prediction records."""
 try:
  with gzip.open(path,"rt",newline="",encoding="utf-8") as f:
   r=csv.DictReader(f)
   if r.fieldnames!=["model","approval_fy","target","predicted_probability"]: return False
   n=0
   for row in r:
    if "..." in row["target"] or "..." in row["predicted_probability"]: return False
    y=int(row["target"]); p=float(row["predicted_probability"]); fy=int(row["approval_fy"])
    if y not in (0,1) or not 0<=p<=1 or fy!=2024: return False
    n+=1
   return n>0
 except (OSError,ValueError,TypeError,KeyError): return False

def run(devout:Path,source:Path,out:Path):
 if out.exists() and any(out.iterdir()): raise ValueError("Evaluation output must be new or empty")
 out.mkdir(parents=True,exist_ok=True)
 dm=json.loads((devout/'task6c_manifest.json').read_text())
 if sha(source)!=dm['source_sha256']: raise ValueError('Raw source checksum differs from development manifest')
 # Freeze gate uses development-only metrics/predictions and model bytes; no FY2024 model scores are read.
 artifact_paths={k:devout/k for k in dm['sha256_outputs'] if k.startswith('models/')}
 verified={k:sha(p)==dm['sha256_outputs'][k] for k,p in artifact_paths.items()}
 if not all(verified.values()): raise ValueError('Development artifact hash mismatch')
 for k in ('cohort_counts_reconcile','split_years_correct','FY2024_not_scored','only_training_preprocessing_fit'):
  if dm['checks'].get(k)!='PASS': raise ValueError('Development manifest check failed: '+k)
 pred=pd.read_csv(devout/'validation_predictions.csv.gz')
 val=pred[pred.model.isin([HGB,LR])]
 if len(val)!=2*dm['validation_rows'] or set(val.approval_fy)!={2023}: raise ValueError('FY2023 predictions do not reconcile')
 # Extract paired rows in the original identical ordering; validate targets match.
 hp=pred[pred.model==HGB].reset_index(drop=True)
 lp=pred[pred.model==LR].reset_index(drop=True)
 if not np.array_equal(hp.target.to_numpy(),lp.target.to_numpy()): raise ValueError('FY2023 matched outcomes differ')
 pair23=paired_delta_ci(hp.target,hp.predicted_probability,lp.predicted_probability)
 met=pd.read_csv(devout/'validation_metrics.csv').set_index('model')
 freeze={"freeze_version":"task6c2-freeze-v1","source_sha256":dm['source_sha256'],"split":{"train":[2020,2021,2022],"development_validation":[2023],"reserved_evaluation":[2024]},"selected_primary":HGB,"benchmark":LR,"reference":BASE,"rationale":"Selected provisionally on FY2023 PR-AUC, Brier and log loss; no model changes after selection.","FY2024_predictive_results_used_for_selection":False,"FY2024_previous_aggregate_cohort_counts_seen":True,"training_prevalence":dm['train_positives']/dm['train_rows'],"validation_prevalence":dm['validation_positives']/dm['validation_rows'],"prevalence_ratio_validation_to_train":(dm['validation_positives']/dm['validation_rows'])/(dm['train_positives']/dm['train_rows']),"FY2023_paired_bootstrap_HGB_minus_logistic_AP":pair23,"FY2023_metrics":{name:{k:float(met.loc[name,k]) for k in ('average_precision','roc_auc','brier_score','log_loss')} for name in (HGB,LR,BASE)},"model_sha256":{k:sha(p) for k,p in artifact_paths.items()},"feature_allowlist":dm['features'],"preprocessing":"Pipelines frozen in joblib artifacts: median imputation + missing indicators and standard scaling for numeric features; most-frequent imputation and one-hot encoding for categoricals.","packages":dm['packages'],"random_seed":dm['settings']['seed'],"checks":{"development_manifest":"PASS","model_artifact_hashes":"PASS","FY2023_prediction_alignment":"PASS","FY2024_not_used_for_selection":"PASS"}}
 freeze_path=out/'model_freeze_manifest.json'; freeze_path.write_text(json.dumps(freeze,indent=2),encoding='utf-8')
 # Verify freeze record and artifact hashes before reading/scoring FY2024 labels.
 frozen=json.loads(freeze_path.read_text())
 if any(sha(devout/k)!=v for k,v in frozen['model_sha256'].items()): raise ValueError('Frozen artifact changed before evaluation')
 if frozen['selected_primary']!=HGB or frozen['checks']['model_artifact_hashes']!='PASS': raise ValueError('Freeze gate failed')
 usecols=['approval_fy','target',*dev.FEATURES]
 data=pd.read_csv(devout/'model_input_local.csv.gz',compression='gzip',usecols=usecols)
 f24=data[data.approval_fy==2024].copy()
 if len(f24)!=60114 or int(f24.target.sum())!=417: raise ValueError(f"FY2024 Task 6B reconciliation failed: n={len(f24)}, positives={int(f24.target.sum())}")
 y=f24.target.to_numpy(dtype=int); models={name:joblib.load(devout/'models'/f'{name}.joblib') for name in (HGB,LR)}
 prevalence=dm['train_positives']/dm['train_rows']; probs={BASE:np.full(len(y),prevalence)}
 X=f24.loc[:,dev.FEATURES]
 for name,model in models.items(): probs[name]=model.predict_proba(X)[:,1]
 rows=[]
 for name,p in probs.items(): rows.append({"model":name,**metrics(y,p)})
 pd.DataFrame(rows).to_csv(out/'fy2024_model_comparison.csv',index=False)
 cal=[]
 for name,p in probs.items():
  bins=pd.qcut(pd.Series(p),q=10,duplicates='drop')
  for band,idx in pd.Series(bins).groupby(bins,observed=True).groups.items():
   ix=np.asarray(list(idx),dtype=int); cal.append({"model":name,"quantile":str(band),"n":len(ix),"mean_predicted":float(p[ix].mean()),"observed_rate":float(y[ix].mean())})
 pd.DataFrame(cal).to_csv(out/'fy2024_quantile_calibration.csv',index=False)
 op=[]
 for name,p in probs.items():
  for t in (.005,.01,.02,.05): op.append({"model":name,"threshold":t,"precision":precision_score(y,p>=t,zero_division=0),"recall":recall_score(y,p>=t,zero_division=0),"flagged_n":int((p>=t).sum())})
 pd.DataFrame(op).to_csv(out/'fy2024_operating_points.csv',index=False)
 paired24=paired_delta_ci(y,probs[HGB],probs[LR])
 (out/'paired_bootstrap_comparison.json').write_text(json.dumps({"FY2023":pair23,"FY2024":paired24},indent=2),encoding='utf-8')
 # Local-only loan-level scoring file.
 score=pd.DataFrame([{"model":name,"approval_fy":2024,"target":int(y[i]),"predicted_probability":float(p[i])} for name,p in probs.items() for i in range(len(y))])
 score.to_csv(out/'fy2024_predictions_local.csv.gz',index=False,compression='gzip')
 # FY2023-to-FY2024 metric changes, using the already frozen FY2023 table.
 changes=[]
 for name in (BASE,LR,HGB):
  for metric in ('average_precision','roc_auc','brier_score','log_loss','observed_prevalence','mean_predicted_probability'):
   changes.append({"model":name,"metric":metric,"FY2023":float(met.loc[name,metric]) if metric in met.columns else float(met.loc[name,'observed_prevalence'] if metric=='observed_prevalence' else met.loc[name,'mean_predicted_probability']),"FY2024":next(r[metric] for r in rows if r['model']==name),"FY2024_minus_FY2023":next(r[metric] for r in rows if r['model']==name)-float(met.loc[name,metric]) if metric in met.columns else 0.0})
 pd.DataFrame(changes).to_csv(out/'FY2023_vs_FY2024_changes.csv',index=False)
 report_names=['fy2024_model_comparison.csv','fy2024_quantile_calibration.csv','fy2024_operating_points.csv','paired_bootstrap_comparison.json','fy2024_predictions_local.csv.gz','FY2023_vs_FY2024_changes.csv']
 hashes={p:sha(out/p) for p in report_names}
 evaluation={"version":"task6c2-evaluation-v1","freeze_manifest_sha256":sha(freeze_path),"source_sha256":dm['source_sha256'],"FY2024_rows":len(f24),"FY2024_positive":int(y.sum()),"FY2024_negative":int(len(y)-y.sum()),"scores_run_once":True,"models_scored":[BASE,LR,HGB],"paired_bootstrap":{"replicates":BOOTSTRAPS,"seed":SEED},"checks":{"freeze_verified_before_score":"PASS","FY2024_cohort_counts":"PASS","same_eligible_observations":"PASS","no_refit_or_retune":"PASS","FY2024_not_used_for_selection":"PASS","reports_hashed":"PASS"},"sha256_outputs":hashes,"FY2024_is_later_year_not_pristine_blind_test":True}
 (out/'evaluation_manifest.json').write_text(json.dumps(evaluation,indent=2),encoding='utf-8')
 print(json.dumps({"freeze":freeze,"FY2024_metrics":rows,"paired_FY2024":paired24,"evaluation_manifest":str(out/'evaluation_manifest.json')},indent=2))

def main():
 p=argparse.ArgumentParser();p.add_argument('--development-dir',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
 if a.out_dir.exists():
  leftovers=[x.name for x in a.out_dir.iterdir() if x.name!="model_freeze_manifest.json"]
  if leftovers: raise SystemExit("Evaluation output directory already has evaluation files: "+", ".join(leftovers))
 run(a.development_dir,a.source,a.out_dir)
if __name__=='__main__': main()
