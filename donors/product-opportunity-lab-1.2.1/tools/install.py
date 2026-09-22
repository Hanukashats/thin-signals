#!/usr/bin/env python3
"""Safely install this skill into a supported Agent Skills directory."""
from __future__ import annotations
import argparse, os, shutil, tempfile
from datetime import datetime
from pathlib import Path


def default_dest(host):
    home=Path.home()
    if host=="hermes": return home/".hermes"/"skills"
    if host=="codex": return Path(os.environ.get("CODEX_HOME", home/".codex"))/"skills"
    if host=="claude": return home/".claude"/"skills"
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--host",choices=["hermes","codex","claude","generic"],default="hermes"); ap.add_argument("--dest",type=Path); ap.add_argument("--replace",action="store_true",help="replace existing install after creating a backup"); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args()
    src=Path(__file__).resolve().parents[1]/"skills"/"product-opportunity-lab"
    base=(args.dest.expanduser() if args.dest else default_dest(args.host))
    if base is None: ap.error("--dest is required for generic host")
    target=base/src.name
    print(f"Source: {src}\nTarget: {target}")
    if args.dry_run: return 0
    base.mkdir(parents=True,exist_ok=True)
    if target.is_symlink(): raise SystemExit(f"Refusing to replace symlink target: {target}")
    backup=None
    if target.exists():
        if not args.replace: raise SystemExit(f"Target exists: {target}. Use --replace to back it up and replace it.")
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup=base/f"{src.name}.backup-{stamp}"
        target.rename(backup)
    tmp=Path(tempfile.mkdtemp(prefix=f".{src.name}-",dir=base))
    try:
        staged=tmp/src.name; shutil.copytree(src,staged)
        staged.rename(target)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True)
        if backup and not target.exists() and backup.exists(): backup.rename(target)
        raise
    finally:
        shutil.rmtree(tmp,ignore_errors=True)
    print(f"Installed {src.name} -> {target}")
    if backup: print(f"Previous install backed up -> {backup}")
    print("Refresh/restart the agent session so the host re-discovers skills.")
    return 0
if __name__=="__main__": raise SystemExit(main())
