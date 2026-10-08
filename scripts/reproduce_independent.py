"""Recreate the independent study from verified raw archives in a new workspace."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import file_sha256,RAW_CATALOG
from run_runtime import checked_environment

def dump(p,o):Path(p).write_text(json.dumps(o,indent=2,allow_nan=False)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw');parser.add_argument('--download',action='store_true')
 args=parser.parse_args();out=args.output_dir.resolve()
 if out.exists():parser.error('Choose a fresh output directory')
 out.mkdir(parents=True);workspace=out/'workspace';workspace.mkdir()
 for folder in ['src','scripts','configs','tests']:shutil.copytree(ROOT/folder,workspace/folder,ignore=shutil.ignore_patterns('__pycache__'))
 shutil.copy2(ROOT/'requirements.txt',workspace/'requirements.txt');raw=workspace/'data/raw';raw.mkdir(parents=True);archives=raw/'archives';archives.mkdir()
 for name in ['hannousse_dom_catalog.json','compphish_dom_catalog.json']:shutil.copy2(ROOT/'data/raw'/name,raw/name)
 manifest={'status':'acquiring_or_copying_verified_raw','started_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
           'legacy_processed_or_experiment_caches_copied':False,'stages':[],'raw_inputs':{},
           'source_sha256':{str(p.relative_to(workspace)):file_sha256(p) for folder in ['src','scripts','configs'] for p in (workspace/folder).rglob('*') if p.is_file()}}
 dump(out/'manifest.json',manifest)
 try:
  manifest['runtime']=checked_environment(ROOT/'requirements.txt')
  dump(out/'manifest.json',manifest)
  if args.download:
   subprocess.run([sys.executable,'scripts/download_verified_inputs.py','--folder',str(raw),'--filenames','hannousse_dataset_B_05_2020.csv'],cwd=workspace,check=True)
   for catalog in ['hannousse_dom_catalog.json','compphish_dom_catalog.json']:
    subprocess.run([sys.executable,'scripts/recover_official_archive_ranges.py','--catalog',str(raw/catalog),'--folder',str(archives)],cwd=workspace,check=True)
  else:
   shutil.copy2(args.raw_dir/'hannousse_dataset_B_05_2020.csv',raw/'hannousse_dataset_B_05_2020.csv')
   for catalog in ['hannousse_dom_catalog.json','compphish_dom_catalog.json']:
    for item in json.loads((raw/catalog).read_text())['files']:
     original=args.raw_dir/'archives'/item['filename']
     if file_sha256(original)!=item['sha256']:raise ValueError('Raw creator archive hash mismatch '+item['filename'])
     shutil.copy2(original,archives/item['filename'])
  phi=raw/'hannousse_dataset_B_05_2020.csv'
  if file_sha256(phi)!=RAW_CATALOG[phi.name]['sha256']:raise ValueError('Source label CSV hash mismatch')
  manifest['raw_inputs']={str(p.relative_to(raw)):file_sha256(p) for p in raw.rglob('*') if p.is_file() and not p.name.endswith('.json')}
  manifest['raw_only_start']=not (workspace/'experiments').exists() and not (workspace/'data/processed').exists()
  for script in ['prepare_independent.py','run_independent.py','verify_independent.py','analyze_independent.py']:
   started=time.perf_counter();log=out/(Path(script).stem+'.log');print('Running',script,flush=True)
   with log.open('w') as stream:result=subprocess.run([sys.executable,'scripts/'+script,'--run-id','independent_run'],cwd=workspace,stdout=stream,stderr=subprocess.STDOUT)
   manifest['stages'].append({'script':script,'returncode':result.returncode,'seconds':time.perf_counter()-started,'log':log.name});dump(out/'manifest.json',manifest)
   if result.returncode:raise RuntimeError('Failed '+script+'; see '+str(log))
  run=workspace/'experiments/independent_run'
  for name in ['verification.json']:shutil.copy2(run/name,out/name)
  for name in ['primary_results.json','data_quality.json','all_test_metrics.csv','selection.json']:shutil.copy2(run/'artifacts'/name,out/name)
  shutil.copytree(run/'analysis',out/'analysis',ignore=shutil.ignore_patterns('*.joblib','*.npz','*manifest.csv'))
  manifest['status']='complete';manifest['result_sha256']={str(p.relative_to(out)):file_sha256(p) for p in out.rglob('*') if p.is_file() and 'workspace' not in p.parts and p.name!='manifest.json'}
 except BaseException as error:manifest.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=str(error) or type(error).__name__);raise
 finally:manifest['finished_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();dump(out/'manifest.json',manifest)
 print('Independent raw reproduction complete:',out,flush=True)

if __name__=='__main__':main()
