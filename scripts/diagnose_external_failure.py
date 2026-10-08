"""Reproduce the severe external false-positive failure from a frozen model.

The 90% bound detects the reported collapse; it is not a deployment target.
No model, threshold, label or accepted experiment artifact is changed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--reproduce', action='store_true')
parser.add_argument('--normal-n', type=int, default=256)
args = parser.parse_args()
if args.normal_n < 1:
    parser.error('--normal-n must be positive')
A = ROOT / 'experiments/revision_20261006_02/artifacts'
spec = next(x for x in json.loads((A / 'frozen_external_models.json').read_text())['models']
            if x['variant'] == 'full_30_features' and x['seed'] == 17)
model_path = A / spec['model']
assert hashlib.sha256(model_path.read_bytes()).hexdigest() == spec['model_sha256']
model = joblib.load(model_path)
assert list(model.classes_) == [0, 1]
frame = pd.read_pickle(A / 'external_features.pkl')
normal = frame[(frame.partition == 'external_holdout') & (frame.y == 0)].sort_values('canonical').head(args.normal_n)
scores = model.predict_proba(normal[spec['features']])[:, 1]
false_positives = int((scores >= spec['threshold']).sum())
result = {'model': spec['model'], 'model_hash_verified': True, 'seed': 17,
          'threshold': spec['threshold'], 'sample_policy': f'first {args.normal_n} legitimate external-holdout canonical URLs in sorted order',
          'normal_examples': len(normal), 'false_positives': false_positives,
          'false_positive_rate': false_positives / len(normal)}
out = ROOT / 'experiments/diagnostic_20261007_external_failure'
out.mkdir(exist_ok=True)
(out / f'reproduction_n_{args.normal_n}.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
if args.reproduce and result['false_positive_rate'] >= 0.90:
    raise SystemExit('REPRODUCED: frozen classifier flags at least 90% of these legitimate URLs.')
