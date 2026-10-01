#!/usr/bin/env python3
"""Check LivingSet ID cross-links (requirements ↔ plan waves ↔ forks). Exit 1 on gaps."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def main() -> int:
    req = load_text("requirements.yaml")
    plan = load_text("plan.yaml")
    forks = load_text("forks.yaml")
    errors: list[str] = []

    req_ids = set(re.findall(r"(?m)^  - id: ([A-Z0-9-]+)", req))
    wave_ids = set(re.findall(r"(?m)^      - id: ([A-Za-z0-9-]+)", plan))
    fork_ids = set(re.findall(r"(?m)^  - id: ([A-Za-z0-9.]+)", forks))

    for wid in re.findall(r"wave: ([A-Za-z0-9-]+)", req):
        if wid not in wave_ids:
            errors.append(f"requirement wave missing in plan.yaml: {wid}")

    for fid in re.findall(r"forks: \[([^\]]*)\]", req):
        for part in fid.split(","):
            part = part.strip()
            if part and part not in fork_ids:
                errors.append(f"requirement fork unknown: {part}")

    for rid in re.findall(r"requirements: \[([^\]]*)\]", plan):
        for part in rid.split(","):
            part = part.strip()
            if part and part not in req_ids:
                errors.append(f"plan wave references unknown requirement: {part}")

    required_files = [
        "00_START_HERE_HANDOFF_RU.md",
        "CONCEPT.md",
        "ARCHITECTURE.md",
        "AGENTS.md",
        "STATUS.md",
        "plan.yaml",
        "forks.yaml",
        "requirements.yaml",
        "docs/EVOLUTION.md",
        "docs/adr/ADR-008-IMPL-PATH-SOURCECRAFT.md",
        "docs/adr/ADR-009-HARNESS-FIRST-7.2.md",
        "docs/plan/PLAN_7.2.md",
        "docs/METHODOLOGY.md",
        "donors/README.md",
        "docs/ops/SOURCECRAFT.md",
        "docs/ops/secrets.paths.yaml",
    ]
    for rel in required_files:
        if not (ROOT / rel).is_file():
            errors.append(f"missing LivingSet file: {rel}")

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print(
        f"OK requirements={len(req_ids)} waves={len(wave_ids)} forks={len(fork_ids)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
