import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sba_task6d1_gross_severity as s

class TestGrossSeverity(unittest.TestCase):
 def test_quantiles_and_denominators(self):
  x=s.summary([1,2,3,4,100])
  self.assertEqual(x['n'],5);self.assertEqual(x['total'],110);self.assertEqual(x['median'],3)
  self.assertEqual(x['q25'],2);self.assertEqual(x['q75'],4)
 def test_ratio_validity(self):
  self.assertEqual(s.chargeoff_ratio(50,100),.5)
  self.assertIsNone(s.chargeoff_ratio(-1,100));self.assertIsNone(s.chargeoff_ratio(1,0));self.assertIsNone(s.chargeoff_ratio(None,100))
 def test_approval_bands(self):
  self.assertEqual(s.loan_band(49999.99),'<50K')
  self.assertEqual(s.loan_band(50000),'50K-<150K')
  self.assertEqual(s.loan_band(150000),'150K-<350K')
  self.assertEqual(s.loan_band(350000),'>=350K')
  self.assertEqual(s.loan_band(0),'INVALID_OR_MISSING')
 def test_status_and_fiscal_year(self):
  self.assertEqual(s.normalize_status('Charged Off'),'CHGOFF')
  self.assertEqual(s.fy(s.parse_date('2020-10-01')),2021)

if __name__=='__main__':unittest.main()
