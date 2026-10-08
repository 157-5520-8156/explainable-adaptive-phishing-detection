"""Freeze development-only selections, then score untouched CompPhish domains."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,shutil,sys,time,warnings
import joblib,numpy as np,pandas as pd
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import file_sha256
from url_model_v2 import calibrate_threshold,training_weights
from evaluation import metrics

def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def fit(family,seed,frame,names,protocol):
 if family=='numeric_logistic':estimator=make_pipeline(StandardScaler(),LogisticRegression(**protocol['numeric_logistic'],random_state=seed))
 elif family=='random_forest':estimator=RandomForestClassifier(**protocol['random_forest'],random_state=seed)
 else:estimator=HistGradientBoostingClassifier(**protocol['hist_gradient'],max_leaf_nodes=int(family.rsplit('_',1)[1]),random_state=seed)
 weights=training_weights(frame)
 with warnings.catch_warnings():
  warnings.simplefilter('error',ConvergenceWarning)
  if family=='numeric_logistic':estimator.fit(frame[names],frame.y,logisticregression__sample_weight=weights)
  else:estimator.fit(frame[names],frame.y,sample_weight=weights)
 if family=='random_forest':estimator.set_params(n_jobs=1)
 return estimator

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
 run=ROOT/'experiments'/args.run_id;A=run/'artifacts';manifest=json.loads((run/'manifest.json').read_text())
 if manifest['status']!='prepared_no_model_scores':raise RuntimeError('Require a fresh prepared unscored archive')
 if (A/'selection.json').exists():raise RuntimeError('Selection archive exists; never overwrite inspected evidence')
 protocol=json.loads((run/'source/configs/independent_protocol.json').read_text())
 for name,digest in manifest['source_sha256'].items():
  if file_sha256(run/'source'/name)!=digest:raise RuntimeError('Frozen source snapshot changed')
 # Importing current extraction modules is not needed: fitting uses frozen matrices.
 source=pd.read_pickle(A/'source_features.pkl');target=pd.read_pickle(A/'target_features.pkl')
 st=source[source.partition.eq('source_train')].copy();sc=source[source.partition.eq('source_calibration')].copy()
 tt=target[target.partition.eq('target_train')].copy();tc=target[target.partition.eq('target_calibration')].copy()
 del source,target # Test rows are read again only after the explicit selection freeze.
 names_by_branch=json.loads((A/'feature_names.json').read_text());modeldir=A/'models';modeldir.mkdir()
 snapshot=run/'source/scripts/run_independent.py';shutil.copy2(__file__,snapshot)
 manifest['training_runner_sha256']=file_sha256(snapshot);manifest['status']='fitting_development_only';dump(run/'manifest.json',manifest)
 validation=[];model_specs=[];fits=[]
 for regime in protocol['fitting_regimes']:
  train=st if regime=='source_only' else pd.concat([st,tt],ignore_index=True)
  train=train.sample(frac=1,random_state=71007).groupby(['source','y','group'],sort=False).head(12).reset_index(drop=True)
  cal=sc if regime=='source_only' else pd.concat([sc,tc],ignore_index=True)
  cal=cal.reset_index(drop=True)
  if set(train.group)&set(cal.group):raise RuntimeError('Fitting/calibration group overlap')
  train[['URL','group','y','source']].to_csv(A/f'{regime}_training_manifest.csv',index=False)
  cal[['URL','group','y','source']].to_csv(A/f'{regime}_calibration_manifest.csv',index=False)
  for branch,names in names_by_branch.items():
   for family in protocol['families']:
    for seed in protocol['seeds']:
     started=time.perf_counter();model=fit(family,seed,train,names,protocol)
     p=model.predict_proba(cal[names])[:,1]
     basename=f'{regime}_{branch}_{family}_{seed}';file=modeldir/(basename+'.joblib');joblib.dump(model,file,compress=3)
     spec={'regime':regime,'branch':branch,'family':family,'seed':seed,'features':names,'training_n':len(train),
           'model_path':str(file.relative_to(run)),'sha256':file_sha256(file),'fit_seconds':time.perf_counter()-started,'cutoffs':{}}
     np.savez_compressed(A/(basename+'_calibration_scores.npz'),scores=p)
     for alpha in protocol['operating_points']:
      cutoff=calibrate_threshold(cal.y,p,cal.source,alpha)['threshold'];spec['cutoffs'][str(alpha)]=cutoff
      for src,g in cal.groupby('source'):
       validation.append({'regime':regime,'branch':branch,'family':family,'seed':seed,'budget':alpha,'threshold':cutoff,'source':src,
                          **metrics(g.y,p[g.index],cutoff,g.group)})
     model_specs.append(spec)
     pd.DataFrame(validation).to_csv(A/'calibration_metrics.csv',index=False)
     print('CAL',regime,branch,family,seed,'R',round(np.mean([x['recall'] for x in validation if x['regime']==regime and x['branch']==branch and x['family']==family and x['seed']==seed and x['budget']==protocol['primary_budget']]),4),flush=True)
 frame=pd.DataFrame(validation);primary=frame[frame.budget.eq(protocol['primary_budget'])];selected=[]
 for (regime,branch),g in primary.groupby(['regime','branch']):
  rank=g.groupby('family')[['recall','average_precision']].mean().reset_index();rank['order']=rank.family.map({n:i for i,n in enumerate(protocol['families'])})
  rank=rank.sort_values(['recall','average_precision','order'],ascending=[False,False,True])
  selected.append({'regime':regime,'branch':branch,'family':rank.family.iloc[0],'ranking':rank.to_dict(orient='records')})
 decision={'frozen_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'target_test_scored':False,
           'selection_data':'specified source/target development calibration roles only','selected':selected,'models':model_specs,
           'protocol_sha256':file_sha256(run/'source/configs/independent_protocol.json')}
 dump(A/'selection.json',decision);manifest['status']='all_selections_frozen_before_target_test';manifest['selection_sha256']=file_sha256(A/'selection.json');dump(run/'manifest.json',manifest)
 # Only here does any estimator see the sealed target feature rows.
 target=pd.read_pickle(A/'target_features.pkl');test=target[target.partition.eq('sealed_test')].reset_index(drop=True)
 test[['URL','group','y','source','content_hash']].to_csv(A/'test_identity_manifest.csv',index=False)
 rows=[]
 for spec in model_specs:
  file=run/spec['model_path']
  if file_sha256(file)!=spec['sha256']:raise RuntimeError('Changed fitted model')
  model=joblib.load(file);p=model.predict_proba(test[spec['features']])[:,1]
  basename=Path(spec['model_path']).stem
  for alpha in protocol['operating_points']:
   cutoff=spec['cutoffs'][str(alpha)]
   prediction=(p>=cutoff).astype(int)
   ledger=test[['URL','group','y','content_hash']].copy();ledger['score']=p;ledger['threshold']=cutoff;ledger['prediction']=prediction
   ledger.to_csv(A/(basename+f'_budget{alpha}_test_predictions.csv'),index=False)
   rows.append({k:spec[k] for k in ['regime','branch','family','seed']}|{'budget':alpha,'threshold':cutoff}|metrics(test.y,p,cutoff,test.group))
 pd.DataFrame(rows).to_csv(A/'all_test_metrics.csv',index=False)
 allmetrics=pd.DataFrame(rows);main=[]
 for selected_spec in selected:
  g=allmetrics[(allmetrics.regime==selected_spec['regime'])&(allmetrics.branch==selected_spec['branch'])&(allmetrics.family==selected_spec['family'])&(allmetrics.budget==protocol['primary_budget'])]
  main.append({**{k:selected_spec[k] for k in ['regime','branch','family']},'test_n':len(test),
               'mean':g[['fpr','recall','precision','f1','average_precision','roc_auc','domain_macro_fpr','domain_macro_recall']].mean().to_dict(),
               'all_seeds_meet_prespecified_targets':bool((g.fpr.le(protocol['acceptance_targets']['fpr'])&g.recall.ge(protocol['acceptance_targets']['recall'])).all())})
 dump(A/'primary_results.json',main)
 dump(A/'constant_baselines.json',{name:metrics(test.y,np.repeat(score,len(test)),.5,test.group) for name,score in [('always_normal',0.),('always_phishing',1.)]})
 manifest['status']='target_test_scored_after_selection_freeze';manifest['test_scored_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
 manifest['artifact_sha256']={str(p.relative_to(run)):file_sha256(p) for p in A.rglob('*') if p.is_file()};dump(run/'manifest.json',manifest)
 print(json.dumps(main,indent=2),flush=True)

if __name__=='__main__':main()
