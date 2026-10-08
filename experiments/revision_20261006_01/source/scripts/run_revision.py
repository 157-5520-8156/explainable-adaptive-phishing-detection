"""Run the revised protocol in a new, timestamped and hashed experiment archive."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import experiment as E
from features import canonical_url,domain_group,features,parse_url

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')

class Tee:
    def __init__(self,*streams):self.streams=streams
    def write(self,text):
        for s in self.streams:s.write(text);s.flush()
    def flush(self):
        for s in self.streams:s.flush()

def external_frame(phi,cols,out,protocol):
    raw=pd.read_csv(ROOT/'data/raw/wangchuk_dataset2.csv')
    assert list(raw.columns)==['URL','Label'] and set(raw.Label.unique())=={0,1}
    audit={'raw_rows':len(raw),'raw_class_counts':{str(k):int(v) for k,v in raw.Label.value_counts().items()},
           'schema':'URL,Label; 0 legitimate, 1 phishing','raw_sha256':digest(ROOT/'data/raw/wangchuk_dataset2.csv')}
    raw['canonical']=raw.URL.map(canonical_url);raw['group']=raw.URL.map(domain_group)
    bad=raw.URL.isna()|raw.canonical.eq('')|raw.group.eq('')|raw.URL.str.contains(r'[\s<>\"]',regex=True,na=True)
    audit['quality_excluded_by_class']={str(c):int((bad&(raw.Label==c)).sum()) for c in [0,1]}
    f=raw[~bad].copy();conflicts=f.groupby('canonical').Label.nunique();keys=set(conflicts[conflicts>1].index)
    audit['conflicting_keys_removed']=len(keys);f=f[~f.canonical.isin(keys)]
    before=len(f);f=f.drop_duplicates('canonical');audit['duplicate_rows_removed']=before-len(f)
    overlap=f.group.isin(set(phi.group));audit['source_domain_overlap_excluded_by_class']={str(c):int((overlap&(f.Label==c)).sum()) for c in [0,1]}
    f=f[~overlap].reset_index(drop=True);f['y']=f.Label.astype(int)
    matrix=pd.DataFrame([features(u) for u in f.URL]);f=pd.concat([f[['URL','canonical','group','y']],matrix],axis=1)
    assert np.isfinite(f[cols].to_numpy()).all()
    splitter=GroupShuffleSplit(n_splits=1,test_size=protocol['external_holdout_group_fraction'],random_state=protocol['external_partition_seed'])
    adaptation_idx,holdout_idx=next(splitter.split(f,groups=f.group))
    f['partition']='adaptation';f.loc[holdout_idx,'partition']='external_holdout'
    assert not set(f.loc[adaptation_idx,'group'])&set(f.loc[holdout_idx,'group'])
    assert not set(f.group)&set(phi.group)
    audit['partitions']={}
    for part,g in f.groupby('partition'):
        audit['partitions'][part]={'n':len(g),'groups':int(g.group.nunique()),'phishing':int(g.y.sum()),'legitimate':int((g.y==0).sum()),
                                  'legitimate_groups':int(g[g.y==0].group.nunique()),'phishing_groups':int(g[g.y==1].group.nunique()),
                                  'legitimate_nonempty_path_fraction':float((g[g.y==0].path_length>0).mean()),'phishing_nonempty_path_fraction':float((g[g.y==1].path_length>0).mean())}
    f[['canonical','group','y','partition']].to_csv(out/'external_partition_manifest.csv',index=False)
    f.to_pickle(out/'external_features.pkl');dump(out/'external_data_audit.json',audit)
    print('External audit',json.dumps(audit),flush=True)
    return f

def external_evaluation(ext,cols,out):
    hold=ext[ext.partition=='external_holdout'];rows=[];preds=[]
    main=pd.read_csv(out/'static_metrics.csv',float_precision='round_trip');ab=pd.read_csv(out/'exploratory_ablation.csv',float_precision='round_trip')
    host=['host_length','host_digit_ratio','host_hyphens','subdomain_count','suffix_length','host_is_ip','has_punycode']
    frozen=[]
    for seed in E.CONFIG['model_seeds']:
        for variant,selected,file in [('full_30_features',cols,f'rf_seed_{seed}.joblib'),('host_only_7_features',host,f'host_only_seed_{seed}.joblib')]:
            threshold=float(main[(main.model=='Random Forest')&(main.seed==seed)].threshold.iloc[0]) if variant=='full_30_features' else float(ab[(ab.variant=='host_only')&(ab.seed==seed)].threshold.iloc[0])
            frozen.append({'variant':variant,'seed':seed,'model':file,'model_sha256':digest(out/file),'threshold':threshold,'features':selected})
    dump(out/'frozen_external_models.json',{'frozen_at':now(),'no_external_labels_used_for_model_or_threshold_selection':True,'models':frozen})
    for spec in frozen:
        model=joblib.load(out/spec['model']);prob=model.predict_proba(hold[spec['features']])[:,1]
        row={'variant':spec['variant'],'seed':spec['seed'],'threshold':spec['threshold'],**E.metric_row(hold.y.to_numpy(),prob,spec['threshold'])}
        pp=hold[['canonical','group','y']].copy();pp['probability']=prob;pp['threshold']=spec['threshold'];pp['variant']=spec['variant'];pp['seed']=spec['seed']
        pp['correct']=(pp.probability>=pp.threshold)==pp.y
        row['macro_domain_legitimate_recall']=float(pp[pp.y==0].groupby('group').correct.mean().mean())
        row['macro_domain_phishing_recall']=float(pp[pp.y==1].groupby('group').correct.mean().mean())
        rows.append(row);preds.append(pp.drop(columns='correct'))
        print('External',spec['variant'],spec['seed'],'F1',row['f1'],'FPR',row['false_positive_rate'],flush=True)
    pd.DataFrame(rows).to_csv(out/'external_metrics.csv',index=False)
    pd.concat(preds,ignore_index=True).to_csv(out/'external_predictions.csv',index=False)
    primary=preds[0];groups=list(primary.groupby('group',sort=False).indices.values());rng=np.random.default_rng(61006)
    y=primary.y.to_numpy();prob=primary.probability.to_numpy();threshold=float(primary.threshold.iloc[0]);bs=[]
    for _ in range(200):
        idx=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))]);m=E.metric_row(y[idx],prob[idx],threshold)
        bs.append([m['f1'],m['average_precision'],m['recall'],m['false_positive_rate']])
    b=np.array(bs);dump(out/'external_uncertainty.json',{k:{'lower':float(np.quantile(b[:,i],.025)),'upper':float(np.quantile(b[:,i],.975))} for i,k in enumerate(['f1','average_precision','recall','false_positive_rate'])})

def make_source_replay(phi,ext,seed,phase_a,total,warm_n,scenario):
    dev=phi[phi.partition=='train'].sample(frac=1,random_state=seed).drop_duplicates('group')
    warm=[];a=[];b=[]
    target=ext[ext.partition=='adaptation']
    for label in [0,1]:
        draw=dev[dev.y==label].sample(n=(warm_n+phase_a)//2,random_state=seed+label)
        warm.append(draw.iloc[:warm_n//2]);a.append(draw.iloc[warm_n//2:])
        b.append(target[target.y==label].sample(n=(total-phase_a)//2,random_state=seed+label+10))
    warm=pd.concat(warm).sample(frac=1,random_state=seed).assign(source='PhiUSIIL',phase='warmup')
    a=pd.concat(a).sample(frac=1,random_state=seed+1).assign(source='PhiUSIIL',phase='A')
    b=pd.concat(b).sample(frac=1,random_state=seed+2).assign(source='Wangchuk',phase='B')
    stream=pd.concat([a,b],ignore_index=True)
    if scenario=='stationary_mixture':
        pool=pd.concat([warm,stream],ignore_index=True)
        warm=pd.concat([pool[pool.y==label].sample(n=warm_n//2,random_state=seed+label+30) for label in [0,1]])
        stream=pool[~pool.canonical.isin(set(warm.canonical))].sample(frac=1,random_state=seed+40).reset_index(drop=True)
        stream['phase']=np.where(np.arange(len(stream))<phase_a,'A','B')
    assert len(stream)==total and stream.canonical.is_unique and not set(stream.canonical)&set(warm.canonical)
    assert not set(stream.group)&set(ext.loc[ext.partition=='external_holdout','group'])
    meta={'scenario':scenario,'seed':seed,'warmup':len(warm),'stream':len(stream),'boundary_index':phase_a if scenario=='source_switch' else None,
          'warmup_groups':int(warm.group.nunique()),'stream_groups':int(stream.group.nunique()),'warmup_stream_shared_groups':len(set(warm.group)&set(stream.group)),
          'phishing_count':int(stream.y.sum()),'phase_A_rows':phase_a,'phase_B_rows':total-phase_a,
          'source_counts':{str(k):int(v) for k,v in stream.source.value_counts().items()},'external_holdout_domain_overlap':0,
          'interpretation':'Controlled replay of unchanged archived real URL records; order is experimental, not verified chronology; repeated target domains are retained and disclosed.'}
    return warm.reset_index(drop=True),stream,meta

def replay_experiments(phi,ext,cols,out,protocol):
    rows=[];preds=[];windows=[];events=[];arrival=[];scenarios=[]
    for scenario in protocol['stream_scenarios']:
        for seed,phase_a in zip(protocol['stream_seeds'],protocol['phase_A_sizes']):
            warm,stream,meta=make_source_replay(phi,ext,seed,phase_a,protocol['stream_total'],protocol['warmup_size'],scenario)
            scenarios.append(meta)
            for name,f in [('warmup',warm),('stream',stream)]:
                f[['canonical','group','y','source','phase']].to_csv(out/f'{scenario}_{seed}_{name}_manifest.csv',index=False)
            for delay in protocol['label_delay_batches']:
                for policy in protocol['policies']:
                    log=[];r,p,w,e=E.simulate(warm,stream,cols,seed,policy,delay,audit_log=log)
                    r['scenario']=scenario;p['scenario']=scenario
                    for entry in w+e+log:entry['scenario']=scenario
                    rows.append(r);preds.append(p);windows.extend(w);events.extend(e);arrival.extend(log)
                    print('Replay',scenario,seed,delay,policy,'F1',round(r['f1'],4),'phaseB',round(r['phase_B_f1'],4),'fits',r['updates'],'cutoffs',r['threshold_updates'],flush=True)
    pd.DataFrame(rows).to_csv(out/'replay_metrics.csv',index=False)
    pd.concat(preds,ignore_index=True).to_csv(out/'replay_predictions.csv',index=False)
    pd.DataFrame(windows).to_csv(out/'replay_windows.csv',index=False)
    pd.DataFrame(events).to_csv(out/'replay_update_events.csv',index=False)
    pd.DataFrame(arrival).to_csv(out/'label_arrival_ledger.csv',index=False)
    dump(out/'replay_scenarios.json',scenarios)

def split_sensitivity(phi,cols,out,protocol):
    original_out=E.OUT;original_seed=E.CONFIG['split_seed'];rows=[]
    try:
        for seed in protocol['source_split_sensitivity_seeds']:
            sub=out/f'split_{seed}';sub.mkdir();E.OUT=sub;E.CONFIG['split_seed']=seed
            shutil.copy2(original_out/'data_audit.json',sub/'data_audit.json')
            f,_=E.group_split(phi);tr=f[f.partition=='train'];va=f[f.partition=='validation'];te=f[f.partition=='test']
            model=RandomForestClassifier(**E.CONFIG['random_forest'],random_state=17);model.fit(tr[cols],tr.y)
            cutoff=E.val_threshold(va.y,model.predict_proba(va[cols])[:,1]);prob=model.predict_proba(te[cols])[:,1]
            row={'split_seed':seed,'model_seed':17,'threshold':cutoff,**E.metric_row(te.y.to_numpy(),prob,cutoff)};rows.append(row)
            pp=te[['canonical','group','y']].copy();pp['probability']=prob;pp['threshold']=cutoff;pp.to_csv(sub/'predictions.csv',index=False)
            print('Split sensitivity',seed,row['f1'],flush=True)
    finally:E.OUT=original_out;E.CONFIG['split_seed']=original_seed
    pd.DataFrame(rows).to_csv(out/'split_sensitivity.csv',index=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    run=ROOT/'experiments'/args.run_id
    if run.exists():raise FileExistsError('Choose a fresh run ID; existing evidence is never overwritten')
    run.mkdir(parents=True);out=run/'artifacts';out.mkdir();E.OUT=out
    for name in ['src','configs','tests']:
        shutil.copytree(ROOT/name,run/'source'/name,ignore=shutil.ignore_patterns('__pycache__'))
    (run/'source/scripts').mkdir();shutil.copy2(__file__,run/'source/scripts/run_revision.py');shutil.copy2(ROOT/'requirements.txt',run/'source/requirements.txt')
    protocol=json.loads((run/'source/configs/revision_protocol.json').read_text())
    manifest={'status':'running','started_at':now(),'command':f'.venv/bin/python scripts/run_revision.py --run-id {args.run_id}',
              'base_git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'source_snapshot_sha256':{str(p.relative_to(run)):digest(p) for p in (run/'source').rglob('*') if p.is_file()},
              'raw_data_sha256':{name:digest(ROOT/'data/raw'/name) for name in ['PhiUSIIL_Phishing_URL_Dataset.csv','wangchuk_dataset2.csv']},
              'environment':{'python':platform.python_version(),'platform':platform.platform(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scikit-learn','scipy','shap','river','tldextract','matplotlib']}}}
    dump(run/'manifest.json',manifest)
    with (run/'console.log').open('w') as log:
        sys.stdout=Tee(sys.__stdout__,log);sys.stderr=Tee(sys.__stderr__,log)
        try:
            dump(out/'environment.json',{**manifest['environment'],'config_sha256':digest(ROOT/'configs/experiment.json'),'revision_protocol_sha256':digest(ROOT/'configs/revision_protocol.json')})
            phi=E.prepare();phi,cols=E.group_split(phi)
            # Source-only fitting finishes before any external score is computed.
            E.static_experiment(phi,cols);E.ablation(phi,cols);E.explain(phi,cols)
            ext=external_frame(phi,cols,out,protocol);external_evaluation(ext,cols,out)
            split_sensitivity(phi,cols,out,protocol);replay_experiments(phi,ext,cols,out,protocol)
            manifest['status']='completed';manifest['finished_at']=now()
        except Exception:
            manifest['status']='failed';manifest['finished_at']=now();manifest['traceback']=traceback.format_exc();traceback.print_exc()
            raise
        finally:
            manifest['artifact_sha256']={str(p.relative_to(run)):digest(p) for p in out.rglob('*') if p.is_file()}
            dump(run/'manifest.json',manifest)
    print('Completed audited run:',run)

if __name__=='__main__':main()
