"""Verify declared archive files without network or file mutations. Python 3.8+."""
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def verify(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    errors, seen = [], set()
    records = manifest['files']
    if not records:
        errors.append('Empty manifest')
    for record in records:
        rel = PurePosixPath(record['path'])
        if rel.is_absolute() or '..' in rel.parts or any(':' in p for p in rel.parts):
            errors.append('Unsafe path: '+str(rel))
            continue
        if str(rel) in seen:
            errors.append('Duplicate path: '+str(rel))
            continue
        seen.add(str(rel))
        path = root.joinpath(*rel.parts)
        if root not in path.resolve().parents or path.is_symlink():
            errors.append('Path escapes package or is symlink: '+str(rel))
        elif not path.is_file():
            errors.append('Missing file: '+str(rel))
        elif path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
            errors.append('Content mismatch: '+str(rel))
    return {'status':'PASS' if not errors else 'FAIL', 'declared_files':len(records),
            'errors':errors, 'scope':'Declared immutable files; generated runs/ are not part of the manifest.'}

def main():
    try:
        result = verify()
    except Exception as error:
        result = {'status':'FAIL','errors':[str(error)]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
