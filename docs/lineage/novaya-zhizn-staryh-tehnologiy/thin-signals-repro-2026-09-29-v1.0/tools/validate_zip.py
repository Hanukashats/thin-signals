"""Unpack a trusted experiment archive into a NEW directory and replay it."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

def run(command,cwd,log_path):
    env=dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONIOENCODING']='utf-8'
    result=subprocess.run(command,cwd=str(cwd),env=env,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',timeout=180)
    log_path.write_text(result.stdout,encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Validation failed; see '+str(log_path))
    return json.loads(result.stdout)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New validation directory, never overwritten')
    args=parser.parse_args()
    archive_path=args.archive.resolve()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    unpacked=output/'unpacked'
    unpacked.mkdir()
    roots=set()
    with zipfile.ZipFile(str(archive_path)) as archive:
        bad=archive.testzip()
        if bad:
            raise RuntimeError('ZIP CRC failure: '+bad)
        entries=archive.infolist()
        seen=set()
        for entry in entries:
            rel=PurePosixPath(entry.filename)
            if rel.is_absolute() or '..' in rel.parts or any(':' in p for p in rel.parts) or not rel.parts:
                raise ValueError('Unsafe ZIP path')
            if entry.filename in seen:
                raise ValueError('Duplicate ZIP path')
            seen.add(entry.filename)
            if ((entry.external_attr >> 16) & 0o170000)==0o120000:
                raise ValueError('Symlink not allowed')
            roots.add(rel.parts[0])
            target=unpacked.joinpath(*rel.parts).resolve()
            if unpacked not in target.parents:
                raise ValueError('ZIP target escapes output')
            if entry.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(entry) as source,target.open('xb') as destination:
                    shutil.copyfileobj(source,destination)
    if len(roots)!=1:
        raise ValueError('Expected one package root')
    package=unpacked/next(iter(roots))
    integrity=run([sys.executable,'-B','verify_archive.py'],package,output/'integrity.log')
    replay=run([sys.executable,'-B','reproduce.py','--output',str(output/'replay')],package,output/'replay.log')
    details=json.loads((output/'replay'/'replay_result.json').read_text(encoding='utf-8'))
    report={'status':'PASS' if integrity['status']==replay['status']=='PASS' else 'FAIL',
            'validated_at_utc':datetime.now(timezone.utc).isoformat(),'archive':archive_path.name,
            'zip_entries':len(entries),'zip_crc':'PASS','integrity':integrity,'replay':details}
    result_path=output/'verification.json'
    result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'result':str(result_path),'zip_entries':len(entries)}))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
