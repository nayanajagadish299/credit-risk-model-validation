import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sba_task6c_24m_model_validation as s


class TestTask6C(unittest.TestCase):
    def test_feature_allowlist_excludes_outcomes_and_forbidden_fields(self):
        forbidden={"TermInMonths","BusinessAge","LoanStatus","ChargeOffDate","PaidInFullDate","GrossChargeOffAmount","FirstDisbursementDate","JobsSupported"}
        self.assertTrue(set(s.FEATURES).isdisjoint(forbidden))
    def test_preprocessing_pipeline_fit_predict(self):
        X=pd.DataFrame({"log_gross_approval":[10.,11.,np.nan,12.],"guarantee_share":[.5,.7,.8,.6],"initial_interest_rate":[5.,6.,7.,8.],"naics2":["54","31","54","44"],"project_state":["CA","NY","CA","TX"],"business_type":["A","B","A","B"],"processing_method":["P","P","D","D"],"revolver_status":["N","Y","N","Y"],"fixed_or_variable_interest_ind":["F","V","F","V"],"collateral_ind":["Y","N","Y","N"]})
        y=np.array([0,1,0,1])
        model=s.make_preprocessor("logistic"); model.fit(X,y)
        p=model.predict_proba(X)[:,1]
        self.assertEqual(p.shape,(4,)); self.assertTrue(np.all((p>=0)&(p<=1)))
    def test_metric_and_bootstrap_schema(self):
        y=np.array([0,0,1,0,1,0]); p=np.array([.1,.2,.8,.15,.7,.3])
        m=s.score_metrics(y,p)
        self.assertTrue({"average_precision","roc_auc","brier_score","log_loss","mean_predicted_probability","observed_prevalence"}.issubset(m))
        b=s.bootstrap_ap(y,p,n_boot=20,seed=9)
        self.assertEqual(b["replicates_requested"],20)
        self.assertLessEqual(b["ap_95pct_low"],b["ap_95pct_high"])

if __name__=="__main__": unittest.main()
