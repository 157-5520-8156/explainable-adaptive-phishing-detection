"""Download only the CSV from the creator's verified CC BY 4.0 release."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://data.mendeley.com/public-files/datasets/c2gw7fy2j4/files/575316f4-ee1d-453e-a04f-7b950915b61b/file_downloaded'
EXPECTED = '21093e2902e5441c86a6daf95e86e7c332046e477fdf109a579d7bd81e586d6c'
target = ROOT / 'data/raw/hannousse_dataset_B_05_2020.csv'
if not target.exists():
    data = subprocess.check_output(['curl', '--location', '--fail', '--silent', '--show-error',
                                    '--max-filesize', '5000000', URL])
    assert hashlib.sha256(data).hexdigest() == EXPECTED
    target.write_bytes(data)
assert hashlib.sha256(target.read_bytes()).hexdigest() == EXPECTED
metadata = {'title': 'Web page phishing detection', 'version': 3,
            'authors': ['Abdelhakim Hannousse', 'Salima Yahiouche'],
            'doi': '10.17632/c2gw7fy2j4.3', 'published': '2021-06-25',
            'collection_period': 'May 2020; not per-record observation timestamps',
            'repository': 'https://data.mendeley.com/datasets/c2gw7fy2j4/3',
            'download_url': URL, 'license': 'CC BY 4.0', 'sha256': EXPECTED,
            'bytes': target.stat().st_size, 'used_columns': ['url', 'status'],
            'released_engineered_features_used': False, 'live_destinations_visited': False,
            'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
(ROOT / 'data/raw/hannousse_provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
print('Verified creator-release CSV:', target)
