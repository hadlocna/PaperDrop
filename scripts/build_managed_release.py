#!/usr/bin/env python3
"""Package both interfaces and a complete offline speech pack; no device secrets."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import sys

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('version')
p.add_argument('--speech-dir', required=True)
p.add_argument('--output-dir', default='artifacts/firmware')
a = p.parse_args()
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', a.version):
    p.error('Invalid version')
speech = Path(a.speech_dir)
sys.path.insert(0, str(root/'agent/streamdeck'))
from languages import LANGUAGES, all_phrases, translate
needed = {hashlib.sha256(translate(phrase, lang).encode()).hexdigest()+'.wav' for phrase in all_phrases() for lang in LANGUAGES}
missing = [name for name in needed if not (speech/name).exists()]
if missing:
    p.error(f'Missing {len(missing)} required speech clips')
out = root/a.output_dir
out.mkdir(parents=True, exist_ok=True)
archive = out/f'paperdrop-{a.version}.tar.gz'
with tarfile.open(archive, 'w:gz') as tar:
    family = json.loads((root/'agent/streamdeck/family.json').read_text())
    portraits = {p['portrait'] for p in family['children']}
    for src, prefix in [(root/'agent/src','src'), (root/'agent/streamdeck','streamdeck')]:
        for path in sorted(src.rglob('*')):
            relative = path.relative_to(src)
            if not path.is_file() or path.is_symlink() or any(part.startswith('.') or part == '__pycache__' for part in relative.parts) or path.suffix in ('.pyc', '.command') or path.name.startswith('test_'):
                continue
            if 'portraits' in relative.parts and path.name not in portraits:
                continue
            tar.add(path, arcname=str(Path(prefix)/relative))
    for name in sorted(needed):
        tar.add(speech/name, arcname='streamdeck/speech/'+name)
    for name in ('runtime.py', 'requirements.txt'):
        tar.add(root/'agent/factory'/name, arcname=name)
    data = json.dumps({'format':2,'version':a.version}).encode()
    info = tarfile.TarInfo('release.json');info.size=len(data);info.mode=0o644
    tar.addfile(info,io.BytesIO(data))
manifest = {'format':2,'version':a.version,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'url':'https://api.paperdrop.me/uploads/'+archive.name}
(out/f'paperdrop-{a.version}.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(archive)
print(f'Included {len(needed)} speech clips')
