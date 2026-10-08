"""Fit fixed candidates; freeze selection using development validation only."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import shutil
import sys
import time
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sklearn.exceptions import ConvergenceWarning

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from url_model_v2 import ModelBundle, calibrate_threshold, lexical_view, training_weights

parser = argparse.ArgumentParser()
parser.add_argument('--run-id', default='redesign_20261007_01')
args = parser.parse_args()
RUN = ROOT / 'experiments' / args.run_id
A = RUN / 'artifacts'
P = json.loads((RUN / 'source/configs/redesign_protocol.json').read_text())
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')

def metrics(y, scores, threshold, groups=None):
    y, scores = np.asarray(y), np.asarray(scores)
    pred = scores >= threshold
    tn, fp, fn, tp = map(int, confusion_matrix(y, pred, labels=[0, 1]).ravel())
    out = {'n': len(y), 'normal_n': tn + fp, 'phishing_n': tp + fn,
           'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
           'fpr': fp / (fp + tn) if fp + tn else None,
           'recall': tp / (tp + fn) if tp + fn else None,
           'precision': tp / (tp + fp) if tp + fp else 0,
           'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
           'average_precision': float(average_precision_score(y, scores)),
           'roc_auc': float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else None}
    if groups is not None:
        g = pd.DataFrame({'group': np.asarray(groups), 'y': y, 'positive': pred})
        out['domain_macro_fpr'] = float(g[g.y == 0].groupby('group').positive.mean().mean())
        out['domain_macro_recall'] = float(g[g.y == 1].groupby('group').positive.mean().mean())
    return out

def fit_bundle(family, seed, train, columns, protocol=P):
    w = training_weights(train)
    start = time.perf_counter()
    vectorizer = None
    if family == 'char_logistic':
        vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(3, 5), min_df=3,
                                     max_features=80000, sublinear_tf=True, lowercase=False)
        X = vectorizer.fit_transform([lexical_view(u) for u in train.URL])
        names = vectorizer.get_feature_names_out().tolist()
        estimator = LogisticRegression(**protocol['char_logistic'], random_state=seed)
    else:
        X = train[columns]
        names = columns
        if family in {'random_forest', 'source_only_random_forest'}:
            estimator = RandomForestClassifier(**protocol['random_forest'], random_state=seed)
        elif family == 'hist_gradient_boosting':
            estimator = HistGradientBoostingClassifier(**protocol['hist_gradient_boosting'], random_state=seed)
        elif family == 'numeric_logistic':
            estimator = make_pipeline(StandardScaler(), LogisticRegression(**protocol['numeric_logistic'], random_state=seed))
        else:
            raise ValueError(family)
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        if family == 'numeric_logistic':
            estimator.fit(X, train.y, logisticregression__sample_weight=w)
        else:
            estimator.fit(X, train.y, sample_weight=w)
    return ModelBundle(family, estimator, names, vectorizer), time.perf_counter() - start

if __name__ == '__main__':
    model_dir = A / 'static_models'
    model_dir.mkdir(exist_ok=True)
    manifest = json.loads((RUN / 'manifest.json').read_text())
    assert sha(ROOT / 'src/url_model_v2.py') == manifest['source_sha256']['src/url_model_v2.py']
    dest = RUN / 'source/scripts/run_redesign_static.py'
    shutil.copy2(__file__, dest)
    manifest['static_runner_sha256'] = sha(dest)
    manifest['status'] = 'development_training_no_test_scores'
    dump(RUN / 'manifest.json', manifest)
    dev = pd.read_pickle(A / 'development.pkl')
    train = pd.read_pickle(A / 'training.pkl')
    val = dev[dev.partition == 'validation'].reset_index(drop=True)
    columns = json.loads((A / 'feature_names.json').read_text())
    rows, calibrations, specifications = [], [], []
    families = P['families'] + ['source_only_random_forest']
    for family in families:
        current_train = train[train.source == 'PhiUSIIL'] if family.startswith('source_only') else train
        current_val = val[val.source == 'PhiUSIIL'] if family.startswith('source_only') else val
        current_val = current_val.reset_index(drop=True)
        for seed in P['seeds']:
            file = model_dir / f'{family}_{seed}.joblib'
            metadata_file = model_dir / f'{family}_{seed}.json'
            if file.exists() and metadata_file.exists():
                meta = json.loads(metadata_file.read_text())
                assert sha(file) == meta['sha256']
                bundle = joblib.load(file)
                seconds = meta['fit_seconds']
            else:
                print('Fit', family, seed, 'rows', len(current_train), flush=True)
                bundle, seconds = fit_bundle(family, seed, current_train, columns)
                joblib.dump(bundle, file, compress=3)
                meta = {'family': family, 'seed': seed, 'fit_seconds': seconds,
                        'training_n': len(current_train), 'sha256': sha(file)}
                dump(metadata_file, meta)
            if bundle.vectorizer is None:
                scores = bundle.estimator.predict_proba(current_val[columns])[:, 1]
            else:
                scores = bundle.predict_proba(current_val.URL)
            np.savez_compressed(A / f'validation_scores_{family}_{seed}.npz', scores=scores)
            specifications.append({**meta, 'path': str(file.relative_to(RUN))})
            for alpha in P['operating_points']:
                calibration = calibrate_threshold(current_val.y, scores, current_val.source, alpha)
                calibrations.append({'family': family, 'seed': seed, **calibration})
                for source, g in current_val.groupby('source'):
                    row = {'family': family, 'seed': seed, 'fpr_budget': alpha,
                           'threshold': calibration['threshold'], 'source': source,
                           **metrics(g.y, scores[g.index], calibration['threshold'], g.group)}
                    rows.append(row)
                    print('Validation', family, seed, source, alpha,
                          'FPR', round(row['fpr'], 4), 'recall', round(row['recall'], 4), flush=True)
                dump(A / 'validation_calibrations.json', calibrations)
                pd.DataFrame(rows).to_csv(A / 'validation_metrics.csv', index=False)
    frame = pd.DataFrame(rows)
    primary = frame[(frame.fpr_budget == P['primary_fpr_budget']) & frame.family.isin(P['families'])]
    selection = primary.groupby('family')[['recall', 'average_precision']].mean().reset_index()
    selection['tie_order'] = selection.family.map({n: i for i, n in enumerate(P['families'])})
    selection = selection.sort_values(['recall', 'average_precision', 'tie_order'], ascending=[False, False, True])
    family = selection.family.iloc[0]
    decision = {'frozen_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'selected_family': family,
                'selection_data': 'development validation only', 'test_scores_inspected': False,
                'validation_ranking': selection.to_dict(orient='records'), 'models': specifications,
                'protocol_sha256': sha(RUN / 'source/configs/redesign_protocol.json'),
                'calibrations': calibrations}
    dump(A / 'validation_selection.json', decision)
    manifest['status'] = 'selection_frozen_before_test_scoring'
    manifest['selection_sha256'] = sha(A / 'validation_selection.json')
    dump(RUN / 'manifest.json', manifest)
    print('FROZEN SELECTED FAMILY:', family, flush=True)
