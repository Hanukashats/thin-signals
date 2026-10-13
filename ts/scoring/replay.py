"""Reproduce the frozen 170-row scoring evaluation across rules versions."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ts.scoring.scorer import FeatureVector, load_rules, score

_IND_RE = re.compile(r"events=(\d+), origins=(\d+)")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def load_scoring_records(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        required = {"id", "gold", "pred_default", "confidence", "split", "predictors"}
        if not isinstance(row, dict) or not required <= set(row):
            raise ValueError(f"invalid scoring record at line {line_number}")
        if row["split"] not in {"train", "holdout"}:
            raise ValueError(f"invalid scoring split at line {line_number}")
        if not isinstance(row["predictors"], list):
            raise TypeError(f"invalid scoring predictors at line {line_number}")
        rows.append(row)
    if not rows:
        raise ValueError("scoring replay is empty")
    return rows


def _feature_vector(row: dict[str, Any]) -> FeatureVector:
    predictors = row["predictors"]
    features = {
        predictor["code"]: predictor["value"]
        for predictor in predictors
        if str(predictor.get("code", "")).startswith("P")
    }
    counters = {
        predictor["code"]: True
        for predictor in predictors
        if str(predictor.get("code", "")).startswith("M")
    }
    events = origins = 0
    independence = next(
        (predictor for predictor in predictors if predictor.get("code") == "IND"),
        None,
    )
    if independence is not None:
        match = _IND_RE.fullmatch(str(independence.get("evidence", "")))
        if match is None:
            raise ValueError(f"record {row['id']} has an invalid independence trace")
        events, origins = (int(value) for value in match.groups())
    transition_predictor = next(
        (predictor for predictor in predictors if predictor.get("code") == "TR"),
        None,
    )
    transition_value = transition_predictor.get("value", 0) if transition_predictor else 0
    transition = "verified" if transition_value == 1 else "supported" if transition_value == 0.5 else "unknown"
    primary = row.get("primary_pattern") or ""
    return FeatureVector(
        primary_pattern=primary,
        secondary_patterns=list(row.get("secondary_patterns") or []),
        features=features,
        counters=counters,
        evidence_events=events,
        independent_origins=origins,
        transition=transition,
        mode="description",
        named_primary=bool(primary),
    )


def _metrics(rows: list[dict[str, Any]], path: str) -> dict[str, int | float]:
    gold = [row["gold"] == "weak_signal" for row in rows]
    predicted = [row[path]["label"] == "weak_signal" for row in rows]
    tp = sum(actual and expected for actual, expected in zip(predicted, gold, strict=True))
    fp = sum(actual and not expected for actual, expected in zip(predicted, gold, strict=True))
    fn = sum(not actual and expected for actual, expected in zip(predicted, gold, strict=True))
    tn = sum(not actual and not expected for actual, expected in zip(predicted, gold, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "n": len(rows),
        "accuracy": round((tp + tn) / len(rows), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "false_promotions": fp,
    }


def evaluate_scoring_replay(
    records: list[dict[str, Any]],
    baseline_version: str = "rules-0.1",
    candidate_version: str = "rules-0.2",
) -> dict[str, Any]:
    baseline_rules = load_rules(baseline_version)
    candidate_rules = load_rules(candidate_version)
    evaluated: list[dict[str, Any]] = []
    reproduction_mismatches = 0
    changed_labels = decreased = increased = 0
    for row in records:
        vector = _feature_vector(row)
        baseline = score(vector, baseline_rules)
        candidate = score(vector, candidate_rules)
        if baseline.label != row["pred_default"] or baseline.confidence != row["confidence"]:
            reproduction_mismatches += 1
        if candidate.label != baseline.label:
            changed_labels += 1
        if baseline.confidence is not None and candidate.confidence is not None:
            decreased += candidate.confidence < baseline.confidence
            increased += candidate.confidence > baseline.confidence
        evaluated.append({
            "id": row["id"],
            "split": row["split"],
            "gold": row["gold"],
            "baseline": {"label": baseline.label, "confidence": baseline.confidence},
            "candidate": {"label": candidate.label, "confidence": candidate.confidence},
        })
    metrics: dict[str, dict[str, dict[str, int | float]]] = {}
    for split in ("train", "holdout", "all"):
        selected = evaluated if split == "all" else [row for row in evaluated if row["split"] == split]
        metrics[split] = {
            "baseline": _metrics(selected, "baseline"),
            "candidate": _metrics(selected, "candidate"),
        }
    summary: dict[str, Any] = {
        "baseline_rules": baseline_version,
        "candidate_rules": candidate_version,
        "records_digest": _digest(records),
        "n": len(records),
        "baseline_reproduction_mismatches": reproduction_mismatches,
        "changed_labels": changed_labels,
        "decreased_confidence": decreased,
        "increased_confidence": increased,
        "metrics": metrics,
        "records": evaluated,
        "limitations": [
            "This is a frozen description-mode replay using stored extraction outputs.",
            "It isolates deterministic scoring and does not rerun retrieval or model extraction.",
            "Live search yield is measured only by the separately bounded release canary.",
        ],
    }
    summary["result_digest"] = _digest(summary)
    return summary


def render_scoring_replay_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Frozen scoring replay — rules 0.1 → 0.2",
        "",
        (
            f"Replayed **{summary['n']}** stored rows from `{summary['baseline_rules']}` "
            f"through `{summary['candidate_rules']}`."
        ),
        "",
        "| split/rules | n | accuracy | P | R | F1 | FP |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for split in ("train", "holdout", "all"):
        for path in ("baseline", "candidate"):
            row = summary["metrics"][split][path]
            version = summary[f"{path}_rules"]
            lines.append(
                f"| {split}/{version} | {row['n']} | {row['accuracy']:.4f} | "
                f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {row['fp']} |"
            )
    lines += [
        "",
        "## Regression checks",
        "",
        f"- Baseline reproduction mismatches: **{summary['baseline_reproduction_mismatches']}**.",
        f"- Changed labels: **{summary['changed_labels']}**.",
        f"- Confidence decreases / increases: **{summary['decreased_confidence']} / {summary['increased_confidence']}**.",
        "",
        "## Limitation",
        "",
        (
            "Это замороженный replay сохранённых extraction-результатов. Он проверяет только формулу "
            "и не повторяет живой поиск или ответы модели; живой поиск проверяется отдельным bounded canary."
        ),
        "",
        f"Records SHA-256: `{summary['records_digest']}`",
        f"Result SHA-256: `{summary['result_digest']}`",
    ]
    return "\n".join(lines) + "\n"


def write_scoring_replay(records_path: Path, out_dir: Path) -> dict[str, Any]:
    summary = evaluate_scoring_replay(load_scoring_records(records_path))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_scoring_replay_report(summary), encoding="utf-8")
    return summary
