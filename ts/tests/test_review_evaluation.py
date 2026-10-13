from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from ts.review.evaluation import (
    evaluate_case,
    evaluate_review_dataset,
    load_review_dataset,
    write_review_evaluation,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/review_eval_v1.json"


def test_review_eval_has_disjoint_frozen_replay_and_sealed_holdout():
    dataset = load_review_dataset(DATASET)
    replay = {row["case_id"] for row in dataset["cases"] if row["split"] == "replay"}
    holdout = {row["case_id"] for row in dataset["cases"] if row["split"] == "holdout"}
    replay_scenarios = {row["scenario"] for row in dataset["cases"] if row["split"] == "replay"}
    holdout_scenarios = {row["scenario"] for row in dataset["cases"] if row["split"] == "holdout"}

    assert len(replay) == 8
    assert len(holdout) == 8
    assert replay.isdisjoint(holdout)
    assert replay_scenarios.isdisjoint(holdout_scenarios)
    assert dataset["frozen_code_sha"] == "9f3a1398fc3a82bb024e81d1c72e4fadb46eb4fc"
    assert dataset["arbiter_candidate"] == "review-arbiter-0.2"
    assert dataset["holdout"]["sealed"] is True
    assert dataset["holdout"]["adjudication_method"]


def test_gold_labels_do_not_change_any_path_decision():
    case = load_review_dataset(DATASET)["cases"][0]
    changed = deepcopy(case)
    changed["gold_accept"] = not case["gold_accept"]
    changed["gold_verdict"] = "REJECT" if case["gold_verdict"] != "REJECT" else "PROMOTE"

    original = evaluate_case(case)
    relabelled = evaluate_case(changed)

    assert {
        path: row["verdict"] for path, row in original.items()
    } == {
        path: row["verdict"] for path, row in relabelled.items()
    }


def test_loader_rejects_holdout_that_reuses_a_replay_scenario(tmp_path):
    dataset = json.loads(DATASET.read_text())
    dataset["cases"][8]["scenario"] = dataset["cases"][0]["scenario"]
    path = tmp_path / "leaky.json"
    path.write_text(json.dumps(dataset))

    with pytest.raises(ValueError, match="structurally distinct"):
        load_review_dataset(path)


def test_full_review_beats_baseline_without_unsafe_promotions():
    summary = evaluate_review_dataset(load_review_dataset(DATASET))

    for split in ("replay", "holdout", "all"):
        baseline = summary["metrics"][split]["baseline"]
        proposed = summary["metrics"][split]["proposed"]
        assert baseline["recall"] == 1.0
        assert baseline["false_promotions"] > 0
        assert baseline["evidence_less_promotions"] > 0
        assert baseline["unresolved_critical_promotions"] > 0
        assert proposed["precision"] == 1.0
        assert proposed["recall"] == 1.0
        assert proposed["false_promotions"] == 0
        assert proposed["evidence_less_promotions"] == 0
        assert proposed["unresolved_critical_promotions"] == 0
        assert proposed["evidence_coverage"] == 1.0
        assert proposed["stability"] == 1.0
        assert proposed["exact_verdict_accuracy"] == 1.0
        assert proposed["overpromotions"] == 0


def test_ablations_are_conservative_and_resource_metrics_are_complete():
    summary = evaluate_review_dataset(load_review_dataset(DATASET))
    metrics = summary["metrics"]["all"]

    assert metrics["no_defender"]["recall"] == 0.0
    assert metrics["no_defender"]["false_promotions"] == 0
    assert metrics["no_control"]["recall"] == 0.0
    assert metrics["no_control"]["false_promotions"] == 0
    assert metrics["baseline"]["tokens"] == 0
    assert metrics["baseline"]["cost_usd"] == 0.0
    assert metrics["proposed"]["tokens"] > metrics["no_defender"]["tokens"] > 0
    assert metrics["proposed"]["cost_usd"] > metrics["no_control"]["cost_usd"] > 0
    assert metrics["proposed"]["latency_ms"] > 0


def test_ablations_execute_twice_through_runner_and_record_role_failure():
    case = load_review_dataset(DATASET)["cases"][0]
    paths = evaluate_case(case)

    assert paths["no_defender"]["stable"] is True
    assert ["defender", "role_call_failed"] in paths["no_defender"]["role_errors"]
    assert paths["no_control"]["stable"] is True
    assert ["control_critic", "role_call_failed"] in paths["no_control"]["role_errors"]
    assert paths["no_defender"]["verdict"] == "HOLD"
    assert paths["no_control"]["verdict"] == "HOLD"


def test_ablations_preserve_the_case_provider_failure():
    case = next(
        row for row in load_review_dataset(DATASET)["cases"]
        if row["scenario"] == "provider_failure"
    )
    paths = evaluate_case(case)

    assert paths["no_defender"]["role_errors"] == [
        ["critic", "role_call_failed"],
        ["defender", "role_call_failed"],
    ]
    assert paths["no_control"]["role_errors"] == [
        ["critic", "role_call_failed"],
        ["control_critic", "role_call_failed"],
    ]
    assert paths["no_defender"]["tokens"] == paths["no_control"]["tokens"] == 300
    assert paths["no_defender"]["cost_usd"] == paths["no_control"]["cost_usd"] == 0.002
    assert paths["no_defender"]["latency_ms"] == paths["no_control"]["latency_ms"] == 20


def test_unknown_critical_replacement_is_derived_as_unresolved(monkeypatch):
    from ts.review import evaluation

    case = next(
        row for row in load_review_dataset(DATASET)["cases"]
        if row["scenario"] == "valid_narrowing"
    )
    candidate, evidence, outputs = evaluation._fixture(case)
    outputs["defender"]["rebuttals"][0]["replacement_claim"]["status"] = "unknown"
    monkeypatch.setattr(
        evaluation,
        "_fixture",
        lambda _case: (deepcopy(candidate), deepcopy(evidence), deepcopy(outputs)),
    )

    proposed = evaluate_case(case)["proposed"]

    assert proposed["verdict"] == "HOLD"
    assert proposed["unresolved_critical"] is True


def test_safety_metrics_are_derived_not_hidden_by_risk_annotations():
    dataset = load_review_dataset(DATASET)
    expected = evaluate_review_dataset(dataset)["metrics"]["all"]
    unlabelled = deepcopy(dataset)
    for case in unlabelled["cases"]:
        case["risk_flags"] = []
    observed = evaluate_review_dataset(unlabelled)["metrics"]["all"]

    for path in ("baseline", "proposed", "no_defender", "no_control"):
        assert observed[path]["evidence_less_promotions"] == expected[path]["evidence_less_promotions"]
        assert observed[path]["unresolved_critical_promotions"] == expected[path]["unresolved_critical_promotions"]


def test_eval_output_is_reproducible_and_states_fixture_limit(tmp_path):
    first = write_review_evaluation(DATASET, tmp_path / "first")
    second = write_review_evaluation(DATASET, tmp_path / "second")

    first_summary = json.loads((tmp_path / "first/summary.json").read_text())
    second_summary = json.loads((tmp_path / "second/summary.json").read_text())
    report = (tmp_path / "first/report.md").read_text()
    assert first["result_digest"] == second["result_digest"]
    assert first_summary == second_summary
    assert "fixture" in report.lower()
    assert "не измеряет качество живых ответов модели" in report


def test_review_eval_cli_writes_the_reproducible_artifact(tmp_path, capsys):
    from ts.cli import main

    out = tmp_path / "cli"
    assert main([
        "review-eval",
        "--dataset", str(DATASET),
        "--out", str(out),
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["result_digest"]
    assert payload["holdout"]["proposed"]["false_promotions"] == 0
    assert (out / "summary.json").exists()
    assert (out / "report.md").exists()
