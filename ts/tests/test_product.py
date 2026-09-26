"""GOAL finish slice: persisted run, API payload, Russian screen, ZDR allowlist."""
from __future__ import annotations

from fastapi.testclient import TestClient

from ts.api import create_app
from ts.harness import Harness
from ts.llm import ModelNotAllowed, OpenRouterClient
from ts.persist import load_report, save_report
from ts.sources.connectors import Hit
from ts.tests.test_harness import Scripted
from ts.tests.test_llm import make_client, settings
from ts.ui_text import panels, screen


def _report(tmp_path):
    hit = Hit("arxiv", "https://arxiv.org/abs/1", "New cell", "pilot", "paper", published="2026-01-02", doi="10.9/cell")
    harness = Harness(snapshot_dir=tmp_path, corpus_version="live-w3")
    return harness.run("product-cell-query", [Scripted("arxiv", [hit])])


def test_second_query_does_not_search_again(tmp_path):
    from sqlalchemy import delete

    from ts.db import session_factory
    from ts.db.models import Candidate, Decision, Run
    from ts.live import run_query

    hit = Hit("arxiv", "https://arxiv.org/abs/77", "Quiet cell", "grant", "paper", published="2026-02-02", doi="10.9/quiet")
    src = Scripted("arxiv", [hit])
    factory = session_factory()
    first = run_query("quiet-cell-repeat", limit=2, connectors=[src], session_factory=factory)
    calls = src.calls
    second = run_query("quiet-cell-repeat", limit=2, connectors=[src], session_factory=factory)
    assert second["repeated"] is True and second["run_id"] == first["run_id"] and src.calls == calls
    with factory() as session:
        session.execute(delete(Decision).where(Decision.run_id == first["run_id"]))
        session.execute(delete(Run).where(Run.id == first["run_id"]))
        session.execute(delete(Candidate).where(Candidate.id == f"live-{first['run_id']}"))
        session.commit()


def test_repeat_returns_the_same_postgres_run(tmp_path):
    from sqlalchemy import delete

    from ts.db import session_factory
    from ts.db.models import Candidate, Decision, Run

    report = _report(tmp_path)
    factory = session_factory()
    with factory() as session:
        first = save_report(session, report)
        second = save_report(session, report)
        loaded = load_report(session, report.idempotency_key)
        assert first == second == loaded["run_id"]
        assert loaded["run_status"] == "succeeded"
        assert loaded["signal_label"] == report.card["label"]
        assert loaded["signal_label"] != loaded["run_status"]
        session.execute(delete(Decision).where(Decision.run_id == first))
        session.execute(delete(Run).where(Run.id == first))
        session.execute(delete(Candidate).where(Candidate.id == f"live-{first}"))
        session.commit()


def test_api_separates_run_status_label_and_exclusion():
    def runner(query, limit, extract):
        return {
            "run_id": "abc", "run_status": "succeeded", "query": query, "repeated": False,
            "signal_label": "noise", "confidence": 0.0, "policy_action": "WATCHLIST",
            "policy_reason": "no_verified_change", "reason_codes": [], "predictors": [],
            "sources": [{"name": "Paper", "url": "https://arxiv.org/abs/1", "date": None,
                         "date_unknown_reason": "источник не указал дату", "type": "paper",
                         "language": "en", "trust": "primary"}],
            "events": 1, "top": [], "shortfall": 15,
            "exclusion_registry": [{"technology": query, "label": "noise", "policy_action": "WATCHLIST",
                                    "policy_reason": "no_verified_change"}],
            "model_id": None, "provider": None, "rules_version": "rules-0.1",
            "counters": {"sources": 1, "admitted": 0, "excluded": 1, "confident": 0},
        }

    client = TestClient(create_app(runner))
    body = client.post("/v1/runs", json={"query": "фотонный процессор", "limit": 2}).json()
    assert body["run_status"] == "succeeded"
    assert body["signal_label"] == "noise"
    assert body["sources"][0]["trust"] == "primary"
    assert body["exclusion_registry"]
    assert body["shortfall"] == 15
    view = screen(body)
    text = "\n".join(view["lines"] + view["sources"] + view["excluded"])
    assert "Статус прогона: succeeded" in text
    assert "Метка сигнала: шум" in text
    board = panels(body)
    assert board["run_status"] == "succeeded"
    assert board["signal_label"] == "шум"
    assert board["run_status"] != board["signal_label"]
    assert board["shortfall"] == 15
    assert board["sources"] and "Paper" in board["sources"][0]
    assert "дата не указана" in text or "источник не указал дату" in text


def test_latest_run_is_shown_without_scoring():
    stored = {
        "run_status": "succeeded", "signal_label": "noise", "query": "клетка",
        "shortfall": 15, "sources": [], "exclusion_registry": [], "predictors": [],
        "confidence": None, "top": [],
    }
    client = TestClient(create_app(lambda *args: {}, latest=lambda: stored))
    body = client.get("/v1/runs/latest").json()
    assert body["run"]["run_status"] == "succeeded"
    assert body["run"]["signal_label"] == "noise"
    assert body["run"]["run_status"] != body["run"]["signal_label"]
    empty = TestClient(create_app(lambda *args: {}, latest=lambda: None))
    assert empty.get("/v1/runs/latest").json()["run"] is None


def test_openrouter_allowlist_rejects_unknown_model(tmp_path):
    client = make_client(tmp_path)
    assert isinstance(client, OpenRouterClient)
    try:
        client.check_model("openai/gpt-4o-secret")
        raise AssertionError("model outside the allowlist must be rejected")
    except ModelNotAllowed:
        pass
    client.check_model("qwen/qwen3.6-35b-a3b")
    # settings() is used so the fixture file stays the single place that builds a ZDR client
    assert settings(tmp_path).llm_provider_policy["data_collection"] == "deny"
