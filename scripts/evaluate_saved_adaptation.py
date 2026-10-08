"""Post-hoc external evaluation of the last applied replay checkpoints.

The holdout was previously inspected for the source-only test. This is a
diagnostic extension, not a new untouched confirmatory test. Model versions
and thresholds come from the last original prediction batch; no fitting or
selection using holdout performance occurs here.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/revision_20261006_02'
A = RUN / 'artifacts'
OUT = ROOT / 'experiments/diagnostic_20261007_external_failure'
OUT.mkdir(exist_ok=True)
manifest = json.loads((RUN / 'manifest.json').read_text())
spec = json.loads((A / 'frozen_external_models.json').read_text())['models'][0]
hold = pd.read_pickle(A / 'external_features.pkl')
hold = hold[hold.partition == 'external_holdout'].reset_index(drop=True)
assert len(hold) == 40810
pred = pd.read_csv(A / 'replay_predictions.csv',
                   usecols=['scenario', 'seed', 'policy', 'delay_batches', 'batch', 'model_version', 'threshold'])
pred = pred[pred.scenario == 'source_switch']
specs = []
for key, g in pred.groupby(['seed', 'policy', 'delay_batches'], sort=True):
    seed, policy, delay = key
    last = g[g.batch == g.batch.max()]
    assert last.model_version.nunique() == last.threshold.nunique() == 1
    version = int(last.model_version.iloc[0])
    relative = f'artifacts/replay_models/source_switch_{seed}_{policy}_{delay}/version_{version}.joblib'
    assert relative in manifest['artifact_sha256']
    path = RUN / relative
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == manifest['artifact_sha256'][relative]
    stream = pd.read_csv(A / f'source_switch_{seed}_stream_manifest.csv', usecols=['group'])
    assert not set(stream.group) & set(hold.group)
    specs.append({'seed': int(seed), 'policy': policy, 'delay_batches': int(delay),
                  'version': version, 'threshold': float(last.threshold.iloc[0]),
                  'model': relative, 'model_sha256': digest})
protocol = {'started_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'status': 'post-hoc diagnostic; evaluation specification saved before scoring these checkpoints',
            'test': 'same 40,810-row domain-disjoint external holdout used by the earlier frozen source-model evaluation',
            'checkpoint_selection': 'last applied model and threshold at the last original replay prediction batch',
            'no_refitting': True, 'no_threshold_selection_using_holdout': True,
            'model_count': len(specs), 'specifications': specs}
(OUT / 'post_adaptation_protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
rows, probabilities = [], []
for s in specs:
    model = joblib.load(RUN / s['model'])
    assert list(model.classes_) == [0, 1] and list(model.feature_names_in_) == spec['features']
    p = model.predict_proba(hold[spec['features']])[:, 1]
    yp = p >= s['threshold']
    tn, fp, fn, tp = map(int, confusion_matrix(hold.y, yp, labels=[0, 1]).ravel())
    rows.append({**s, 'n': len(hold), 'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
                 'fpr': fp / (fp + tn), 'recall': tp / (tp + fn),
                 'precision': tp / (tp + fp) if tp + fp else 0,
                 'f1': 2 * tp / (2 * tp + fp + fn),
                 'average_precision': float(average_precision_score(hold.y, p)),
                 'roc_auc': float(roc_auc_score(hold.y, p))})
    probabilities.append(p)
    print(f"{s['seed']} {s['policy']} delay={s['delay_batches']} "
          f"F1={rows[-1]['f1']:.4f} FPR={rows[-1]['fpr']:.4f}", flush=True)
frame = pd.DataFrame(rows)
frame.to_csv(OUT / 'post_adaptation_external_metrics.csv', index=False)
hold[['canonical', 'group', 'y']].to_csv(OUT / 'post_adaptation_holdout_index.csv', index=False)
np.savez_compressed(OUT / 'post_adaptation_scores.npz', scores=np.array(probabilities))
summary = frame.groupby(['policy', 'delay_batches'])[['f1', 'fpr', 'recall', 'average_precision']].mean()
summary.to_csv(OUT / 'post_adaptation_external_means.csv')
print(summary.to_string())
