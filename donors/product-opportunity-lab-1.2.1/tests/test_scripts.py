#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/"skills"/"product-opportunity-lab"

def run(*args): return subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True)

def main():
    # Structural + portable/Codex-common-denominator frontmatter validation.
    for target in ("portable","agentskills","codex","all"):
        v=run(REPO/"tools"/"validate_skill.py","--target",target)
        assert v.returncode==0, v.stdout+v.stderr

    s=run(ROOT/"scripts"/"score_opportunities.py",REPO/"tests"/"sample_opportunities.json")
    assert s.returncode==0, s.stdout+s.stderr
    rows=json.loads(s.stdout); byid={r["id"]:r for r in rows}
    assert byid["strong-b2b"]["readiness"]=="R4"
    assert byid["interesting-unproven"]["readiness"]=="R2"
    assert byid["interesting-unproven"]["quality"] > 70
    assert byid["weak-consumer"]["next_action"]=="KILL_OR_PIVOT"
    # P0 regression: internal/OSS readiness must not require external WTP.
    assert byid["internal-strong"]["readiness"]=="R4", byid["internal-strong"]
    assert byid["oss-strong"]["readiness"]=="R4", byid["oss-strong"]
    # P0 regression: weak/unverified negative signal must be verified, not terminal-killed.
    assert byid["weak-unverified-fail"]["readiness"]=="R1"
    assert byid["weak-unverified-fail"]["next_action"]=="VERIFY_GATE_BEFORE_COMMITMENT"
    # P0 regression: weak durability alone must not hard-kill a cashflow opportunity.
    assert byid["cashflow-low-durability"]["readiness"]=="R4"

    md=run(ROOT/"scripts"/"score_opportunities.py",REPO/"tests"/"compare_opportunities.json","--markdown")
    assert md.returncode==0, md.stdout+md.stderr
    assert "| Rank |" not in md.stdout
    assert "Quality/upside order:" in md.stdout and "Readiness/commitment order:" in md.stdout
    # Both candidates are non-dominated on quality/readiness axes.
    assert "Pareto front:" in md.stdout and "High Upside R2" in md.stdout and "Solid Proven R4" in md.stdout

    a=run(ROOT/"scripts"/"audit_evidence.py",REPO/"tests"/"sample_evidence.jsonl","--candidates",REPO/"tests"/"sample_opportunities.json")
    assert a.returncode==0, a.stdout+a.stderr
    assert "suggested_maturity" in a.stdout

    bad=run(ROOT/"scripts"/"audit_evidence.py",REPO/"tests"/"bad_job_commitment_evidence.jsonl")
    assert bad.returncode==1 and "should not by itself be tagged solution_commitment" in bad.stdout

    over=run(ROOT/"scripts"/"audit_evidence.py",REPO/"tests"/"bad_job_commitment_evidence.jsonl","--candidates",REPO/"tests"/"overclaim_candidates.json")
    assert over.returncode==1 and "solution_commitment" in over.stdout and "budget" in over.stdout

    # Workspace bootstrap records archetype and deadline without forcing a global profile.
    with tempfile.TemporaryDirectory() as td:
        ws=Path(td)/"venture"
        b=run(ROOT/"scripts"/"bootstrap.py","--slug","x","--workspace",ws,"--archetype","internal","--decision-deadline","today")
        assert b.returncode==0, b.stdout+b.stderr
        meta=json.loads((ws/"runs"/"x"/"run.json").read_text())
        assert meta["skill_version"]=="1.2.1" and meta["business_archetype"]=="internal" and meta["decision_deadline"]=="today"

    with tempfile.TemporaryDirectory() as td:
        base=Path(td)
        for host in ("hermes","codex","claude","generic"):
            dest=base/host/"skills"
            dry=run(REPO/"tools"/"install.py","--host",host,"--dest",dest,"--dry-run")
            assert dry.returncode==0 and "Target:" in dry.stdout
            ins=run(REPO/"tools"/"install.py","--host",host,"--dest",dest)
            assert ins.returncode==0 and (dest/ROOT.name/"SKILL.md").exists()
            assert not (dest/ROOT.name/"tests").exists()
            assert not (dest/ROOT.name/"scripts"/"install.py").exists()
            rep=run(REPO/"tools"/"install.py","--host",host,"--dest",dest,"--replace")
            assert rep.returncode==0 and "backed up" in rep.stdout

    r=run(REPO/"tools"/"simulate_routes.py",REPO/"tests"/"route_scenarios.json")
    assert r.returncode==0 and "PASS: 20 adaptive routing scenarios" in r.stdout, r.stdout+r.stderr

    print("OK: all v1.2.1 deterministic/structural tests passed")
if __name__=="__main__": main()
