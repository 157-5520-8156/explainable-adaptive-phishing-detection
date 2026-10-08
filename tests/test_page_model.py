import sys
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from page_model import PageBundle

class PageInputTest(unittest.TestCase):
    def test_page_model_does_not_fabricate_missing_page_features(self):
        bundle = PageBundle('random_forest', None, [])
        with self.assertRaisesRegex(ValueError, 'Archived page measurements required'):
            bundle.matrix(pd.DataFrame({'URL': ['https://example.org/']}))

class FeedbackTest(unittest.TestCase):
    def test_cutoff_change_rejects_old_decision_errors(self):
        from adaptive_page import FeedbackMonitor
        class Recorder:
            def __init__(self): self.values = []; self.drift_detected = False
            def update(self, value): self.values.append(value)
        monitor = FeedbackMonitor(Recorder)
        monitor.reveal([0, 1], [1, 1], 0)
        self.assertEqual(monitor.detector.values, [1, 0])
        monitor.decision_changed()
        monitor.reveal([0, 1], [1, 1], 0)
        self.assertEqual(monitor.detector.values, [])
        self.assertEqual(monitor.ignored_old_errors, 2)
        monitor.reveal([0], [0], 1)
        self.assertEqual(monitor.detector.values, [0])

class ThresholdCalibrationTest(unittest.TestCase):
    def test_retained_estimator_fit_domains_never_enter_threshold_calibration(self):
        from adaptive_page import threshold_calibration_pool
        fit = pd.DataFrame({'normalized':['a'], 'group':['fit'], 'y':[0]})
        cal = pd.DataFrame({'normalized':['b','c'], 'group':['cal0','cal1'], 'y':[0,1]})
        revealed = pd.DataFrame({'normalized':['d','e'], 'group':['fit','new'], 'y':[1,0]})
        pool = threshold_calibration_pool(fit,cal,revealed)
        self.assertEqual(set(pool.group), {'cal0','cal1','new'})
