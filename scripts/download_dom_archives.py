"""Fetch creator data archives and verify their exact bytes; no deserialization."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'data/raw/archives';folder.mkdir(parents=True,exist_ok=True)
for f in json.loads((ROOT/'data/raw/hannousse_dom_catalog.json').read_text())['files']:
 target=folder/f['filename']
 if not target.exists():
  part=target.with_suffix(target.suffix+'.part')
  subprocess.run(['curl','--location','--fail','--silent','--show-error','--max-time','180',f['url'],'--output',str(part)],check=True)
  if hashlib.sha256(part.read_bytes()).hexdigest()!=f['sha256']:
   alternate=f['url'].replace('/file_downloaded','/file_viewed')
   subprocess.run(['curl','--location','--fail','--silent','--show-error','--max-time','180',alternate+'?fresh=20261007','--output',str(part)],check=True)
   if hashlib.sha256(part.read_bytes()).hexdigest()!=f['sha256']:raise RuntimeError('Creator checksum mismatch: '+f['filename'])
  part.rename(target)
 if hashlib.sha256(target.read_bytes()).hexdigest()!=f['sha256']:raise RuntimeError('Changed local archive: '+f['filename'])
 print('Verified',target.name,flush=True)
