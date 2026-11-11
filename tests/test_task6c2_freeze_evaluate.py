import sys,unittest,gzip,tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sba_task6c2_freeze_evaluate as s

class TestTask6C2(unittest.TestCase):
 def test_paired_bootstrap_deterministic(self):
  y=np.array([0,0,1,0,1,0,0,1]); a=np.array([.1,.2,.8,.1,.7,.2,.3,.6]); b=np.array([.2,.1,.6,.2,.5,.4,.3,.5])
  x=s.paired_delta_ci(y,a,b,n=50,seed=17); z=s.paired_delta_ci(y,a,b,n=50,seed=17)
  self.assertEqual(x,z); self.assertEqual(x["replicates_requested"],50); self.assertLessEqual(x["ci_95_low"],x["ci_95_high"])
 def test_metric_outputs(self):
  m=s.metrics(np.array([0,1,0,1]),np.array([.1,.8,.2,.7]))
  self.assertAlmostEqual(m["average_precision"],1.0); self.assertAlmostEqual(m["roc_auc"],1.0)
 def test_array_strings_in_prediction_cells_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'sample.gz'
   with gzip.open(path,'wt') as z:
    z.write('model,approval_fy,target,predicted_probability\n')
    z.write('hgb,2024,"[0 1 ...]","[0.1 0.9 ...]"\n')
   self.assertFalse(s.prediction_file_valid(path))
 def test_scalar_prediction_rows_are_accepted(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'sample.gz'
   with gzip.open(path,'wt') as z:
    z.write('model,approval_fy,target,predicted_probability\n')
    z.write('hgb,2024,0,0.1\nhgb,2024,1,0.9\n')
   self.assertTrue(s.prediction_file_valid(path))

if __name__=="__main__": unittest.main()
