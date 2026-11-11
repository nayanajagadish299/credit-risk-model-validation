#!/usr/bin/env python3
"""Aggregate-only source-lineage audit for the SBA 7(a) FY2010-2014 cohort.

Python 3.10+, standard-library only.
Reads the raw FY2010-FY2019 SBA 7(a) CSV as a stream, deduplicates exact
full-row duplicates with a temporary SQLite hash index, and writes aggregate
CSV/JSON reports only. It does NOT write loan-level records or predictions.

Important: analysis is restricted to ApprovalFY 2010-2014. FY2015-2016
locked-test outcomes are not summarized, modelled, or evaluated.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

DEFAULT_FILES = ["FOIA_7a_FY2010_FY2019_asof_260930.csv"]
ANALYSIS_FY = set(range(2010, 2015))

def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())

def get(row: dict, field: str) -> str:
    return (row.get(norm_key(field), "") or "").strip()

def parse_num(value: str) -> Optional[float]:
    s = (value or "").strip().replace(",", "").replace("$", "").replace("%", "")
    if not s:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except ValueError:
        return None

def parse_date(value: str) -> Optional[date]:
    s = (value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def add_months(d: date, months: int) -> date:
    import calendar
    m = d.month - 1 + months
    y = d.year + m // 12
    mo = m % 12 + 1
    return date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))

def derived_fy(d: Optional[date]) -> Optional[int]:
    if d is None:
        return None
    return d.year + 1 if d.month >= 10 else d.year

def norm_status(value: str) -> str:
    s = re.sub(r"[^A-Za-z]", "", (value or "")).upper()
    aliases = {
        "PAIDINFULL": "PIF",
        "CHARGEDOFF": "CHGOFF",
        "CANCELLED": "CANCLD",
        "CANCELED": "CANCLD",
        "COMMITMENT": "COMMIT",
    }
    return aliases.get(s, s)

def strict_label(origin, asof, status, paid, charge):
    """Same strict 120-month competing-outcome logic as the cohort builder."""
    if origin is None or asof is None or origin > asof:
        return None
    horizon = add_months(origin, 120)
    if horizon > asof:
        return None
    if status not in {"CHGOFF", "PIF", "EXEMPT"}:
        return None
    if paid is not None and charge is not None:
        return None
    if status == "CHGOFF":
        if charge is None or charge < origin or charge > asof:
            return None
        return int(charge <= horizon)
    if status == "PIF":
        if paid is None or paid < origin or paid > asof:
            return None
        return 0
    if paid is not None or charge is not None:
        return None
    return 0

def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", type=Path, default=Path("."))
    ap.add_argument("--out-dir", type=Path, default=Path("sba_task5d_lineage_output"))
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES)
    ap.add_argument("--expected-snapshot", default="2026-09-30")
    args = ap.parse_args()

    paths = [args.input_dir / name for name in args.files]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise SystemExit("Missing source file(s):\n  " + "\n  ".join(missing))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    status_by_fy = defaultdict(Counter)
    program_by_fy = Counter()
    age_by_fy = Counter()
    feature_missing = defaultdict(Counter)
    term_by_fy = defaultdict(Counter)
    term_product = defaultdict(Counter)
    date_quality = defaultdict(Counter)
    origin_sensitivity = defaultdict(Counter)
    jobs = defaultdict(lambda: {"n": 0, "missing": 0, "negative": 0, "zero": 0,
                                "sum": 0.0, "min": None, "max": None})
    term_values = defaultdict(Counter)
    snapshots = Counter()
    source_manifest = []
    totals = Counter()
    quality_global = Counter()

    candidate_fields = [
        "BusinessAge", "JobsSupported", "RevolverStatus",
        "FixedorVariableInterestInd", "CollateralInd",
        "InitialInterestRate", "NaicsCode", "ProjectState",
        "BusinessType", "ProcessingMethod",
    ]

    with tempfile.TemporaryDirectory(prefix="sba_task5d_lineage_") as td:
        con = sqlite3.connect(Path(td) / "seen.sqlite")
        con.execute("CREATE TABLE seen (row_hash TEXT PRIMARY KEY)")
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        try:
            for path in paths:
                file_rows = 0
                file_analysis_rows = 0
                file_duplicates = 0

                with path.open("r", newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames:
                        raise ValueError(f"No header found in {path.name}")
                    norm_headers = [norm_key(x) for x in reader.fieldnames]
                    required = ["ApprovalDate", "ApprovalFY", "AsOfDate", "Program",
                                "FirstDisbursementDate", "TermInMonths", "GrossApproval",
                                "SBAGuaranteedApproval", "InitialInterestRate", "LoanStatus",
                                "PaidInFullDate", "ChargeOffDate", "ProcessingMethod",
                                "BusinessAge", "JobsSupported", "RevolverStatus",
                                "FixedorVariableInterestInd", "CollateralInd"]
                    missing_cols = [x for x in required if norm_key(x) not in norm_headers]
                    if missing_cols:
                        raise ValueError(f"{path.name} missing columns: {missing_cols}")

                    for raw in reader:
                        file_rows += 1
                        totals["source_rows_read"] += 1
                        if None in raw or any(v is None for v in raw.values()):
                            quality_global["malformed_rows"] += 1
                            continue

                        norm_raw = {norm_key(k): (v or "") for k, v in raw.items() if k is not None}

                        # First read only the approval-year fields needed to select
                        # the analysis window. Do not inspect outcomes/features for
                        # FY2015+ rows; preserve the locked temporal test.
                        approval = parse_date(get(norm_raw, "ApprovalDate"))
                        fy_raw = get(norm_raw, "ApprovalFY")
                        try:
                            fy = int(float(fy_raw)) if fy_raw else None
                        except ValueError:
                            fy = None
                        derived = derived_fy(approval)
                        if fy is None and derived is not None:
                            fy = derived
                            quality_global["approval_fy_filled_from_approval_date"] += 1
                        elif fy is not None and derived is not None and fy != derived:
                            quality_global["approval_fy_mismatch_with_approval_date"] += 1

                        if fy not in ANALYSIS_FY:
                            totals["rows_skipped_outside_analysis_fy"] += 1
                            continue

                        file_analysis_rows += 1
                        row_values = [(raw.get(k) or "").strip() for k in reader.fieldnames]
                        digest = hashlib.sha256(
                            json.dumps(row_values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                        ).hexdigest()
                        cur = con.execute("INSERT OR IGNORE INTO seen(row_hash) VALUES (?)", (digest,))
                        if cur.rowcount == 0:
                            file_duplicates += 1
                            totals["exact_duplicate_excess_rows"] += 1
                            continue
                        totals["unique_rows_seen"] += 1
                        totals["fy2010_2014_unique_rows_analysed"] += 1

                        asof = parse_date(get(norm_raw, "AsOfDate"))
                        disb = parse_date(get(norm_raw, "FirstDisbursementDate"))
                        paid = parse_date(get(norm_raw, "PaidInFullDate"))
                        charge = parse_date(get(norm_raw, "ChargeOffDate"))
                        status = norm_status(get(norm_raw, "LoanStatus"))
                        if asof:
                            snapshots[asof.isoformat()] += 1

                        program = get(norm_raw, "Program") or "__BLANK__"
                        program_by_fy[(fy, program)] += 1
                        status_by_fy[fy][status or "__BLANK__"] += 1

                        age = get(norm_raw, "BusinessAge") or "__BLANK__"
                        age_by_fy[(fy, age)] += 1

                        for field in candidate_fields:
                            val = get(norm_raw, field)
                            if not val:
                                feature_missing[(fy, field)]["missing"] += 1
                            feature_missing[(fy, field)]["rows"] += 1

                        # Date/status consistency checks; aggregate counts only.
                        dq = date_quality[fy]
                        checks = {
                            "approval_date_missing_or_invalid": approval is None,
                            "asof_date_missing_or_invalid": asof is None,
                            "first_disbursement_missing_or_invalid": disb is None,
                            "first_disbursement_before_approval": bool(disb and approval and disb < approval),
                            "first_disbursement_after_snapshot": bool(disb and asof and disb > asof),
                            "paid_date_missing_or_invalid_for_PIF": status == "PIF" and paid is None,
                            "chargeoff_date_missing_or_invalid_for_CHGOFF": status == "CHGOFF" and charge is None,
                            "both_paid_and_chargeoff_dates_present": paid is not None and charge is not None,
                            "paid_before_approval": bool(paid and approval and paid < approval),
                            "paid_before_disbursement": bool(paid and disb and paid < disb),
                            "chargeoff_before_approval": bool(charge and approval and charge < approval),
                            "chargeoff_before_disbursement": bool(charge and disb and charge < disb),
                            "chargeoff_after_snapshot": bool(charge and asof and charge > asof),
                            "paid_after_snapshot": bool(paid and asof and paid > asof),
                            "EXEMPT_with_terminal_date": status == "EXEMPT" and (paid is not None or charge is not None),
                        }
                        for k, v in checks.items():
                            if v:
                                dq[k] += 1

                        # Term integrity. Preserve the raw numeric value; do not round.
                        term = parse_num(get(norm_raw, "TermInMonths"))
                        if term is None or not (1 <= term <= 360):
                            term_by_fy[fy]["missing_or_outside_1_360"] += 1
                        else:
                            term_by_fy[fy]["valid_term"] += 1
                            if abs(term - round(term)) < 1e-9:
                                term_by_fy[fy]["integer_term"] += 1
                            else:
                                term_by_fy[fy]["non_integer_term"] += 1
                            multiple12 = abs(term / 12 - round(term / 12)) < 1e-9
                            pattern = "multiple_of_12" if multiple12 else "not_multiple_of_12"
                            term_by_fy[fy][pattern] += 1
                            term_values[fy][str(term)] += 1

                        # Jobs-supported source summary; the value is self-reported.
                        j = parse_num(get(norm_raw, "JobsSupported"))
                        ja = jobs[fy]
                        ja["n"] += 1
                        if j is None:
                            ja["missing"] += 1
                        else:
                            if j < 0:
                                ja["negative"] += 1
                            if j == 0:
                                ja["zero"] += 1
                            ja["sum"] += j
                            ja["min"] = j if ja["min"] is None else min(ja["min"], j)
                            ja["max"] = j if ja["max"] is None else max(ja["max"], j)

                        # Strict approval-origin target and disbursement-origin sensitivity.
                        ga = parse_num(get(norm_raw, "GrossApproval"))
                        sg = parse_num(get(norm_raw, "SBAGuaranteedApproval"))
                        rate = parse_num(get(norm_raw, "InitialInterestRate"))
                        valid_amount = ga is not None and ga > 0 and sg is not None and 0 <= sg <= ga
                        valid_rate = rate is not None and rate >= 0
                        valid_term = term is not None and 1 <= term <= 360
                        if valid_amount and valid_rate and valid_term:
                            y_approval = strict_label(approval, asof, status, paid, charge)
                            y_disb = None
                            if disb is not None and approval is not None and asof is not None and approval <= disb <= asof:
                                y_disb = strict_label(disb, asof, status, paid, charge)

                            if y_approval is not None:
                                origin_sensitivity[fy]["approval_origin_eligible"] += 1
                                origin_sensitivity[fy]["approval_origin_chargeoffs"] += y_approval
                            if y_disb is not None:
                                origin_sensitivity[fy]["disbursement_origin_eligible"] += 1
                                origin_sensitivity[fy]["disbursement_origin_chargeoffs"] += y_disb
                            if y_approval is not None and y_disb is not None:
                                os = origin_sensitivity[fy]
                                os["both_origins_eligible"] += 1
                                os["approval_events_on_overlap"] += y_approval
                                os["disbursement_events_on_overlap"] += y_disb
                                if y_approval != y_disb:
                                    os["labels_changed_on_overlap"] += 1
                                    os["changed_0_to_1"] += int(y_approval == 0 and y_disb == 1)
                                    os["changed_1_to_0"] += int(y_approval == 1 and y_disb == 0)

                            if y_approval is not None and term is not None:
                                multiple12 = abs(term / 12 - round(term / 12)) < 1e-9
                                pattern = "multiple_of_12" if multiple12 else "not_multiple_of_12"
                                method = get(norm_raw, "ProcessingMethod") or "__BLANK__"
                                revolver = get(norm_raw, "RevolverStatus") or "__BLANK__"
                                key = (fy, method, revolver, pattern)
                                term_product[key]["observations"] += 1
                                term_product[key]["chargeoffs"] += y_approval

                source_manifest.append({
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "rows_read": file_rows,
                    "fy2010_2014_rows_before_dedup": file_analysis_rows,
                    "exact_duplicate_excess_rows_within_analysis_window": file_duplicates,
                })
            con.commit()
        finally:
            con.close()

    # Aggregate output tables.
    write_csv(args.out_dir / "program_by_fy.csv",
              [{"approval_fy": k[0], "program": k[1], "observations": v}
               for k, v in sorted(program_by_fy.items())],
              ["approval_fy", "program", "observations"])

    write_csv(args.out_dir / "status_by_fy.csv",
              [{"approval_fy": fy, "loan_status": status, "observations": n}
               for fy in sorted(status_by_fy) for status, n in sorted(status_by_fy[fy].items())],
              ["approval_fy", "loan_status", "observations"])

    write_csv(args.out_dir / "business_age_by_fy.csv",
              [{"approval_fy": k[0], "business_age_category": k[1], "observations": v}
               for k, v in sorted(age_by_fy.items())],
              ["approval_fy", "business_age_category", "observations"])

    write_csv(args.out_dir / "candidate_feature_missingness_by_fy.csv",
              [{"approval_fy": k[0], "field": k[1], "rows": v["rows"],
                "missing": v["missing"],
                "missing_pct": round(100 * v["missing"] / v["rows"], 4) if v["rows"] else 0}
               for k, v in sorted(feature_missing.items())],
              ["approval_fy", "field", "rows", "missing", "missing_pct"])

    write_csv(args.out_dir / "term_integrity_by_fy.csv",
              [{"approval_fy": fy, **dict(term_by_fy[fy])}
               for fy in sorted(term_by_fy)],
              ["approval_fy", "valid_term", "missing_or_outside_1_360",
               "integer_term", "non_integer_term", "multiple_of_12", "not_multiple_of_12"])

    write_csv(args.out_dir / "term_pattern_by_fy_method_revolver.csv",
              [{"approval_fy": k[0], "processing_method": k[1], "revolver_status": k[2],
                "term_pattern": k[3], "observations": v["observations"],
                "chargeoffs": v["chargeoffs"],
                "chargeoff_rate_pct": round(100 * v["chargeoffs"] / v["observations"], 4)
                    if v["observations"] else 0}
               for k, v in sorted(term_product.items())],
              ["approval_fy", "processing_method", "revolver_status", "term_pattern",
               "observations", "chargeoffs", "chargeoff_rate_pct"])

    write_csv(args.out_dir / "date_quality_by_fy.csv",
              [{"approval_fy": fy, "quality_flag": flag, "count": n}
               for fy in sorted(date_quality) for flag, n in sorted(date_quality[fy].items())],
              ["approval_fy", "quality_flag", "count"])

    write_csv(args.out_dir / "approval_vs_disbursement_origin_sensitivity.csv",
              [{"approval_fy": fy, **dict(origin_sensitivity[fy])}
               for fy in sorted(origin_sensitivity)],
              ["approval_fy", "approval_origin_eligible", "approval_origin_chargeoffs",
               "disbursement_origin_eligible", "disbursement_origin_chargeoffs",
               "both_origins_eligible", "approval_events_on_overlap",
               "disbursement_events_on_overlap", "labels_changed_on_overlap",
               "changed_0_to_1", "changed_1_to_0"])

    jobs_rows = []
    for fy in sorted(jobs):
        x = jobs[fy]
        n_nonmissing = x["n"] - x["missing"]
        jobs_rows.append({
            "approval_fy": fy, "rows": x["n"], "missing": x["missing"],
            "missing_pct": round(100*x["missing"]/x["n"], 4) if x["n"] else 0,
            "nonmissing": n_nonmissing, "zero": x["zero"], "negative": x["negative"],
            "mean": round(x["sum"]/n_nonmissing, 4) if n_nonmissing else "",
            "min": x["min"] if x["min"] is not None else "",
            "max": x["max"] if x["max"] is not None else "",
        })
    write_csv(args.out_dir / "jobs_supported_by_fy.csv", jobs_rows,
              ["approval_fy", "rows", "missing", "missing_pct", "nonmissing",
               "zero", "negative", "mean", "min", "max"])

    term_value_rows = []
    for fy in sorted(term_values):
        for value, n in term_values[fy].most_common(40):
            term_value_rows.append({"approval_fy": fy, "term_in_months": value, "observations": n})
    write_csv(args.out_dir / "top_term_values_by_fy.csv", term_value_rows,
              ["approval_fy", "term_in_months", "observations"])

    snapshot_values = dict(snapshots)
    expected_ok = args.expected_snapshot == "any" or set(snapshot_values) == {args.expected_snapshot}
    manifest = {
        "project": "SBA 7(a) Task 5D source-lineage audit",
        "analysis_years_only": sorted(ANALYSIS_FY),
        "locked_test_policy": "This audit does not summarize or evaluate FY2015-FY2016 outcomes.",
        "holdout_status_note": "An earlier project baseline run already evaluated FY2015-FY2016 and reported test metrics; this is not a virgin holdout.",
        "source_files": source_manifest,
        "totals": dict(totals),
        "snapshot_date_counts": snapshot_values,
        "expected_snapshot": args.expected_snapshot,
        "snapshot_matches_expected": expected_ok,
        "global_quality_flags": dict(quality_global),
        "outputs_are_aggregate_only": True,
        "raw_rows_exported": False,
        "direct_identifiers_exported": False,
        "row_level_predictions_exported": False,
        "notes": [
            "Approval-origin target follows the current strict cohort logic.",
            "Disbursement-origin is a sensitivity analysis, not a silent replacement of the reference methodology.",
            "Term divisibility is calculated from the parsed raw TermInMonths value without rounding.",
            "BusinessAge categories are tabulated by fiscal year for comparison with the SBA dictionary's stated collection timing.",
            "JobsSupported summaries are descriptive; the field is lender-reported and should be treated as self-reported.",
            "This audit does not alter cohort files or model artifacts."
        ]
    }
    (args.out_dir / "source_lineage_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("TASK 5D SOURCE-LINEAGE AUDIT COMPLETE")
    print(json.dumps({
        "analysis_years": sorted(ANALYSIS_FY),
        "files_processed": len(source_manifest),
        "source_rows_read": totals["source_rows_read"],
        "exact_duplicate_excess_rows": totals["exact_duplicate_excess_rows"],
        "snapshot_matches_expected": expected_ok,
        "output_directory": str(args.out_dir.resolve()),
        "this_audit_evaluated_fy2015_2016": False
    }, indent=2))

if __name__ == "__main__":
    main()
