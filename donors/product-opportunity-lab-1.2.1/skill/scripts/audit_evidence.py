#!/usr/bin/env python3
"""Audit a Product Opportunity Lab v1.2.1 JSONL evidence ledger.

Checks structure, claim coverage, counterevidence, independence, archetype-aware
requirements, common semantic mistakes, and suggests conservative evidence maturity.
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter, defaultdict
from pathlib import Path

REQ={"id","claim","claim_kind","stance","signal_for","evidence_type","source_ref","source_family","independence_key","observed_at"}
KINDS={"OBSERVED","INFERRED","PROJECTED"}; STANCES={"support","rebut","neutral"}
SIGNALS={"problem","budget","switching","distribution","feasibility_trust","solution_commitment","retention","market","competitor"}
NON_SOLUTION_COMMITMENT_TYPES={"job_posting","gig_posting","rfp","existing_spend","invoice","labor_budget"}
COMMITMENT_TYPES={"paid_pilot","deposit","preorder","contract","purchase_order","procurement_step","paid_concierge","sponsor_commitment","internal_deployment_commitment","maintainer_commitment","integration_commitment"}
TARGET_TYPES={"transaction","renewal","paid_usage","production_use","retained_use","repeat_purchase","active_internal_use","repeated_external_use"}
OBSERVED_DIRECT_TYPES={"observed_workflow","workflow_observation","usage_log","existing_spend","invoice","primary_documentation","customer_interview","past_behavior_interview","support_ticket","directory","job_posting","gig_posting","rfp"}
PROX_ORDER={"directional":1,"observed":2,"commitment":3,"target_behavior":4}


def load_candidates(path):
    if not path or not path.exists(): return {},{}
    data=json.loads(path.read_text(encoding="utf-8")); cs=data.get("candidates",[]) if isinstance(data,dict) else data
    return {c.get("id"):c for c in cs}, {c.get("id"):c.get("business_archetype","commercial") for c in cs}


def critical_for(archetype):
    if archetype=="commercial":
        return ["problem","budget","switching","distribution","feasibility_trust","solution_commitment"]
    return ["problem","distribution","feasibility_trust","solution_commitment","retention"]


def suggested_level(rs, signal):
    support=[r for r in rs if r.get("stance")=="support" and signal in r.get("signal_for",[])]
    if not support: return 0,0
    # low segment match cannot on its own justify strong maturity
    eligible=[r for r in support if str(r.get("segment_match","unknown")).lower()!="low"] or support
    origins={r.get("independence_key") for r in eligible if r.get("independence_key")}
    if any(str(r.get("evidence_type","")).lower() in TARGET_TYPES or str(r.get("proximity","")).lower()=="target_behavior" for r in eligible):
        return 4,len(origins)
    if any(str(r.get("evidence_type","")).lower() in COMMITMENT_TYPES or str(r.get("proximity","")).lower()=="commitment" for r in eligible):
        return 3,len(origins)
    observed=[r for r in eligible if r.get("claim_kind")=="OBSERVED" or str(r.get("evidence_type","")).lower() in OBSERVED_DIRECT_TYPES or str(r.get("proximity","")).lower()=="observed"]
    observed_origins={r.get("independence_key") for r in observed if r.get("independence_key")}
    # One direct primary artifact or two independent observations can support E2.
    if len(observed_origins)>=2 or any(str(r.get("evidence_type","")).lower() in {"usage_log","existing_spend","invoice","primary_documentation","production_use"} for r in observed):
        return 2,len(origins)
    return 1,len(origins)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("ledger",type=Path); ap.add_argument("--candidates",type=Path); args=ap.parse_args()
    if not args.ledger.exists(): print(f"ERROR: missing {args.ledger}",file=sys.stderr); return 2
    candidates, archetypes=load_candidates(args.candidates)
    rows=[]; errors=[]; warnings=[]; seen_ids=set()
    for n,line in enumerate(args.ledger.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        try: r=json.loads(line)
        except json.JSONDecodeError as e: errors.append(f"line {n}: invalid JSON: {e}"); continue
        miss=REQ-r.keys()
        if miss: errors.append(f"line {n}: missing {sorted(miss)}")
        if r.get("id") in seen_ids: errors.append(f"line {n}: duplicate id {r.get('id')}")
        seen_ids.add(r.get("id"))
        if r.get("claim_kind") not in KINDS: errors.append(f"line {n}: bad claim_kind")
        if r.get("stance") not in STANCES: errors.append(f"line {n}: bad stance")
        sf=r.get("signal_for",[])
        if not isinstance(sf,list) or not sf: errors.append(f"line {n}: signal_for must be non-empty list")
        elif any(x not in SIGNALS for x in sf): errors.append(f"line {n}: bad signal_for value")
        et=str(r.get("evidence_type","")).lower()
        if et in NON_SOLUTION_COMMITMENT_TYPES and "solution_commitment" in sf:
            warnings.append(f"line {n}: {et} should not by itself be tagged solution_commitment")
        prox=r.get("proximity")
        if prox is not None and prox not in PROX_ORDER:
            errors.append(f"line {n}: bad proximity {prox}")
        if r.get("segment_match") not in (None,"high","medium","low","unknown"):
            errors.append(f"line {n}: bad segment_match")
        if r.get("sample_n") is not None and (not isinstance(r.get("sample_n"),int) or r.get("sample_n")<1):
            errors.append(f"line {n}: sample_n must be positive integer")
        rows.append(r)

    bycand=defaultdict(list)
    for r in rows: bycand[r.get("candidate_id") or "__market__"].append(r)

    print(f"Records: {len(rows)} | Structural errors: {len(errors)}")
    for e in errors: print("ERROR:",e)

    summaries={}
    for cid,rs in bycand.items():
        origins={r.get("independence_key") for r in rs if r.get("independence_key")}
        fams={r.get("source_family") for r in rs if r.get("source_family")}
        st=Counter(r.get("stance") for r in rs); kinds=Counter(r.get("claim_kind") for r in rs)
        coverage=Counter()
        for r in rs:
            for sig in r.get("signal_for",[]): coverage[sig]+=1
        if len(origins)<2 and len(rs)>=2: warnings.append(f"{cid}: evidence has <2 independent origins")
        if st.get("rebut",0)==0: warnings.append(f"{cid}: no counterevidence/rebut records")
        if kinds.get("INFERRED",0)+kinds.get("PROJECTED",0) > kinds.get("OBSERVED",0): warnings.append(f"{cid}: inference/projection exceeds observed records")
        arch=archetypes.get(cid,"commercial")
        if cid!="__market__":
            for sig in critical_for(arch):
                if coverage[sig]==0: warnings.append(f"{cid}: no evidence mapped to critical claim '{sig}' for archetype {arch}")
        maturity={}
        for sig in ["problem","budget","switching","distribution","feasibility_trust","solution_commitment","retention"]:
            lvl,norig=suggested_level(rs,sig); maturity[sig]={"level":f"E{lvl}","independent_origins":norig}
        summaries[cid]=maturity
        print(f"{cid}: archetype={arch} n={len(rs)} origins={len(origins)} families={len(fams)} support={st.get('support',0)} rebut={st.get('rebut',0)} observed={kinds.get('OBSERVED',0)}")
        print("  suggested_maturity: " + " ".join(f"{k}:{v['level']}(n={v['independent_origins']})" for k,v in maturity.items()))

    # Claimed-vs-suggested maturity cross-check. Conservative warnings only; the
    # suggestion is a sanity check, not a replacement for domain judgment.
    for cid,c in candidates.items():
        rs=bycand.get(cid,[])
        if not rs: continue
        claims=c.get("critical_claims",{}); sug=summaries.get(cid,{})
        for sig,claimed in claims.items():
            if sig not in sug: continue
            try: cl=int(str(claimed).upper().replace("E","")); sl=int(sug[sig]["level"][1])
            except Exception: continue
            if cl>sl+1:
                warnings.append(f"{cid}: claims {sig} {claimed} materially above ledger suggestion {sug[sig]['level']} (n={sug[sig]['independent_origins']})")
        arch=archetypes.get(cid,"commercial")
        # Commercial strong-budget/commitment claims need appropriate evidence types.
        if arch=="commercial":
            def lvl(k):
                try:return int(str(claims.get(k,"E0")).upper().replace("E",""))
                except:return 0
            if lvl("budget")>=3 and not any(str(r.get("evidence_type","")).lower() in (COMMITMENT_TYPES|TARGET_TYPES|{"existing_spend","invoice","labor_budget"}) and "budget" in r.get("signal_for",[]) for r in rs):
                warnings.append(f"{cid}: claims budget {claims.get('budget')} without recognized strong budget evidence")
            if lvl("solution_commitment")>=3 and not any(str(r.get("evidence_type","")).lower() in (COMMITMENT_TYPES|TARGET_TYPES) and "solution_commitment" in r.get("signal_for",[]) for r in rs):
                warnings.append(f"{cid}: claims solution_commitment {claims.get('solution_commitment')} without recognized target/commitment evidence")

    for w in warnings: print("WARNING:",w)
    if errors: return 2
    return 1 if warnings else 0

if __name__=="__main__": raise SystemExit(main())
