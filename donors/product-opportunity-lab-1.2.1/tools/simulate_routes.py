#!/usr/bin/env python3
"""Development-only regression simulator for Product Opportunity Lab v1.2.1 routing.

This is not a market-validation model. It checks that the documented shortcut policy
produces the intended control-flow for representative scenarios.
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def route(s):
    p=["FRAME"]
    mode=s.get("mode","VALIDATE")
    stakes=s.get("stakes","MEDIUM")
    commercial=s.get("commercial","commercial")
    readiness=int(str(s.get("readiness","R1")).replace("R",""))

    if s.get("decision_deadline") and s.get("info_improvement_unavailable"):
        p.append("FORCE_DECISION")
        return p,"PROVISIONAL_OPTION_PRESERVING_DECISION"

    if s.get("cheap_dependency"):
        p.append("DEPENDENCY_PREFLIGHT")
        if s.get("dependency_result")=="FAIL":
            return p,"KILL_OR_PIVOT"

    if mode in {"DISCOVER","SCAN"} and not s.get("known_buyer") and not s.get("strong_commitment"):
        p.append("BROAD_DISCOVERY")
        if s.get("speculative_lane"):
            p.append("SPECULATIVE_E0")
    if s.get("problem_e",0)<2 and not s.get("known_buyer"):
        p.append("PAIN_JTBD")
    if s.get("trend_material"):
        p.append("TREND_WHY_NOW")

    if commercial=="internal":
        p += ["INTERNAL_ROI_ADOPTION"]
    elif commercial=="noncommercial":
        p += ["USEFULNESS_ADOPTION"]
    else:
        if s.get("competitor_material") or s.get("request_build") or readiness>=3:
            p.append("STATUS_QUO_COMPETITION")
        if s.get("failure_material"):
            p.append("FAILURE_ARCHAEOLOGY")
        if s.get("economics_material") or s.get("request_build") or readiness>=3:
            p.append("ECONOMICS")
        if s.get("market_ceiling_material"):
            p.append("MARKET_CEILING")
        if not s.get("distribution_known",False):
            p.append("DISTRIBUTION")

    if s.get("feasibility_material") or stakes=="HIGH" or s.get("request_build"):
        p.append("FEASIBILITY_TRUST")
    if s.get("solution_choice_open") and s.get("solution_risk"):
        p.append("SOLUTION_COMPARE")

    p.append("EVALUATE")

    if s.get("hard_fail"):
        return p,"KILL_OR_PIVOT"
    if s.get("info_inaccessible"):
        return p,"HOLD"

    if s.get("research_stalled"):
        if s.get("real_test_available"):
            p.append("DIRECT_TEST")
            return p,"EXPERIMENTAL_BUILD_OR_VALIDATE"
        return p,"HOLD"

    if stakes=="HIGH" and (s.get("request_build") or readiness>=4):
        p.append("INDEPENDENT_RED_TEAM")
    elif s.get("falsification_needed",True):
        p.append("FALSIFICATION_PASS")

    if s.get("decision_stable"):
        return p,s.get("stable_action","DECIDE")

    if s.get("strong_commitment") and readiness>=4 and s.get("request_build"):
        return p,"PRODUCTION_BUILD"
    if s.get("strong_commitment") and readiness>=3:
        return p,"FOCUSED_R3_R4_DILIGENCE"

    if s.get("real_test_available") and readiness<=3:
        p.append("DIRECT_TEST")
        return p,"EXPERIMENTAL_BUILD_OR_VALIDATE"

    if s.get("request_build"):
        if s.get("explicit_override"):
            return p,"BUILD_WITH_RISK_DEBT"
        if readiness>=4:
            return p,"PRODUCTION_BUILD"
        if readiness>=3:
            return p,"EXPERIMENTAL_BUILD"
        return p,"VALIDATE"

    if mode=="DISCOVER" and s.get("shortlist_only"):
        return p,"SHORTLIST"
    return p,{0:"THESIS",1:"RESEARCH",2:"VALIDATE",3:"EXPERIMENTAL_BUILD",4:"PRODUCTION_CANDIDATE"}[readiness]


def main():
    path=Path(sys.argv[1] if len(sys.argv)>1 else "tests/route_scenarios.json")
    data=json.loads(path.read_text())
    failures=[]
    for s in data:
        p,t=route(s)
        for x in s.get("must_include",[]):
            if x not in p: failures.append(f"{s['id']}: missing {x}; path={p}")
        for x in s.get("must_exclude",[]):
            if x in p: failures.append(f"{s['id']}: should exclude {x}; path={p}")
        if t!=s["terminal"]: failures.append(f"{s['id']}: terminal {t} != {s['terminal']}; path={p}")
        print(f"{s['id']}: {' -> '.join(p)} => {t}")
    if failures:
        print("\nFAILURES:")
        for f in failures: print("-",f)
        return 1
    print(f"\nPASS: {len(data)} adaptive routing scenarios")
    return 0

if __name__=="__main__": raise SystemExit(main())
