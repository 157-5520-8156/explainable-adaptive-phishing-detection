"""Freeze archived-page model using calibration domains only, then replay labels."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import shutil
import sys
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, GroupShuffleSplit
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from page_model import PageBundle, CONTENT_FEATURES
from url_model_v2 import normalize_url, numeric_frame, calibrate_threshold, training_weights
from adaptive_page import FeedbackMonitor, threshold_calibration_pool
from evaluation import metrics
RUN = ROOT / 'experiments/page_20261007_01'
A = RUN / 'artifacts'
P = json.loads((ROOT / 'configs/page_protocol.json').read_text())

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path, obj): Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')
def fit(family, seed, train, names):
    config = P[family]
    cls = RandomForestClassifier if family == 'random_forest' else HistGradientBoostingClassifier
    model = cls(**config, random_state=seed)
    model.fit(train[names], train.y, sample_weight=training_weights(train))
    if family=='random_forest':model.set_params(n_jobs=1)
    return PageBundle(family, model, names)

def split_domains(f, seed, fraction):
    train_idx, cal_idx = next(GroupShuffleSplit(n_splits=1, test_size=fraction, random_state=seed).split(f, f.y, f.group))
    train, cal = f.iloc[train_idx].copy(), f.iloc[cal_idx].copy()
    assert not set(train.group) & set(cal.group)
    if train.y.nunique() != 2 or cal.y.nunique() != 2:
        raise ValueError('Both classes required in refit and calibration parts')
    return train, cal

def scores(bundle, f): return bundle.estimator.predict_proba(f[bundle.feature_names])[:, 1]
def cutoff(bundle, f): return calibrate_threshold(f.y, scores(bundle, f), f.source, P['primary_fpr_budget'])['threshold']

def replay(initial, initial_threshold, train, cal, pool, seed, policy, delay, order):
    cfg = P['replay']
    out = A / 'replays' / f'{order}_{policy}_delay{delay}_seed{seed}'
    out.mkdir(parents=True)
    if order == 'stationary':
        stream = pool.sample(frac=1, random_state=seed)
    else:
        from urllib.parse import urlsplit
        group_mean = pool.assign(path_length=pool.URL.map(lambda u: len(urlsplit(normalize_url(u)).path))).groupby('group').path_length.mean()
        ranks = group_mean.sample(frac=1, random_state=seed).sort_values(kind='stable').index
        rank = {g: i for i, g in enumerate(ranks)}
        stream = pool.assign(profile_rank=pool.group.map(rank)).sort_values('profile_rank', kind='stable')
    stream = stream.reset_index(drop=True)
    stream[['URL', 'group', 'y']].to_csv(out / 'stream_manifest.csv', index=False)
    anchor = pd.concat([train, cal]).sample(n=min(cfg['anchor_rows'], len(train) + len(cal)), random_state=seed)
    bundle, threshold = initial, initial_threshold
    monitor = FeedbackMonitor(delta=cfg['adwin_delta'])
    arrivals, recent, predictions, events, timings = [], [], [], [], []
    last_update, updates = -999, 0
    start = time.perf_counter()
    for batch, lo in enumerate(range(0, len(stream), cfg['batch_size'])):
        f = stream.iloc[lo:lo + cfg['batch_size']].copy()
        p = scores(bundle, f)
        pred = (p >= threshold).astype(int)
        version = monitor.version
        for j, (idx, row) in enumerate(f.iterrows()):
            predictions.append({'row': int(idx), 'batch': batch, 'group': row.group, 'y': int(row.y),
                                'score': float(p[j]), 'threshold': threshold, 'prediction': int(pred[j]),
                                'decision_version': version, 'label_available_batch': batch + delay})
        arrivals.append((batch + delay, batch, f, pred, version))
        due = [item for item in arrivals if item[0] <= batch]
        arrivals = [item for item in arrivals if item[0] > batch]
        alarm = False
        for available, origin, revealed, old_pred, old_version in due:
            recent.append(revealed)
            alarm |= monitor.reveal(revealed.y, old_pred, old_version)
            timings.append({'prediction_batch': origin, 'arrival_batch': batch, 'scheduled_batch': available,
                            'prediction_version': old_version, 'current_version': monitor.version, 'n': len(revealed)})
        if not due or policy == 'fixed': continue
        should = (policy == 'threshold' or
                  (policy == 'periodic' and (batch - delay + 1) % cfg['periodic_every'] == 0) or
                  (policy == 'drift' and alarm and batch - last_update >= cfg['cooldown_batches']))
        if not should: continue
        labelled = pd.concat(recent).tail(cfg['recent_labels'])
        available = pd.concat([anchor, labelled]).drop_duplicates('normalized').reset_index(drop=True)
        if policy == 'threshold':
            # This estimator remains fitted on the original domains: none may
            # enter its new calibration pool, regardless of a synthetic split.
            update_train = train
            update_cal = threshold_calibration_pool(train, cal, labelled)
            assert not set(update_train.group) & set(update_cal.group)
        else:
            update_train, update_cal = split_domains(available, seed + batch, cfg['calibration_fraction'])
        old_threshold = threshold
        started = time.perf_counter()
        if policy != 'threshold': bundle = fit(initial.family, seed, update_train, initial.feature_names)
        threshold = cutoff(bundle, update_cal)
        monitor.decision_changed()
        updates += 1
        last_update = batch
        joblib.dump({'bundle': bundle, 'threshold': threshold, 'decision_version': monitor.version}, out / f'checkpoint_{monitor.version}.joblib', compress=3)
        events.append({'batch': batch, 'decision_version': monitor.version, 'policy': policy, 'alarm': bool(alarm),
                       'old_threshold': old_threshold, 'threshold': threshold,
                       'fit_n': len(update_train), 'calibration_n': len(update_cal),
                       'seconds': time.perf_counter() - started, 'refit_performed': policy != 'threshold',
                       'max_label_prediction_batch': max(x[1] for x in due),
                       'training_domains': sorted(set(update_train.group)), 'calibration_domains': sorted(set(update_cal.group))})
    # Pending labels are not revealed after the stream solely to improve a final model.
    f = pd.DataFrame(predictions)
    f.to_csv(out / 'predictions.csv', index=False)
    dump(out / 'events.json', events)
    dump(out / 'label_arrivals.json', timings)
    state = {'bundle': bundle, 'threshold': threshold, 'decision_version': monitor.version}
    joblib.dump(state, out / 'final.joblib', compress=3)
    # Metrics use per-arrival cutoffs, not a retrospective final cutoff.
    result = metrics(f.y, f.score, 0, f.group)
    from sklearn.metrics import confusion_matrix
    tn, fp, fn, tp = map(int, confusion_matrix(f.y, f.prediction, labels=[0, 1]).ravel())
    result.update({'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp, 'fpr': fp/(tn+fp), 'recall': tp/(tp+fn),
                   'precision': tp/(tp+fp) if tp+fp else 0, 'f1': 2*tp/(2*tp+fp+fn),
                   'domain_macro_fpr': float(f[f.y == 0].groupby('group').prediction.mean().mean()),
                   'domain_macro_recall': float(f[f.y == 1].groupby('group').prediction.mean().mean()),
                   'order': order, 'policy': policy, 'delay': delay, 'seed': seed, 'updates': updates,
                   'ignored_old_errors': monitor.ignored_old_errors, 'pending_labels': sum(len(x[2]) for x in arrivals),
                   'seconds': time.perf_counter()-start, 'final_model_sha256': sha(out/'final.joblib')})
    dump(out/'summary.json', result)
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',default='page_20261007_01')
    parser.add_argument('--base-partition',default=P['base_partition'])
    args=parser.parse_args()
    RUN=ROOT/'experiments'/args.run_id; A=RUN/'artifacts'
    P['base_partition']=args.base_partition
    if RUN.exists(): raise SystemExit('Archive exists; refusing overwrite')
    A.mkdir(parents=True)
    files = ['configs/page_protocol.json', 'src/page_model.py', 'src/url_model_v2.py', 'src/features.py',
             'src/adaptive_page.py', 'src/evaluation.py', 'scripts/run_page_study.py', 'requirements.txt']
    for name in files:
        dest = RUN / 'source' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name, dest)
    dump(RUN/'source/configs/page_protocol.json',P)
    manifest = {'started_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'status': 'preparing',
                'source_sha256': {n: sha(RUN/'source'/n) for n in files},
                'raw_sha256': sha(ROOT/'data/raw/hannousse_dataset_B_05_2020.csv'),
                'base_partition_sha256': sha(ROOT/'experiments'/P['base_partition']/'artifacts/new_source_partition_manifest.csv')}
    dump(RUN/'manifest.json', manifest)
    base = ROOT/'experiments'/P['base_partition']/'artifacts'
    h = pd.concat([pd.read_pickle(base/'hannousse_adaptation.pkl'), pd.read_pickle(base/'sealed_hannousse_eval.pkl')])
    raw = pd.read_csv(ROOT/'data/raw/hannousse_dataset_B_05_2020.csv')
    raw['normalized'] = raw.url.map(normalize_url)
    raw = raw.drop_duplicates('normalized')
    content = raw.set_index('normalized')[CONTENT_FEATURES]
    h = h.reset_index(drop=True).join(content, on='normalized', validate='one_to_one')
    assert h[CONTENT_FEATURES].notna().all().all()
    X = numeric_frame(h.URL, version='normalized_url_v3')
    names = list(X.columns) + CONTENT_FEATURES
    for c in X: h[c] = X[c].to_numpy()
    assert np.isfinite(h[names].to_numpy(dtype=float)).all()
    # Grouped folds are read from the already fixed URL partition; no test predictions.
    initial_pool, pool, test = h[h.fold == 3], h[h.fold == 4], h[h.fold <= 2]
    initial_train, cal = split_domains(initial_pool, 20261007, .3)
    initial_train.to_pickle(A/'initial_train.pkl'); cal.to_pickle(A/'calibration.pkl')
    pool.to_pickle(A/'replay_pool.pkl'); test.to_pickle(A/'sealed_test.pkl')
    for role, f in [('initial_train', initial_train), ('calibration', cal), ('replay', pool), ('test', test)]:
        f[['URL','normalized','group','y']].to_csv(A/f'{role}_manifest.csv', index=False)
    roles = [initial_train, cal, pool, test]
    for i, left in enumerate(roles):
        for right in roles[i+1:]: assert not set(left.group) & set(right.group)
    dump(A/'partition_counts.json', {role: {'n':len(f),'normal':int(f.y.eq(0).sum()),'phishing':int(f.y.sum()),'domains':int(f.group.nunique())}
                                   for role,f in zip(['initial_train','calibration','replay','test'],roles)})
    dump(A/'feature_names.json', names)
    validation, models, cuts = [], {}, {}
    for family in P['families']:
        for seed in P['seeds']:
            bundle = fit(family, seed, initial_train, names)
            joblib.dump(bundle, A/f'{family}_{seed}.joblib', compress=3)
            models[(family,seed)] = bundle
            p = scores(bundle, cal)
            for alpha in P['operating_points']:
                cut = calibrate_threshold(cal.y,p,cal.source,alpha)['threshold']
                validation.append({'family':family,'seed':seed,'budget':alpha,'threshold':cut,**metrics(cal.y,p,cut,cal.group)})
                cuts[(family,seed,alpha)] = cut
            print('CALIBRATION', family, seed, validation[-1]['fpr'], validation[-1]['recall'], flush=True)
    frame = pd.DataFrame(validation)
    frame.to_csv(A/'validation_metrics.csv',index=False)
    rank = frame[frame.budget.eq(P['primary_fpr_budget'])].groupby('family')[['recall','average_precision']].mean().sort_values(['recall','average_precision'],ascending=False)
    family = rank.index[0]
    dump(A/'selection.json', {'frozen_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'family':family,
                              'ranking':rank.reset_index().to_dict(orient='records'), 'test_scores_inspected':False,
                              'primary_budget':P['primary_fpr_budget'], 'calibrations':validation})
    manifest['status']='static_selection_frozen_no_test_scores';dump(RUN/'manifest.json',manifest)
    rows=[]
    for order in P['replay']['orders']:
        for delay in P['replay']['delays']:
            for policy in P['replay']['policies']:
                for seed in P['seeds']:
                    result=replay(models[(family,seed)],cuts[(family,seed,P['primary_fpr_budget'])],initial_train,cal,pool,seed,policy,delay,order)
                    rows.append(result);pd.DataFrame(rows).to_csv(A/'replay_metrics.csv',index=False)
                    print('REPLAY',order,policy,delay,seed,'FPR',round(result['fpr'],4),'R',round(result['recall'],4),'updates',result['updates'],flush=True)
    manifest['status']='all_replays_frozen_before_test_scoring'
    manifest['artifact_sha256']={str(p.relative_to(RUN)):sha(p) for p in A.rglob('*') if p.is_file()}
    dump(RUN/'manifest.json',manifest)
