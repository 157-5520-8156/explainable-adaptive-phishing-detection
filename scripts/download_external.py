"""Fetch a creator-published CC BY 4.0 dataset and verify its repository checksum."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
URL='https://data.mendeley.com/public-files/datasets/3jddhy2f6s/files/575f34ca-98c8-42cd-affe-7dad6aaf17a2/file_downloaded'
EXPECTED='fccce1a99282b3cd8a1fe08fa83350fe44f7afc4c8889a6d0a94ef9c4d7897e3'
target=ROOT/'data/raw/wangchuk_dataset2.csv'
if not target.exists():
    content=subprocess.check_output(['curl','--location','--fail','--silent','--show-error','--max-filesize','13000000',URL])
    assert hashlib.sha256(content).hexdigest()==EXPECTED
    target.write_bytes(content)
assert hashlib.sha256(target.read_bytes()).hexdigest()==EXPECTED
metadata={'title':'Phishing URL dataset','creator':'Tandin Wangchuk','version':1,'doi':'10.17632/3jddhy2f6s.1',
    'repository':'https://data.mendeley.com/datasets/3jddhy2f6s/1','download_url':URL,'license':'CC BY 4.0',
    'published':'2026-01-09','verified_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
    'sha256':EXPECTED,'bytes':target.stat().st_size,'label_mapping':{'0':'legitimate','1':'phishing'},
    'label_mapping_evidence':'Numeric counts match the two class totals in the creator description; individual labels have not been independently verified.',
    'live_destinations_visited':False}
(ROOT/'data/raw/wangchuk_provenance.json').write_text(json.dumps(metadata,indent=2))
print('Verified external data:',target)
