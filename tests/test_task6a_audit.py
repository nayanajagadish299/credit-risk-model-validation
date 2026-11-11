"""Unit checks; no original SBA data needed."""
import sys
import unittest
import csv
import json
import tempfile
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sba_task6a_contemporary_audit as s


class TestAudit(unittest.TestCase):
    def test_fiscal_year(self):
        self.assertEqual(s.fiscal_year(s.parse_date("09/30/2026")), 2026)
        self.assertEqual(s.fiscal_year(s.parse_date("10/01/2025")), 2026)
        self.assertEqual(s.fiscal_year(s.parse_date("10/01/2026")), 2027)

    def test_data_parsing(self):
        self.assertEqual(s.parse_number("$1,050.50"), 1050.5)
        self.assertIsNone(s.parse_number("not-a-number"))
        self.assertEqual(s.normalize_status("Charged Off"), "CHGOFF")
        self.assertEqual(s.normalize_status("Paid in Full"), "PIF")
        self.assertEqual(s.group_label("541611", code=True), "54")
        self.assertEqual(s.group_label("California"), "OTHER_OR_INVALID")

    def test_aggregate(self):
        stat = s.empty_stat()
        s.update_stat(stat, 100.0, 80.0)
        s.update_stat(stat, None, 1.0)
        self.assertEqual(stat["loans"], 2)
        self.assertEqual(stat["approved_usd"], 100)
        self.assertEqual(stat["guarantee_share_sum"], 0.8)
        self.assertEqual(stat["guarantee_valid_n"], 1)


    def test_synthetic_end_to_end(self):
        fields = ["ApprovalFY", "ApprovalDate", "AsOfDate", "GrossApproval",
                  "SBAGuaranteedApproval", "LoanStatus", "ProjectState", "NaicsCode",
                  "BusinessType", "CollateralInd", "ProcessingMethod",
                  "InitialInterestRate", "RevolverStatus", "FixedorVariableInterestInd", "BorrName"]
        base = {"ApprovalFY": "2024", "ApprovalDate": "10/20/2023",
                "AsOfDate": "09/30/2026", "GrossApproval": "100000",
                "SBAGuaranteedApproval": "75000", "LoanStatus": "EXEMPT",
                "ProjectState": "CA", "NaicsCode": "541611", "BusinessType": "CORPORATION",
                "CollateralInd": "Y", "ProcessingMethod": "7A General",
                "InitialInterestRate": "8.5", "RevolverStatus": "0",
                "FixedorVariableInterestInd": "F", "BorrName": "PRIVATE TEST BORROWER"}
        rec2 = {**base, "ApprovalFY": "2025", "ApprovalDate": "10/20/2024", "GrossApproval": "200000"}
        rec3 = {**base, "ApprovalFY": "2026", "ApprovalDate": "10/20/2025", "GrossApproval": "300000"}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "source.csv"
            dest = root / "output"
            with src.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows([base, base, rec2, rec3])
            old_expected = s.EXPECTED_SOURCE_ROWS
            try:
                s.EXPECTED_SOURCE_ROWS = 4
                s.audit(src, dest, hashlib.sha256(src.read_bytes()).hexdigest(), 10)
            finally:
                s.EXPECTED_SOURCE_ROWS = old_expected
            manifest = json.loads((dest / "task6a_manifest.json").read_text())
            self.assertEqual(manifest["counts"]["unique_rows"], 3)
            self.assertEqual(manifest["counts"]["duplicate_excess_rows"], 1)
            with (dest / "yearly_summary.csv").open(encoding="utf-8-sig") as f:
                annual = list(csv.DictReader(f))
            self.assertEqual([r["loans"] for r in annual if int(r["approval_fy"]) in (2024, 2025, 2026)], ["1", "1", "1"])
            self.assertFalse((dest / "loans.csv").exists())
            self.assertNotIn("PRIVATE TEST BORROWER", json.dumps(manifest))


if __name__ == "__main__":
    unittest.main()
