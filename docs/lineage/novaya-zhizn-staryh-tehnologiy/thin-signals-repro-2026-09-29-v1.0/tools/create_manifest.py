"""Packaging utility: inventory immutable package files; do not use to hide a mismatch."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    files=[]
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel=path.relative_to(ROOT)
        if rel.as_posix()=='MANIFEST.json' or rel.parts[0]=='runs' or '__pycache__' in rel.parts or path.suffix=='.pyc':
            continue
        if path.is_symlink():
            raise ValueError('Symlinks are not part of this package: '+str(rel))
        content=path.read_bytes()
        files.append({'path':rel.as_posix(),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
    manifest={'schema_version':1,'package':'thin-signals-repro-2026-09-29-v1.0',
              'generated_at_utc':datetime.now(timezone.utc).isoformat(),
              'excludes':['MANIFEST.json','runs/**','**/__pycache__/**','**/*.pyc'],
              'hash_algorithm':'SHA-256','files':files}
    (ROOT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files)}))

if __name__=='__main__':
    main()
