"""Download UCI 967 without visiting any URL in the dataset."""
from pathlib import Path
import hashlib
import io
import json
import urllib.request
from zipfile import ZipFile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
RAW.mkdir(parents=True, exist_ok=True)
META_URL = "https://archive.ics.uci.edu/api/dataset?id=967"
ZIP_URL = "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AcademicPhishingStudy/0.1"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()

metadata = json.loads(fetch(META_URL))
(RAW / "uci_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
target = RAW / "PhiUSIIL_Phishing_URL_Dataset.csv"
if not target.exists():
    archive = fetch(ZIP_URL)
    (RAW / "uci967.zip").write_bytes(archive)
    with ZipFile(io.BytesIO(archive)) as z:
        candidates = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(candidates) != 1:
            raise RuntimeError(f"Unexpected CSV members: {candidates}")
        target.write_bytes(z.read(candidates[0]))
provenance = {
    "repository": "https://archive.ics.uci.edu/dataset/967/phiusil-phishing-url-dataset",
    "metadata_url": META_URL,
    "download_url": ZIP_URL,
    "retrieved_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "csv_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "csv_bytes": target.stat().st_size,
    "license": "CC BY 4.0",
    "raw_labels": {"0": "phishing", "1": "legitimate"},
    "live_websites_visited": False,
}
(RAW / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
print(json.dumps(provenance, indent=2), flush=True)
