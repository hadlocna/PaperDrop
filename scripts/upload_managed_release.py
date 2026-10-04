#!/usr/bin/env python3
"""Upload a managed package in bounded, checksum-verified chunks; never publish it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--description', default='Managed PaperDrop runtime update')
    args = parser.parse_args()
    password = os.environ.get('PAPERDROP_ADMIN_PASSWORD')
    if not password:
        parser.error('Set PAPERDROP_ADMIN_PASSWORD in the environment')
    size = args.archive.stat().st_size
    if not 0 < size <= 600 * 1024 * 1024:
        parser.error('Archive must be between 1 byte and 600 MiB')
    digest = hashlib.sha256()
    with args.archive.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    ident = digest.hexdigest()
    with tarfile.open(args.archive, 'r:gz') as archive:
        release = json.load(archive.extractfile('release.json'))
    if release.get('format') != 2:
        parser.error('Expected a managed release')
    base = 'https://api.paperdrop.me/api/admin/firmware-upload/' + ident

    def request(url, body, method, content_type):
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, method=method, headers={
                    'x-admin-password': password, 'Content-Type': content_type,
                })
                with urllib.request.urlopen(req, timeout=45) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code < 500 or attempt == 2:
                    raise SystemExit(f'Upload rejected (HTTP {error.code}): {error.read(4096).decode()}')
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise SystemExit('Upload connection failed; rerun to retry safely')
            time.sleep(attempt + 1)

    chunk_bytes = 8 * 1024 * 1024
    count = (size + chunk_bytes - 1) // chunk_bytes
    with args.archive.open('rb') as source:
        for index in range(count):
            request(f'{base}/chunks/{index}', source.read(chunk_bytes), 'PUT', 'application/octet-stream')
            print(f'Uploaded {index + 1}/{count}', flush=True)
    result = request(base + '/complete', json.dumps({
        'count': count, 'version': release['version'], 'description': args.description,
    }).encode(), 'POST', 'application/json')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
