#!/usr/bin/env python3
"""Deterministically evaluate Product Opportunity Lab v1.2.1 candidates.

The helper keeps Opportunity Quality, gate state, evidence maturity, and Decision
Readiness separate. It intentionally does not emit one universal scalar rank.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

PILLARS = ["demand", "economics", "adoption", "execution", "timing_market", "durability"]
WEIGHT_PROFILES = {
    "balanced": {"demand":25,"economics":20,"adoption":20,"execution":15,"timing_market":10,"durability":10},
    "cashflow": {"demand":25,"economics":25,"adoption":20,"execution":15,"timing_market":5,"durability":10},
    "venture": {"demand":20,"economics":15,"adoption":15,"execution":10,"timing_market":20,"durability":20},
}
CLAIMS = ["problem","budget","switching","distribution","feasibility_trust","solution_commitment","retention"]
GATES = [f"G{i}" for i in range(1,8)]
ARCHETYPES = {"commercial","internal","devtool-oss","noncommercial"}
RORDER={"R0":0,"R1":1,"R2":2,"R3":3,"R4":4}


def load(path: Path):
    data=json.loads(path.read_text(encoding="utf-8"))
    return data.get("candidates", []) if isinstance(data, dict) else data


def norm_state(v):
    if v is True or str(v).lower()=="pass": return "PASS"
    if v is False or str(v).lower()=="fail": return "FAIL"
    return "UNKNOWN"


def gate_result(v):
    if isinstance(v,dict):
        return {
            "state":norm_state(v.get("state","unknown")),
            "confidence":str(v.get("confidence","unspecified")).lower(),
            "scope":str(v.get("scope","current_wedge")),
            "evidence_refs":list(v.get("evidence_refs",[]) or []),
            "note":str(v.get("note","") or ""),
        }
    return {"state":norm_state(v),"confidence":"unspecified","scope":"current_wedge","evidence_refs":[],"note":""}


def elevel(v):
    s=str(v).upper()
    if s not in {"E0","E1","E2","E3","E4"}: raise ValueError(f"bad evidence maturity {v}")
    return int(s[1])


def quality_score(pillars, profile):
    weights=WEIGHT_PROFILES[profile]
    vals={}
    for p in PILLARS:
        if p not in pillars: raise ValueError(f"missing pillar: {p}")
        x=float(pillars[p])
        if not 0 <= x <= 5: raise ValueError(f"pillar {p} outside 0..5: {x}")
        vals[p]=x
    return sum(weights[p] * vals[p] / 5.0 for p in PILLARS)


def fail_policy(gates):
    fails=[(g,r) for g,r in gates.items() if r["state"]=="FAIL"]
    if not fails: return None
    reliable=[(g,r) for g,r in fails if r["confidence"] in {"verified","supported"}]
    if reliable:
        return "TERMINAL_FAIL", [g for g,_ in reliable]
    return "VERIFY_FAIL", [g for g,_ in fails]


def commercial_readiness(c, all_pass):
    if all_pass and c["problem"]>=3 and c["budget"]>=3 and c["switching"]>=2 and c["distribution"]>=2 and c["feasibility_trust"]>=3 and c["solution_commitment"]>=3:
        return "R4", "PRODUCTION_BUILD_CANDIDATE"
    if c["problem"]>=2 and c["budget"]>=2 and c["switching"]>=1 and c["distribution"]>=2 and c["feasibility_trust"]>=2 and c["solution_commitment"]>=2:
        return "R3", "EXPERIMENTAL_BUILD_OR_STRONG_VALIDATION"
    if c["problem"]>=2 and c["budget"]>=1 and c["distribution"]>=1 and c["feasibility_trust"]>=1:
        return "R2", "VALIDATE"
    return None


def noncommercial_readiness(c, all_pass, archetype):
    # Internal/OSS/public-good readiness is about real problem, access/adoption,
    # deliverability, target use/commitment, and recurrence—not external WTP.
    if all_pass and c["problem"]>=3 and c["distribution"]>=2 and c["feasibility_trust"]>=3 and c["solution_commitment"]>=3 and c["retention"]>=2:
        action="PRODUCTION_DEPLOYMENT_CANDIDATE" if archetype=="internal" else "MATURE_RELEASE_OR_PRODUCTION_CANDIDATE"
        return "R4", action
    if c["problem"]>=2 and c["distribution"]>=2 and c["feasibility_trust"]>=2 and c["solution_commitment"]>=2:
        action="EXPERIMENTAL_DEPLOYMENT" if archetype=="internal" else "EXPERIMENTAL_BUILD_OR_ADOPTION_TEST"
        return "R3", action
    if c["problem"]>=2 and c["distribution"]>=1 and c["feasibility_trust"]>=1:
        return "R2", "VALIDATE_USEFULNESS_ADOPTION"
    return None


def readiness(gates, claims, archetype):
    fp=fail_policy(gates)
    if fp:
        kind, gs=fp
        if kind=="TERMINAL_FAIL": return "R0", "KILL_OR_PIVOT", gs
        return "R1", "VERIFY_GATE_BEFORE_COMMITMENT", gs
    c={k:elevel(claims[k]) for k in CLAIMS}
    all_pass=all(r["state"]=="PASS" for r in gates.values())
    result = commercial_readiness(c,all_pass) if archetype=="commercial" else noncommercial_readiness(c,all_pass,archetype)
    if result: return result[0],result[1],[]
    if any(v>=1 for v in c.values()) or any(r["state"]=="PASS" for r in gates.values()):
        return "R1", "RESEARCH", []
    return "R0", "THESIS_ONLY", []


def score_candidate(c):
    profile=c.get("objective_profile","balanced")
    if profile not in WEIGHT_PROFILES: raise ValueError(f"{c.get('id','?')}: bad objective_profile {profile}")
    archetype=c.get("business_archetype","commercial")
    if archetype not in ARCHETYPES: raise ValueError(f"{c.get('id','?')}: bad business_archetype {archetype}")
    gates={g:gate_result(c.get("gates",{}).get(g,"unknown")) for g in GATES}
    claims=c.get("critical_claims",{})
    missing=[k for k in CLAIMS if k not in claims]
    if missing: raise ValueError(f"{c.get('id','?')}: missing critical_claims: {', '.join(missing)}")
    for k in CLAIMS: elevel(claims[k])
    pillars=c.get("pillars",{})
    q=quality_score(pillars, profile)
    r, action, blocking=readiness(gates,claims,archetype)
    flags=[]
    if profile=="venture" and r=="R4":
        if float(pillars.get("durability",0))<3 or float(pillars.get("timing_market",0))<3:
            flags.append("VENTURE_THESIS_UNRESOLVED")
    return {
        "id":c.get("id"),"name":c.get("name",c.get("id")),"objective_profile":profile,"business_archetype":archetype,
        "quality":round(q,1),"pillars":pillars,"gates":gates,
        "critical_claims":{k:str(claims[k]).upper() for k in CLAIMS},
        "readiness":r,"next_action":action,"blocking_gates":blocking,"strategic_flags":flags,
    }


def pareto_mark(rows):
    for a in rows:
        aq=a["quality"]; ar=RORDER[a["readiness"]]
        a["pareto_front"]=not any(
            (b["quality"]>=aq and RORDER[b["readiness"]]>=ar and (b["quality"]>aq or RORDER[b["readiness"]]>ar))
            for b in rows if b is not a
        )


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path)
    ap.add_argument("--markdown",action="store_true")
    ap.add_argument("--order-by",choices=["input","quality","readiness"],default="input",help="presentation order only; does not create a universal rank")
    args=ap.parse_args()
    try: rows=[score_candidate(c) for c in load(args.input)]
    except (OSError,json.JSONDecodeError,ValueError,TypeError) as e:
        print(f"ERROR: {e}",file=sys.stderr); return 2
    pareto_mark(rows)
    quality_order=sorted(rows,key=lambda r:r["quality"],reverse=True)
    readiness_order=sorted(rows,key=lambda r:(RORDER[r["readiness"]],r["quality"]),reverse=True)
    if args.order_by=="quality": rows=quality_order
    elif args.order_by=="readiness": rows=readiness_order

    if args.markdown:
        print("| Candidate | Archetype | Quality | Readiness | Pareto | Evidence profile | Gates | Next action |")
        print("|---|---|---:|---|---|---|---|---|")
        for r in rows:
            ep=" ".join(f"{k[:3]}:{v}" for k,v in r["critical_claims"].items())
            gs=" ".join(f"{k}:{v['state'][0]}" for k,v in r["gates"].items())
            print(f"| {r['name']} | {r['business_archetype']} | {r['quality']:.1f} | {r['readiness']} | {'YES' if r['pareto_front'] else 'no'} | {ep} | {gs} | {r['next_action']} |")
        print("\nQuality/upside order: " + " > ".join(r["name"] for r in quality_order))
        print("Readiness/commitment order: " + " > ".join(r["name"] for r in readiness_order))
        print("Pareto front: " + ", ".join(r["name"] for r in rows if r["pareto_front"]))
    else:
        print(json.dumps(rows,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__": raise SystemExit(main())
