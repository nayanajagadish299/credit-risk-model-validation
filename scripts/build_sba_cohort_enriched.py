#!/usr/bin/env python3
"""Build a separate enriched, privacy-safe SBA 7(a) cohort for Task 4 feature diagnostics.

Python 3.10+. Standard-library only. Reads the four September 30, 2026 SBA FOIA
CSV files as a stream, removes exact full-row duplicates using a temporary
SQLite hash index, validates cohort rules, and writes privacy-safe gzip CSVs.

The script deliberately creates TWO binary cohort versions:
1) reference_replication: mirrors the documented reference rules used by the
   prior audit so counts can be reconciled to the published project;
2) strict_120m: requires a fully observed, logically consistent terminal
   outcome through the 120-month horizon. This is the preferred primary
   empirical cohort, subject to confirming status definitions in the SBA data
   dictionary.

No borrower/lender names, addresses, ZIPs, LocationID, bank IDs, franchise
names, raw event dates, or row hashes are exported.
"""
from __future__ import annotations

import argparse
import csv
import gzip
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

DEFAULT_FILES = [
    "FOIA_7a_FY1991_FY1999_asof_260930.csv",
    "FOIA_7a_FY2000_FY2009_asof_260930.csv",
    "FOIA_7a_FY2010_FY2019_asof_260930.csv",
    "FOIA_7a_FY2020_Present_asof_260930.csv",
]

EXPECTED_FIELDS = [
    "AsOfDate", "Program", "LocationID", "BorrName", "BorrStreet",
    "BorrCity", "BorrState", "BorrZip", "BankName", "BankFDICNumber",
    "BankNCUANumber", "BankStreet", "BankCity", "BankState", "BankZip",
    "GrossApproval", "SBAGuaranteedApproval", "ApprovalDate", "ApprovalFY",
    "FirstDisbursementDate", "ProcessingMethod", "InitialInterestRate",
    "FixedorVariableInterestInd", "TermInMonths", "NaicsCode",
    "NaicsDescription", "FranchiseCode", "FranchiseName", "ProjectCounty",
    "ProjectState", "SBADistrictOffice", "CongressionalDistrict",
    "BusinessType", "BusinessAge", "LoanStatus", "PaidInFullDate",
    "ChargeOffDate", "GrossChargeOffAmount", "RevolverStatus",
    "JobsSupported", "CollateralInd", "SoldSecMrktInd",
]

# Task 4 candidate fields are exported for diagnostics only.
# Inclusion in a predictive model requires separate point-in-time review.
FEATURE_FIELDS = [
    "GrossApproval", "SBAGuaranteedApproval", "TermInMonths",
    "InitialInterestRate", "NaicsCode", "ProjectState", "BusinessAge",
    "BusinessType", "ProcessingMethod", "RevolverStatus",
    "FixedorVariableInterestInd", "CollateralInd", "JobsSupported",
]
NUMERIC_FEATURES = {
    "GrossApproval", "SBAGuaranteedApproval", "TermInMonths",
    "InitialInterestRate", "JobsSupported",
}
CATEGORICAL_FEATURES = {
    "NaicsCode", "ProjectState", "BusinessAge", "BusinessType",
    "ProcessingMethod", "RevolverStatus", "FixedorVariableInterestInd",
    "CollateralInd",
}
ALLOWED_STATUS = {"CHGOFF", "PIF", "EXEMPT"}

# Counts from the user's September-2026 second-pass audit. These are
# reconciliation targets, not hard-coded output values.
EXPECTED_SOURCE_SHA256 = {
    "FOIA_7a_FY1991_FY1999_asof_260930.csv": "d28df8e5d78a7aedcfb03693c5d42f0f0a38557470b5c8201cafce326e5c567d",
    "FOIA_7a_FY2000_FY2009_asof_260930.csv": "e0122bce7e468fc1c4bb6f0a24100bfa0ead8c6065332a2b28cb01671ba5273e",
    "FOIA_7a_FY2010_FY2019_asof_260930.csv": "39aa32b71fb5dbb4bfb178c9b3d597c92bb6903622027c2f8360d13e57d0abb2",
    "FOIA_7a_FY2020_Present_asof_260930.csv": "b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6",
}
EXPECTED_SOURCE_ROWS = {
    "FOIA_7a_FY1991_FY1999_asof_260930.csv": 337033,
    "FOIA_7a_FY2000_FY2009_asof_260930.csv": 690333,
    "FOIA_7a_FY2010_FY2019_asof_260930.csv": 545751,
    "FOIA_7a_FY2020_Present_asof_260930.csv": 403644,
}

