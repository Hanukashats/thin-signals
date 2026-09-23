"""`ts eval` — P/R/F1 of the logical model on organizer positives + negatives_v1 (EV-01..03, TZ-01/02).

Input adapter accepts the organizer format (XLSX/CSV/JSON with columns Технология / Область / Компании /
Источники, optional label column) and our JSON files. Contamination guard: only technology, domain,
companies reach the extractor — rationale/stage/trend/score never do.
Split: by semantic family (METHODOLOGY §9) → train/holdout; τ is calibrated on train, reported on holdout.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ts.extract import Extractor, to_feature_vector
from ts.scoring.scorer import FeatureVector, score

POSITIVE = "weak_signal"
# organizer XLSX header -> our field
ORGANIZER_COLUMNS = {
    "технология": "technology", "технология (слабый сигнал)": "technology", "technology": "technology",
    "область": "domain", "domain": "domain",
    "компании": "companies", "companies": "companies",
    "источники": "source_urls", "sources": "source_urls",
    "метка": "label", "label": "label", "класс": "label",
    "№": "dataset_id", "id": "dataset_id",
}
# semantic families among the 100 positives (dataset_id) — must not be split across train/holdout
FAMILIES = [(8, 45, 80), (44, 84), (18, 59), (47, 60), (19, 43, 82), (2, 50, 67, 69, 91), (46, 56, 75)]


@dataclass
class Item:
    id: str
    technology: str
    domain: str | None
    companies: str | None
    label: str                 # gold: weak_signal | watchlist | mature | noise
    family: str
    source: str                # positives | negatives
    hint_pattern: str | None = None   # dataset annotation, reporting only


# ---------------------------------------------------------------- adapters
def _norm(h: str) -> str:
    return " ".join(str(h).strip().lower().split())


def read_organizer(path: Path, label_default: str = POSITIVE, label_map: dict | None = None) -> list[Item]:
    rows: list[dict] = []
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        header = None
        for r in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in r]
            if header is None:
                if any(_norm(v) in ORGANIZER_COLUMNS for v in vals):
                    header = [ORGANIZER_COLUMNS.get(_norm(v), _norm(v)) for v in vals]
                continue
            if not any(vals):
                continue
            rows.append(dict(zip(header, vals)))
    elif path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append({ORGANIZER_COLUMNS.get(_norm(k), _norm(k)): v for k, v in r.items()})
    else:
        data = json.loads(path.read_text())
        rows = data["rows"] if isinstance(data, dict) and "rows" in data else data
        rows = [{ORGANIZER_COLUMNS.get(_norm(k), k): v for k, v in r.items()} for r in rows]
    items = []
    for i, r in enumerate(rows):
        tech = (r.get("technology") or "").strip()
        if not tech:
            continue
        raw_label = str(r.get("label") or label_default).strip().lower()
        label = (label_map or {}).get(raw_label, raw_label)
        did = str(r.get("dataset_id") or r.get("id") or i + 1)
        items.append(Item(id=did, technology=tech, domain=r.get("domain"), companies=r.get("companies"),
                          label=label, family=str(r.get("family") or did), source=str(path.name),
                          hint_pattern=r.get("primary_pattern")))
    return items


def load_positives(path: Path = Path("data/dataset_patterns_100.json")) -> list[Item]:
    items = read_organizer(path, label_default=POSITIVE)
    fam_of = {str(d): f"fam{fi}" for fi, fam in enumerate(FAMILIES) for d in fam}
    for it in items:
        it.family = fam_of.get(it.id, f"pos{it.id}")
        it.source = "positives"
    return items


def load_negatives(path: Path = Path("data/negatives_v1.json")) -> list[Item]:
    items = read_organizer(path, label_default="mature")
    for it in items:
        it.source = "negatives"
        it.family = f"neg-{it.family}"
    return items


def split(items: list[Item], seed: str = "ts-eval-v1") -> tuple[list[Item], list[Item]]:
    """Deterministic ~50/50 split by family: whole family goes to one side."""
    train, hold = [], []
    for it in items:
        h = int(hashlib.sha256(f"{seed}|{it.family}".encode()).hexdigest(), 16)
        (train if h % 2 == 0 else hold).append(it)
    return train, hold


# ---------------------------------------------------------------- metrics
def binary_metrics(pairs: list[tuple[str, str]]) -> dict:
    """pairs: (gold, pred) labels; positive = weak_signal."""
    tp = sum(1 for g, p in pairs if g == POSITIVE and p == POSITIVE)
    fp = sum(1 for g, p in pairs if g != POSITIVE and p == POSITIVE)
    fn = sum(1 for g, p in pairs if g == POSITIVE and p != POSITIVE)
    tn = sum(1 for g, p in pairs if g != POSITIVE and p != POSITIVE)
    n = len(pairs) or 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "accuracy": round((tp + tn) / n, 4),
            "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}


def label_at(conf: float | None, counter_label: str | None, tau: float, tau_watch: float) -> str:
    if counter_label:
        return counter_label
    if conf is None:
        return "noise"
    if conf >= tau:
        return POSITIVE
    return "watchlist" if conf >= tau_watch else "noise"


def calibrate_tau(records: list[dict], grid: tuple[float, ...] = tuple(round(x / 100, 2) for x in range(10, 80, 2))) -> dict:
    best = None
    for tau in grid:
        pairs = [(r["gold"], label_at(r["confidence"], r["counter_label"], tau, tau * 0.6)) for r in records]
        m = binary_metrics(pairs)
        key = (m["f1"], m["precision"])
        if best is None or key > best[0]:
            best = (key, tau, m)
    return {"tau": best[1], "tau_watchlist": round(best[1] * 0.6, 3), "train_metrics": best[2]}


# ---------------------------------------------------------------- run
def run_eval(extractor: Extractor, positives: list[Item], negatives: list[Item], rules: dict,
             workers: int = 4, out_dir: Path = Path("reports/eval")) -> dict:
    items = positives + negatives
    mode = extractor.mode

    def one(it: Item) -> dict:
        row = {"technology": it.technology, "domain": it.domain, "companies": it.companies}
        try:
            out, meta = extractor.extract(row)
        except Exception as e:  # noqa: BLE001 — keep going; failed extraction = unknown everything
            return {**asdict(it), "error": str(e)[:300], "confidence": None, "counter_label": None,
                    "pred_default": "noise", "primary_pattern": None, "predictors": [], "reason_codes": ["extract_error"]}
        fv: FeatureVector = to_feature_vector(out, mode, it.companies)
        res = score(fv, rules)
        counter_label = res.label if res.gate == "maturity" else None
        return {**asdict(it), "confidence": res.confidence, "counter_label": counter_label,
                "pred_default": res.label, "primary_pattern": fv.primary_pattern,
                "secondary_patterns": fv.secondary_patterns, "reason_codes": res.reason_codes,
                "predictors": res.predictors, "one_line_ru": out.get("one_line_ru"),
                "model_id": meta["model_id"], "provider": meta["provider"], "cached": meta["cached"],
                "latency_s": meta.get("latency_s")}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        records = list(ex.map(one, items))
    for r in records:
        r["gold"] = r["label"]

    train_ids = {it.id + it.source for it in split(items)[0]}
    train = [r for r in records if r["id"] + r["source"] in train_ids]
    hold = [r for r in records if r["id"] + r["source"] not in train_ids]
    cal = calibrate_tau(train)
    tau, tau_w = cal["tau"], cal["tau_watchlist"]
    for r in records:
        r["pred"] = label_at(r["confidence"], r["counter_label"], tau, tau_w)
        r["split"] = "train" if r["id"] + r["source"] in train_ids else "holdout"

    def metrics(rs):
        return binary_metrics([(r["gold"], r["pred"]) for r in rs])

    summary = {
        "date": datetime.now(tz=UTC).date().isoformat(), "rules_version": rules["version"], "mode": mode,
        "model": extractor.model, "prompt_version": "extract-v1",
        "n_positives": len(positives), "n_negatives": len(negatives),
        "calibration": {"tau": tau, "tau_watchlist": tau_w, "train": metrics(train)},
        "holdout": metrics(hold), "overall": metrics(records),
        "default_thresholds_overall": binary_metrics([(r["gold"], r["pred_default"]) for r in records]),
        "confusion_3way": dict(Counter(f"{r['gold']}->{r['pred']}" for r in records)),
        "errors": sum(1 for r in records if r.get("error")),
        "providers": dict(Counter(r.get("provider") for r in records)),
    }
    # per hint-pattern recall (positives only; hints are reporting-only)
    by_hint: dict[str, list] = defaultdict(list)
    for r in records:
        if r["source"] == "positives":
            by_hint[r.get("hint_pattern") or "?"].append(r["pred"] == POSITIVE)
    summary["recall_by_dataset_pattern"] = {k: {"n": len(v), "recall": round(sum(v) / len(v), 3)}
                                            for k, v in sorted(by_hint.items())}
    by_cat: dict[str, list] = defaultdict(list)
    for r in records:
        if r["source"] == "negatives":
            by_cat[r.get("label")].append(r["pred"] != POSITIVE)
    summary["specificity_by_negative_label"] = {k: {"n": len(v), "rate": round(sum(v) / len(v), 3)}
                                                for k, v in sorted(by_cat.items())}

    out_dir = out_dir / summary["date"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "records.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (out_dir / "report.md").write_text(render_report(summary, records))
    summary["out_dir"] = str(out_dir)
    return summary


def render_report(s: dict, records: list[dict]) -> str:
    def mt(m):
        return (f"n={m['n']} · acc **{m['accuracy']:.3f}** · P {m['precision']:.3f} · R {m['recall']:.3f} · "
                f"F1 **{m['f1']:.3f}** · TP {m['tp']} FP {m['fp']} FN {m['fn']} TN {m['tn']}")

    lines = [f"# ts eval — {s['date']} · {s['rules_version']} · mode `{s['mode']}` · {s['model']}", "",
             (f"Positives {s['n_positives']} (организаторы, только Технология/Область/Компании) + negatives {s['n_negatives']} (`data/negatives_v1.json`). "
              f"Split по семантическим семействам; τ калибруется на train, отчёт по holdout. Provider(s): {s['providers']}. Ошибок извлечения: {s['errors']}."), "",
             "| Срез | Метрики |", "|---|---|",
             f"| train (калибровка τ={s['calibration']['tau']}, watchlist≥{s['calibration']['tau_watchlist']}) | {mt(s['calibration']['train'])} |",
             f"| **holdout** | {mt(s['holdout'])} |",
             f"| overall | {mt(s['overall'])} |",
             f"| overall при τ из rules-файла (без калибровки) | {mt(s['default_thresholds_overall'])} |", "",
             "## Матрица 3-way (gold → pred)", "", "| переход | n |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(s["confusion_3way"].items())]
    lines += ["", "## Recall по паттерну разметки организаторов (hint — только для отчёта)", "", "| pattern | n | recall |", "|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['recall']:.2f} |" for k, v in s["recall_by_dataset_pattern"].items()]
    lines += ["", "## Доля правильно отклонённых негативов по классу", "", "| gold | n | не-weak_signal |", "|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['rate']:.2f} |" for k, v in s["specificity_by_negative_label"].items()]
    fn = [r for r in records if r["gold"] == POSITIVE and r["pred"] != POSITIVE]
    fp = [r for r in records if r["gold"] != POSITIVE and r["pred"] == POSITIVE]
    lines += ["", f"## Пропущенные сигналы (FN, {len(fn)})", ""]
    lines += [f"- №{r['id']} {r['technology'][:70]} → {r['pred']} (c={r['confidence']}, {', '.join(r['reason_codes'][:3])})" for r in fn]
    lines += ["", f"## Ложные сигналы (FP, {len(fp)})", ""]
    lines += [f"- {r['id']} {r['technology'][:70]} [gold {r['gold']}] → c={r['confidence']}, primary {r['primary_pattern']}" for r in fp]
    lines += ["", "Каждая запись в `records.jsonl` содержит `predictors` (код, статус, вес, вклад, обоснование) — это объяснение решения для карточки."]
    return "\n".join(lines) + "\n"
