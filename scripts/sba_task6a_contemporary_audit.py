#!/usr/bin/env python3
"""Task 6A: descriptive-only aggregate audit of September 2026 SBA 7(a) FY2020-Present CSV.

No outcomes are modeled. Snapshot status is *not* treated as a fixed-horizon
charge-off rate. Only aggregate summaries are written outside the repository.
Standard library only, compatible with Python 3.10+.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path

EXPECTED_SOURCE_SHA256 = "b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6"
EXPECTED_SOURCE_ROWS = 403644
EXPECTED_AS_OF = date(2026, 9, 30)
YEARS = tuple(range(2020, 2027))
MIN_GROUP_SIZE = 10

REQUIRED = (
    "ApprovalFY", "ApprovalDate", "AsOfDate", "GrossApproval",
    "SBAGuaranteedApproval", "LoanStatus", "ProjectState", "NaicsCode",
    "BusinessType", "CollateralInd", "ProcessingMethod",
    "InitialInterestRate", "RevolverStatus", "FixedorVariableInterestInd",
)
AUDIT_MISSING = (
    "ApprovalFY", "ApprovalDate", "GrossApproval", "SBAGuaranteedApproval",
    "LoanStatus", "ProjectState", "NaicsCode", "BusinessType",
    "ProcessingMethod", "InitialInterestRate", "RevolverStatus",
    "FixedorVariableInterestInd", "CollateralInd", "BusinessAge", "JobsSupported",
    "ChargeOffDate", "GrossChargeOffAmount",
)


def normalize_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def parse_number(s: str):
    s = str(s or "").strip().replace(",", "").replace("$", "").replace("%", "")
    if not s:
        return None
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def parse_date(s: str):
    s = str(s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def fiscal_year(d: date) -> int:
    return d.year + (d.month >= 10)


def normalize_status(raw: str) -> str:
    key = re.sub(r"[^A-Za-z]", "", raw or "").upper()
    return {
        "PAIDINFULL": "PIF", "CHARGEDOFF": "CHGOFF", "CANCELLED": "CANCLD",
        "CANCELED": "CANCLD", "COMMITMENT": "COMMIT",
    }.get(key, key or "MISSING")


def group_label(raw: str, *, code: bool = False) -> str:
    x = (raw or "").strip().upper()
    if code:
        digits = re.sub(r"\D", "", x)
        return digits[:2] if len(digits) >= 2 else "MISSING_OR_INVALID"
    if not x:
        return "MISSING"
    # Avoid publishing arbitrary loan-level/free-text values in aggregate labels.
    if len(x) > 3 or not re.fullmatch(r"[A-Z]{2,3}", x):
        return "OTHER_OR_INVALID"
    return x


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(2 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, header: list[str], records: list[dict]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(records)


def empty_stat():
    return {"loans": 0, "amount_valid_n": 0, "approved_usd": 0.0,
            "guaranteed_usd": 0.0, "guarantee_valid_n": 0, "guarantee_share_sum": 0.0}


def update_stat(stat: dict, approval, guaranteed):
    stat["loans"] += 1
    if approval is not None and approval > 0:
        stat["amount_valid_n"] += 1
        stat["approved_usd"] += approval
    if approval is not None and approval > 0 and guaranteed is not None and 0 <= guaranteed <= approval:
        stat["guarantee_valid_n"] += 1
        stat["guaranteed_usd"] += guaranteed
        stat["guarantee_share_sum"] += guaranteed / approval


def stat_row(key: dict, stat: dict) -> dict:
    n = stat["loans"]
    valid = stat["amount_valid_n"]
    gn = stat["guarantee_valid_n"]
    return {**key, "loans": n,
            "approved_total_usd": round(stat["approved_usd"], 2),
            "mean_approval_usd": round(stat["approved_usd"] / valid, 2) if valid else "",
            "valid_approval_n": valid,
            "guaranteed_total_usd": round(stat["guaranteed_usd"], 2),
            "mean_guarantee_share": round(stat["guarantee_share_sum"] / gn, 6) if gn else "",
            "valid_guarantee_n": gn}


def audit(input_path: Path, output_dir: Path, expected_hash: str, min_group_size: int):
    if not input_path.is_file():
        raise SystemExit(f"Missing original source CSV: {input_path}")
    if output_dir.resolve() == input_path.parent.resolve():
        raise SystemExit("Output directory must be separate from the raw source directory")
    actual_hash = file_hash(input_path)
    if actual_hash.lower() != expected_hash.lower():
        raise SystemExit("STOP: source SHA-256 differs from verified September 2026 snapshot. Do not proceed with this input.")

    totals = defaultdict(empty_stat)
    by_status = defaultdict(empty_stat)
    by_state = defaultdict(empty_stat)
    by_naics = defaultdict(empty_stat)
    missing = defaultdict(Counter)
    overall = Counter()
    status_all = Counter()
    snapshot_dates = Counter()
    seen = set()
    verified_fields = None
    header = None

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("Missing CSV header")
        header = [normalize_key(h) for h in reader.fieldnames]
        if len(set(header)) != len(header):
            raise SystemExit("Duplicate normalized input column names")
        verified_fields = set(header)
        not_found = [c for c in REQUIRED if normalize_key(c) not in verified_fields]
        if not_found:
            raise SystemExit("Missing required source fields: " + ", ".join(not_found))

        for row in reader:
            overall["raw_rows"] += 1
            # Exact full-row deduplication within this source, consistent with the
            # wider project's duplicate concept (but not across other CSVs).
            items = tuple(row.get(k) or "" for k in reader.fieldnames)
            digest = hashlib.sha256(json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).digest()
            if digest in seen:
                overall["duplicate_excess_rows"] += 1
                continue
            seen.add(digest)
            overall["unique_rows"] += 1
            r = dict(zip(header, items))
            get = lambda k: r.get(normalize_key(k), "")
            raw_fy = parse_number(get("ApprovalFY"))
            approval_fy = int(raw_fy) if raw_fy is not None and raw_fy.is_integer() else None
            approval_date = parse_date(get("ApprovalDate"))
            snapshot_date = parse_date(get("AsOfDate"))
            snapshot_dates[snapshot_date.isoformat() if snapshot_date else "UNPARSEABLE"] += 1
            if approval_fy is None:
                overall["missing_or_invalid_approval_fy"] += 1
                continue
            if approval_date is None:
                overall["missing_or_invalid_approval_date"] += 1
            elif fiscal_year(approval_date) != approval_fy:
                overall["approval_fy_vs_date_mismatch"] += 1
            if approval_fy not in YEARS:
                overall["rows_outside_fy2020_2026"] += 1
                continue

            overall["included_unique_fy2020_2026_rows"] += 1
            for field in AUDIT_MISSING:
                if not str(get(field)).strip():
                    missing[approval_fy][field] += 1

            amount = parse_number(get("GrossApproval"))
            guaranteed = parse_number(get("SBAGuaranteedApproval"))
            if amount is None or amount <= 0:
                overall["missing_or_nonpositive_approval"] += 1
            if guaranteed is None or amount is None or amount <= 0 or not (0 <= guaranteed <= amount):
                overall["invalid_guarantee_ratio"] += 1
            status = normalize_status(get("LoanStatus"))
            state = group_label(get("ProjectState"))
            sector = group_label(get("NaicsCode"), code=True)
            status_all[status] += 1
            update_stat(totals[approval_fy], amount, guaranteed)
            update_stat(by_status[(approval_fy, status)], amount, guaranteed)
            update_stat(by_state[(approval_fy, state)], amount, guaranteed)
            update_stat(by_naics[(approval_fy, sector)], amount, guaranteed)

    if snapshot_dates != {EXPECTED_AS_OF.isoformat(): overall["unique_rows"]}:
        raise SystemExit("STOP: unexpected AsOfDate values in input. See source data; no outputs written. " + str(dict(snapshot_dates)))
    if overall["raw_rows"] != EXPECTED_SOURCE_ROWS:
        raise SystemExit(f"STOP: unexpected source row count {overall['raw_rows']}; expected {EXPECTED_SOURCE_ROWS}.")
    if overall["included_unique_fy2020_2026_rows"] == 0:
        raise SystemExit("STOP: no valid included rows")

    output_dir.mkdir(parents=True, exist_ok=True)
    stats = ["loans", "approved_total_usd", "mean_approval_usd", "valid_approval_n",
             "guaranteed_total_usd", "mean_guarantee_share", "valid_guarantee_n"]
    yearly = [stat_row({"approval_fy": fy}, totals[fy]) for fy in YEARS]
    write_csv(output_dir / "yearly_summary.csv", ["approval_fy"] + stats, yearly)

    groups_info = [("status_by_fy.csv", "snapshot_status", by_status),
                   ("state_by_fy.csv", "project_state", by_state),
                   ("naics2_by_fy.csv", "naics2_sector", by_naics)]
    suppressed = {}
    for filename, category, groups in groups_info:
        records = []
        sup = 0
        for (fy, label), stat in sorted(groups.items()):
            if stat["loans"] < min_group_size:
                sup += 1
                continue
            records.append(stat_row({"approval_fy": fy, category: label}, stat))
        write_csv(output_dir / filename, ["approval_fy", category] + stats, records)
        suppressed[filename] = sup

    missing_rows = [{"approval_fy": fy, "field": field, "missing_n": missing[fy][field],
                     "total_n": totals[fy]["loans"],
                     "missing_pct": round(100 * missing[fy][field] / totals[fy]["loans"], 3) if totals[fy]["loans"] else ""}
                    for fy in YEARS for field in AUDIT_MISSING]
    write_csv(output_dir / "missingness_by_fy.csv", ["approval_fy", "field", "missing_n", "total_n", "missing_pct"], missing_rows)

    manifest = {
        "task": "6A contemporary SBA descriptive audit, not predictive validation",
        "source_basename": input_path.name,
        "source_sha256": actual_hash,
        "source_sha256_verified": True,
        "source_rows_expected": EXPECTED_SOURCE_ROWS,
        "snapshot_as_of": EXPECTED_AS_OF.isoformat(),
        "fy_range": [2020, 2026],
        "counts": dict(overall),
        "snapshot_status_totals": dict(sorted(status_all.items())),
        "group_suppression_min_n": min_group_size,
        "suppressed_group_counts": suppressed,
        "outputs": ["yearly_summary.csv", "status_by_fy.csv", "state_by_fy.csv", "naics2_by_fy.csv", "missingness_by_fy.csv"],
        "limitations": [
            "Status reflects September 2026 retrospective snapshot, not approval-time status.",
            "Snapshot charge-off proportions must not be called 24-month or 120-month rates.",
            "FY2025-2026 approvals do not have two full years of follow-up as of September 2026.",
            "Sums of GrossApproval represent nominal approved dollars, not loss, outstanding balance or disbursement.",
            "Current-snapshot values may not equal approval-time values, and FY2026 may not be final.",
            "No loan-level records are written. Small groups are suppressed; individual records remain in the original source.",
        ],
    }
    (output_dir / "task6a_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Task 6A aggregate audit: COMPLETE")
    print(json.dumps({"source_verified": True, "unique_fy2020_2026_loans": overall["included_unique_fy2020_2026_rows"],
                      "duplicate_excess_rows": overall["duplicate_excess_rows"],
                      "status_totals": dict(status_all),
                      "output_directory": str(output_dir.resolve())}, indent=2))
    print("IMPORTANT: Snapshot statuses are descriptive only, not fixed-horizon default rates.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--expected-sha256", default=EXPECTED_SOURCE_SHA256,
                   help="Only change after independently verifying a new snapshot; defaults to project verified 2026 source")
    p.add_argument("--min-group-size", type=int, default=MIN_GROUP_SIZE)
    a = p.parse_args()
    if a.min_group_size < 10:
        p.error("min-group-size must be >= 10")
    audit(a.input, a.out_dir, a.expected_sha256, a.min_group_size)


if __name__ == "__main__":
    main()
