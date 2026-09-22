#!/usr/bin/env python3
"""Create a resumable .venture-lab v1.2.1 workspace and run skeleton."""
from __future__ import annotations
import argparse, json, shutil
from datetime import datetime, timezone
from pathlib import Path

SKILL_VERSION="1.2.1"; SCHEMA_VERSION="1.2.1"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--slug",required=True)
    ap.add_argument("--workspace",default=".venture-lab")
    ap.add_argument("--profile",type=Path)
    ap.add_argument("--mode",default="DISCOVER")
    ap.add_argument("--depth",default="STANDARD")
    ap.add_argument("--objective",choices=["balanced","cashflow","venture"],default="balanced")
    ap.add_argument("--archetype",choices=["commercial","internal","devtool-oss","noncommercial"],default="commercial")
    ap.add_argument("--decision-deadline",default=None,help="optional ISO/text deadline copied into run metadata")
    args=ap.parse_args()
    ws=Path(args.workspace); run=ws/"runs"/args.slug; run.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    files={
      "frame.md":"# Decision Frame\n\n",
      "evidence.jsonl":"",
      "candidates.json":"{\n  \"candidates\": []\n}\n",
      "claims.json":"{\n  \"claims\": []\n}\n",
      "research-notes.md":"# Research Notes\n\n",
      "decision.md":"# Decision\n\n",
      "experiments.md":"# Experiments\n\n",
    }
    for name,content in files.items():
        p=run/name
        if not p.exists(): p.write_text(content,encoding="utf-8")
    manifest=run/"run.json"
    if not manifest.exists():
        manifest.write_text(json.dumps({
            "schema_version":SCHEMA_VERSION,"skill_version":SKILL_VERSION,"slug":args.slug,
            "mode":args.mode.upper(),"depth":args.depth.upper(),"objective_profile":args.objective,
            "business_archetype":args.archetype,"decision_deadline":args.decision_deadline,
            "created_at":now,"updated_at":now,"current_node":"frame"
        },indent=2)+"\n",encoding="utf-8")
    gp=ws/"founder-profile.md"
    if not gp.exists() and args.profile and args.profile.exists(): shutil.copyfile(args.profile,gp)
    print(run.resolve()); return 0
if __name__=="__main__": raise SystemExit(main())
