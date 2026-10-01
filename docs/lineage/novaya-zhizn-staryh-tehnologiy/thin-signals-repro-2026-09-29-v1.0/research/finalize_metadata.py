import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sources=json.loads((ROOT/'sources.json').read_text(encoding='utf-8'))
snapshot=json.loads((ROOT/'metadata_doi_final.json').read_text(encoding='utf-8'))
records={x['source_id']:x['record'] for x in snapshot['crossref_dois'] if x['status']=='retrieved'}
for s in sources:
    if s['id'] in records:
        r=records[s['id']]
        s['metadata_verified']=True
        s['crossref_published']=r.get('published_online') or r.get('published')
        s['canonical_title']=r.get('title')
(ROOT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
