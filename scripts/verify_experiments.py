"""Audit saved evidence independently of the training loop."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, confusion_matrix, average_precision_score

ROOT=Path(__file__).resolve().parents[1];R=ROOT/"results"
provenance=json.loads((ROOT/"data/raw/provenance.json").read_text())
assert hashlib.sha256((ROOT/"data/raw/PhiUSIIL_Phishing_URL_Dataset.csv").read_bytes()).hexdigest()==provenance['csv_sha256']
split=pd.read_csv(R/"split_manifest.csv")
sets={p:set(split.loc[split.partition==p,'group']) for p in ['train','validation','test']}
assert not sets['train']&sets['validation'] and not sets['train']&sets['test'] and not sets['validation']&sets['test']
assert split.canonical.is_unique
static=pd.read_csv(R/"static_predictions.csv",float_precision="round_trip");sm=pd.read_csv(R/"static_metrics.csv",float_precision="round_trip")
for _,r in sm.iterrows():
 p=static[(static.model==r.model)&(static.seed==r.seed)]
 assert set(p.canonical)==set(split.loc[split.partition=='test','canonical'])
 assert abs(f1_score(p.y,p.probability>=r.threshold)-r.f1)<1e-12
 assert abs(average_precision_score(p.y,p.probability)-r.average_precision)<1e-12
 assert list(confusion_matrix(p.y,p.probability>=r.threshold).ravel())==[r.tn,r.fp,r.fn,r.tp]
stream=pd.read_csv(R/"stream_predictions.csv",float_precision="round_trip");metrics=pd.read_csv(R/"stream_metrics.csv",float_precision="round_trip");events=pd.read_csv(R/"stream_update_events.csv",float_precision="round_trip")
for _,r in metrics.iterrows():
 p=stream[(stream.seed==r.seed)&(stream.policy==r.policy)&(stream.delay_batches==r.delay_batches)]
 assert p.group.is_unique and not set(p.group)&sets['test']
 assert abs(f1_score(p.y,p.probability>=.5)-r.f1)<1e-12
 assert abs(average_precision_score(p.y,p.probability)-r.average_precision)<1e-12
 e=events[(events.seed==r.seed)&(events.policy==r.policy)&(events.delay_batches==r.delay_batches)]
 assert len(e)==r.updates
 assert (e.revealed_source_batch+r.delay_batches<=e.after_prediction_batch).all()
 versions=p.groupby('batch').model_version.first()
 for b,v in versions.items():
  assert v==int((e.after_prediction_batch<b).sum())
for seed in metrics.seed.unique():
 base=stream[(stream.seed==seed)&(stream.policy=='fixed')&(stream.delay_batches==0)].sort_values('batch')
 for policy in ['periodic','drift']:
  for delay in [0,2]:
   p=stream[(stream.seed==seed)&(stream.policy==policy)&(stream.delay_batches==delay)].sort_values('batch')
   assert list(p.canonical)==list(base.canonical)
   assert np.array_equal(p.y.to_numpy(),base.y.to_numpy())
   assert np.allclose(p.loc[p.batch==0,'probability'],base.loc[base.batch==0,'probability'],atol=1e-12)
values=np.load(R/"shap_values.npz")
assert np.max(abs(values['base']+values['values'].sum(axis=1)-values['probability']))<1e-5
result={'passed':True,'checks':['raw data SHA256','canonical deduplication','domain-disjoint partitions','static metric reconstruction','same stream and initial model across strategies','label delay and model version causality','stream metric reconstruction','SHAP additivity'],
        'limitations':'Checks establish artifact consistency and the stated protocol, not dataset representativeness or deployment effectiveness.'}
(R/"verification.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
