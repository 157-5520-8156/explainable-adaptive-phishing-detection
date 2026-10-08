"""Compare substantive outputs to retained reference evidence, without reusing it."""
from pathlib import Path
import argparse,json,hashlib
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--reproduction-dir',type=Path,required=True);args=parser.parse_args();r=args.reproduction_dir
pairs=[('page_final_test_metrics.csv',ROOT/'experiments/page_20261007_02/artifacts/final_test_metrics.csv'),
       ('page_replay_metrics.csv',ROOT/'experiments/page_20261007_02/artifacts/replay_metrics.csv'),
       ('url_test_metrics.csv',ROOT/'experiments/redesign_20261007_03/artifacts/test_metrics.csv')]
results=[]
for new,old in pairs:
 left=pd.read_csv(r/new,float_precision='round_trip');right=pd.read_csv(old,float_precision='round_trip')
 keys=['order','policy','delay','seed'] if new.startswith('page') else ['evaluation','family','seed','budget','source']
 measures=['tn','fp','fn','tp','fpr','recall','precision','f1','average_precision','roc_auc','domain_macro_fpr','domain_macro_recall']
 a=left.sort_values(keys).reset_index(drop=True);b=right.sort_values(keys).reset_index(drop=True)
 assert a[keys].equals(b[keys])
 difference=float(np.max(np.abs(a[measures].to_numpy()-b[measures].to_numpy())))
 thresholded=['tn','fp','fn','tp','fpr','recall','precision','f1','domain_macro_fpr','domain_macro_recall']
 assert np.array_equal(a[['tn','fp','fn','tp']].to_numpy(),b[['tn','fp','fn','tp']].to_numpy()),new
 assert np.max(np.abs(a[thresholded].to_numpy()-b[thresholded].to_numpy()))<1e-12,new
 # Parallel forest reductions may perturb tied probabilities near machine epsilon,
 # changing AP/AUC tie ranking while all original decisions remain identical.
 assert difference<1e-5,(new,difference)
 results.append({'file':new,'records':len(a),'max_metric_difference':difference})
# Input and role partition comparisons happen only after the clean run completes.
for name in ['development_partition_manifest.csv','new_source_partition_manifest.csv','training_manifest.csv']:
 fresh=r/'workspace/experiments/url_run/artifacts'/name;old=ROOT/'experiments/redesign_20261007_03/artifacts'/name
 assert fresh.read_bytes()==old.read_bytes(),name
 results.append({'file':name,'byte_identical_partition':True})
score_checks=[]
for old in (ROOT/'experiments/redesign_20261007_03/artifacts').glob('test_scores_*.npz'):
 fresh=r/'workspace/experiments/url_run/artifacts'/old.name
 a=np.load(fresh)['scores'];b=np.load(old)['scores'];delta=float(np.max(np.abs(a-b)))
 assert delta<1e-12,(old.name,delta)
 score_checks.append({'file':old.name,'max_score_difference':delta})
decision_checks=[]
url_new=pd.read_csv(r/'url_test_metrics.csv',float_precision='round_trip')
url_old=pd.read_csv(ROOT/'experiments/redesign_20261007_03/artifacts/test_metrics.csv',float_precision='round_trip')
for _,row in url_new.drop_duplicates(['evaluation','family','seed','budget']).iterrows():
 old=url_old[(url_old.evaluation==row.evaluation)&(url_old.family==row.family)&(url_old.seed==row.seed)&(url_old.budget==row.budget)].iloc[0]
 name=f'test_scores_{row.evaluation}_{row.family}_{int(row.seed)}.npz'
 newp=np.load(r/'workspace/experiments/url_run/artifacts'/name)['scores'];oldp=np.load(ROOT/'experiments/redesign_20261007_03/artifacts'/name)['scores']
 changed=int(((newp>=row.threshold)!=(oldp>=old.threshold)).sum());assert changed==0
 decision_checks.append({'file':name,'budget':float(row.budget),'changed_decisions':changed})
page_vector_checks=0
for directory in (ROOT/'experiments/page_20261007_02/artifacts/replays').iterdir():
 for filename in ['predictions.csv','test_predictions.csv']:
  old=pd.read_csv(directory/filename,float_precision='round_trip')
  new=pd.read_csv(r/'workspace/experiments/page_run/artifacts/replays'/directory.name/filename,float_precision='round_trip')
  assert np.array_equal(old.prediction,new.prediction)
  page_vector_checks+=1
summary={'status':'PASS','reference_read_only_after_reproduction_completed':True,'measurements':results,'saved_score_comparisons':score_checks,'url_decision_comparisons':decision_checks,'identical_page_prediction_vectors':page_vector_checks,'thresholded_predictions_and_counts_identical':True,'ranking_metric_tolerance':1e-5,'ranking_tolerance_basis':'Observed machine-precision score variation in parallel forest aggregation changes tie ordering; score differences separately audited.','interpretation':'Deterministic reproduction on the same pinned environment and raw inputs; not independent evidence of generalization.'}
(r/'reference_comparison.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
