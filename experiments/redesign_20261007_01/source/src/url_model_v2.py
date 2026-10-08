"""Normalized, offline URL representation for the redesigned classifier."""
from urllib.parse import urlsplit
from collections import Counter
from dataclasses import dataclass
import math
import re
import numpy as np
import pandas as pd
from features import features


def normalize_url(url):
    if not isinstance(url, str) or not url.strip():
        return ''
    raw = url.strip()
    try:
        parsed = urlsplit(raw if '://' in raw else 'http://' + raw)
        if parsed.scheme.lower() not in {'http', 'https'} or not parsed.hostname:
            return ''
        # Preserve case-sensitive userinfo, path, query and fragment.
        authority = parsed.netloc.rsplit('@', 1)
        authority[-1] = authority[-1].lower()
        return parsed._replace(scheme=parsed.scheme.lower(), netloc='@'.join(authority),
                               path=parsed.path or '/').geturl()
    except ValueError:
        return ''


def numeric_features(url):
    normalized = normalize_url(url)
    if not normalized:
        raise ValueError('A valid HTTP(S) URL with a hostname is required')
    out = features(normalized)
    parsed = urlsplit(normalized)
    host = parsed.hostname or ''
    path = parsed.path
    def entropy(text):
        n = max(len(text), 1)
        return -sum((k / n) * math.log2(k / n) for k in Counter(text).values())
    host_words = re.findall(r'[A-Za-z]+', host)
    path_words = re.findall(r'[A-Za-z]+', path)
    host_labels = host.split('.')
    out.update({
        'host_entropy': entropy(host), 'path_entropy': entropy(path),
        'query_entropy': entropy(parsed.query),
        'path_digit_ratio': sum(c.isdigit() for c in path) / max(len(path), 1),
        'path_letter_ratio': sum(c.isalpha() for c in path) / max(len(path), 1),
        'host_longest_label': max(map(len, host_labels), default=0),
        'host_longest_word': max(map(len, host_words), default=0),
        'path_longest_word': max(map(len, path_words), default=0),
        'host_word_count': len(host_words), 'path_word_count': len(path_words),
        'path_extension_length': len(path.rsplit('.', 1)[-1]) if '.' in path.rsplit('/', 1)[-1] else 0,
        'explicit_port': int(bool(re.search(r':\d+$', parsed.netloc))),
        'colon_count': normalized.count(':'), 'semicolon_count': normalized.count(';'),
        'longest_character_run': max((len(x[0]) for x in re.finditer(r'(.)\1*', normalized)), default=0),
    })
    return out


def numeric_frame(urls, without_scheme=True):
    frame = pd.DataFrame([numeric_features(str(u)) for u in urls])
    if without_scheme:
        frame = frame.drop(columns='has_https')
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError('Nonfinite URL features')
    return frame


def lexical_view(url):
    normalized = normalize_url(url)
    if not normalized:
        raise ValueError('A valid HTTP(S) URL is required')
    # Avoid using the source-specific http/https frequency as a text shortcut.
    return normalized.split('://', 1)[1]


def calibrate_threshold(y, scores, sources, fpr_budget):
    """Smallest cutoff meeting the observed normal-row FPR budget in each source.

    Tied scores are treated as a group. A cutoff above one may legitimately
    reject every phishing prediction when a classifier has collapsed; callers
    must inspect recall rather than calling this an effective operating point.
    """
    y, p, sources = np.asarray(y), np.asarray(scores, dtype=float), np.asarray(sources)
    if not 0 <= fpr_budget < 1 or len(y) != len(p) or len(p) != len(sources):
        raise ValueError('Invalid calibration arguments')
    if set(np.unique(y)) != {0, 1} or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Both classes and finite probabilities are required')
    cutoffs = []
    for source in np.unique(sources):
        normal = np.sort(p[(sources == source) & (y == 0)])[::-1]
        if len(normal):
            allowed = int(math.floor(fpr_budget * len(normal) + 1e-12))
            cutoffs.append(float(np.nextafter(normal[allowed], np.inf)))
    if not cutoffs:
        raise ValueError('No legitimate calibration examples')
    threshold = max(cutoffs)
    pred = p >= threshold
    details = {}
    for source in np.unique(sources):
        mask = sources == source
        normal, positive = mask & (y == 0), mask & (y == 1)
        details[str(source)] = {'normal_n': int(normal.sum()), 'phishing_n': int(positive.sum()),
                                'fpr': float(pred[normal].mean()) if normal.any() else None,
                                'recall': float(pred[positive].mean()) if positive.any() else None}
    return {'threshold': threshold, 'fpr_budget': fpr_budget, 'by_source': details,
            'recall': float(pred[y == 1].mean())}


def training_weights(frame):
    """Equal source/class mass, then equal domain mass within each stratum."""
    sizes = frame.groupby(['source', 'y', 'group']).y.transform('size').to_numpy()
    domains = frame.groupby(['source', 'y']).group.transform('nunique').to_numpy()
    strata = frame[['source', 'y']].drop_duplicates().shape[0]
    weights = 1 / (strata * domains * sizes)
    return weights * len(frame) / weights.sum()


@dataclass
class ModelBundle:
    family: str
    estimator: object
    feature_names: list
    vectorizer: object = None
    feature_version: str = 'normalized_url_v2'

    def matrix(self, urls):
        if self.vectorizer is not None:
            return self.vectorizer.transform([lexical_view(u) for u in urls])
        return numeric_frame(urls)[self.feature_names]

    def predict_proba(self, urls):
        return self.estimator.predict_proba(self.matrix(urls))
