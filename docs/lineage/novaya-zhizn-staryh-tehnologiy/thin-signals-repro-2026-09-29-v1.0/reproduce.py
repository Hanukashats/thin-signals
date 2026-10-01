"""Replay the frozen research in a new directory; no network access. Python 3.8+."""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from verify_archive import verify, sha256

ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def normalized_text(path):
    return path.read_text(encoding='utf-8-sig').replace('\r\n','\n').replace('\r','\n')

def file_hashes(folder):
    return {str(p.relative_to(folder)):sha256(p) for p in folder.iterdir() if p.is_file()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,help='New output directory; an existing directory is never overwritten.')
    args = parser.parse_args()
    integrity = verify(ROOT)
    if integrity['status'] != 'PASS':
        print(json.dumps(integrity,ensure_ascii=False))
        return 1
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (args.output or ROOT/'runs'/('replay-'+stamp)).resolve()
    if output == ROOT or ROOT in output.parents and output.relative_to(ROOT).parts[0] != 'runs':
        parser.error('Inside the archive, outputs must be in runs/ to preserve frozen files.')
    output.mkdir(parents=True,exist_ok=False)
    baseline = ROOT/'research'
    before = file_hashes(baseline)
    work = output/'work'
    shutil.copytree(str(baseline),str(work),ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    steps=[]
    for name,command in [
        ('unit_tests',['-B','-m','unittest','-v']),
        ('score',['-B','score.py']),
        ('report',['-B','build_report.py'])
    ]:
        result = subprocess.run([sys.executable]+command,cwd=str(work),env=env,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                encoding='utf-8',errors='replace',timeout=120)
        (output/(name+'.log')).write_text(result.stdout,encoding='utf-8')
        steps.append({'step':name,'exit_code':result.returncode,'log':name+'.log'})
        if result.returncode:
            break
    comparisons=[]
    for name in ('ranking.json','sensitivity.json'):
        comparisons.append({'file':name,'equal':read(baseline/name)==read(work/name),'comparison':'JSON structure'})
    for name in ('ranking.csv','REPORT.md'):
        comparisons.append({'file':name,'equal':normalized_text(baseline/name)==normalized_text(work/name),
                            'comparison':'UTF-8 text with normalized line endings'})
    cards=read(work/'candidates.json')
    sources=read(work/'sources.json')
    ranking=read(work/'ranking.json')
    exclusions=read(work/'exclusions.json')
    queries=read(work/'market_search_log.json')['queries']
    expected=read(ROOT/'expected_results.json')
    source_ids={s['id'] for s in sources}
    observed={
        'candidates':len(cards),'sources':len(sources),'audit_decisions':len(exclusions),
        'commercial_queries':len(queries),'fully_qualified':sum(r['fully_qualified'] for r in ranking),
        'top_three':[r['id'] for r in ranking[:3]],
        'doi_records':len(read(work/'metadata_doi_final.json')['crossref_dois']),
        'sensitivity_scenarios':read(work/'sensitivity.json')['scenarios']}
    counts_equal=observed==expected['observed_baseline']
    references_valid=(len({c['id'] for c in cards})==len(cards) and len(source_ids)==len(sources)
        and all(set(c['source_ids'])<=source_ids for c in cards)
        and all(set(x['source_ids'])<=source_ids for x in exclusions)
        and {c['id'] for c in cards}<={q['id'] for q in queries})
    unchanged=before==file_hashes(baseline)
    passed=(len(steps)==3 and all(s['exit_code']==0 for s in steps)
            and all(c['equal'] for c in comparisons) and counts_equal and references_valid and unchanged)
    report={'status':'PASS' if passed else 'FAIL','mode':'offline_frozen_replay',
            'executed_at_utc':datetime.now(timezone.utc).isoformat(),
            'python_version':sys.version.split()[0], 'network_used':False,
            'integrity':integrity,'steps':steps,'comparisons':comparisons,
            'observed':observed,'baseline_counts_equal':counts_equal,
            'references_valid':references_valid,'baseline_unchanged':unchanged,
            'scope':'Deterministic replay and data integrity, not scientific or commercial validation.'}
    (output/'replay_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'result':str(output/'replay_result.json'),
                      'comparisons_passed':sum(c['equal'] for c in comparisons),
                      'baseline_unchanged':unchanged},ensure_ascii=False))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
