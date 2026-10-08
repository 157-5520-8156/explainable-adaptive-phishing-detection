"""One-command raw-only reproduction in a fresh isolated workspace."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,shutil,subprocess,sys,time,importlib.metadata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import verify_raw_directory,file_sha256
from run_runtime import checked_environment

def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw')
 parser.add_argument('--output-dir',type=Path,required=True)
 parser.add_argument('--download',action='store_true',help='Download and verify creator raw files instead of requiring existing CSVs')
 parser.add_argument('--prepare-only',action='store_true',help='Create raw-only partitions; no model fitting')
 args=parser.parse_args();out=args.output_dir.resolve()
 if out.exists():parser.error('Output exists; choose a fresh directory')
 out.mkdir(parents=True)
 manifest={'status':'preparing','started_at':now(),'stages':[],'raw_only_start':True,'old_experiment_or_processed_cache_copied':False}
 write(out/'manifest.json',manifest)
 try:
  manifest['runtime']=checked_environment(ROOT/'requirements.txt')
  if args.download:
   args.raw_dir=out/'downloaded_raw'
   from download_verified_inputs import acquire
   acquire(args.raw_dir)
  inputs=verify_raw_directory(args.raw_dir)
  workspace=out/'workspace';workspace.mkdir()
  source_names=[]
  for folder in ['src','scripts','configs','tests']:
   shutil.copytree(ROOT/folder,workspace/folder,ignore=shutil.ignore_patterns('__pycache__'))
   source_names.extend(str(p.relative_to(workspace)) for p in (workspace/folder).rglob('*') if p.is_file())
  shutil.copy2(ROOT/'requirements.txt',workspace/'requirements.txt');source_names.append('requirements.txt')
  raw=workspace/'data/raw';raw.mkdir(parents=True,exist_ok=True)
  for name in inputs:shutil.copy2(args.raw_dir/name,raw/name)
  assert not (workspace/'data/processed').exists() and not (workspace/'experiments').exists()
  manifest.update(status='running',input_files=inputs,source_sha256={n:file_sha256(workspace/n) for n in source_names})
  write(out/'manifest.json',manifest)
 except BaseException as error:
  manifest.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=str(error) or type(error).__name__,finished_at=now())
  write(out/'manifest.json',manifest)
  raise
 commands=[['scripts/prepare_redesign.py','--run-id','url_run']]
 if not args.prepare_only:
  commands += [['scripts/run_redesign_static.py','--run-id','url_run'],
               ['scripts/run_page_study.py','--run-id','page_run','--base-partition','url_run'],
               ['scripts/evaluate_redesign.py','--page-run-id','page_run','--url-run-id','url_run'],
               ['scripts/verify_redesign.py','--run-id','page_run'],
               ['scripts/analyze_redesign.py','--run-id','page_run','--url-run-id','url_run']]
 try:
  for command in commands:
   start=time.perf_counter();stage={'command':command,'started_at':now()};log=out/(Path(command[0]).stem+'.log')
   print('Running', ' '.join(command),flush=True)
   with log.open('w') as stream:
    result=subprocess.run([sys.executable,*command],cwd=workspace,stdout=stream,stderr=subprocess.STDOUT)
   stage.update(returncode=result.returncode,seconds=time.perf_counter()-start,finished_at=now(),log=log.name)
   manifest['stages'].append(stage);write(out/'manifest.json',manifest)
   if result.returncode:raise RuntimeError(f'Stage failed: {command[0]}; inspect {log}')
  manifest['status']='prepared_from_raw' if args.prepare_only else 'complete'
  if not args.prepare_only:
   page=workspace/'experiments/page_run';url=workspace/'experiments/url_run'
   for source,target in [(page/'verification.json','verification.json'),(page/'artifacts/final_test_metrics.csv','page_final_test_metrics.csv'),
                         (page/'artifacts/replay_metrics.csv','page_replay_metrics.csv'),(url/'artifacts/test_metrics.csv','url_test_metrics.csv')]:shutil.copy2(source,out/target)
   shutil.copytree(page/'analysis',out/'analysis',ignore=shutil.ignore_patterns('*.joblib','*.npz','*manifest.csv'))
   manifest['result_sha256']={str(p.relative_to(out)):file_sha256(p) for p in out.rglob('*') if p.is_file() and 'workspace' not in p.parts and p.name!='manifest.json'}
 except BaseException as error:
  manifest['status']='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed';manifest['error']=str(error);raise
 finally:
  manifest['finished_at']=now();write(out/'manifest.json',manifest)
 print('Reproduction status:',manifest['status'],'outputs:',out,flush=True)

if __name__=='__main__':main()
