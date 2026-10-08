"""Preserve the first archive; repair threshold calibration without model selection."""
from pathlib import Path
import importlib.util,json,shutil,hashlib
import pandas as pd,joblib
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'experiments/page_20261007_01';NEW=ROOT/'experiments/page_20261007_02'
if NEW.exists():raise SystemExit('Refusing to overwrite corrected archive')
shutil.copytree(OLD,NEW)
spec=importlib.util.spec_from_file_location('page_runner',ROOT/'scripts/run_page_study.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.RUN=NEW;m.A=NEW/'artifacts';A=m.A
for name in ['scripts/run_page_study.py','scripts/correct_threshold_study.py']:
    dest=NEW/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
protocol=json.loads((NEW/'source/configs/page_protocol.json').read_text())
protocol['correction_after_test_inspection']='Threshold-only calibration now uses original calibration plus revealed recent replay domains, excluding every domain used by its retained initial estimator. No estimator/hyperparameter/cutoff selection based on test. Corrected threshold tests are post-inspection verification, not new blind evidence.'
(NEW/'source/configs/page_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
selection=json.loads((A/'selection.json').read_text());family=selection['family'];train=pd.read_pickle(A/'initial_train.pkl');cal=pd.read_pickle(A/'calibration.pkl');pool=pd.read_pickle(A/'replay_pool.pkl')
rows=[]
for order in m.P['replay']['orders']:
 for delay in m.P['replay']['delays']:
  for seed in m.P['seeds']:
   directory=A/'replays'/f'{order}_threshold_delay{delay}_seed{seed}'
   shutil.rmtree(directory) # Original remains fully recoverable in OLD.
   bundle=joblib.load(A/f'{family}_{seed}.joblib')
   cut=next(c['threshold'] for c in selection['calibrations'] if c['family']==family and c['seed']==seed and c['budget']==.05)
   result=m.replay(bundle,cut,train,cal,pool,seed,'threshold',delay,order);rows.append(result)
   print(order,delay,seed,result['fpr'],result['recall'],flush=True)
retained=pd.read_csv(A/'replay_metrics.csv');retained=retained[retained.policy.ne('threshold')]
pd.concat([retained,pd.DataFrame(rows)]).to_csv(A/'replay_metrics.csv',index=False)
# Reuse unaffected frozen predictions/checkpoints, score only corrected threshold runs.
from evaluation import metrics
from importlib import util
espec=util.spec_from_file_location('evaluation_runner',ROOT/'scripts/evaluate_redesign.py');e=util.module_from_spec(espec);espec.loader.exec_module(e)
test=pd.read_pickle(A/'sealed_test.pkl');tests=[];intervals=[]
for result in rows:
 directory=A/'replays'/f"{result['order']}_threshold_delay{result['delay']}_seed{result['seed']}"
 state=joblib.load(directory/'final.joblib');p=state['bundle'].predict_proba(test)[:,1];pred=(p>=state['threshold']).astype(int)
 f=pd.DataFrame({'group':test.group,'y':test.y,'score':p,'prediction':pred});f.to_csv(directory/'test_predictions.csv',index=False)
 tests.append({k:result[k] for k in ['order','policy','delay','seed','updates']}|{'threshold':state['threshold']}|metrics(test.y,p,state['threshold'],test.group))
 if result['seed']==42:intervals.append({k:result[k] for k in ['order','policy','delay','seed']}|{'cluster_bootstrap_95':e.grouped_bootstrap(f)})
prior=pd.read_csv(A/'final_test_metrics.csv');pd.concat([prior[prior.policy.ne('threshold')],pd.DataFrame(tests)]).to_csv(A/'final_test_metrics.csv',index=False)
ci=json.loads((A/'test_cluster_intervals.json').read_text());ci=[x for x in ci if x['policy']!='threshold'];(A/'test_cluster_intervals.json').write_text(json.dumps(ci+intervals,indent=2)+'\n')
manifest=json.loads((NEW/'manifest.json').read_text());manifest.update(status='corrected_threshold_policy_post_inspection', correction_basis=protocol['correction_after_test_inspection'], reused_from=str(OLD.relative_to(ROOT)), untouched_original_runs=36, rerun_threshold_runs=12)
manifest['source_sha256']={str(p.relative_to(NEW/'source')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (NEW/'source').rglob('*') if p.is_file()}
manifest['artifact_sha256']={str(p.relative_to(NEW)):hashlib.sha256(p.read_bytes()).hexdigest() for p in A.rglob('*') if p.is_file()}
(NEW/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
