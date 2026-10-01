"""Build a ZIP from the verified manifest, never including generated runs/."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_archive import verify

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():
        parser.error('Output already exists; choose a new filename.')
    check=verify(ROOT)
    if check['status']!='PASS':
        raise RuntimeError(json.dumps(check))
    records=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'))['files']
    names=sorted([x['path'] for x in records]+['MANIFEST.json'])
    with zipfile.ZipFile(str(output),'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in names:
            info=zipfile.ZipInfo(ROOT.name+'/'+name,date_time=(2026,9,29,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,(ROOT/name).read_bytes())
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(output),'files':len(names),'bytes':output.stat().st_size,'sha256':digest}))

if __name__=='__main__':
    main()
