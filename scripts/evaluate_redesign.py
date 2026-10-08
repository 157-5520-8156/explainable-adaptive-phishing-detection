"""Score frozen URL and archived-page models; do not select using test outcomes."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import sys
import joblib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from evaluation import metrics

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,o): Path(p).write_text(json.dumps(o,indent=2,allow_nan=False)+'\n')

def grouped_bootstrap(frame, seed=20261007, replicates=1000):
    # Resample whole registered-domain clusters, preserving within-domain records.
    g=frame.assign(tp=((frame.y==1)&(frame.prediction==1)).astype(int),
                   fp=((frame.y==0)&(frame.prediction==1)).astype(int),
                   positive=(frame.y==1).astype(int),normal=(frame.y==0).astype(int))
    sums=g.groupby('group')[['tp','fp','positive','normal']].sum().to_numpy()
    rng=np.random.default_rng(seed); values=[]
    for _ in range(replicates):
        total=sums[rng.integers(0,len(sums),len(sums))].sum(axis=0)
        tp,fp,pos,norm=total
        values.append([fp/norm,tp/pos,2*tp/(pos+tp+fp)])
    return {name:list(map(float,np.quantile(np.array(values)[:,i],[.025,.975]))) for i,name in enumerate(['fpr','recall','f1'])}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--page-run-id',default='page_20261007_01')
    parser.add_argument('--url-run-id',default='redesign_20261007_03')
    args=parser.parse_args()
    page=ROOT/'experiments'/args.page_run_id;A=page/'artifacts'
    manifest=json.loads((page/'manifest.json').read_text())
    assert manifest['status']=='all_replays_frozen_before_test_scoring'
    assert not (A/'final_test_metrics.csv').exists(), 'Refuse overwrite of inspected test evidence'
    selection=json.loads((A/'selection.json').read_text());family=selection['family']
    test=pd.read_pickle(A/'sealed_test.pkl')
    rows,intervals=[],[]
    for meta in sorted((A/'replays').glob('*/summary.json')):
        replay=json.loads(meta.read_text());state=joblib.load(meta.parent/'final.joblib')
        bundle,threshold=state['bundle'],state['threshold']
        # Validate the public prediction path against cached feature matrix.
        p=bundle.predict_proba(test)[:,1]
        pred=(p>=threshold).astype(int)
        frame=pd.DataFrame({'group':test.group,'y':test.y,'score':p,'prediction':pred})
        frame.to_csv(meta.parent/'test_predictions.csv',index=False)
        row={k:replay[k] for k in ['order','policy','delay','seed','updates']}
        row.update(threshold=threshold,**metrics(test.y,p,threshold,test.group));rows.append(row)
        if replay['seed']==42:
            intervals.append({**{k:row[k] for k in ['order','policy','delay','seed']},'cluster_bootstrap_95':grouped_bootstrap(frame)})
        print('SEALED PAGE TEST',row['order'],row['policy'],row['delay'],row['seed'],'FPR',round(row['fpr'],4),'R',round(row['recall'],4),flush=True)
    pd.DataFrame(rows).to_csv(A/'final_test_metrics.csv',index=False);dump(A/'test_cluster_intervals.json',intervals)
    # Fixed score baselines use exactly the same test records.
    dump(A/'constant_test_baselines.json',{n:metrics(test.y,np.repeat(score,len(test)),.5,test.group) for n,score in [('always_normal',0.),('always_phishing',1.)]})
    manifest['status']='test_scored_after_all_replays_frozen';manifest['test_scored_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    manifest['evaluation_runner_sha256']=sha(__file__)
    manifest['artifact_sha256']={str(p.relative_to(page)):sha(p) for p in A.rglob('*') if p.is_file()}
    dump(page/'manifest.json',manifest)
    url=ROOT/'experiments'/args.url_run_id;U=url/'artifacts'
    selection=json.loads((U/'validation_selection.json').read_text());protocol=json.loads((url/'source/configs/redesign_protocol.json').read_text())
    assert not (U/'test_metrics.csv').exists()
    dev=pd.read_pickle(U/'development.pkl');internal=dev[dev.partition.eq('test')]
    external=pd.read_pickle(U/'sealed_hannousse_eval.pkl')
    calibration=selection['calibrations'];rows=[]
    # All candidates retained for analysis; primary remains the frozen selected family.
    for spec in selection['models']:
        family,seed=spec['family'],spec['seed'];bundle=joblib.load(url/spec['path'])
        for label,f in [('internal',internal),('unseen_source',external)]:
            if family.startswith('source_only') and label=='internal': f=f[f.source.eq('PhiUSIIL')]
            p=bundle.predict_proba(f.URL)[:,1]
            np.savez_compressed(U/f'test_scores_{label}_{family}_{seed}.npz',scores=p)
            for alpha in protocol['operating_points']:
                cut=next(c['threshold'] for c in calibration if c['family']==family and c['seed']==seed and c['fpr_budget']==alpha)
                for source,g in f.reset_index(drop=True).groupby('source'):
                    row={'evaluation':label,'family':family,'seed':seed,'budget':alpha,'threshold':cut,'source':source,**metrics(g.y,p[g.index],cut,g.group)}
                    rows.append(row)
    pd.DataFrame(rows).to_csv(U/'test_metrics.csv',index=False)
    manifest=json.loads((url/'manifest.json').read_text());manifest['status']='test_scored_after_selection_frozen';manifest['test_scored_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    manifest['test_metrics_sha256']=sha(U/'test_metrics.csv');dump(url/'manifest.json',manifest)
