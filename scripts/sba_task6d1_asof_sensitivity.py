#!/usr/bin/env python3
"""Aggregate-only as-of sensitivity for the SBA Task 6D.1 severity study."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import date, datetime
from pathlib import Path

import numpy as np

EXPECTED_SHA256 = "b56194df6da2c22c318fcfc9f8f087152bc54e2be391c4cc70316514c37ef8e6"
EXPECTED_ROWS = 403644
EXPECTED_CHGOFF = 8202
EXPECTED_FUTURE_DATED = 18
SNAPSHOT = date(2026, 9, 30)
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%m-%d-%Y", "%Y/%m/%d")


def canon(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_date(value: str | None):
    value = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def parse_number(value: str | None):
    try:
        n = float((value or "").strip().replace(",", "").replace("$", ""))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def chargeoff_metrics(records: list[dict]) -> dict:
    amounts = [r["amount"] for r in records if r["amount"] is not None and r["amount"] >= 0]
    ratios = [r["ratio"] for r in records if r["ratio"] is not None]
    result = {"chargeoff_loans": len(records), "valid_nonnegative_amount_n": len(amounts),
              "valid_ratio_n": len(ratios), "invalid_ratio_n": len(records) - len(ratios)}
    if amounts:
        result.update({"gross_chargeoff_total": float(sum(amounts)), "gross_chargeoff_mean": float(np.mean(amounts)),
                       "gross_chargeoff_median": float(np.quantile(amounts, .5)),
                       "gross_chargeoff_q25": float(np.quantile(amounts, .25)),
                       "gross_chargeoff_q75": float(np.quantile(amounts, .75)),
                       "gross_chargeoff_p90": float(np.quantile(amounts, .90)),
                       "gross_chargeoff_p95": float(np.quantile(amounts, .95)),
                       "gross_chargeoff_p99": float(np.quantile(amounts, .99))})
    else:
        result.update({k: "" for k in ("gross_chargeoff_total", "gross_chargeoff_mean", "gross_chargeoff_median",
                                        "gross_chargeoff_q25", "gross_chargeoff_q75", "gross_chargeoff_p90",
                                        "gross_chargeoff_p95", "gross_chargeoff_p99")})
    result["mean_gross_chargeoff_to_approval_ratio"] = float(np.mean(ratios)) if ratios else ""
    return result


def build_populations(records: list[dict]) -> tuple[dict, dict, dict]:
    """Return aggregate metrics and flags; input rows are never emitted."""
    original = records
    future_only = [r for r in records if "chargeoff_after_snapshot" not in r["flags"]]
    asof = [r for r in records if r["date"] is not None and r["date"] <= SNAPSHOT]
    populations = {"original_task6d1": original, "future_dated_excluded_only": future_only,
                   "strict_asof_snapshot": asof}
    metrics = [{"population": name, **chargeoff_metrics(rows)} for name, rows in populations.items()]
    flag_names = ("missing_or_invalid_gross_chargeoff_amount", "negative_gross_chargeoff_amount",
                  "zero_gross_chargeoff_amount", "missing_or_invalid_gross_approval",
                  "nonpositive_gross_approval", "missing_or_invalid_sba_guaranteed_approval",
                  "guarantee_outside_0_to_approval", "missing_chargeoff_date", "invalid_chargeoff_date",
                  "missing_or_invalid_approval_date", "approval_fy_date_mismatch", "chargeoff_before_approval",
                  "gross_chargeoff_exceeds_gross_approval", "chargeoff_after_snapshot")
    flags = []
    for name, rows in populations.items():
        counts = {flag: sum(flag in r["flags"] for r in rows) for flag in flag_names}
        flags.extend({"population": name, "quality_flag": flag, "records": count} for flag, count in counts.items())
    return metrics, flags, {k: len(v) for k, v in populations.items()}


def analyze(source: Path, out_dir: Path) -> dict:
    digest = sha256(source)
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Source SHA-256 mismatch: {digest}")
    if out_dir.resolve() == source.parent.resolve():
        raise ValueError("Output directory must not be the raw source directory")
    records = []
    seen = set()
    raw_n = duplicate_n = 0
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = {canon(h): h for h in reader.fieldnames or []}
        required = ("LoanStatus", "GrossChargeOffAmount", "GrossApproval", "SBAGuaranteedApproval",
                    "ChargeOffDate", "ApprovalDate", "ApprovalFY")
        missing = [field for field in required if canon(field) not in headers]
        if missing:
            raise ValueError(f"Missing source fields: {missing}")
        for row in reader:
            raw_n += 1
            signature = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).digest()
            if signature in seen:
                duplicate_n += 1
                continue
            seen.add(signature)
            get = lambda field: (row.get(headers[canon(field)], "") or "").strip()
            if re.sub(r"[^A-Za-z]", "", get("LoanStatus")).upper() not in ("CHGOFF", "CHARGEDOFF"):
                continue
            amount = parse_number(get("GrossChargeOffAmount"))
            approval = parse_number(get("GrossApproval"))
            guarantee = parse_number(get("SBAGuaranteedApproval"))
            approval_date = parse_date(get("ApprovalDate"))
            chargeoff_date = parse_date(get("ChargeOffDate"))
            try:
                reported_fy = int(float(get("ApprovalFY")))
            except (TypeError, ValueError):
                reported_fy = None
            flags = []
            if amount is None: flags.append("missing_or_invalid_gross_chargeoff_amount")
            elif amount < 0: flags.append("negative_gross_chargeoff_amount")
            elif amount == 0: flags.append("zero_gross_chargeoff_amount")
            if approval is None: flags.append("missing_or_invalid_gross_approval")
            elif approval <= 0: flags.append("nonpositive_gross_approval")
            if guarantee is None: flags.append("missing_or_invalid_sba_guaranteed_approval")
            elif approval is not None and (guarantee < 0 or guarantee > approval): flags.append("guarantee_outside_0_to_approval")
            if not get("ChargeOffDate"): flags.append("missing_chargeoff_date")
            elif chargeoff_date is None: flags.append("invalid_chargeoff_date")
            if approval_date is None: flags.append("missing_or_invalid_approval_date")
            elif reported_fy is not None and approval_date.year + (approval_date.month >= 10) != reported_fy:
                flags.append("approval_fy_date_mismatch")
            if approval_date and chargeoff_date and chargeoff_date < approval_date: flags.append("chargeoff_before_approval")
            if amount is not None and approval is not None and approval > 0 and amount > approval:
                flags.append("gross_chargeoff_exceeds_gross_approval")
            if chargeoff_date and chargeoff_date > SNAPSHOT: flags.append("chargeoff_after_snapshot")
            records.append({"amount": amount, "ratio": amount / approval if amount is not None and amount >= 0 and approval is not None and approval > 0 else None,
                            "date": chargeoff_date, "flags": flags})
    if raw_n != EXPECTED_ROWS:
        raise ValueError(f"Unexpected raw row count: {raw_n}")
    if len(records) != EXPECTED_CHGOFF:
        raise ValueError(f"Unexpected deduplicated CHGOFF count: {len(records)}")
    n_future = sum("chargeoff_after_snapshot" in r["flags"] for r in records)
    if n_future != EXPECTED_FUTURE_DATED:
        raise ValueError(f"Unexpected future-dated CHGOFF count: {n_future}")
    undated = [r for r in records if "missing_chargeoff_date" in r["flags"] or "invalid_chargeoff_date" in r["flags"]]
    undated_nonzero_amount = sum(r["amount"] not in (None, 0) for r in undated)
    metrics, flags, counts = build_populations(records)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {"severity_comparison.csv": metrics, "quality_flags_comparison.csv": flags}
    for name, rows in outputs.items():
        with (out_dir / name).open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    checks = {
        "source_checksum": "PASS", "source_rows": "PASS", "deduplicated_chgoff_count": "PASS",
        "future_dated_rows_reconcile": "PASS" if n_future == EXPECTED_FUTURE_DATED else "FAIL",
        "strict_asof_exclusions_reconcile": "PASS" if counts["original_task6d1"] - counts["strict_asof_snapshot"] == n_future + sum("missing_chargeoff_date" in r["flags"] or "invalid_chargeoff_date" in r["flags"] for r in records) else "FAIL",
        "undated_chargeoff_amounts_reconcile": "PASS" if len(undated) == 11 and undated_nonzero_amount == 0 else "FAIL",
        "population_nested": "PASS" if counts["strict_asof_snapshot"] <= counts["original_task6d1"] else "FAIL",
        "aggregate_reports_written": "PASS"
    }
    manifest = {"study": "Task 6D.1 separate strict-as-of snapshot sensitivity", "snapshot_date": SNAPSHOT.isoformat(),
                "source_file": source.name, "source_sha256": digest, "raw_rows": raw_n,
                "duplicate_excess_rows": duplicate_n, "unique_chgoff_rows": len(records),
                "future_dated_chgoff_rows_excluded": n_future,
                "strict_asof_excluded_total": counts["original_task6d1"] - counts["strict_asof_snapshot"],
                "missing_or_invalid_date_rows_excluded_from_strict_asof": counts["original_task6d1"] - counts["strict_asof_snapshot"] - n_future,
                "undated_chargeoff_rows_with_nonzero_amount": undated_nonzero_amount,
                "population_counts": counts, "checks": checks,
                "report_sha256": {name: sha256(out_dir / name) for name in outputs},
                "interpretation": "Gross charge-off severity and gross charge-off-to-approval ratio only; this ratio is not LGD. Original Task 6D.1 outputs are unchanged."}
    (out_dir / "task6d1_asof_sensitivity_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if any(result != "PASS" for result in checks.values()):
        raise RuntimeError(f"QA checks failed: {checks}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.source, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
