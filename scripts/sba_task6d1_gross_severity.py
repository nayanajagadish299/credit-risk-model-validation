#!/usr/bin/env python3
"""Aggregate-only gross charge-off severity study for the SBA 7(a) FOIA snapshot."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,re
from collections import Counter,defaultdict
from datetime import date,datetime
from pathlib import Path
import numpy as np

EXPECTED_SHA256='b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6'
EXPECTED_ROWS=403644
EXPECTED_DEDUPED_CHGOFF=8202
EXPECTED_MISSING_CHARGEOFF_DATE=11
MIN_GROUP_N=30
AS_OF=date(2026,9,30)
FORMATS=('%Y-%m-%d','%m/%d/%Y','%m/%d/%y','%Y%m%d','%m-%d-%Y','%Y/%m/%d')

def key(x): return re.sub(r'[^a-z0-9]','',(x or '').lower())
def normalize_status(x):
 s=re.sub(r'[^A-Za-z]','',(x or '')).upper()
 return {'CHARGEDOFF':'CHGOFF','PAIDINFULL':'PIF','CANCELLED':'CANCLD','CANCELED':'CANCLD','COMMITMENT':'COMMIT'}.get(s,s or 'MISSING')
def parse_num(x):
 try:
  y=float((x or '').strip().replace(',','').replace('$',''))
  return y if math.isfinite(y) else None
 except ValueError:return None
def parse_date(x):
 s=(x or '').strip()
 for fmt in FORMATS:
  try:return datetime.strptime(s,fmt).date()
  except ValueError:pass
 return None
def fy(d):return d.year+(d.month>=10)
def file_hash(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**22),b''):h.update(b)
 return h.hexdigest()
def summary(values):
 a=np.asarray(values,dtype=float)
 if not len(a):return {'n':0,'total':0.0,'mean':'','median':'','q25':'','q75':'','p90':'','p95':'','p99':''}
 return {'n':int(len(a)),'total':float(a.sum()),'mean':float(a.mean()),'median':float(np.quantile(a,.5)), 'q25':float(np.quantile(a,.25)),'q75':float(np.quantile(a,.75)),'p90':float(np.quantile(a,.9)),'p95':float(np.quantile(a,.95)),'p99':float(np.quantile(a,.99))}
def loan_band(x):
 if x is None or x<=0:return 'INVALID_OR_MISSING'
 if x<50000:return '<50K'
 if x<150000:return '50K-<150K'
 if x<350000:return '150K-<350K'
 return '>=350K'
def chargeoff_ratio(amount,approval):
 if amount is None or amount<0 or approval is None or approval<=0:return None
 return amount/approval

def audit(source:Path,out:Path):
 if file_hash(source)!=EXPECTED_SHA256:raise ValueError('STOP: source SHA-256 mismatch')
 if out.resolve()==source.parent.resolve():raise ValueError('Output must be separate from raw source')
 allrows=Counter(); statuscounts=Counter();flags=Counter();seen=set(); chgoff=[]
 # One record per exact row after within-file deduplication, matching Task 6A/6B.
 with source.open('r',encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);fields={key(h):h for h in r.fieldnames or []}
  required=['AsOfDate','ApprovalDate','ApprovalFY','LoanStatus','GrossApproval','SBAGuaranteedApproval','ChargeOffDate','GrossChargeOffAmount','NaicsCode','ProjectState']
  missing=[x for x in required if key(x) not in fields]
  if missing:raise ValueError('Missing required source fields: '+', '.join(missing))
  for row in r:
   allrows['raw']+=1
   sig=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).digest()
   if sig in seen:allrows['duplicate_excess']+=1;continue
   seen.add(sig);allrows['unique']+=1
   get=lambda n:(row.get(fields.get(key(n),''),'') or '').strip()
   st=normalize_status(get('LoanStatus'));statuscounts[st]+=1
   if st!='CHGOFF':continue
   co=parse_num(get('GrossChargeOffAmount'));ga=parse_num(get('GrossApproval'));sg=parse_num(get('SBAGuaranteedApproval'))
   ad=parse_date(get('ApprovalDate'));cd=parse_date(get('ChargeOffDate'));rawfy=get('ApprovalFY')
   try:reported_fy=int(float(rawfy))
   except (ValueError,TypeError):reported_fy=None
   vintage=reported_fy if reported_fy is not None else 'MISSING_FY'
   rowflags=[]
   if co is None:rowflags.append('missing_or_invalid_gross_chargeoff_amount')
   elif co<0:rowflags.append('negative_gross_chargeoff_amount')
   elif co==0:rowflags.append('zero_gross_chargeoff_amount')
   if ga is None:rowflags.append('missing_or_invalid_gross_approval')
   elif ga<=0:rowflags.append('nonpositive_gross_approval')
   if sg is None:rowflags.append('missing_or_invalid_sba_guaranteed_approval')
   elif ga is not None and (sg<0 or sg>ga):rowflags.append('guarantee_outside_0_to_approval')
   if not get('ChargeOffDate'):rowflags.append('missing_chargeoff_date')
   elif cd is None:rowflags.append('invalid_chargeoff_date')
   if ad is None:rowflags.append('missing_or_invalid_approval_date')
   elif reported_fy is not None and fy(ad)!=reported_fy:rowflags.append('approval_fy_date_mismatch')
   if ad and cd and cd<ad:rowflags.append('chargeoff_before_approval')
   if cd and cd>AS_OF:rowflags.append('chargeoff_after_snapshot')
   if co is not None and ga is not None and ga>0 and co>ga:rowflags.append('gross_chargeoff_exceeds_gross_approval')
   for flag in rowflags:flags[flag]+=1
   ratio=chargeoff_ratio(co,ga)
   naics=''.join(z for z in get('NaicsCode') if z.isdigit())[:2] or 'MISSING'
   state=get('ProjectState').upper() or 'MISSING'
   band=loan_band(ga)
   cal_year=cd.year if cd else 'MISSING_OR_INVALID_DATE'
   chgoff.append({'amount':co,'ratio':ratio,'vintage':vintage,'chargeoff_year':cal_year,'naics2':naics,'state':state,'size_band':band,'approval':ga,'date':cd,'flags':rowflags})
 if allrows['raw']!=EXPECTED_ROWS:raise ValueError(f"Unexpected source rows: {allrows['raw']}")
 dims=[('OVERALL',''),('APPROVAL_FY','vintage'),('CHARGEOFF_CALENDAR_YEAR','chargeoff_year'),('NAICS2','naics2'),('PROJECT_STATE','state'),('ORIGINAL_GROSS_APPROVAL_BAND','size_band')]
 def groups_by(dim,field):
  if dim=='OVERALL':return [('ALL',chgoff)]
  return [(str(x),[r for r in chgoff if str(r[field])==str(x)]) for x in sorted({str(r[field]) for r in chgoff})]
 out.mkdir(parents=True,exist_ok=True)
 dist=[];ratio_rows=[];suppressed=Counter()
 for dim,field in dims:
  for label,records in groups_by(dim,field):
   if dim!='OVERALL' and len(records)<MIN_GROUP_N:suppressed[dim]+=1;continue
   vals=[r['amount'] for r in records if r['amount'] is not None]
   d=summary(vals);dist.append({'dimension':dim,'group':label,'chgoff_records_denominator':len(records),'valid_amount_n':d['n'],**{k:d[k] for k in ('total','mean','median','q25','q75','p90','p95','p99')}})
   ratios=[r['ratio'] for r in records if r['ratio'] is not None];rs=summary(ratios)
   ratio_rows.append({'dimension':dim,'group':label,'chgoff_records_denominator':len(records),'valid_ratio_n':rs['n'],'invalid_ratio_n':len(records)-rs['n'],**{k:rs[k] for k in ('mean','median','q25','q75','p90','p95','p99')}})
 def write(name,rows,headers=None):
  if headers is None:headers=list(rows[0]) if rows else []
  with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
   w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
 write('gross_chargeoff_amount_distribution.csv',dist)
 write('gross_chargeoff_to_approval_ratio.csv',ratio_rows)
 # Vintage-by-event-calendar-year cross-tab keeps approval cohorts separate from charge-off timing.
 cross=Counter()
 for r in chgoff:cross[(str(r['vintage']),str(r['chargeoff_year']))]+=1
 write('vintage_by_chargeoff_calendar_year.csv',[{'approval_fy':v,'chargeoff_calendar_year':c,'chgoff_records':n} for (v,c),n in sorted(cross.items())])
 quality=[{'flag':k,'records':v} for k,v in sorted(flags.items())]
 write('quality_flags.csv',quality,['flag','records'])
 denom=len(chgoff); amounts=[r['amount'] for r in chgoff if r['amount'] is not None];ratios=[r['ratio'] for r in chgoff if r['ratio'] is not None]
 overall={'raw_rows':allrows['raw'],'duplicate_excess_rows':allrows['duplicate_excess'],'unique_rows':allrows['unique'],'unique_chgoff_records':denom,'missing_or_invalid_chargeoff_date':flags['missing_chargeoff_date']+flags['invalid_chargeoff_date'],'valid_gross_chargeoff_amount_n':len(amounts),'valid_ratio_n':len(ratios),'invalid_ratio_n':denom-len(ratios),'gross_chargeoff_amount_exceeds_approval':flags['gross_chargeoff_exceeds_gross_approval'],'mean_gross_chargeoff_to_approval_ratio':float(np.mean(ratios)) if ratios else '', 'denominator':'All exact-row-deduplicated CHGOFF-status records; amount and ratio valid counts shown separately.'}
 write('overall_reconciliation.csv',[overall])
 report_names=['gross_chargeoff_amount_distribution.csv','gross_chargeoff_to_approval_ratio.csv','vintage_by_chargeoff_calendar_year.csv','quality_flags.csv','overall_reconciliation.csv']
 hashes={n:file_hash(out/n) for n in report_names}
 checks={'source_checksum':'PASS','source_raw_row_count':'PASS','exact_row_deduplication':'PASS','chgoff_records_reconcile':'PASS' if denom==EXPECTED_DEDUPED_CHGOFF else 'FAIL','missing_chargeoff_dates_reconcile':'PASS' if flags['missing_chargeoff_date']==EXPECTED_MISSING_CHARGEOFF_DATE else 'FAIL','group_suppression_min_n':'PASS','aggregate_reports_hashed':'PASS'}
 manifest={'study':'Task 6D.1 gross charge-off severity, descriptive only','source_file':source.name,'source_sha256':file_hash(source),'snapshot_date':AS_OF.isoformat(),'source_rows':allrows['raw'],'duplicate_excess_rows':allrows['duplicate_excess'],'unique_rows':allrows['unique'],'status_counts':dict(statuscounts),'chgoff_records':denom,'missing_chargeoff_dates':flags['missing_chargeoff_date'],'amount_valid_n':len(amounts),'ratio_valid_n':len(ratios),'ratio_denominator':'CHGOFF rows with finite GrossChargeOffAmount >= 0 and finite GrossApproval > 0','minimum_comparison_group_n':MIN_GROUP_N,'suppressed_group_counts':dict(suppressed),'quality_flags':dict(flags),'checks':checks,'report_sha256':hashes,'interpretation_limits':['GrossChargeOffAmount is not recovery-adjusted loss, LGD, or EAD.','GrossChargeOffAmount/GrossApproval is only a gross charge-off-to-approval ratio, never LGD.','Approval-vintage comparisons face unequal loan ages and right-censoring; charge-off calendar year is reported separately.','Recoveries are incomplete/unavailable; this is not net economic loss.','Selection on CHGOFF status and retrospective FOIA visibility can bias severity comparisons.','No flagged amount is capped or silently removed; validity-specific denominators are explicit.']}
 # Assertions are performed before manifest is written.
 if flags['missing_chargeoff_date']!=EXPECTED_MISSING_CHARGEOFF_DATE:checks['missing_chargeoff_dates_reconcile']='FAIL'
 if any(v!='PASS' for v in checks.values()):manifest['checks']=checks
 (out/'task6d1_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps({'overall':overall,'checks':checks,'manifest':str(out/'task6d1_manifest.json')},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();audit(a.source,a.out_dir)
if __name__=='__main__':main()
