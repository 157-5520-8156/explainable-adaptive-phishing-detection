"""Acquire the three creator CSVs into a chosen directory and verify pinned bytes."""
from pathlib import Path
import argparse,io,json,subprocess,sys,zipfile
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import RAW_CATALOG,file_sha256,verify_raw_directory
from recover_official_archive_ranges import recover
MENDED=[
 {'filename':'wangchuk_dataset2.csv','bytes':11234312,'sha256':RAW_CATALOG['wangchuk_dataset2.csv']['sha256'],'url':'https://data.mendeley.com/public-files/datasets/3jddhy2f6s/files/575f34ca-98c8-42cd-affe-7dad6aaf17a2/file_downloaded'},
 {'filename':'hannousse_dataset_B_05_2020.csv','bytes':3661166,'sha256':RAW_CATALOG['hannousse_dataset_B_05_2020.csv']['sha256'],'url':'https://data.mendeley.com/public-files/datasets/c2gw7fy2j4/files/575316f4-ee1d-453e-a04f-7b950915b61b/file_downloaded'}]

def acquire(folder,filenames=None):
 selected=set(filenames or RAW_CATALOG)
 if selected-set(RAW_CATALOG):raise ValueError("Unknown input filenames")
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 phi=folder/'PhiUSIIL_Phishing_URL_Dataset.csv'
 if phi.name in selected and not phi.exists():
  url='https://archive.ics.uci.edu/static/public/967/phiusiil%2Bphishing%2Burl%2Bdataset.zip'
  with requests.Session() as session:
   session.auth=lambda request:request
   print('Downloading official UCI archive',flush=True)
   with session.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=(20,40),stream=True) as response:
    response.raise_for_status();parts=[];n=0
    for block in response.iter_content(1024*1024):
     n+=len(block)
     if n>100000000:raise ValueError('UCI archive exceeds expected safety bound')
     parts.append(block)
     if n//(5*1024*1024)!=(n-len(block))//(5*1024*1024):print('UCI archive bytes received',n,flush=True)
  archive=b''.join(parts)
  with zipfile.ZipFile(io.BytesIO(archive)) as z:
   files=[x for x in z.infolist() if x.filename.lower().endswith('.csv')]
   if len(files)!=1 or files[0].file_size>100000000:raise ValueError('Unexpected UCI CSV archive')
   data=z.read(files[0])
  partial=phi.with_suffix('.csv.part');partial.write_bytes(data)
  if file_sha256(partial)!=RAW_CATALOG[phi.name]['sha256']:raise ValueError('UCI creator raw hash mismatch')
  partial.rename(phi)
 for record in MENDED:
  if record['filename'] in selected:recover(record,folder,8*1024*1024,6)
 audit={}
 for name in selected:
  path=folder/name
  if file_sha256(path)!=RAW_CATALOG[name]['sha256']:raise ValueError('Input raw hash mismatch '+name)
  audit[name]={**RAW_CATALOG[name],'bytes':path.stat().st_size}
 (folder/'verified_input_catalog.json').write_text(json.dumps(audit,indent=2)+'\n')
 return audit

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--filenames',nargs='+');args=parser.parse_args();acquire(args.folder,args.filenames)