EXPECTED_BY_FY = {
    2010: (39888, 3470),
    2011: (45548, 2888),
    2012: (38825, 2247),
    2013: (40369, 2251),
    2014: (45888, 2778),
    2015: (55337, 3632),
    2016: (56711, 3996),
}

OUTPUT_FIELDS = [
    "approval_fy", "approval_date", "as_of_date",
    "gross_approval", "sba_guaranteed_approval", "term_in_months",
    "initial_interest_rate", "naics_code", "project_state",
    "business_age", "business_type", "processing_method", "revolver_status",
    "fixed_or_variable_interest_ind", "collateral_ind", "jobs_supported",
    "target_chargeoff_within_120m", "outcome_class", "split",
]
SURVIVAL_FIELDS = [
    "approval_fy", "approval_date", "as_of_date",
    "gross_approval", "sba_guaranteed_approval", "term_in_months",
    "initial_interest_rate", "naics_code", "project_state",
    "business_age", "business_type", "processing_method", "revolver_status",
    "fixed_or_variable_interest_ind", "collateral_ind", "jobs_supported",
    "event_type", "followup_days", "followup_months",
]


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


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
        "PAIDINFULL": "PIF", "CHARGEDOFF": "CHGOFF",
        "CANCELLED": "CANCLD", "CANCELED": "CANCLD",
        "COMMITMENT": "COMMIT",
    }
    return aliases.get(s, s)


def classify_120(origin: Optional[date], asof: Optional[date], status: str,
                 paid: Optional[date], charge: Optional[date]) -> str:
    """Strict 120-month competing-outcome classification."""
    if origin is None:
        return "NO_VALID_ORIGIN_DATE"
    if asof is None:
        return "NO_VALID_SNAPSHOT_DATE"
    if origin > asof:
        return "ORIGIN_AFTER_SNAPSHOT"
    horizon = add_months(origin, 120)
    if horizon > asof:
        return "NOT_YET_120M_MATURED"
    if status in {"CANCLD", "COMMIT"}:
        return "EXCLUDED_CANCELLED_OR_COMMITMENT"
    if status not in ALLOWED_STATUS:
        return "EXCLUDED_UNRECOGNISED_OR_MISSING_STATUS"
    if paid is not None and charge is not None:
        return "UNRESOLVED_BOTH_TERMINAL_DATES"
    if status == "CHGOFF":
        if charge is None:
            return "UNRESOLVED_CHARGEOFF_DATE_MISSING_OR_INVALID"
        if charge < origin:
            return "UNRESOLVED_CHARGEOFF_BEFORE_ORIGIN"
        if charge > asof:
            return "UNRESOLVED_CHARGEOFF_AFTER_SNAPSHOT"
        return "CHARGEOFF_WITHIN_120M" if charge <= horizon else "CHARGEOFF_AFTER_120M"
    if status == "PIF":
        if paid is None:
            return "UNRESOLVED_PAID_DATE_MISSING_OR_INVALID"
        if paid < origin:
            return "UNRESOLVED_PAID_BEFORE_ORIGIN"
        if paid > asof:
            return "UNRESOLVED_PAID_AFTER_SNAPSHOT"
        return "PIF_WITHIN_120M" if paid <= horizon else "PIF_AFTER_120M"
    if paid is not None or charge is not None:
        return "UNRESOLVED_EXEMPT_HAS_TERMINAL_DATE"
    return "NO_TERMINAL_EVENT_RECORDED_THROUGH_120M"


def classify_survival(origin: Optional[date], asof: Optional[date], status: str,
                      paid: Optional[date], charge: Optional[date]):
    """Approval-origin event/censor classification for survival analysis."""
    if origin is None or asof is None or origin > asof:
        return None
    if status not in ALLOWED_STATUS:
        return None
    if paid is not None and charge is not None:
        return None
    if status == "CHGOFF":
        event_date, event_type = charge, "CHARGEOFF"
    elif status == "PIF":
        event_date, event_type = paid, "PAID_IN_FULL_COMPETING"
    else:
        if paid is not None or charge is not None:
            return None
        event_date, event_type = asof, "RIGHT_CENSORED_EXEMPT"
    if event_date is None or event_date < origin or event_date > asof:
        return None
    days = (event_date - origin).days
    return event_type, days, days / 30.4375


