"""Verify run hashes, original predictions, manual PR arithmetic and label chronology."""
from pathlib import Path
import argparse,json,hashlib,sys
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import f1_score,confusion_matrix

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
run=ROOT/'experiments'/args.run_id;out=run/'artifacts';m=json.loads((run/'manifest.json').read_text())
assert m['status']=='completed'
for n,h in m['artifact_sha256'].items():assert hashlib.sha256((run/n).read_bytes()).hexdigest()==h,n
for n,h in m['source_snapshot_sha256'].items():assert hashlib.sha256((run/n).read_bytes()).hexdigest()==h,n
for n,h in m['raw_data_sha256'].items():assert hashlib.sha256((ROOT/'data/raw'/n).read_bytes()).hexdigest()==h,n

def manual_ap(y,s):
    order=np.argsort(-s,kind='stable');ys=y[order];scores=s[order]
    ends=np.r_[np.flatnonzero(np.diff(scores)!=0),len(scores)-1]
    tp=np.cumsum(ys)[ends];p=tp/(ends+1);r=tp/y.sum()
    return float(np.sum(np.diff(np.r_[0.,r])*p))

report={'hashes_verified':True,'metric_rows_verified':{},'max_manual_ap_difference':0.,'probability_reconstructions':0,'checks':[]}
for prefix,keycols in [('static',['model','seed']),('external',['variant','seed']),('replay',['scenario','seed','policy','delay_batches'])]:
    pred=pd.read_csv(out/f'{prefix}_predictions.csv',float_precision='round_trip')
    metrics=pd.read_csv(out/f'{prefix}_metrics.csv',float_precision='round_trip')
    bykey={key:g for key,g in pred.groupby(keycols,sort=False)}
    for _,row in metrics.iterrows():
        key=tuple(row[c] for c in keycols);g=bykey[key];y=g.y.to_numpy();p=g.probability.to_numpy();threshold=g.threshold.to_numpy()
        assert np.isfinite(p).all() and ((p>=-1e-12)&(p<=1+1e-12)).all()
        assert abs(f1_score(y,p>=threshold)-row.f1)<1e-12
        diff=abs(manual_ap(y,p)-row.average_precision);assert diff<1e-12
        report['max_manual_ap_difference']=max(report['max_manual_ap_difference'],diff)
        assert list(confusion_matrix(y,p>=threshold,labels=[0,1]).ravel())==[row.tn,row.fp,row.fn,row.tp]
    report['metric_rows_verified'][prefix]=len(metrics)

source=pd.read_csv(out/'split_manifest.csv');external=pd.read_csv(out/'external_partition_manifest.csv')
sg={p:set(g.group) for p,g in source.groupby('partition')};eg={p:set(g.group) for p,g in external.groupby('partition')}
assert not sg['train']&sg['test'] and not sg['train']&sg['validation'] and not sg['test']&sg['validation']
assert not set(source.group)&set(external.group) and not eg['adaptation']&eg['external_holdout']
arrivals=pd.read_csv(out/'label_arrival_ledger.csv')
assert (arrivals.arrival_batch==arrivals.source_batch+arrivals.delay_batches).all()
used=arrivals[arrivals.used_by_detector]
assert (used.current_version==used.prediction_version).all()
replay=pd.read_csv(out/'replay_predictions.csv',float_precision='round_trip');events=pd.read_csv(out/'replay_update_events.csv')
metrics=pd.read_csv(out/'replay_metrics.csv')
for key,g in replay.groupby(['scenario','seed','policy','delay_batches']):
    scenario,seed,policy,delay=key
    expected=pd.read_csv(out/f'{scenario}_{seed}_stream_manifest.csv')
    assert list(g.canonical)==list(expected.canonical) and np.array_equal(g.y,expected.y)
    assert not set(g.group)&eg['external_holdout']
    e=events[(events.scenario==scenario)&(events.seed==seed)&(events.policy==policy)&(events.delay_batches==delay)]
    for b,v in g.groupby('batch').model_version.first().items():assert v==int((e.after_prediction_batch<b).sum())
    assert (e.revealed_source_batch+delay<=e.after_prediction_batch).all()

# Recompute probabilities independently from stored model checkpoints and feature records.
phi=pd.read_pickle(ROOT/'data/processed/url_features.pkl');ext=pd.read_pickle(out/'external_features.pkl')
combined=pd.concat([phi,ext],ignore_index=True).drop_duplicates('canonical').set_index('canonical')
cols=json.loads((out/'data_audit.json').read_text())['feature_names']
source_test=source[source.partition=='test']
for _,row in pd.read_csv(out/'exploratory_ablation.csv',float_precision='round_trip').iterrows():
    model=joblib.load(out/f'{row.variant}_seed_{row.seed}.joblib')
    prob=model.predict_proba(combined.loc[source_test.canonical,list(model.feature_names_in_)])[:,1]
    y=source_test.y.to_numpy()
    assert abs(f1_score(y,prob>=row.threshold)-row.f1)<1e-12
    assert abs(manual_ap(y,prob)-row.average_precision)<1e-12
report['metric_rows_verified']['source_ablation']=9
for _,row in pd.read_csv(out/'split_sensitivity.csv',float_precision='round_trip').iterrows():
    pp=pd.read_csv(out/f'split_{int(row.split_seed)}'/'predictions.csv',float_precision='round_trip')
    assert abs(f1_score(pp.y,pp.probability>=pp.threshold)-row.f1)<1e-12
    assert abs(manual_ap(pp.y.to_numpy(),pp.probability.to_numpy())-row.average_precision)<1e-12
report['metric_rows_verified']['split_sensitivity']=2
for key,g in replay.groupby(['scenario','seed','policy','delay_batches']):
    scenario,seed,policy,delay=key
    for version,v in g.groupby('model_version'):
        sample=v.sample(n=min(5,len(v)),random_state=73)
        model=joblib.load(out/'replay_models'/f'{scenario}_{seed}_{policy}_{delay}'/f'version_{version}.joblib')
        prob=model.predict_proba(combined.loc[sample.canonical,cols])[:,1]
        assert np.allclose(prob,sample.probability.to_numpy(),atol=1e-12,rtol=0)
        report['probability_reconstructions']+=len(sample)
vals=np.load(out/'shap_values.npz');assert np.max(abs(vals['base']+vals['values'].sum(axis=1)-vals['probability']))<1e-5
report['checks']=['raw/source/artifact hashes','static/external/replay confusion counts and F1','independent AP with tied-score groups','domain-disjoint source and external holdout','identical replay records across policies','labels revealed only after original prediction','current-model-only ADWIN feedback','model versions follow recorded updates','sampled probability reconstruction from saved checkpoints','SHAP additivity']
report['limitations']='Verification checks execution and numerical consistency. Published ground-truth labels, real temporal chronology and deployment reliability are not independently established.'
(run/'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
