"""Local-only contract probes for the user supplied Auto-Goal v0.3.0 archive.

Starts only its test kernel on an ephemeral loopback port, with temporary state.
No installation, real goal activation, remote requests, or source modifications.
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
SRC=next((BASE/'source').iterdir()) if len(sys.argv)<2 else Path(sys.argv[1]).resolve()

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

testmod=load('upstream_probes',SRC/'tests/test_goal_kernel_vnext.py')
compiler=load('compiler_probes',SRC/'.cursor/skills/auto-goal/scripts/goal_constructor.py')
kernel=load('kernel_probes',SRC/'host-services/goal-kernel/server.py')
Test=testmod.GoalKernelVNextTests
results=[]

def record(id,observation,confirmed):
    results.append(dict(id=id,observation=observation,observed=bool(confirmed)))

def fresh():
    body=Test.goal_body(vnext=True)
    status,res=Test.request('POST','/v1/goals',body,agent='operator')
    assert status==201,res
    return res['goal']['id']

def post(g,action,body,agent='implementer'):
    return Test.request('POST',f'/v1/goals/{g}/{action}',body,agent=agent)

Test.setUpClass()
try:
    # Ordinary documented new-style legacy payload is not constructor-v1.
    code,res=Test.request('POST','/v1/goals',{'goal':'Audit legacy creation with no criteria'},agent='operator')
    g=res['goal']['id'];v,out=post(g,'verify',{'passed':True},agent='')
    record('AG01',{'create_http':code,'constructor_present':'x_constructor' in res['goal'],'verify_without_identity_http':v,'status':out.get('goal',{}).get('status')},v==200 and out['goal']['status']=='VERIFIED')

    g=fresh();code,res=post(g,'increment',{'step':'Audit incomplete increment contract','capability':'repo-read','criterion':'DOES_NOT_EXIST','contract':'not an object'})
    record('AG02',{'http':code,'criterion':res.get('increment',{}).get('criterion'),'contract':res.get('increment',{}).get('contract')},code==200)

    g=fresh();a,_=post(g,'checkpoint',{'note':'same completed delivery'});b,res=post(g,'checkpoint',{'note':'same completed delivery'})
    record('AG03',{'first_http':a,'repeated_http':b,'stop':res.get('stop')},a==200 and b==409 and res.get('stop')=='STAGNATION_REPLAN_REQUIRED')

    g=fresh()
    for cid in ['C01','C02']:
        code,res=post(g,f'criteria/{cid}',{'status':'PASS','evidence':['a claim without a document or measurement']});assert code==200
    _,view=Test.request('GET',f'/v1/goals/{g}/context?role=verifier')
    projected=view.get('context_state',{})
    text=compiler.render_context(projected,'verifier')
    record('AG04',{'goal_status':projected.get('status'),'default_verifier_criteria':projected.get('criteria'),'current_criterion_none':'CURRENT CRITERION: none' in text,'current_evidence_none':'CURRENT EVIDENCE:\n- none' in text},projected.get('criteria')==[])
    (BASE/'verifier_empty_context.txt').write_text(text)
    v,out=post(g,'verify',{'passed':True,'note':'accepted without additional artifact receipt'},agent='another-identity')
    record('AG05',{'http':v,'status':out.get('goal',{}).get('status'),'input_evidence':'a claim without a document or measurement'},v==200)

    manifest=json.loads((SRC/'.cursor/skills/auto-goal/examples/software-change.json').read_text())
    compiled=compiler.compile_manifest(manifest)
    original_digest=compiled['x_constructor']['manifest_digest']
    compiled['goal']='Changed goal with retained original digest'
    compiled['criteria'][0]['description']='Changed acceptance while retaining original digest'
    code,res=Test.request('POST','/v1/goals',compiled,agent='operator')
    record('AG06',{'http':code,'digest_unchanged':res.get('goal',{}).get('x_constructor',{}).get('manifest_digest')==original_digest,'goal_changed':res.get('goal',{}).get('goal')==compiled['goal']},code==201)

    m=copy.deepcopy(manifest);m['approvals']=['unused-approval']
    try:
        compiler.compile_manifest(m)
    except compiler.ManifestError as error:
        record('AG07',{'classification':'positive_control','rejected':str(error)},'unused approval' in str(error))
    else:
        record('AG07',{'classification':'positive_control','rejected':False},False)

    g=fresh();evidence=[f'evidence-{i:02d}' for i in range(9)]
    post(g,'criteria/C01',{'status':'UNKNOWN','evidence':evidence})
    _,res=Test.request('GET',f'/v1/goals/{g}/context?role=verifier&criterion=C01')
    c=res['context_state']['criteria'][0]
    record('AG08',{'stored_count':9,'projected_count':len(c['evidence']),'last_evidence_present':'evidence-08' in c['evidence'],'has_truncation_marker':any('trunc' in k or 'more' in k or 'total' in k for k in c)},len(c['evidence'])==8 and 'evidence-08' not in c['evidence'])

    g=fresh()
    for cid in ['C01','C02']:post(g,f'criteria/{cid}',{'status':'PASS','evidence':['test receipt for '+cid]})
    fail_code,f=post(g,'verify',{'passed':False,'note':'Critical result does not satisfy acceptance'},agent='reviewer-one')
    pass_code,p=post(g,'verify',{'passed':True,'note':'Accept same criteria without resolving rejection'},agent='reviewer-two')
    record('AG09',{'rejection_http':fail_code,'status_after_rejection':f['goal']['status'],'retry_http':pass_code,'final_status':p['goal']['status']},pass_code==200 and p['goal']['status']=='VERIFIED')

    g=fresh();code,res=post(g,'increment',{'step':'Researcher claims implementation authority','capability':'repo-read','criterion':'C01'},agent='researcher-not-in-roster')
    record('AG10',{'http':code,'actor':res.get('increment',{}).get('agent'),'capability':res.get('increment',{}).get('capability')},code==200)

    # Same process, deterministic lost-update demonstration. It does not run two daemons.
    with tempfile.TemporaryDirectory() as tmp:
        kernel.DATA=Path(tmp)
        goal=kernel._new_goal(Test.goal_body(vnext=True),creator='operator');kernel._save(goal)
        reader_a=kernel._load(goal['id']);reader_b=kernel._load(goal['id'])
        reader_a['notes'].append('writer-A-update');kernel._save(reader_a)
        reader_b['notes'].append('writer-B-update');kernel._save(reader_b)
        final=kernel._load(goal['id'])
        record('AG11',{'final_notes':final['notes'],'optimistic_revision_field':'revision' in final},'writer-A-update' not in final['notes'])

    # New research evidence can still pause a run if no coarse criterion has passed.
    g=fresh();stops=[]
    for i in range(2):
        _,inc=post(g,'increment',{'step':f'Resolve relevant scientific question {i}','capability':'repo-read','criterion':'C01'})
        post(g,'evidence',{'increment_id':inc['increment']['id'],'evidence':f'new-independent-result-{i}'})
        code,res=post(g,'checkpoint',{'note':f'New evidence wave {i}'})
        stops.append({'http':code,'evidence_gain':res['checkpoint']['evidence_gain'],'meaningful':res['checkpoint']['meaningful'],'stop':res['stop']})
    record('AG12',{'checkpoints':stops},stops[-1]['http']==409)

    research=compiler.compile_manifest(json.loads((SRC/'examples/manifests/research.json').read_text()))
    _,created=Test.request('POST','/v1/goals',research,agent='operator');g=created['goal']['id']
    code,res=post(g,'increment',{'step':'Use capability from general profile example','capability':'web-search','criterion':'C01'})
    record('AG13',{'profile_example_capability':'web-search','catalog_has_capability':any('web-search' in m.get('capabilities',[]) for m in testmod.CATALOG['modules'].values()),'http':code,'error':res.get('error')},code==403)

    post(g,'criteria/C01',{'status':'PASS','evidence':['primary sources checked']},agent='researcher')
    _,updated=post(g,'criteria/C02',{'status':'PASS','evidence':['independent reproduction receipt']},agent='verifier')
    code,res=post(g,'verify',{'passed':True,'note':'Final acceptance by the designated verifier'},agent='verifier')
    record('AG14',{'example_C02_role':research['criteria'][1]['role'],'status_after_C02':updated['goal']['status'],'final_verify_http':code,'error':res.get('error')},code==403)
finally:
    Test.tearDownClass()

(BASE/'probe_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False,indent=2))
assert all(r['observed'] for r in results),'One proposed finding did not reproduce; inspect results.'