def source_get(row: dict, field: str) -> str:
    return (row.get(norm_key(field), "") or "").strip()


def numeric_validity(ga, sg, term, rate):
    valid_term = term is not None and 1 <= term <= 360
    valid_amount = ga is not None and ga > 0 and sg is not None and 0 <= sg <= ga
    valid_rate = rate is not None and rate >= 0
    return valid_term, valid_amount, valid_rate


def split_for_fy(fy: int) -> Optional[str]:
    if 2010 <= fy <= 2014:
        return "train"
    if 2015 <= fy <= 2016:
        return "locked_test"
    return None


def safe_feature_values(row: dict) -> dict:
    vals = {}
    for field in FEATURE_FIELDS:
        raw = source_get(row, field)
        if field in NUMERIC_FEATURES:
            val = parse_num(raw)
            vals[field.lower()] = "" if val is None else str(val)
        else:
            vals[field.lower()] = raw
    # Rename fields to stable, human-readable export names.
    return {
        "gross_approval": vals["grossapproval"],
        "sba_guaranteed_approval": vals["sbaguaranteedapproval"],
        "term_in_months": vals["terminmonths"],
        "initial_interest_rate": vals["initialinterestrate"],
        "naics_code": vals["naicscode"],
        "project_state": vals["projectstate"],
        "business_age": vals["businessage"],
        "business_type": vals["businesstype"],
        "processing_method": vals["processingmethod"],
        "revolver_status": vals["revolverstatus"],
        "fixed_or_variable_interest_ind": vals["fixedorvariableinterestind"],
        "collateral_ind": vals["collateralind"],
        "jobs_supported": vals["jobssupported"],
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class GzipCsvWriter:
    def __init__(self, path: Path, fields: list[str]):
        self.path = path
        self.file = gzip.open(path, "wt", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        self.writer.writeheader()

    def writerow(self, row: dict):
        self.writer.writerow(row)

    def close(self):
        self.file.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", type=Path, default=Path("."), help="Folder containing the four raw SBA CSVs")
    ap.add_argument("--out-dir", type=Path, default=Path("sba_cohort_output"), help="Output folder")
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES, help="Optional explicit list of four source files")
    ap.add_argument("--expected-snapshot", default="2026-09-30", help="Expected source snapshot date; use 'any' to disable")
    args = ap.parse_args()

    if not args.files:
        raise SystemExit("Provide at least one SBA 7(a) source CSV with --files or use the four-file default.")
    input_paths = [args.input_dir / name for name in args.files]
    missing = [str(p) for p in input_paths if not p.exists()]
    if missing:
        raise SystemExit("Missing source file(s):\n  " + "\n  ".join(missing))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "ref_train": GzipCsvWriter(args.out_dir / "reference_train_fy2010_2014.csv.gz", OUTPUT_FIELDS),
        "ref_test": GzipCsvWriter(args.out_dir / "reference_locked_test_fy2015_2016.csv.gz", OUTPUT_FIELDS),
        "strict_train": GzipCsvWriter(args.out_dir / "strict_train_fy2010_2014.csv.gz", OUTPUT_FIELDS),
        "strict_test": GzipCsvWriter(args.out_dir / "strict_locked_test_fy2015_2016.csv.gz", OUTPUT_FIELDS),
        "survival": GzipCsvWriter(args.out_dir / "approval_origin_survival.csv.gz", SURVIVAL_FIELDS),
    }

    counters = Counter()
    by_fy = defaultdict(Counter)
    quality = Counter()
    snapshots = Counter()
    source_manifest = []
    parse_issue_counts = Counter()

    with tempfile.TemporaryDirectory(prefix="sba_cohort_hash_") as td:
        db_path = Path(td) / "seen.sqlite"
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE seen (row_hash TEXT PRIMARY KEY)")
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("PRAGMA temp_store=MEMORY")

        try:
            for path in input_paths:
                source_hash = file_sha256(path)
                source_entry = {
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": source_hash,
                    "expected_sha256_from_audit": EXPECTED_SOURCE_SHA256.get(path.name),
                    "sha256_matches_audit": source_hash == EXPECTED_SOURCE_SHA256.get(path.name) if path.name in EXPECTED_SOURCE_SHA256 else None,
                    "expected_rows_from_audit": EXPECTED_SOURCE_ROWS.get(path.name),
                }
                source_manifest.append(source_entry)
                file_rows = 0
                file_header_signature = None
                file_duplicates = 0
                open_fn = gzip.open if path.suffix.lower() == ".gz" else open
                with open_fn(path, "rt", newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames:
                        raise ValueError(f"No header found in {path.name}")
                    normalized_headers = [norm_key(h) for h in reader.fieldnames]
                    if file_header_signature is None:
                        file_header_signature = normalized_headers
                    missing_fields = [x for x in EXPECTED_FIELDS if norm_key(x) not in normalized_headers]
                    if missing_fields:
                        raise ValueError(f"{path.name} missing expected fields: {missing_fields}")
                    if len(normalized_headers) != len(set(normalized_headers)):
                        raise ValueError(f"Duplicate/ambiguous column names in {path.name}")
                    if "_canonical_header_signature" not in counters:
                        counters["_canonical_header_signature"] = normalized_headers
                    elif counters["_canonical_header_signature"] != normalized_headers:
                        raise ValueError(f"Column order/schema differs across source files: {path.name}")

                    for raw_row in reader:
                        file_rows += 1
                        if None in raw_row or any(v is None for v in raw_row.values()):
                            raise ValueError(f"Malformed row with extra or missing fields in {path.name}, row {file_rows + 1}")
                        counters["source_rows_read"] += 1
                        row = {norm_key(k): (v or "") for k, v in raw_row.items() if k is not None}
                        # Hash all source columns in their input header order. Only the
                        # digest enters the temporary DB; it is never written to outputs.
                        row_values = [((raw_row.get(h) or "").strip()) for h in reader.fieldnames]
                        digest = hashlib.sha256(json.dumps(row_values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
                        cur = con.execute("INSERT OR IGNORE INTO seen(row_hash) VALUES (?)", (digest,))
                        if cur.rowcount == 0:
                            file_duplicates += 1
                            counters["exact_duplicate_excess_rows"] += 1
                            continue
                        counters["deduplicated_rows"] += 1

                        approval = parse_date(source_get(row, "ApprovalDate"))
                        disb = parse_date(source_get(row, "FirstDisbursementDate"))
                        asof = parse_date(source_get(row, "AsOfDate"))
                        paid_raw = source_get(row, "PaidInFullDate")
                        charge_raw = source_get(row, "ChargeOffDate")
                        paid = parse_date(paid_raw)
                        charge = parse_date(charge_raw)
                        status = norm_status(source_get(row, "LoanStatus"))

                        for label, raw, parsed in (
                            ("ApprovalDate", source_get(row, "ApprovalDate"), approval),
                            ("FirstDisbursementDate", source_get(row, "FirstDisbursementDate"), disb),
                            ("AsOfDate", source_get(row, "AsOfDate"), asof),
                            ("PaidInFullDate", paid_raw, paid),
                            ("ChargeOffDate", charge_raw, charge),
                        ):
                            if raw.strip() and parsed is None:
                                parse_issue_counts[label] += 1
                                quality[f"unparseable_{label}"] += 1
                        if asof:
                            snapshots[asof.isoformat()] += 1
                        else:
                            quality["missing_or_invalid_AsOfDate"] += 1

                        fy_raw = source_get(row, "ApprovalFY")
                        try:
                            fy = int(float(fy_raw)) if fy_raw else None
                        except ValueError:
                            fy = None
                        derived = derived_fy(approval)
                        if fy is None and derived is not None:
                            fy = derived
                            quality["ApprovalFY_filled_from_ApprovalDate"] += 1
                        elif fy is not None and derived is not None and fy != derived:
                            quality["ApprovalFY_mismatch_with_ApprovalDate"] += 1

                        ga = parse_num(source_get(row, "GrossApproval"))
                        sg = parse_num(source_get(row, "SBAGuaranteedApproval"))
                        term = parse_num(source_get(row, "TermInMonths"))
                        rate = parse_num(source_get(row, "InitialInterestRate"))
                        charge_amt = parse_num(source_get(row, "GrossChargeOffAmount"))
                        valid_term, valid_amount, valid_rate = numeric_validity(ga, sg, term, rate)

                        if approval and disb and disb < approval:
                            quality["first_disbursement_before_approval"] += 1
                        if disb and paid and paid < disb:
                            quality["paid_in_full_before_disbursement"] += 1
                        if disb and charge and charge < disb:
                            quality["chargeoff_before_disbursement"] += 1
                        if asof and charge and charge > asof:
                            quality["chargeoff_after_snapshot"] += 1
                        if asof and paid and paid > asof:
                            quality["paid_in_full_after_snapshot"] += 1
                        if ga is None or ga <= 0:
                            quality["gross_approval_missing_or_nonpositive"] += 1
                        if sg is None or sg < 0 or (ga is not None and sg > ga):
                            quality["guaranteed_approval_missing_or_out_of_range"] += 1
                        if term is None or not (1 <= term <= 360):
                            quality["term_missing_or_outside_1_360"] += 1
                        if rate is not None and rate < 0:
                            quality["negative_interest_rate"] += 1
                        if charge_amt is not None and charge_amt < 0:
                            quality["negative_gross_chargeoff_amount"] += 1
                        if charge_amt is not None and ga is not None and charge_amt > ga:
                            quality["gross_chargeoff_amount_exceeds_gross_approval_review"] += 1
                        if status == "CHGOFF" and charge is None:
                            quality["CHGOFF_missing_or_invalid_chargeoff_date"] += 1
                        if status == "PIF" and paid is None:
                            quality["PIF_missing_or_invalid_paid_date"] += 1

                        # Reference-reproduction cohort (exactly as in the prior audit).
                        ref_base = bool(
                            approval and asof and fy is not None and 2001 <= fy <= 2016
                            and add_months(approval, 120) <= asof
                            and status in ALLOWED_STATUS
                        )
                        if status == "CHGOFF":
                            ref_base = ref_base and charge is not None and approval <= charge <= asof
                        if ref_base:
                            counters["reference_base_eligible"] += 1
                            if fy is not None:
                                by_fy[fy]["reference_base_eligible"] += 1
                            if valid_term and valid_amount:
                                counters["reference_term_amount_eligible"] += 1
                                if fy is not None:
                                    by_fy[fy]["reference_term_amount_eligible"] += 1
                                if fy >= 2010 and valid_rate:
                                    counters["reference_final_eligible"] += 1
                                    if fy is not None:
                                        by_fy[fy]["reference_final_eligible"] += 1
                                    target = int(status == "CHGOFF" and charge is not None and charge <= add_months(approval, 120))
                                    counters["reference_final_chargeoffs"] += target
                                    by_fy[fy]["reference_final_chargeoffs"] += target
                                    if status == "PIF" and paid is None:
                                        quality["reference_PIF_included_with_missing_paid_date"] += 1
                                    split = split_for_fy(fy)
                                    if split:
                                        rec = {
                                            "approval_fy": fy,
                                            "approval_date": approval.isoformat(),
                                            "as_of_date": asof.isoformat(),
                                            **safe_feature_values(row),
                                            "target_chargeoff_within_120m": target,
                                            "outcome_class": "CHARGEOFF_WITHIN_120M" if target else "NON_CHARGEOFF_WITHIN_120M_REFERENCE",
                                            "split": split,
                                        }
                                        outputs["ref_train" if split == "train" else "ref_test"].writerow(rec)
                                        counters[f"reference_{split}_rows"] += 1

                        # Strict fixed-horizon cohort: only unambiguous outcomes.
                        if approval and asof and fy is not None and 2010 <= fy <= 2016 and valid_term and valid_amount and valid_rate:
                            strict_label = classify_120(approval, asof, status, paid, charge)
                            strict_valid = strict_label in {
                                "CHARGEOFF_WITHIN_120M", "CHARGEOFF_AFTER_120M",
                                "PIF_WITHIN_120M", "PIF_AFTER_120M",
                                "NO_TERMINAL_EVENT_RECORDED_THROUGH_120M",
                            }
                            by_fy[fy][f"strict_outcome_{strict_label}"] += 1
                            if strict_valid:
                                counters["strict_final_eligible"] += 1
                                by_fy[fy]["strict_final_eligible"] += 1
                                target = int(strict_label == "CHARGEOFF_WITHIN_120M")
                                counters["strict_final_chargeoffs"] += target
                                by_fy[fy]["strict_final_chargeoffs"] += target
                                split = split_for_fy(fy)
                                if split:
                                    rec = {
                                        "approval_fy": fy,
                                        "approval_date": approval.isoformat(),
                                        "as_of_date": asof.isoformat(),
                                        **safe_feature_values(row),
                                        "target_chargeoff_within_120m": target,
                                        "outcome_class": strict_label,
                                        "split": split,
                                    }
                                    outputs["strict_train" if split == "train" else "strict_test"].writerow(rec)
                                    counters[f"strict_{split}_rows"] += 1
                            else:
                                counters["strict_unresolved_or_ineligible"] += 1

                        # Approval-origin survival cohort. No 120m maturity is
                        # required; follow-up is event time or snapshot censoring.
                        if approval and fy is not None and 2001 <= fy <= 2016:
                            surv = classify_survival(approval, asof, status, paid, charge)
                            if surv is not None:
                                event_type, days, months = surv
                                counters["survival_eligible"] += 1
                                by_fy[fy]["survival_eligible"] += 1
                                survival_rec = {
                                    "approval_fy": fy,
                                    "approval_date": approval.isoformat(),
                                    "as_of_date": asof.isoformat(),
                                    **safe_feature_values(row),
                                    "event_type": event_type,
                                    "followup_days": days,
                                    "followup_months": round(months, 4),
                                }
                                outputs["survival"].writerow(survival_rec)

                source_entry["rows_read"] = file_rows
                source_entry["exact_duplicate_excess_rows"] = file_duplicates
                source_entry["rows_match_audit"] = file_rows == EXPECTED_SOURCE_ROWS.get(path.name) if path.name in EXPECTED_SOURCE_ROWS else None

            con.commit()
            counters["files_processed"] = len(input_paths)
            counters["source_files_total_bytes"] = sum(x["bytes"] for x in source_manifest)
            counters["unique_snapshot_dates"] = len(snapshots)
            counters["snapshot_date_values"] = dict(snapshots)
            if args.expected_snapshot != "any":
                expected = parse_date(args.expected_snapshot)
                if expected is None:
                    raise ValueError("--expected-snapshot must be YYYY-MM-DD or 'any'")
                if set(snapshots) != {expected.isoformat()}:
                    quality["snapshot_date_mismatch"] += 1

            # FY reconciliation table, including expected reference counts.
            cohort_rows = []
            for fy in range(2001, 2017):
                expected_pair = EXPECTED_BY_FY.get(fy)
                observed_n = by_fy[fy]["reference_final_eligible"]
                observed_y = by_fy[fy]["reference_final_chargeoffs"]
                cohort_rows.append({
                    "approval_fy": fy,
                    "reference_base_eligible": by_fy[fy]["reference_base_eligible"],
                    "reference_final_eligible": observed_n,
                    "reference_final_chargeoffs": observed_y,
                    "reference_final_chargeoff_rate_pct": round(100 * observed_y / observed_n, 4) if observed_n else "",
                    "strict_final_eligible": by_fy[fy]["strict_final_eligible"],
                    "strict_final_chargeoffs": by_fy[fy]["strict_final_chargeoffs"],
                    "strict_chargeoff_rate_pct": round(100 * by_fy[fy]["strict_final_chargeoffs"] / by_fy[fy]["strict_final_eligible"], 4) if by_fy[fy]["strict_final_eligible"] else "",
                    "split": split_for_fy(fy) or "historical_only",
                    "expected_reference_final_eligible_from_audit": expected_pair[0] if expected_pair else "",
                    "expected_reference_final_chargeoffs_from_audit": expected_pair[1] if expected_pair else "",
                    "reference_population_count_matches_audit": (observed_n == expected_pair[0]) if expected_pair else "",
                    "reference_chargeoff_count_matches_audit": (observed_y == expected_pair[1]) if expected_pair else "",
                })

            with (args.out_dir / "cohort_counts_by_fy.csv").open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(cohort_rows[0].keys()), lineterminator="\n")
                writer.writeheader(); writer.writerows(cohort_rows)
            with (args.out_dir / "quality_flags.csv").open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(["quality_flag", "count"])
                writer.writerows(sorted(quality.items()))

            expected_total = sum(v[0] for v in EXPECTED_BY_FY.values())
            expected_events = sum(v[1] for v in EXPECTED_BY_FY.values())
            reconciliation = {
                "expected_from_prior_audit": {"population": expected_total, "chargeoffs": expected_events},
                "observed_reference_final": {
                    "population": counters["reference_final_eligible"],
                    "chargeoffs": counters["reference_final_chargeoffs"],
                },
                "population_matches": counters["reference_final_eligible"] == expected_total,
                "chargeoffs_match": counters["reference_final_chargeoffs"] == expected_events,
            }
            manifest = {
                "project": "SBA 7(a) credit-risk cohort construction",
                "builder_version": "1.0.0",
                "snapshot_date_counts": dict(snapshots),
                "source_files": source_manifest,
                "counters": dict(counters),
                "reference_reconciliation": reconciliation,
                "cohort_rules": {
                    "reference_replication": "Approval-date origin; FY2001-2016; approval+120 calendar months <= AsOfDate; status CHGOFF/PIF/EXEMPT; CHGOFF requires ChargeOffDate between ApprovalDate and AsOfDate; term 1-360; GrossApproval > 0; 0 <= SBAGuaranteedApproval <= GrossApproval; FY2010-2016 additionally requires nonmissing nonnegative InitialInterestRate. Reference target is CHGOFF with ChargeOffDate <= approval+120 months.",
                    "strict_120m": "FY2010-2016; same valid term/amount/rate feature gates; 120-month horizon matured; only CHARGEOFF_WITHIN_120M, CHARGEOFF_AFTER_120M, PIF_WITHIN_120M, PIF_AFTER_120M and EXEMPT with no terminal dates are retained; unresolved date/status combinations are excluded. PIF is a competing event and is labelled non-charge-off for cumulative-incidence binary target, not treated as an ordinary censor.",
                    "train_test": "Train FY2010-2014; locked temporal test FY2015-2016. Keep test set untouched until final evaluation.",
                    "survival": "Approval-date origin; FY2001-2016; CHGOFF and PIF are distinct event causes; eligible EXEMPT records with no terminal dates are right-censored at AsOfDate.",
                },
                "model_feature_allowlist": FEATURE_FIELDS,
                "excluded_from_outputs": [
                    "LocationID", "BorrName", "BorrStreet", "BorrCity", "BorrZip",
                    "BankName", "BankFDICNumber", "BankNCUANumber", "BankStreet",
                    "BankCity", "BankZip", "FranchiseName", "LoanStatus",
                    "PaidInFullDate", "ChargeOffDate", "GrossChargeOffAmount",
                ],
                "quality_flags": dict(quality),
                "parse_issue_counts": dict(parse_issue_counts),
                "outputs": [
                    "reference_train_fy2010_2014.csv.gz",
                    "reference_locked_test_fy2015_2016.csv.gz",
                    "strict_train_fy2010_2014.csv.gz",
                    "strict_locked_test_fy2015_2016.csv.gz",
                    "approval_origin_survival.csv.gz",
                    "cohort_counts_by_fy.csv", "quality_flags.csv",
                ],
                "privacy": {
                    "raw_rows_exported": False,
                    "direct_identifiers_exported": False,
                    "temporary_row_hashes_exported": False,
                    "temporary_dedup_database_deleted_after_run": True,
                },
                "important_limitations": [
                    "This is an approval-level FOIA snapshot, not a monthly servicing panel.",
                    "A charge-off is an observed loan outcome, not automatically every definition of default.",
                    "The reference cohort intentionally mirrors the previous audit and can include PIF rows with missing paid dates; inspect the quality flag and use the strict cohort for the primary analysis.",
                    "PIF is treated as a competing event for survival analysis and as a non-charge-off event by 120 months for the cumulative-incidence binary target.",
                    "No empirical LGD, EAD, CCF, recovery cash flows, or monthly delinquency target is created.",
                    "A repeated LocationID is not treated as a duplicate or unique loan key; only exact full-row duplicates are removed.",
                ],
            }
            (args.out_dir / "cohort_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            print("SBA cohort construction complete")
            print(json.dumps({
                "deduplicated_rows": counters["deduplicated_rows"],
                "exact_duplicate_excess_rows": counters["exact_duplicate_excess_rows"],
                "reference_final_population": counters["reference_final_eligible"],
                "reference_final_chargeoffs": counters["reference_final_chargeoffs"],
                "strict_final_population": counters["strict_final_eligible"],
                "strict_final_chargeoffs": counters["strict_final_chargeoffs"],
                "survival_population": counters["survival_eligible"],
                "reference_reconciliation": reconciliation,
                "output_directory": str(args.out_dir.resolve()),
            }, indent=2))
        finally:
            con.close()
            for writer in outputs.values():
                writer.close()


if __name__ == "__main__":
    main()
