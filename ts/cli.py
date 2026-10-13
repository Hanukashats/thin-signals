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
    from ts.live import run_query

    payload = run_query(args.query, limit=args.limit, extract=args.extract)
    print(json.dumps({
        "id": payload["run_id"], "repeated": payload["repeated"], "model_id": payload.get("model_id"),
        "run_status": payload["run_status"], "signal_label": payload["signal_label"],
        "sources": payload["counters"]["sources"], "events": payload["events"],
        "policy_action": payload["policy_action"], "policy_reason": payload["policy_reason"],
        "top": len(payload["top"]), "shortfall": payload["shortfall"],
        "excluded": len(payload["exclusion_registry"]),
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_review_eval(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ts.review.evaluation import write_review_evaluation

    summary = write_review_evaluation(Path(args.dataset), Path(args.out))
    print(json.dumps({
        "dataset_digest": summary["dataset_digest"],
        "result_digest": summary["result_digest"],
        "replay": summary["metrics"]["replay"],
        "holdout": summary["metrics"]["holdout"],
        "out_dir": str(Path(args.out)),
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_score_replay(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ts.scoring.replay import write_scoring_replay

    summary = write_scoring_replay(Path(args.records), Path(args.out))
    print(json.dumps({
        "records_digest": summary["records_digest"],
        "result_digest": summary["result_digest"],
        "n": summary["n"],
        "changed_labels": summary["changed_labels"],
        "metrics": summary["metrics"],
        "out_dir": str(Path(args.out)),
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

    review_ev = sub.add_parser(
        "review-eval",
        help="deterministic replay/holdout/ablation evaluation for adversarial review",
    )
    review_ev.add_argument("--dataset", default="data/review_eval_v1.json")
    review_ev.add_argument("--out", default="reports/eval/review-2026-10-13")
    review_ev.set_defaults(fn=cmd_review_eval)

    score_replay = sub.add_parser(
        "score-replay",
        help="replay frozen scoring rows across rules-0.1 and rules-0.2",
    )
    score_replay.add_argument("--records", default="reports/eval/2026-09-23/records.jsonl")
    score_replay.add_argument("--out", default="reports/eval/rules-0.2-2026-10-13")
    score_replay.set_defaults(fn=cmd_score_replay)

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
