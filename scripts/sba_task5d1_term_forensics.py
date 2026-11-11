#!/usr/bin/env python3
"""Task 5D.1: aggregate-only TermInMonths / outcome-timing forensic audit.

Purpose: check one possible mechanism behind the extraordinary association of
non-12-month loan terms with charge-off. The audit uses *outcomes for diagnosis*
only; event dates are NEVER candidate prediction features.

Input: official 7(a) FY2010-FY2019 FOIA source CSV as of 2026-09-30.
Analysis FY: 2010 through 2014 only. FY2015-FY2016 is never summarized.
Outputs: aggregated CSVs / a JSON manifest only; no loan-level data.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import sqlite3
import statistics
import tempfile
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path
from sba_task5d_source_lineage_audit import (
    norm_key, get, parse_num, parse_date, derived_fy, norm_status, strict_label, write_csv,
)

YEARS = set(range(2010, 2015))
EXPECTED = {"raw_window_rows": 243525, "duplicates": 799,
            "unique_window_rows": 242726, "strict_cohort": 210516,
            "strict_chargeoffs": 13634}


def months_elapsed(a: date, b: date) -> float:
    """Calendar-month component plus within-month day fraction (not exact tenor)."""
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.4375


def monthly_bucket(v: float) -> str:
    if v < 0: return "negative"
    if v < 12: return "00-<12"
    if v < 24: return "12-<24"
    if v < 36: return "24-<36"
    if v < 60: return "36-<60"
    if v < 84: return "60-<84"
    if v <= 120: return "84-120"
    return ">120"


def diff_bucket(v: float) -> str:
    if v < -12: return "term_>12m_shorter_than_event"
    if v < -3: return "term_3to12m_shorter"
    if v < -1: return "term_1to3m_shorter"
    if v <= 1: return "term_within_1m_event"
    if v <= 3: return "term_1to3m_longer"
    if v <= 12: return "term_3to12m_longer"
    return "term_>12m_longer_than_event"


def summarize_match(rows: dict) -> list[dict]:
    result = []
    for (fy, kind, pat), values in sorted(rows.items()):
        if not values: continue
        n = len(values)
        result.append({
            "approval_fy": fy, "observed_terminal_event": kind,
            "term_pattern": pat, "observations": n,
            "within_1_month_n": sum(abs(x)<=1 for x in values),
            "within_3_months_n": sum(abs(x)<=3 for x in values),
            "within_6_months_n": sum(abs(x)<=6 for x in values),
            "within_12_months_n": sum(abs(x)<=12 for x in values),
            "within_1_month_pct": round(100*sum(abs(x)<=1 for x in values)/n, 4),
            "within_3_months_pct": round(100*sum(abs(x)<=3 for x in values)/n, 4),
            "median_term_minus_elapsed_months": round(statistics.median(values), 3)
        })
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",type=Path, default=Path('FOIA_7a_FY2010_FY2019_asof_260930.csv'))
    ap.add_argument("--out-dir",type=Path, default=Path('sba_task5d1_term_forensics_output'))
    ap.add_argument("--skip-expected-check",action='store_true',help='only for synthetic smoke tests')
    args=ap.parse_args()
    if not args.input.is_file():raise SystemExit(f"Source CSV missing: {args.input}")
    args.out_dir.mkdir(parents=True,exist_ok=True)
    tally=Counter()
    feature_by_fy=defaultdict(lambda:Counter())
    term_by_status=defaultdict(Counter)
    elapsed_buckets=Counter()
    differences=Counter()
    event_diffs=defaultdict(list)
    long_term=Counter()

    with tempfile.TemporaryDirectory(prefix='sba_5d1_dedupe_') as td:
        con=sqlite3.connect(str(Path(td)/'dedupe.sqlite'))
        try:
            con.execute('CREATE TABLE seen (row_hash TEXT PRIMARY KEY)')
            with args.input.open('r',newline='',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f)
                if not reader.fieldnames: raise ValueError('Empty CSV')
                required=['ApprovalDate','ApprovalFY','AsOfDate','Program','TermInMonths',
                          'GrossApproval','SBAGuaranteedApproval','InitialInterestRate',
                          'LoanStatus','PaidInFullDate','ChargeOffDate']
                absent=[k for k in required if norm_key(k) not in [norm_key(x) for x in reader.fieldnames]]
                if absent:raise ValueError(f'Missing columns: {absent}')
                for raw in reader:
                    tally['source_rows_all']+=1
                    if None in raw or any(v is None for v in raw.values()):
                        tally['malformed_rows']+=1;continue
                    r={norm_key(k): (v or '') for k,v in raw.items() if k is not None}
                    approval=parse_date(get(r,'ApprovalDate'))
                    raw_fy=get(r,'ApprovalFY')
                    try:fy=int(float(raw_fy)) if raw_fy else derived_fy(approval)
                    except ValueError:fy=derived_fy(approval)
                    if fy not in YEARS:continue
                    tally['raw_window_rows']+=1
                    digest=hashlib.sha256(json.dumps(
                        [(raw.get(k) or '').strip() for k in reader.fieldnames],
                        ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                    if con.execute('INSERT OR IGNORE INTO seen VALUES (?)',(digest,)).rowcount==0:
                        tally['duplicates']+=1;continue
                    tally['unique_window_rows']+=1
                    asof=parse_date(get(r,'AsOfDate'))
                    status=norm_status(get(r,'LoanStatus'))
                    paid=parse_date(get(r,'PaidInFullDate'))
                    charge=parse_date(get(r,'ChargeOffDate'))
                    term=parse_num(get(r,'TermInMonths'))
                    ga=parse_num(get(r,'GrossApproval'))
                    sg=parse_num(get(r,'SBAGuaranteedApproval'))
                    rate=parse_num(get(r,'InitialInterestRate'))
                    if term is None or not 1<=term<=360:continue
                    if ga is None or ga<=0 or sg is None or not 0<=sg<=ga:continue
                    if rate is None or rate<0:continue
                    y=strict_label(approval,asof,status,paid,charge)
                    if y is None:continue
                    tally['strict_cohort']+=1
                    tally['strict_chargeoffs']+=y
                    pat='multiple_of_12' if math.isclose(term/12,round(term/12),abs_tol=1e-9) else 'not_multiple_of_12'
                    feature_by_fy[(fy,pat)]['loans']+=1
                    feature_by_fy[(fy,pat)]['chargeoffs']+=y
                    term_by_status[(fy,pat,status)]['loans']+=1
                    term_by_status[(fy,pat,status)]['chargeoffs']+=y
                    long_term[(fy,pat,round(term),y)]+=1

                    # Diagnostic only: event timing is never used in the model.
                    # PIF and CHGOFF have an observed terminal date in the 2026 extract.
                    if status in {'CHGOFF','PIF'}:
                        event=charge if status=='CHGOFF' else paid
                        if event is not None and approval is not None and event>=approval:
                            elapsed=months_elapsed(approval,event)
                            delta=term-elapsed
                            event_diffs[(fy,status,pat)].append(delta)
                            elapsed_buckets[(fy,status,pat,monthly_bucket(elapsed))]+=1
                            differences[(fy,status,pat,diff_bucket(delta))]+=1
        finally:con.close()

    def records_from_pair(data,cols):
        out=[]
        for key,cnt in sorted(data.items()):
            r=dict(zip(cols,key));r.update(dict(cnt));out.append(r)
        return out

    cohort_rows=records_from_pair(feature_by_fy,['approval_fy','term_pattern'])
    for x in cohort_rows:x['chargeoff_rate_pct']=round(100*x['chargeoffs']/x['loans'],4)
    write_csv(args.out_dir/'cohort_term_pattern_by_fy.csv',cohort_rows,
              ['approval_fy','term_pattern','loans','chargeoffs','chargeoff_rate_pct'])

    status_rows=records_from_pair(term_by_status,['approval_fy','term_pattern','loan_status'])
    write_csv(args.out_dir/'term_pattern_by_loan_status.csv',status_rows,
              ['approval_fy','term_pattern','loan_status','loans','chargeoffs'])

    matched=summarize_match(event_diffs)
    write_csv(args.out_dir/'term_vs_terminal_event_summary.csv',matched,
              ['approval_fy','observed_terminal_event','term_pattern','observations',
               'within_1_month_n','within_3_months_n','within_6_months_n','within_12_months_n',
               'within_1_month_pct','within_3_months_pct','median_term_minus_elapsed_months'])

    hist=[dict(zip(['approval_fy','observed_terminal_event','term_pattern','term_minus_event_bin'],k),observations=v)
          for k,v in sorted(differences.items())]
    write_csv(args.out_dir/'term_minus_event_gap_histogram.csv',hist,
              ['approval_fy','observed_terminal_event','term_pattern','term_minus_event_bin','observations'])

    eb=[dict(zip(['approval_fy','observed_terminal_event','term_pattern','elapsed_months_bin'],k),observations=v)
        for k,v in sorted(elapsed_buckets.items())]
    write_csv(args.out_dir/'terminal_event_elapsed_months_histogram.csv',eb,
              ['approval_fy','observed_terminal_event','term_pattern','elapsed_months_bin','observations'])

    by_outcome=defaultdict(list)
    for (fy,pat,term,y),n in long_term.items():by_outcome[(fy,pat,y)].append((n,term))
    ranks=[]
    for (fy,pat,y),pairs in sorted(by_outcome.items()):
        for rank,(n,term) in enumerate(sorted(pairs,key=lambda x:(-x[0],x[1]))[:15],1):
            ranks.append({'approval_fy':fy,'term_pattern':pat,'chargeoff_label':y,
                         'rank':rank,'term_in_months':term,'loans':n})
    write_csv(args.out_dir/'top_exact_terms_by_outcome.csv',ranks,
              ['approval_fy','term_pattern','chargeoff_label','rank','term_in_months','loans'])

    checks={k: (tally[k]==v) for k,v in EXPECTED.items()}
    manifest={'task':'5D.1 term/event-time forensic audit',
              'source_file':args.input.name,'analysis_fy':[2010,2011,2012,2013,2014],
              'snapshot_expected':'2026-09-30','tallies':dict(tally),
              'expected_checks':checks,'all_expected_checks_pass':all(checks.values()),
              'outputs_aggregate_only':True,'raw_loan_rows_exported':False,
              'fy2015_2016_outcomes_read':False,
              'interpretation':'Near-matches between term and retrospective event time would be suspicious, not proof; failure to find near-matches cannot establish point-in-time validity. No label/outcome/event-time variable should be used at prediction time.',
              'caveat':'Strict eligibility is conditioned on retrospective final status; this audit diagnoses sources rather than proving prospective availability.'}
    (args.out_dir/'forensics_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'tallies':dict(tally),'expected_checks':checks,'outputs':str(args.out_dir)},indent=2))
    if not all(checks.values()) and not args.skip_expected_check:
        raise SystemExit('Quality gate FAILED: audit counts differ from Task 5D. Inspect input/snapshot and do not treat outputs as validated.')

if __name__=='__main__':main()
