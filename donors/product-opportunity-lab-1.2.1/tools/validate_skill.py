#!/usr/bin/env python3
"""Structural/host-compatibility validator for Product Opportunity Lab v1.2.1."""
from __future__ import annotations
import argparse, re
from pathlib import Path

PORTABLE_ALLOWED={"name","description"}
AGENTSKILLS_ALLOWED={"name","description","license","compatibility","metadata","allowed-tools"}
CODEX_ALLOWED={"name","description","license","metadata","allowed-tools"}


def frontmatter(text):
    m=re.match(r"^---\n(.*?)\n---\n",text,re.S)
    if not m: return None,None,"SKILL.md missing YAML frontmatter"
    block=m.group(1); keys=[]; vals={}; current=None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"): continue
        if not raw.startswith((" ","\t")) and ":" in raw:
            k,v=raw.split(":",1); current=k.strip(); keys.append(current); vals[current]=v.strip().strip('"\'')
        elif current=="description" and raw.startswith("  "):
            vals[current]=(vals.get(current,"")+" "+raw.strip()).strip()
    return keys,vals,None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--target",choices=["portable","agentskills","codex","all"],default="all"); args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]/"skills"/"product-opportunity-lab"; sk=root/"SKILL.md"; errors=[]
    text=sk.read_text(encoding="utf-8"); keys,fm,err=frontmatter(text)
    if err: errors.append(err); keys=[]; fm={}
    name=fm.get("name","").strip(); desc=fm.get("description","").replace(">-","").strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",name): errors.append(f"invalid name: {name}")
    if name!=root.name: errors.append(f"name must match directory: {name} != {root.name}")
    if len(name)>64: errors.append("name >64 chars")
    if not desc: errors.append("description missing/empty")
    if len(desc)>1024: errors.append(f"description >1024 chars ({len(desc)})")
    if any(ch in desc for ch in "<>"): errors.append("description contains angle bracket")
    target_sets=[]
    if args.target in ("portable","all"): target_sets.append(("portable",PORTABLE_ALLOWED))
    if args.target in ("agentskills","all"): target_sets.append(("agentskills",AGENTSKILLS_ALLOWED))
    if args.target in ("codex","all"): target_sets.append(("codex",CODEX_ALLOWED))
    for label,allowed in target_sets:
        unexpected=set(keys)-allowed
        if unexpected: errors.append(f"{label}: unexpected frontmatter keys: {sorted(unexpected)}")
    refs=re.findall(r"\]\(([^)]+)\)",text)
    for ref in refs:
        if ref.startswith(("http://","https://","#")): continue
        if not (root/ref).exists(): errors.append(f"missing referenced file: {ref}")
    for p in [root/"agents"/"openai.yaml",root/"references",root/"scripts",root/"assets",root/"LICENSE.txt"]:
        if not p.exists(): errors.append(f"missing expected resource: {p.relative_to(root)}")
    if len(text.splitlines())>500: errors.append("SKILL.md exceeds 500 lines")
    if errors:
        for e in errors: print("ERROR:",e)
        return 2
    print(f"OK: {root}")
    print(f"Targets: {args.target} | SKILL.md lines: {len(text.splitlines())} | description chars: {len(desc)}")
    return 0
if __name__=="__main__": raise SystemExit(main())
