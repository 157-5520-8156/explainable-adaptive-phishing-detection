"""Independent replay-ledger and frozen-test checks from saved predictions."""
from pathlib import Path
import hashlib,json,sys
import numpy as np,pandas as pd
from sklearn.metrics import confusion_matrix
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'experiments/page_20261007_01';A=RUN/'artifacts'
roles={n:pd.read_pickle(A/f'{n}.pkl') for n in ['initial_train','calibration','replay_pool','sealed_test']}
checks=[]
for i,(name,f) in enumerate(roles.items()):
    for other,g in list(roles.items())[i+1:]:
        assert not set(f.group)&set(g.group);checks.append(f'{name}/{other} domains disjoint')
summary_rows=pd.read_csv(A/'final_test_metrics.csv');verified=0
for directory in (A/'replays').iterdir():
    summary=json.loads((directory/'summary.json').read_text())
    predictions=pd.read_csv(directory/'predictions.csv')
    arrivals=json.loads((directory/'label_arrivals.json').read_text())
    events=json.loads((directory/'events.json').read_text())
    assert len(predictions)==len(roles['replay_pool'])
    assert predictions.row.nunique()==len(predictions)
    assert np.array_equal(predictions.prediction,(predictions.score>=predictions.threshold).astype(int))
    assert (predictions.label_available_batch==predictions.batch+summary['delay']).all()
    for arrival in arrivals:
        assert arrival['arrival_batch']==arrival['scheduled_batch']==arrival['prediction_batch']+summary['delay']
    for event in events:
        assert event['max_label_prediction_batch']+summary['delay']<=event['batch']
        assert not set(event['training_domains']) & set(event['calibration_domains'])
        assert not (set(event['training_domains'])|set(event['calibration_domains'])) & set(roles['sealed_test'].group)
    for filename,row in [('predictions.csv',summary),('test_predictions.csv',summary_rows[(summary_rows.order==summary['order'])&(summary_rows.policy==summary['policy'])&(summary_rows.delay==summary['delay'])&(summary_rows.seed==summary['seed'])].iloc[0])]:
        f=pd.read_csv(directory/filename);counts=confusion_matrix(f.y,f.prediction,labels=[0,1]).ravel()
        for key,value in zip(['tn','fp','fn','tp'],counts): assert int(row[key])==int(value)
        assert abs(float(row['fpr'])-counts[1]/sum(counts[:2]))<1e-12
        assert abs(float(row['recall'])-counts[3]/sum(counts[2:]))<1e-12
        if filename=='test_predictions.csv':
            assert len(f)==6849;assert np.array_equal(f.y,roles['sealed_test'].y)
        verified+=1
manifest=json.loads((RUN/'manifest.json').read_text())
for name,digest in manifest['artifact_sha256'].items(): assert hashlib.sha256((RUN/name).read_bytes()).hexdigest()==digest
result={'status':'PASS','replay_realizations':48,'verified_prediction_files':verified,
        'domain_isolation_checks':checks,'label_arrival_and_update_timing_verified':True,
        'confusion_matrices_recomputed':True,'frozen_artifact_hashes_verified':True,
        'limitation':'This verifies implementation and calculations, not dataset labels or universal generalization.'}
(RUN/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
