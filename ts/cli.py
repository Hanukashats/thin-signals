"""`ts` CLI — W1: db, seed, llm. W2 adds `eval`, W3 `run`."""
from __future__ import annotations

import argparse
import json
import sys


def cmd_db(args: argparse.Namespace) -> int:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    if args.action == "upgrade":
        command.upgrade(cfg, args.revision)
    elif args.action == "downgrade":
        command.downgrade(cfg, args.revision)
    elif args.action == "current":
        command.current(cfg, verbose=True)
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ts.db import session_factory
    from ts.seed import SEED_FILE, import_seed, rows, to_candidate

    if args.action == "check":
        cands = [to_candidate(r) for r in rows(Path(args.file or SEED_FILE))]
        print(json.dumps({"rows": len(cands), "unique_ids": len({c["id"] for c in cands}),
                          "with_sources": sum(1 for c in cands if c["source_urls"])}, ensure_ascii=False))
        return 0
    with session_factory()() as s:
        print(json.dumps(import_seed(s, Path(args.file or SEED_FILE)), ensure_ascii=False))
    return 0


def cmd_llm(args: argparse.Namespace) -> int:
    from ts.llm import OpenRouterClient
    from ts.settings import load

    s = load()
    c = OpenRouterClient(s)
    if args.action == "zdr-check":
        reg = c.zdr_providers(force=True)
        out = {m: sorted(reg.get(m, [])) for m in s.allowed_models}
        print(json.dumps({"policy": s.llm_provider_policy, "allowed_models_zdr_providers": out}, ensure_ascii=False, indent=1))
        return 0 if all(out.values()) else 1
    r = c.probe(args.model)
    print(json.dumps({"model_id": r.model_id, "provider": r.provider, "content": r.content,
                      "usage": r.usage, "latency_s": r.latency_s}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ts", description="Thin Signals harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    db = sub.add_parser("db", help="alembic migrations")
    db.add_argument("action", choices=["upgrade", "downgrade", "current"])
    db.add_argument("revision", nargs="?", default="head")
    db.set_defaults(fn=cmd_db)

    seed = sub.add_parser("seed", help="organizer dataset -> candidates(seed_unverified)")
    seed.add_argument("action", choices=["import", "check"])
    seed.add_argument("--file")
    seed.set_defaults(fn=cmd_seed)

    llm = sub.add_parser("llm", help="OpenRouter ZDR client")
    llm.add_argument("action", choices=["probe", "zdr-check"])
    llm.add_argument("--model")
    llm.set_defaults(fn=cmd_llm)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
