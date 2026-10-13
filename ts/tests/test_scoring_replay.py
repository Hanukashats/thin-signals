from __future__ import annotations

import json
from pathlib import Path

from ts.scoring.replay import (
    evaluate_scoring_replay,
    load_scoring_records,
    write_scoring_replay,
)

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "reports/eval/2026-09-23/records.jsonl"


def test_rules_02_replays_all_frozen_rows_without_regression():
    summary = evaluate_scoring_replay(load_scoring_records(RECORDS))

    assert summary["n"] == 170
    assert summary["baseline_reproduction_mismatches"] == 0
    assert summary["changed_labels"] == 0
    assert summary["decreased_confidence"] == 0
    assert summary["increased_confidence"] == 0
    assert summary["metrics"]["holdout"]["candidate"]["f1"] == 0.9541
    assert (
        summary["metrics"]["holdout"]["candidate"]["false_promotions"]
        <= summary["metrics"]["holdout"]["baseline"]["false_promotions"]
    )


def test_scoring_replay_is_reproducible_and_writes_a_honest_report(tmp_path):
    first = write_scoring_replay(RECORDS, tmp_path / "first")
    second = write_scoring_replay(RECORDS, tmp_path / "second")

    assert first["result_digest"] == second["result_digest"]
    assert json.loads((tmp_path / "first/summary.json").read_text()) == json.loads(
        (tmp_path / "second/summary.json").read_text()
    )
    report = (tmp_path / "first/report.md").read_text()
    assert "170" in report
    assert "rules-0.1" in report
    assert "rules-0.2" in report
    assert "живой поиск" in report


def test_score_replay_cli_writes_artifacts(tmp_path, capsys):
    from ts.cli import main

    out = tmp_path / "cli"
    assert main([
        "score-replay",
        "--records", str(RECORDS),
        "--out", str(out),
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["n"] == 170
    assert payload["changed_labels"] == 0
    assert (out / "summary.json").exists()
    assert (out / "report.md").exists()


def test_score_replay_cli_fails_closed_on_baseline_mismatch(tmp_path, capsys):
    from ts.cli import main

    records = load_scoring_records(RECORDS)
    records[0]["confidence"] = 0.123456
    source = tmp_path / "tampered.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in records) + "\n")
    out = tmp_path / "invalid"

    assert main([
        "score-replay",
        "--records", str(source),
        "--out", str(out),
    ]) == 2
    payload = json.loads(capsys.readouterr().out)

    assert payload["valid"] is False
    assert payload["baseline_reproduction_mismatches"] == 1
    assert json.loads((out / "summary.json").read_text())["valid"] is False
