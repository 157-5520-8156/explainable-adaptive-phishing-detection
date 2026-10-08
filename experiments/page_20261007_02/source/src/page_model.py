"""Offline model for creator-supplied archived page measurements."""
from dataclasses import dataclass
import numpy as np
from url_model_v2 import numeric_frame

CONTENT_FEATURES = [
    'nb_hyperlinks', 'ratio_intHyperlinks', 'ratio_extHyperlinks', 'ratio_nullHyperlinks',
    'nb_extCSS', 'ratio_intRedirection', 'ratio_extRedirection', 'ratio_intErrors',
    'ratio_extErrors', 'login_form', 'external_favicon', 'links_in_tags', 'submit_email',
    'ratio_intMedia', 'ratio_extMedia', 'sfh', 'iframe', 'popup_window', 'safe_anchor',
    'onmouseover', 'right_clic', 'empty_title', 'domain_in_title', 'domain_with_copyright']

@dataclass
class PageBundle:
    family: str
    estimator: object
    feature_names: list
    feature_version: str = 'normalized_url_v3'

    def matrix(self, records):
        missing = set(CONTENT_FEATURES + ['URL']) - set(records.columns)
        if missing:
            raise ValueError('Archived page measurements required: ' + ', '.join(sorted(missing)))
        matrix = numeric_frame(records.URL, version=self.feature_version)
        for name in CONTENT_FEATURES:
            matrix[name] = records[name].to_numpy()
        matrix = matrix[self.feature_names]
        if not np.isfinite(matrix.to_numpy(dtype=float)).all():
            raise ValueError('Page measurements must be finite numeric values')
        return matrix

    def predict_proba(self, records):
        return self.estimator.predict_proba(self.matrix(records))
