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


def cmd_eval(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ts.eval import load_negatives, load_positives, read_organizer, run_eval
    from ts.extract import Extractor
    from ts.llm import OpenRouterClient
    from ts.scoring.scorer import load_rules
    from ts.settings import load

    s = load()
    rules = load_rules(args.rules)
    positives = read_organizer(Path(args.positives)) if args.positives else load_positives()
    negatives = read_organizer(Path(args.negatives), label_default="mature") if args.negatives else load_negatives()
    if args.limit:
        positives, negatives = positives[: args.limit], negatives[: args.limit]
    ex = Extractor(OpenRouterClient(s), model=args.model or s.llm_primary, mode=args.mode, rules=rules)
    summary = run_eval(ex, positives, negatives, rules, workers=args.workers)
    print(json.dumps({k: summary[k] for k in ("holdout", "overall", "calibration", "confusion_3way", "errors", "out_dir")},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    import httpx

    from ts.harness import Harness
    from ts.settings import load
    from ts.sources.connectors import (
        ArxivConnector,
        CrossrefConnector,
        GithubConnector,
        OpenAlexConnector,
        SearxConnector,
    )

    s = load()
    if s.product_mode and args.extract:
        print(json.dumps({
            "error": "product_mode",
            "why": "В режиме сдачи OpenRouter выключен: нужен отдельный разрешённый шлюз. Сейчас извлечение только в лабораторном режиме.",
        }, ensure_ascii=False))
        return 2

    def get(url: str) -> str:
        response = httpx.get(url, timeout=40, follow_redirects=True, headers={"User-Agent": "thin-signals/0.1"})
        response.raise_for_status()
        return response.text

    connectors = []
    if s.searxng_url:
        connectors.append(SearxConnector(s.searxng_url, get))
    connectors += [ArxivConnector(get), OpenAlexConnector(get), CrossrefConnector(get), GithubConnector(get)]
    extractor = None
    if args.extract:
        from ts.extract import Extractor
        from ts.llm import OpenRouterClient
        extractor = Extractor(OpenRouterClient(s), model=args.model or s.llm_primary, mode="ledger")
    report = Harness(rules_version=s.rules_version, snapshot_dir=s.snapshot_dir).run(
        args.query, connectors, limit=args.limit, extractor=extractor, fetch_body=get if args.snapshot else None,
    )
    print(json.dumps({
        "id": report.id, "repeated": report.repeated, "model_id": report.model_id, "provider": report.provider,
        "steps": report.steps, "sources": len(report.sources), "events": len(report.events),
        "label": report.card["label"], "policy_action": report.card["policy_action"],
        "policy_reason": report.card["policy_reason"], "top": len(report.top), "shortfall": report.shortfall,
        "excluded": len(report.exclusion_registry),
        "planned_not_deployment": report.card["planned_not_deployment"],
    }, ensure_ascii=False, indent=1))
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

    ev = sub.add_parser("eval", help="P/R/F1 on positives + negatives (EV-01..03)")
    ev.add_argument("--positives", help="organizer XLSX/CSV/JSON (default data/dataset_patterns_100.json)")
    ev.add_argument("--negatives", help="JSON/CSV with label column (default data/negatives_v1.json)")
    ev.add_argument("--rules", default="rules-0.1")
    ev.add_argument("--mode", default="description", choices=["description", "ledger"])
    ev.add_argument("--model")
    ev.add_argument("--workers", type=int, default=4)
    ev.add_argument("--limit", type=int)
    ev.set_defaults(fn=cmd_eval)

    run = sub.add_parser("run", help="live query: search, dedup, countersearch, rank")
    run.add_argument("--query", required=True)
    run.add_argument("--limit", type=int, default=3)
    run.add_argument("--extract", action="store_true", help="ledger extraction via allowlisted OpenRouter model")
    run.add_argument("--model")
    run.add_argument("--snapshot", action="store_true")
    run.set_defaults(fn=cmd_run)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
