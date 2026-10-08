"""Small call-site tests for delayed-feedback provenance, not performance tests."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import experiment

class ToyClassifier(ClassifierMixin,BaseEstimator):
    def __init__(self,random_state=None):self.random_state=random_state
    def fit(self,X,y):return self
    def predict_proba(self,X):
        p=np.where(X['signal'].to_numpy()>0,.8,.2)
        return np.column_stack([1-p,p])

class RecordingDetector:
    instances=[]
    def __init__(self,delta=None):
        self.seen=[];self.drift_detected=False;self.instances.append(self)
    def update(self,error):
        self.seen.append(error);self.drift_detected=True

class StreamProtocolTest(unittest.TestCase):
    def test_reset_detector_rejects_older_model_errors(self):
        """At batch 2 a refit occurs; feedback at 3/4 still belongs to version 0."""
        def frame(n,offset=0):
            return pd.DataFrame({'signal':np.arange(n)%2,'y':np.arange(n)%2,
                'canonical':[f'url_{offset+i}' for i in range(n)],'group':[f'g_{offset+i}' for i in range(n)],'phase':['A' if i<n//2 else 'B' for i in range(n)]})
        cfg={'random_forest':{},'stream':{'batch_size':2,'recent_window':4,'periodic_every':2,'adwin_delta':.002,'cooldown_batches':2}}
        RecordingDetector.instances=[]
        with patch.object(experiment,'CONFIG',cfg),patch.object(experiment,'RandomForestClassifier',ToyClassifier),patch.object(experiment,'ADWIN',RecordingDetector):
            experiment.simulate(frame(4),frame(10,4),['signal'],17,'drift',2)
        self.assertGreaterEqual(len(RecordingDetector.instances),2)
        self.assertEqual(RecordingDetector.instances[1].seen,[],
                         'New detector received labels for predictions from the previous model')

if __name__=='__main__':unittest.main()
