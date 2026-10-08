"""Recover public creator archives using verified HTTP ranges, without loading them.

The supplied catalog fixes each public URL, byte count and SHA-256. Error bodies
are never printed because upstream gateways can embed unrelated request details.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_range_response(response, start: int, end: int, total: int) -> None:
    expected = f'bytes {start}-{end}/{total}'
    if response.status_code != 206 or response.headers.get('Content-Range') != expected:
        raise ValueError('Server did not return the requested byte range')


def recover(record: dict, folder: Path, chunk_bytes: int, attempts: int,
            resume_from: Path | None = None) -> dict:
    name = record['filename']
    if Path(name).name != name:
        raise ValueError('Catalog filename must be a basename')
    url = record['url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'data.mendeley.com' or parsed.username:
        raise ValueError('Only public HTTPS Mendeley creator URLs are supported')
    total = int(record['bytes'])
    if total <= 0:
        raise ValueError('Catalog byte count must be positive')
    target = folder / name
    part = folder / (name + '.range.part')
    if target.exists():
        if target.stat().st_size != total or digest(target) != record['sha256']:
            raise RuntimeError('Existing archive does not match the creator catalog: ' + name)
    else:
        if resume_from is not None and not part.exists():
            shutil.copyfile(resume_from, part)
        part.touch(exist_ok=True)
        if part.stat().st_size > total:
            raise RuntimeError('Partial archive is larger than the creator byte count')
        public_view = url.replace('/file_downloaded', '/file_viewed')
        with requests.Session() as session:
            # Explicit no-op auth disables requests' implicit .netrc lookup.
            session.auth = lambda request: request
            session.headers.update({'User-Agent': 'Mozilla/5.0'})
            while part.stat().st_size < total:
                start = part.stat().st_size
                end = min(start + chunk_bytes, total) - 1
                expected_bytes = end - start + 1
                for attempt in range(attempts):
                    endpoint = public_view if attempt % 2 == 0 else url
                    # Distinct public queries prevent stale gateway range responses.
                    endpoint += ('&' if '?' in endpoint else '?') + (
                        f'range_start={start}&request_nonce={time.time_ns()}')
                    try:
                        with session.get(endpoint, headers={'Range': f'bytes={start}-{end}'},
                                         timeout=(20, 180), stream=True) as response:
                            validate_range_response(response, start, end, total)
                            blocks, observed = [], 0
                            for block in response.iter_content(1024 * 1024):
                                observed += len(block)
                                if observed > expected_bytes:
                                    raise ValueError('Range response exceeded expected length')
                                blocks.append(block)
                            if observed != expected_bytes:
                                raise ValueError('Range response length is incomplete')
                        with part.open('ab') as file:
                            for block in blocks:
                                file.write(block)
                        print(f'Range verified {name}: {end + 1}/{total}', flush=True)
                        break
                    except (requests.RequestException, ValueError) as error:
                        print(f'Range retry {name} offset={start} attempt={attempt + 1} '
                              f'category={type(error).__name__}', flush=True)
                        if attempt + 1 < attempts:
                            time.sleep(min(2 ** attempt, 15))
                else:
                    raise RuntimeError('Public archive recovery failed: ' + name)
        if digest(part) != record['sha256']:
            raise RuntimeError('Complete archive failed creator SHA-256: ' + name)
        part.rename(target)
    audit = {'filename': name, 'public_creator_url': url,
             'bytes': target.stat().st_size, 'sha256': digest(target),
             'creator_sha256_match': True,
             'retrieved_or_verified_utc': datetime.now(timezone.utc).isoformat(),
             'method': 'HTTPS public URL, Mozilla user agent, exact HTTP 206 ranges, full SHA-256',
             'deserialized_or_executed': False}
    (folder / (name + '.acquisition.json')).write_text(json.dumps(audit, indent=2))
    print('Archive creator hash verified: ' + name, flush=True)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--filenames', nargs='*')
    parser.add_argument('--folder', type=Path, default=ROOT / 'data/raw/archives')
    parser.add_argument('--parallel', type=int, default=2, choices=(1, 2))
    parser.add_argument('--chunk-mib', type=int, default=8)
    parser.add_argument('--attempts', type=int, default=6)
    parser.add_argument('--resume-from', type=Path)
    args = parser.parse_args()
    if args.chunk_mib < 1 or args.attempts < 1:
        parser.error('Chunk size and attempts must be positive')
    records = json.loads(args.catalog.read_text())['files']
    if args.filenames:
        chosen = set(args.filenames)
        if chosen - {x['filename'] for x in records}:
            parser.error('Requested filename is absent from the fixed creator catalog')
        records = [x for x in records if x['filename'] in chosen]
    if args.resume_from and len(records) != 1:
        parser.error('--resume-from requires exactly one selected archive')
    args.folder.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(recover, x, args.folder, args.chunk_mib * 1024 * 1024,
                               args.attempts, args.resume_from) for x in records]
        for future in futures:
            future.result()


if __name__ == '__main__':
    main()
