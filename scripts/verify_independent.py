"""Recompute frozen external counts from ledgers and verify all source boundaries."""
from pathlib import Path
import argparse,json,sys
import joblib,numpy as np,pandas as pd
from sklearn.metrics import confusion_matrix,average_precision_score,roc_auc_score
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import file_sha256,RAW_CATALOG
from features import domain_group
from url_model_v2 import normalize_url

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args();run=ROOT/'experiments'/args.run_id;A=run/'artifacts'
 manifest=json.loads((run/'manifest.json').read_text());selection=json.loads((A/'selection.json').read_text());protocol=json.loads((run/'source/configs/independent_protocol.json').read_text())
 if not manifest['test_scored_at']>selection['frozen_at']:raise AssertionError('Selection/scoring timestamp order')
 if manifest['selection_sha256']!=file_sha256(A/'selection.json'):raise AssertionError('Changed selection')
 for name,digest in manifest['artifact_sha256'].items():
  if file_sha256(run/name)!=digest:raise AssertionError('Artifact hash '+name)
 source=pd.read_pickle(A/'source_features.pkl');target=pd.read_pickle(A/'target_features.pkl');test=target[target.partition.eq('sealed_test')].reset_index(drop=True)
 raw_mapping=pd.read_excel(ROOT/'data/raw/archives/Mapping_File.xlsx')
 raw_lookup={int(row.serial_number):(str(row.url),int(row.label)) for row in raw_mapping.itertuples(index=False)}
 assert all(raw_lookup[int(row.serial)]==(row.URL,int(row.y)) for row in target.itertuples(index=False))
 assert file_sha256(ROOT/'data/raw/hannousse_dataset_B_05_2020.csv')==RAW_CATALOG['hannousse_dataset_B_05_2020.csv']['sha256']
 raw_source=pd.read_csv(ROOT/'data/raw/hannousse_dataset_B_05_2020.csv',usecols=['url','status'])
 source_lookup=dict(zip(raw_source.url,raw_source.status.map({'legitimate':0,'phishing':1})))
 assert all(source_lookup[row.URL]==int(row.y) for row in source.itertuples(index=False))
 valid_source=raw_source.url.map(normalize_url).ne('') & ~raw_source.url.str.strip().str.contains(r'[\s<>\"]',regex=True,na=True)
 complete_source_domains=set(raw_source.loc[valid_source,'url'].map(domain_group))
 assert not set(target.group)&complete_source_domains
 for item in manifest['creator_inputs']['source_catalog']['files']:
  assert file_sha256(ROOT/'data/raw/archives'/item['filename'])==item['sha256']
 assert file_sha256(ROOT/'data/raw/archives/CompPhish_All_HTML.zip')==manifest['creator_inputs']['target_zip_sha256']
 assert file_sha256(ROOT/'data/raw/archives/Mapping_File.xlsx')==manifest['creator_inputs']['mapping_sha256']
 groups={role:set(f.group) for role,f in pd.concat([source,target]).groupby('partition')}
 for role,left in groups.items():
  for other,right in groups.items():
   if role!=other:assert not left&right
 assert not set(source.content_hash)&set(target.content_hash)
 scores=pd.read_csv(A/'all_test_metrics.csv',float_precision='round_trip');files=0;max_score_error=0.
 for spec in selection['models']:
  model=joblib.load(run/spec['model_path']);predicted=model.predict_proba(test[spec['features']])[:,1]
  for budget in protocol['operating_points']:
   path=A/(Path(spec['model_path']).stem+f'_budget{budget}_test_predictions.csv');f=pd.read_csv(path,float_precision='round_trip')
   assert np.array_equal(f.URL,test.URL) and np.array_equal(f.group,test.group) and np.array_equal(f.y,test.y)
   assert np.array_equal(f.content_hash,test.content_hash)
   delta=float(np.max(np.abs(f.score.to_numpy()-predicted)));assert delta<1e-12;max_score_error=max(max_score_error,delta)
   assert np.array_equal(f.prediction,(f.score>=f.threshold).astype(int))
   row=scores[(scores.regime==spec['regime'])&(scores.branch==spec['branch'])&(scores.family==spec['family'])&(scores.seed==spec['seed'])&(scores.budget==budget)].iloc[0]
   counts=confusion_matrix(f.y,f.prediction,labels=[0,1]).ravel()
   for key,count in zip(['tn','fp','fn','tp'],counts):assert int(row[key])==int(count)
   tn,fp,fn,tp=counts;assert abs(row.fpr-fp/(tn+fp))<1e-12;assert abs(row.recall-tp/(tp+fn))<1e-12
   assert abs(row.average_precision-average_precision_score(f.y,f.score))<1e-12
   assert abs(row.roc_auc-roc_auc_score(f.y,f.score))<1e-12
   files+=1
 # Family ranking is recomputed from calibration evidence only, independently of test.
 cal=pd.read_csv(A/'calibration_metrics.csv',float_precision='round_trip');cal=cal[cal.budget.eq(protocol['primary_budget'])]
 for chosen in selection['selected']:
  g=cal[(cal.regime==chosen['regime'])&(cal.branch==chosen['branch'])];rank=g.groupby('family')[['recall','average_precision']].mean().reset_index()
  rank['order']=rank.family.map({n:i for i,n in enumerate(protocol['families'])});rank=rank.sort_values(['recall','average_precision','order'],ascending=[False,False,True])
  assert chosen['family']==rank.family.iloc[0]
 for regime in protocol['fitting_regimes']:
  train=pd.read_csv(A/f'{regime}_training_manifest.csv');cal=pd.read_csv(A/f'{regime}_calibration_manifest.csv')
  assert not set(train.group)&set(cal.group) and not (set(train.group)|set(cal.group))&set(test.group)
  if regime=='source_only':assert set(train.source)=={'Hannousse_DOM'} and set(cal.source)=={'Hannousse_DOM'}
 result={'status':'PASS','verified_test_prediction_files':files,'model_specs':len(selection['models']),'test_records_per_file':len(test),
         'max_saved_score_vs_checkpoint_error':max_score_error,'domain_and_exact_content_isolation':True,
         'published_record_identities_and_labels_verified':True,'retained_labels_checked_against_raw_creator_mapping':True,'target_domains_exclude_complete_retained_source_csv':True,'actual_creator_archive_hashes_verified':True,'calibration_only_selection_verified':True,
         'fixed_source_never_uses_target_labels':True,'all_confusion_counts_and_ranking_metrics_recomputed':True,
         'scope':'Implementation/lineage consistency on published historical labels, not independent relabelling or deployment certification.'}
 (run/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
