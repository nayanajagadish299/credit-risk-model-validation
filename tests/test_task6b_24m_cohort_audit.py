import sys
import unittest
import csv
import hashlib
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sba_task6b_24m_cohort_audit as s


class TestTask6B(unittest.TestCase):
    def row(self, approval="2022-01-31", fy="2022", status="EXEMPT", paid="", charge=""):
        headers={s.key(k):k for k in ("ApprovalDate","ApprovalFY","LoanStatus","PaidInFullDate","ChargeOffDate")}
        return {headers[s.key("ApprovalDate")]:approval,headers[s.key("ApprovalFY")]:fy,headers[s.key("LoanStatus")]:status,headers[s.key("PaidInFullDate")]:paid,headers[s.key("ChargeOffDate")]:charge},headers
    def test_maturity_boundary_calendar_month(self):
        self.assertEqual(s.add_months(date(2024,2,29),24),date(2026,2,28))
        self.assertEqual(s.add_months(date(2023,2,28),24),date(2025,2,28))
        self.assertEqual(s.add_months(date(2024,8,31),24),date(2026,8,31))
        self.assertLessEqual(s.add_months(date(2024,9,30),24),s.AS_OF)
        self.assertGreater(s.add_months(date(2024,10,1),24),s.AS_OF)
    def test_chargeoff_within_and_after(self):
        r,h=self.row(charge="2023-12-31");r[h[s.key("LoanStatus")]]="CHGOFF"
        self.assertEqual(s.classify(r,h)[0],1)
        r,h=self.row(charge="2024-02-01");r[h[s.key("LoanStatus")]]="CHGOFF"
        self.assertEqual(s.classify(r,h)[0],0)
    def test_paid_in_full_competing(self):
        r,h=self.row(status="Paid in Full",paid="2023-01-01")
        self.assertEqual(s.classify(r,h)[0],0)
        r,h=self.row(status="PIF",paid="2024-02-01")
        self.assertEqual(s.classify(r,h)[0],0)
    def test_exempt_and_missing_terminal_dates(self):
        r,h=self.row(status="EXEMPT")
        self.assertEqual(s.classify(r,h)[0],0)
        r,h=self.row(status="CHGOFF")
        self.assertIsNone(s.classify(r,h)[0])
        r,h=self.row(status="PIF")
        self.assertIsNone(s.classify(r,h)[0])
    def test_conflicting_terminal_dates(self):
        r,h=self.row(status="CHGOFF",paid="2023-01-01",charge="2023-02-01")
        self.assertIn("both_terminal_dates",s.classify(r,h)[1])
    def test_cancel_and_commit_separate_reasons(self):
        r,h=self.row(status="CANCLD")
        self.assertIn("excluded_status_cancld",s.classify(r,h)[1])
        r,h=self.row(status="COMMIT")
        self.assertIn("excluded_status_commit",s.classify(r,h)[1])
    def test_exclusion_priority_is_mutually_exclusive(self):
        r,h=self.row(approval="not-date",fy="2022",status="CANCLD")
        y,flags,_,_=s.classify(r,h)
        p=next(x for x in ("excluded_status_cancld","excluded_status_commit","invalid_approval_date") if x in flags)
        self.assertIsNone(y)
        self.assertEqual(p,"excluded_status_cancld")
    def test_audit_emits_reconciled_reports(self):
        fields=["ApprovalDate","ApprovalFY","AsOfDate","LoanStatus","PaidInFullDate","ChargeOffDate","FirstDisbursementDate"]
        rows=[{"ApprovalDate":"2022-01-31","ApprovalFY":"2022","AsOfDate":"2026-09-30","LoanStatus":"EXEMPT","PaidInFullDate":"","ChargeOffDate":"","FirstDisbursementDate":""},
              {"ApprovalDate":"2022-01-31","ApprovalFY":"2022","AsOfDate":"2026-09-30","LoanStatus":"CANCLD","PaidInFullDate":"","ChargeOffDate":"","FirstDisbursementDate":""}]
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"in.csv"; out=Path(td)/"out"
            with src.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            s.audit(src,out,hashlib.sha256(src.read_bytes()).hexdigest())
            for name in ("exclusions_by_fy.csv","quality_flag_overlaps.csv","disbursement_diagnostics.csv","outcome_reconciliation_by_fy.csv","task6b_manifest.json"):
                self.assertTrue((out/name).is_file(),name)
            with (out/"outcome_reconciliation_by_fy.csv").open(encoding="utf-8-sig") as f: rec=list(csv.DictReader(f))
            fyrow=next(x for x in rec if x["approval_fy"]=="2022")
            self.assertEqual(fyrow["eligible"],"1"); self.assertEqual(fyrow["positive"],"0"); self.assertEqual(fyrow["negative"],"1")
            with (out/"exclusions_by_fy.csv").open(encoding="utf-8-sig") as f: ex=list(csv.DictReader(f))
            self.assertEqual(sum(int(x["records"]) for x in ex if x["approval_fy"]=="2022"),1)
            manifest=__import__("json").loads((out/"task6b_manifest.json").read_text())
            for field in ("script_version","run_id","source_sha256","snapshot_date","candidate_records","eligible_records","excluded_records","positive_records","negative_records","primary_exclusion_reason_records","later_chargeoffs_negative","output_sha256","checks"):
                self.assertIn(field,manifest)
            self.assertEqual(manifest["candidate_records"],manifest["eligible_records"]+manifest["excluded_records"])
            self.assertEqual(manifest["eligible_records"],manifest["positive_records"]+manifest["negative_records"])
            self.assertEqual(manifest["primary_exclusion_reason_records"],manifest["excluded_records"])
            self.assertTrue(all(value=="PASS" for value in manifest["checks"].values()))
            for name,sha in manifest["output_sha256"].items():
                self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),sha)
    def test_unresolved_and_invalid(self):
        r,h=self.row(status="ACTIVE")
        self.assertIsNone(s.classify(r,h)[0])
        r,h=self.row(approval="not-a-date")
        self.assertIn("invalid_approval_date",s.classify(r,h)[1])
    def test_fiscal_year_reconciliation(self):
        r,h=self.row(approval="2021-10-01",fy="2022")
        self.assertEqual(s.fy(s.parse_date(r[h[s.key("ApprovalDate")]])),2022)
        r,h=self.row(approval="2021-09-30",fy="2022")
        self.assertIn("approval_fy_date_mismatch",s.classify(r,h)[1])

if __name__=="__main__": unittest.main()
