"""Refresh hashes for staged/tracked archive files, excluding the manifest itself."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'ARCHIVE-MANIFEST.json'
manifest = json.loads(path.read_text())
old = {entry['path']: entry for entry in manifest['files']}
names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
entries = []
for name in sorted(n for n in names if n and n != path.name):
    data = (ROOT / name).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    entry = {'path': name, 'bytes': len(data), 'sha256': digest}
    if name in old:
        original = old[name].get('original_sha256', old[name]['sha256'])
        if original != digest:
            entry['original_sha256'] = original
    entries.append(entry)
manifest.update(description='Current source and evidence hashes; original_sha256 retains initial archived hashes for changed files.',
                files=entries)
path.write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Hashed {len(entries)} source, documentation and evidence files.')
