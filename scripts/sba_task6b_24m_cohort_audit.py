#!/usr/bin/env python3
"""Aggregate-only audit of a retrospective 24-month SBA charge-off cohort."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

AS_OF = date(2026, 9, 30)
EXPECTED_SHA256 = "b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6"
SCRIPT_VERSION = "task6b-finalqa-verified-v1"
YEARS = range(2020, 2025)
FEATURES = ("GrossApproval", "SBAGuaranteedApproval", "InitialInterestRate", "NaicsCode", "ProjectState", "BusinessType", "ProcessingMethod", "RevolverStatus", "FixedorVariableInterestInd", "CollateralInd")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%m-%d-%Y", "%Y/%m/%d")

def key(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
def parse_date(s):
    s = (s or "").strip()
    for f in DATE_FORMATS:
        try: return datetime.strptime(s, f).date()
        except ValueError: pass
    return None
def fy(d): return d.year + (d.month >= 10)
def add_months(d, n):
    import calendar
    m=d.month-1+n; y=d.year+m//12; mo=m%12+1
    return date(y,mo,min(d.day,calendar.monthrange(y,mo)[1]))
def status(s):
    x=re.sub(r"[^A-Za-z]", "", s or "").upper()
    return {"PAIDINFULL":"PIF","CHARGEDOFF":"CHGOFF","CANCELLED":"CANCLD","CANCELED":"CANCLD","COMMITMENT":"COMMIT"}.get(x,x or "MISSING")
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(2**21),b""): h.update(b)
    return h.hexdigest()

def classify(row, fields):
    get=lambda f:(row.get(fields.get(key(f),""),"") or "").strip()
    rawdate=get("ApprovalDate"); d=parse_date(rawdate); rawfy=get("ApprovalFY")
    try: afy=int(float(rawfy))
    except (ValueError,TypeError): afy=None
    s=status(get("LoanStatus")); paid_raw=get("PaidInFullDate"); co_raw=get("ChargeOffDate")
    p=parse_date(paid_raw); c=parse_date(co_raw); flags=[]; consistency=[]
    if s in ("CANCLD","COMMIT"): flags.append("excluded_status_"+s.lower())
    elif s not in ("CHGOFF","PIF","EXEMPT"): flags.append("unresolved_or_unrecognized_status")
    if d is None: flags.append("invalid_approval_date")
    if afy is None: flags.append("invalid_approval_fy")
    if d and afy and fy(d)!=afy: flags.append("approval_fy_date_mismatch")
    if p and c: flags.append("both_terminal_dates")
    if (paid_raw and not p) or (co_raw and not c): flags.append("invalid_terminal_date")
    if d and (p and p<d or c and c<d): flags.append("terminal_date_before_approval")
    if (p and p>AS_OF) or (c and c>AS_OF): flags.append("terminal_date_after_snapshot")
    if s=="CHGOFF" and not c: flags.append("chargeoff_status_without_valid_date")
    if s=="PIF" and not p: flags.append("pif_status_without_valid_date")
    if s=="EXEMPT" and (p or c): flags.append("exempt_status_with_terminal_date")
    if d and fy(d) in YEARS and afy and fy(d)==afy:
        consistency.append("fy_reconciled")
    elif d and afy and fy(d)!=afy: consistency.append("fy_mismatch")
    else: consistency.append("fy_unverifiable")
    horizon=add_months(d,24) if d else None
    if horizon and horizon>AS_OF: flags.append("less_than_24m_followup")
    if d and fy(d) not in YEARS: flags.append("outside_candidate_fy2020_2024")
    if get("FirstDisbursementDate") and not parse_date(get("FirstDisbursementDate")): flags.append("invalid_first_disbursement_date")
    fd=parse_date(get("FirstDisbursementDate"))
    if d and fd and fd<d: flags.append("disbursement_before_approval")
    if fd and fd>AS_OF: flags.append("disbursement_after_snapshot")
    if s in ("CHGOFF","PIF") and fd is None: flags.append("no_first_disbursement_evidence")
    priority=("excluded_status_cancld","excluded_status_commit","invalid_approval_date","invalid_approval_fy","approval_fy_date_mismatch","outside_candidate_fy2020_2024","less_than_24m_followup","both_terminal_dates","invalid_terminal_date","terminal_date_before_approval","terminal_date_after_snapshot","chargeoff_status_without_valid_date","pif_status_without_valid_date","exempt_status_with_terminal_date","unresolved_or_unrecognized_status")
    reason=next((x for x in priority if x in flags),None)
    # Date/status contradictions are excluded; missing event dates are not inferred as events.
    if reason is None:
        if s=="CHGOFF": y=int(c<=horizon)
        elif s=="PIF": y=0
        elif s=="EXEMPT": y=0
        else: y=None
        if s=="CHGOFF" and c>horizon: consistency.append("chargeoff_after_24m")
        if s=="CHGOFF" and c<=horizon: consistency.append("chargeoff_within_24m")
        if s=="PIF": consistency.append("paid_in_full_competing_event")
        if s=="EXEMPT": consistency.append("no_terminal_event_censored_at_snapshot")
        return y, flags, consistency, get
    return None,flags,consistency,get

def audit(source, out, expected_hash=EXPECTED_SHA256):
    if not source.is_file(): raise SystemExit(f"Missing source: {source}")
    if out.resolve()==source.parent.resolve(): raise SystemExit("Output must be separate from source directory")
    sha=digest(source)
    if sha.lower()!=expected_hash.lower(): raise SystemExit("STOP: source checksum mismatch; no outputs written")
    counts=defaultdict(Counter); exfy=Counter(); flagfy=Counter(); consistency=Counter(); missing=Counter(); disb=defaultdict(Counter); total=Counter(); seen=set()
    priority=("excluded_status_cancld","excluded_status_commit","invalid_approval_date","invalid_approval_fy","approval_fy_date_mismatch","outside_candidate_fy2020_2024","less_than_24m_followup","both_terminal_dates","invalid_terminal_date","terminal_date_before_approval","terminal_date_after_snapshot","chargeoff_status_without_valid_date","pif_status_without_valid_date","exempt_status_with_terminal_date","unresolved_or_unrecognized_status")
    with source.open("r",encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f); fields={key(h):h for h in (r.fieldnames or [])}
        required=("ApprovalDate","ApprovalFY","AsOfDate","LoanStatus","PaidInFullDate","ChargeOffDate","FirstDisbursementDate")
        absent=[x for x in required if key(x) not in fields]
        if absent: raise SystemExit("Missing required fields: "+", ".join(absent))
        for row in r:
            total["rows"]+=1; get=lambda n:(row.get(fields[key(n)],"") or "").strip()
            sig=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).digest()
            if sig in seen: total["duplicate_excess_rows"]+=1; continue
            seen.add(sig)
            snap=parse_date(get("AsOfDate"))
            total["snapshot_date_expected"]+=int(snap==AS_OF)
            total["snapshot_date_invalid"]+=int(snap!=AS_OF)
            d=parse_date(get("ApprovalDate"))
            try: hint=int(float(get("ApprovalFY")))
            except (ValueError,TypeError): hint=None
            year=fy(d) if d else hint
            if year not in YEARS: continue
            total[f"candidate_fy{year}"]+=1
            y,flags,checks,g=classify(row,fields); primary=next((x for x in priority if x in flags),None)
            if primary: exfy[(year,primary)]+=1
            for flag in flags: flagfy[(year,flag)]+=1
            for check in checks: consistency[check]+=1
            status_label=status(get("LoanStatus")); disbkey=(year,status_label); rawfd=get("FirstDisbursementDate"); fd=parse_date(rawfd)
            disb[disbkey]["n"]+=1
            if not rawfd: disb[disbkey]["missing"]+=1
            elif not fd: disb[disbkey]["invalid"]+=1
            else: disb[disbkey]["valid"]+=1
            for flag in flags:
                if flag in ("invalid_first_disbursement_date","disbursement_before_approval","disbursement_after_snapshot","no_first_disbursement_evidence"): disb[disbkey][flag]+=1
            if y is not None:
                counts[year]["eligible"]+=1; counts[year]["positive"]+=y; counts[year]["negative"]+=1-y
                if status_label=="CHGOFF" and parse_date(get("ChargeOffDate"))>add_months(d,24): counts[year]["later_chargeoffs"]+=1
                if status_label=="PIF": counts[year]["pif"]+=1
                if status_label=="EXEMPT": counts[year]["exempt"]+=1
                for feat in FEATURES:
                    if not g(feat): missing[(year,feat)]+=1
    out.mkdir(parents=True,exist_ok=True)
    def write(name,headers,rows):
        with (out/name).open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
    years=[]; recon=[]
    for year in YEARS:
        c=counts[year]; n=c["eligible"]; cand=total[f"candidate_fy{year}"]; ex=cand-n; exsum=sum(v for (yr,_),v in exfy.items() if yr==year)
        years.append({"approval_fy":year,"candidate":cand,"eligible":n,"positive":c["positive"],"negative":c["negative"],"later_chargeoffs_negative":c["later_chargeoffs"],"chargeoff_prevalence":round(c["positive"]/n,6) if n else ""})
        recon.append({"approval_fy":year,"candidate":cand,"eligible":n,"excluded":ex,"primary_exclusion_sum":exsum,"candidate_reconciles":cand==n+ex,"exclusions_reconcile":ex==exsum,"positive":c["positive"],"negative":c["negative"],"outcome_reconciles":n==c["positive"]+c["negative"]})
    write("outcome_reconciliation_by_fy.csv",list(years[0]),years)
    write("exclusions_by_fy.csv",["approval_fy","primary_reason","records"],[{"approval_fy":yr,"primary_reason":reason,"records":n} for (yr,reason),n in sorted(exfy.items())])
    write("quality_flag_overlaps.csv",["approval_fy","quality_flag","records"],[{"approval_fy":yr,"quality_flag":flag,"records":n} for (yr,flag),n in sorted(flagfy.items())])
    write("outcome_timing_status.csv",["check","records"],[{"check":k,"records":v} for k,v in sorted(consistency.items())])
    write("disbursement_diagnostics.csv",["approval_fy","snapshot_status","records","missing_date","invalid_date","valid_date","invalid_date_flag","before_approval","after_snapshot","no_disbursement_evidence"],[{"approval_fy":yr,"snapshot_status":st,"records":c["n"],"missing_date":c["missing"],"invalid_date":c["invalid"],"valid_date":c["valid"],"invalid_date_flag":c["invalid_first_disbursement_date"],"before_approval":c["disbursement_before_approval"],"after_snapshot":c["disbursement_after_snapshot"],"no_disbursement_evidence":c["no_first_disbursement_evidence"]} for (yr,st),c in sorted(disb.items())])
    write("predictor_missingness.csv",["approval_fy","candidate_predictor","missing_n","eligible_n"],[{"approval_fy":yr,"candidate_predictor":f,"missing_n":n,"eligible_n":counts[yr]["eligible"]} for (yr,f),n in sorted(missing.items())])
    total_candidates=sum(total[f"candidate_fy{yr}"] for yr in YEARS); total_eligible=sum(counts[yr]["eligible"] for yr in YEARS); all_ok=all(x["candidate_reconciles"] and x["exclusions_reconcile"] and x["outcome_reconciles"] for x in recon); primary_sum=sum(exfy.values()); total_excluded=total_candidates-total_eligible
    report_names=["outcome_reconciliation_by_fy.csv","exclusions_by_fy.csv","quality_flag_overlaps.csv","disbursement_diagnostics.csv","outcome_timing_status.csv","predictor_missingness.csv"]
    output_sha256={name:digest(out/name) for name in report_names}
    run_id=hashlib.sha256((sha+SCRIPT_VERSION+json.dumps(output_sha256,sort_keys=True)).encode()).hexdigest()
    manifest={"task":"Task 6B retrospective 24-month charge-off cohort audit","script_version":SCRIPT_VERSION,"run_id":run_id,"target":"Charge-off within 24 calendar months; retrospective charge-off is not necessarily regulatory default.","source":source.name,"source_sha256":sha,"source_sha256_matches_expected":sha==expected_hash,"snapshot_date":AS_OF.isoformat(),"source_rows":total["rows"],"duplicate_excess_rows":total["duplicate_excess_rows"],"candidate_records":total_candidates,"eligible_records":total_eligible,"excluded_records":total_excluded,"positive_records":sum(counts[y]["positive"] for y in YEARS),"negative_records":sum(counts[y]["negative"] for y in YEARS),"primary_exclusion_reason_records":primary_sum,"later_chargeoffs_negative":sum(counts[y]["later_chargeoffs"] for y in YEARS),"snapshot_date_expected_rows":total["snapshot_date_expected"],"snapshot_date_nonconforming_rows":total["snapshot_date_invalid"],"checks":{"checksum":"PASS" if sha==expected_hash else "FAIL","required_schema":"PASS","snapshot_date":"PASS" if total["snapshot_date_invalid"]==0 else "FAIL","candidate_equals_eligible_plus_excluded":"PASS" if total_candidates==total_eligible+total_excluded else "FAIL","eligible_equals_positive_plus_negative":"PASS" if total_eligible==sum(counts[y]["positive"]+counts[y]["negative"] for y in YEARS) else "FAIL","one_primary_exclusion_per_excluded":"PASS" if primary_sum==total_excluded else "FAIL","each_fy_reconciles":"PASS" if all_ok else "FAIL","later_chargeoffs_accounted_as_negative":"PASS" if sum(counts[y]["later_chargeoffs"] for y in YEARS)==consistency["chargeoff_after_24m"] else "FAIL","terminal_fields_used_as_predictors":"FAIL" if any(x in FEATURES for x in ("LoanStatus","ChargeOffDate","PaidInFullDate")) else "PASS","aggregate_only_reports":"PASS","output_checksums":"PASS"},"output_sha256":output_sha256,"exclusion_priority":list(priority),"predictor_provenance_unverified":list(FEATURES),"selection_bias_note":"Cancelled/committed loans are excluded; FirstDisbursementDate missingness is reported but not an eligibility rule. This status-selected population may omit undisbursed approvals and is not representative of all approvals or necessarily all funded exposure.","outputs":report_names+["task6b_manifest.json"]}
    (out/"task6b_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"manifest":manifest,"by_fy":years},indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--input",type=Path,required=True);p.add_argument("--out-dir",type=Path,required=True);p.add_argument("--expected-sha256",default=EXPECTED_SHA256);a=p.parse_args();audit(a.input,a.out_dir,a.expected_sha256)
if __name__=="__main__": main()
