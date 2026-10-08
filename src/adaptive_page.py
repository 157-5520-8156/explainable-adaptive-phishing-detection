"""Label timing and decision-version boundary for archived page replay."""
import numpy as np
from river.drift import ADWIN

class FeedbackMonitor:
    def __init__(self, factory=None, delta=.002):
        self.factory = factory or (lambda: ADWIN(delta=delta))
        self.detector = self.factory()
        self.version = 0
        self.ignored_old_errors = 0

    def decision_changed(self):
        self.version += 1
        self.detector = self.factory()

    def reveal(self, y, predictions, prediction_version):
        if prediction_version != self.version:
            self.ignored_old_errors += len(y)
            return False
        alarm = False
        for error in (np.asarray(y) != np.asarray(predictions)).astype(int):
            self.detector.update(int(error))
            alarm |= bool(self.detector.drift_detected)
        return alarm


def threshold_calibration_pool(initial_fit, initial_calibration, revealed):
    """Use only domains outside the fit of the unchanged threshold-only model."""
    import pandas as pd
    pool = pd.concat([initial_calibration, revealed]).drop_duplicates('normalized')
    pool = pool[~pool.group.isin(set(initial_fit.group))].copy()
    if pool.y.nunique() != 2:
        raise ValueError('Independent threshold calibration requires both classes')
    return pool
