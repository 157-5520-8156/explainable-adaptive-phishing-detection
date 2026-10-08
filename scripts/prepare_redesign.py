"""Create auditable domain partitions without evaluating the new test source."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import shutil
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from raw_protocol import raw_development_inputs
from features import domain_group
from url_model_v2 import normalize_url, numeric_frame

parser = argparse.ArgumentParser()
parser.add_argument('--run-id', default='redesign_20261007_01')
parser.add_argument('--raw-dir', type=Path, default=ROOT/'data/raw')
args = parser.parse_args()
RUN = ROOT / 'experiments' / args.run_id
if RUN.exists():
    raise SystemExit('Refusing to overwrite an existing redesign archive')
RUN.mkdir(parents=True)
A = RUN / 'artifacts'
A.mkdir()
protocol = json.loads((ROOT / 'configs/redesign_protocol.json').read_text())
phi_legacy, wang_legacy, raw_audit = raw_development_inputs(args.raw_dir)
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')
source_files = ['src/raw_protocol.py', 'src/url_model_v2.py', 'src/features.py', 'scripts/prepare_redesign.py',
                'configs/redesign_protocol.json', 'requirements.txt']
for name in source_files:
    dest = RUN / 'source' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / name, dest)
manifest = {'status': 'preparing', 'started_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'source_sha256': {n: sha(ROOT / n) for n in source_files},
            'raw_sha256': {n: sha(args.raw_dir / n) for n in
                           ['PhiUSIIL_Phishing_URL_Dataset.csv', 'wangchuk_dataset2.csv', 'hannousse_dataset_B_05_2020.csv']}}
dump(RUN / 'manifest.json', manifest)

def clean(frame, source):
    f = frame[['URL', 'y']].copy()
    f['source'] = source
    f['normalized'] = f.URL.map(normalize_url)
    bad = f.normalized.eq('') | f.URL.str.strip().str.contains(r'[\s<>\"]', regex=True, na=True)
    quality = {'raw_n': len(f), 'quality_excluded_by_class':
               {str(c): int((bad & f.y.eq(c)).sum()) for c in [0, 1]}}
    f = f[~bad].copy()
    conflicts = f.groupby('normalized').y.nunique()
    keys = set(conflicts[conflicts > 1].index)
    quality['conflicting_normalized_keys'] = len(keys)
    quality['conflicting_rows'] = int(f.normalized.isin(keys).sum())
    f = f[~f.normalized.isin(keys)]
    before = len(f)
    f = f.drop_duplicates('normalized').reset_index(drop=True)
    quality['duplicates_removed'] = before - len(f)
    f['group'] = f.normalized.map(domain_group)
    quality['retained_n'] = len(f)
    return f, quality

def folds(frame):
    assigned = np.zeros(len(frame), dtype=int)
    split = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=protocol['split_seed'])
    for k, (_, idx) in enumerate(split.split(frame, frame.y, frame.group)):
        assigned[idx] = k
    return assigned

raw_h = pd.read_csv(args.raw_dir / 'hannousse_dataset_B_05_2020.csv', usecols=['url', 'status'])
assert set(raw_h.status.unique()) == {'legitimate', 'phishing'}
raw_h = raw_h.rename(columns={'url': 'URL'})
raw_h['y'] = raw_h.status.map({'legitimate': 0, 'phishing': 1})
h, h_audit = clean(raw_h, 'Hannousse')
h['fold'] = folds(h)
h['partition'] = np.where(h.fold <= 2, 'sealed_evaluation', 'adaptation')
all_h_domains = set(h.group)
assert not set(h[h.partition == 'sealed_evaluation'].group) & set(h[h.partition == 'adaptation'].group)
h[['URL', 'normalized', 'group', 'y', 'partition']].to_csv(A / 'new_source_partition_manifest.csv', index=False)
h[h.partition == 'sealed_evaluation'].to_pickle(A / 'sealed_hannousse_eval.pkl')
h[h.partition == 'adaptation'].to_pickle(A / 'hannousse_adaptation.pkl')

dump(A/'raw_reconstruction_audit.json',raw_audit)
phi = phi_legacy[['URL','y']]
w = wang_legacy
w = w[w.partition == 'adaptation'][['URL', 'y']]
sources, audits = [], {'Hannousse': h_audit}
for name, raw in [('PhiUSIIL', phi), ('Wangchuk', w)]:
    f, audits[name] = clean(raw, name)
    overlap = f.group.isin(all_h_domains)
    audits[name]['new_source_domains_excluded_rows'] = int(overlap.sum())
    sources.append(f[~overlap])
dev = pd.concat(sources, ignore_index=True)
conflicts = dev.groupby('normalized').y.nunique()
cross_keys = set(conflicts[conflicts > 1].index)
dev = dev[~dev.normalized.isin(cross_keys)].drop_duplicates('normalized').reset_index(drop=True)
dev['fold'] = folds(dev)
dev['partition'] = np.where(dev.fold <= 2, 'train', np.where(dev.fold == 3, 'validation', 'test'))
assert not set(dev.group) & all_h_domains
for x, y in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
    assert not set(dev[dev.partition == x].group) & set(dev[dev.partition == y].group)
dev[['URL', 'normalized', 'group', 'source', 'y', 'partition']].to_csv(A / 'development_partition_manifest.csv', index=False)
print('Extracting normalized development features for', len(dev), 'URLs', flush=True)
matrix = numeric_frame(dev.URL, version=protocol.get('feature_version', 'normalized_url_v2'))
for c in matrix:
    dev[c] = matrix[c].to_numpy()
dev.to_pickle(A / 'development.pkl')
dump(A / 'feature_names.json', list(matrix.columns))

train = dev[dev.partition == 'train'].sample(frac=1, random_state=protocol['sampling_seed'])
train = train.groupby(['source', 'y', 'group'], sort=False).head(12)
train = train.groupby(['source', 'y'], sort=False).head(30000).reset_index(drop=True)
train.to_pickle(A / 'training.pkl')
train[['normalized', 'group', 'source', 'y']].to_csv(A / 'training_manifest.csv', index=False)
summary = {'source_audits': audits, 'cross_source_conflicting_keys': len(cross_keys),
           'new_source_domains_removed_from_all_development': True, 'test_scores_inspected': False,
           'development': {}, 'new_source': {}, 'sampled_train': {}}
for part, f in dev.groupby('partition'):
    summary['development'][part] = {name: {'n': len(g), 'normal': int(g.y.eq(0).sum()),
                                         'phishing': int(g.y.sum()), 'groups': int(g.group.nunique())}
                                    for name, g in f.groupby('source')}
for part, f in h.groupby('partition'):
    summary['new_source'][part] = {'n': len(f), 'normal': int(f.y.eq(0).sum()),
                                  'phishing': int(f.y.sum()), 'groups': int(f.group.nunique())}
for name, f in train.groupby('source'):
    summary['sampled_train'][name] = {'n': len(f), 'normal': int(f.y.eq(0).sum()), 'phishing': int(f.y.sum())}
dump(A / 'data_quality_and_partitions.json', summary)
manifest['status'] = 'prepared_no_test_scores'
manifest['artifact_sha256'] = {str(p.relative_to(RUN)): sha(p) for p in A.iterdir() if p.is_file()}
dump(RUN / 'manifest.json', manifest)
print(json.dumps(summary, indent=2), flush=True)
