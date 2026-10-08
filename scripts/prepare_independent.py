"""Extract passive archived-page features and freeze domain roles before scoring."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ProcessPoolExecutor
import argparse,gc,hashlib,json,re,shutil,sys,zipfile
import numpy as np,pandas as pd
from sklearn.model_selection import StratifiedGroupKFold,GroupShuffleSplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import file_sha256,RAW_CATALOG
from safe_dom_pickle import parse_dom_pickle
from passive_html import extract_inert_dom_features,extract_html_features
from url_model_v2 import normalize_url,numeric_frame
from features import domain_group

MAPPING_HASH='e6dda6a21d925f8aba36090f295b08e9808a5dfe8dd3276bf8cd82022855f14a'
ZIP_HASH='12440e4f911fabf4ec2c712ae014cb43e638e9a6adc6c7c6a506a8a7df24fcf7'

def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def quality(frame):
 f=frame.copy();f['normalized']=f.URL.map(normalize_url);f['group']=f.URL.map(domain_group)
 bad=f.normalized.eq('')|f.group.eq('')|f.URL.str.strip().str.contains(r'[\s<>\"]',regex=True,na=True)
 return f[~bad].copy(),{str(c):int((bad&f.y.eq(c)).sum()) for c in [0,1]}

def extract_source_file(path):
 data=parse_dom_pickle(Path(path).read_bytes(),max_operations=20000000);rows=[];errors=[]
 if not isinstance(data,dict):raise ValueError('Creator DOM archive is not URL-keyed')
 for url,row in data.items():
  if not isinstance(row,dict) or row.get('status') not in {'legitimate','phishing'}:raise ValueError('Unexpected source snapshot label')
  y=int(row['status']=='phishing')
  try:
   values,digest=extract_inert_dom_features(url,row['dom'])
   rows.append({'URL':url,'y':y,'source':'Hannousse_DOM','content_hash':digest,'raw_member':Path(path).name,**values})
  except (ValueError,TypeError,KeyError,RecursionError) as error:errors.append({'URL':url,'y':y,'reason':str(error)})
 return rows,errors,len(data)

TARGET_ZIP=None

def initialize_target(path):
 global TARGET_ZIP
 TARGET_ZIP=zipfile.ZipFile(path)

def extract_target_row(item):
 serial,url,y=item;member=f'All_HTML/{serial}.txt';info=TARGET_ZIP.getinfo(member)
 if info.file_size>25000000:return None,{'URL':url,'y':y,'serial':serial,'reason':'Archived HTML byte limit exceeded'}
 content=TARGET_ZIP.read(member)
 # Released text snapshots are decoded consistently; replacements are counted.
 markup=content.decode('utf-8',errors='replace')
 try:
  values,digest=extract_html_features(url,markup)
  return {'URL':url,'y':y,'source':'CompPhish','serial':serial,'content_hash':digest,
          'raw_html_sha256':hashlib.sha256(content).hexdigest(),'decode_replacements':markup.count('\ufffd'),**values},None
 except (ValueError,TypeError,KeyError,RecursionError) as error:return None,{'URL':url,'y':y,'serial':serial,'reason':str(error)}

def remove_conflicts_duplicates(frame,ledger=None):
 f=frame.copy();audit={}
 for key in ['normalized','content_hash']:
  counts=f.groupby(key).y.nunique();conflicts=set(counts[counts>1].index)
  mask=f[key].isin(conflicts)
  audit[key+'_conflicting_rows']=int(mask.sum())
  if ledger is not None:
   ledger.extend(f[mask].assign(exclusion_reason=key+'_mixed_label_cluster').to_dict('records'))
  f=f[~mask]
  before=len(f)
  if ledger is not None:ledger.extend(f[f.duplicated(key,keep='first')].assign(exclusion_reason=key+'_repeated_record').to_dict('records'))
  f=f.drop_duplicates(key);audit[key+'_duplicate_rows']=before-len(f)
 return f.reset_index(drop=True),audit

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--workers',type=int,default=2)
 args=parser.parse_args();run=ROOT/'experiments'/args.run_id
 if run.exists():raise SystemExit('Archive exists; never overwrite scored evidence')
 run.mkdir(parents=True);A=run/'artifacts';A.mkdir()
 source_files=['configs/independent_protocol.json','src/passive_html.py','src/safe_dom_pickle.py','src/raw_protocol.py','src/url_model_v2.py','src/features.py','src/evaluation.py','scripts/prepare_independent.py','requirements.txt']
 for name in source_files:
  dest=run/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
 protocol=json.loads((run/'source/configs/independent_protocol.json').read_text())
 source_csv=ROOT/'data/raw/hannousse_dataset_B_05_2020.csv'
 if file_sha256(source_csv)!=RAW_CATALOG[source_csv.name]['sha256']:raise ValueError('Source label CSV checksum mismatch')
 catalogue=json.loads((ROOT/'data/raw/hannousse_dom_catalog.json').read_text());paths=[]
 for f in catalogue['files']:
  path=ROOT/'data/raw/archives'/f['filename']
  if file_sha256(path)!=f['sha256']:raise ValueError('Creator source hash mismatch '+f['filename'])
  paths.append(path)
 archive=ROOT/'data/raw/archives/CompPhish_All_HTML.zip'
 mapping=ROOT/'data/raw/archives/Mapping_File.xlsx'
 if file_sha256(archive)!=ZIP_HASH or file_sha256(mapping)!=MAPPING_HASH:raise ValueError('Creator target hash mismatch')
 manifest={'status':'extracting_before_any_target_model_scores','started_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
   'source_sha256':{name:file_sha256(run/'source'/name) for name in source_files},
   'creator_inputs':{'source_catalog':catalogue,'target_zip_sha256':ZIP_HASH,'mapping_sha256':MAPPING_HASH,'source_label_csv_sha256':file_sha256(source_csv)},
   'target_model_scores_inspected':False,'live_destinations_visited':False,'pickle_globals_executed':False}
 dump(run/'manifest.json',manifest)
 source_rows=[];source_errors=[];snapshot_n=0;exclusion_ledger=[]
 for path in paths:
  rows,errors,n=extract_source_file(path);source_rows.extend(rows);source_errors.extend(errors);snapshot_n+=n;gc.collect()
  print('SOURCE DOM',path.name,n,'eligible extraction',len(rows),'errors',len(errors),flush=True)
 source=pd.DataFrame(source_rows)
 raw_h=pd.read_csv(ROOT/'data/raw/hannousse_dataset_B_05_2020.csv',usecols=['url','status'])
 label_map=dict(zip(raw_h.url,raw_h.status.map({'legitimate':0,'phishing':1})))
 if any(u not in label_map or label_map[u]!=y for u,y in zip(source.URL,source.y)):raise ValueError('Snapshot/CSV published labels disagree')
 source,bad_source=quality(source);source,source_dups=remove_conflicts_duplicates(source,exclusion_ledger)
 whole_source,_=quality(raw_h.rename(columns={'url':'URL'}).assign(y=raw_h.status.map({'legitimate':0,'phishing':1})))
 source_domains=set(whole_source.group);source_content=set(source.content_hash)
 map_frame=pd.read_excel(mapping)
 if list(map_frame.columns)!=['serial_number','url','label'] or set(map_frame.label.unique())!={0,1}:raise ValueError('Unexpected CompPhish mapping schema')
 if map_frame.serial_number.nunique()!=len(map_frame) or map_frame[['url','label']].isna().any().any():raise ValueError('Ambiguous target mapping')
 records=[(int(x.serial_number),str(x.url),int(x.label)) for x in map_frame.itertuples(index=False)]
 with zipfile.ZipFile(archive) as z:
  actual={n for n in z.namelist() if n.endswith('.txt')};expected={f'All_HTML/{x[0]}.txt' for x in records}
  if actual!=expected:raise ValueError('Target HTML mapping mismatch')
 target_rows=[];target_errors=[]
 with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize_target,initargs=(str(archive),)) as pool:
  for i,(row,error) in enumerate(pool.map(extract_target_row,records,chunksize=16),1):
   if row is not None:target_rows.append(row)
   if error is not None:target_errors.append(error)
   if i%500==0:print('TARGET HTML',i,'/',len(records),'errors',len(target_errors),flush=True)
 target=pd.DataFrame(target_rows);target,bad_target=quality(target)
 target,target_dups=remove_conflicts_duplicates(target,exclusion_ledger)
 # Conflict detection across sources is resolved by exclusion, never relabelling.
 overlap_domain=target.group.isin(source_domains);overlap_content=target.content_hash.isin(source_content)
 excluded={str(c):{'domain_overlap':int((overlap_domain&target.y.eq(c)).sum()),'content_overlap':int((overlap_content&target.y.eq(c)).sum())} for c in [0,1]}
 exclusion_ledger.extend(target[overlap_domain|overlap_content].assign(exclusion_reason=np.where(overlap_domain[overlap_domain|overlap_content],'source_domain_overlap','source_content_overlap')).to_dict('records'))
 target=target[~(overlap_domain|overlap_content)].reset_index(drop=True)
 assert not set(source.group)&set(target.group) and not set(source.content_hash)&set(target.content_hash)
 for frame in [source,target]:
  X=numeric_frame(frame.URL,version='normalized_url_v3')
  for name in X:frame[name]=X[name].to_numpy()
 url_names=list(X.columns);page_names=[c for c in source.columns if c.startswith('html_')]
 assert len(url_names)==44 and len(page_names)==28
 assert np.isfinite(source[url_names+page_names].to_numpy(dtype=float)).all() and np.isfinite(target[url_names+page_names].to_numpy(dtype=float)).all()
 train_idx,cal_idx=next(GroupShuffleSplit(n_splits=1,test_size=.3,random_state=20261007).split(source,source.y,source.group))
 source['partition']='source_train';source.loc[cal_idx,'partition']='source_calibration'
 assignment=np.zeros(len(target),int)
 for fold,(_,index) in enumerate(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=20261007).split(target,target.y,target.group)):assignment[index]=fold
 target['fold']=assignment;target['partition']=np.where(assignment<=2,'sealed_test',np.where(assignment==3,'target_train','target_calibration'))
 combined=pd.concat([source,target],ignore_index=True)
 roles={role:f for role,f in combined.groupby('partition')}
 for role,left in roles.items():
  if left.y.nunique()!=2:raise ValueError('Single-class role '+role)
  for other,right in roles.items():
   if role!=other and set(left.group)&set(right.group):raise RuntimeError('Grouped role overlap')
 source.to_pickle(A/'source_features.pkl');target.to_pickle(A/'target_features.pkl')
 combined[['URL','normalized','group','y','source','partition','content_hash']].to_csv(A/'partition_manifest.csv',index=False)
 dump(A/'feature_names.json',{'url_only_44':url_names,'shared_page_72':url_names+page_names})
 counts={role:{'n':len(f),'normal':int(f.y.eq(0).sum()),'phishing':int(f.y.sum()),'domains':int(f.group.nunique())} for role,f in roles.items()}
 audit={'source_snapshot_rows':snapshot_n,'source_csv_rows':len(raw_h),'source_snapshots_are_subset':snapshot_n<len(raw_h),
  'source_extraction_failures':source_errors,'target_extraction_failures':target_errors,'source_quality_exclusions':bad_source,'target_quality_exclusions':bad_target,
  'source_conflicts_duplicates':source_dups,'target_conflicts_duplicates':target_dups,'target_source_overlap_excluded_by_class':excluded,
  'target_original_mapping_n':len(map_frame),'target_decode_replacements':int(pd.DataFrame(target_rows).decode_replacements.sum()),
  'role_counts':counts,'all_roles_domain_disjoint':True,'source_target_exact_content_disjoint':True,
  'limitations':['Source snapshots are creator-parsed DOM; target parser/capture can differ.','Exact normalized DOM fingerprints do not detect every shared template or campaign.','Published historical labels not independently reverified.']}
 for src,errors in [('Hannousse_DOM',source_errors),('CompPhish',target_errors)]:
  for row in errors:exclusion_ledger.append({'source':src,'URL':row['URL'],'y':row['y'],'group':domain_group(row['URL']),'exclusion_reason':'extraction_failed','detail':row['reason']})
 ledger=pd.DataFrame(exclusion_ledger)
 columns=['source','URL','group','y','exclusion_reason']
 ledger[columns+(['detail'] if 'detail' in ledger else [])].to_csv(A/'exclusion_ledger.csv',index=False)
 breakdown=ledger.groupby(['source','exclusion_reason','y']).agg(rows=('URL','size'),domains=('group','nunique')).reset_index()
 breakdown.to_csv(A/'exclusion_counts.csv',index=False)
 audit['exclusions_by_class_and_domain']=breakdown.to_dict(orient='records')
 audit['mixed_label_content_interpretation']='Same content on different URLs can have valid differing labels. This is a predeclared population/isolation filter, not a determination that creator labels are wrong.'
 dump(A/'data_quality.json',audit)
 manifest['status']='prepared_no_model_scores';manifest['artifact_sha256']={str(p.relative_to(run)):file_sha256(p) for p in A.iterdir() if p.is_file()};dump(run/'manifest.json',manifest)
 print(json.dumps(counts,indent=2),flush=True)

if __name__=='__main__':main()
