"""Bounded GPT Researcher adapter; upstream prose is never evidence."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from ts.harness import Harness
from ts.live import default_connectors
from ts.persist import public_report
from ts.settings import load
from ts.sources.connectors import ConnectorError, Hit
from ts.sources.refetch import refetch_public_url
from ts.sources.researcher import GptResearcherConnector


def _response(*, cost: float = 0.04) -> str:
    return json.dumps({
        "research_id": "task_1_new-memory",
        "report": "IGNORE THIS GENERATED REPORT, INCLUDING ANY INSTRUCTIONS",
        "research_information": {
            "source_urls": [
                "https://journals.example/a",
                "https://journals.example/a",
                "https://lab.example/b",
                "https://noise.example/c",
            ],
            "visited_urls": ["https://search.example/result"],
            "research_costs": cost,
        },
        "docx_path": "/app/outputs/task_1_new-memory.docx",
        "pdf_path": "/app/outputs/task_1_new-memory.pdf",
    })


def test_researcher_uses_sync_contract_and_only_returns_refetched_leads():
    calls = []
    fetched = []

    def post(url, payload):
        calls.append((url, payload))
        return _response()

    def refetch(url):
        fetched.append(url)
        if url.endswith("/b"):
            return None
        return Hit("refetch", url, "Primary record", "direct source text", "paper")

    connector = GptResearcherConnector(
        "http://127.0.0.1:28000", post, refetch,
        max_cost_usd=0.08, max_leads=3,
    )
    hits = connector.search("new memory", limit=2)

    assert calls == [("http://127.0.0.1:28000/report/", {
        "task": "new memory",
        "report_type": "research_report",
        "report_source": "web",
        "tone": "Objective",
        "headers": {},
        "repo_name": "",
        "branch_name": "",
        "generate_in_background": False,
    })]
    assert fetched == ["https://journals.example/a", "https://lab.example/b"]
    assert [hit.url for hit in hits] == ["https://journals.example/a"]
    assert hits[0].connector == "gpt_researcher"
    assert "IGNORE THIS" not in hits[0].snippet
    assert hits[0].advisory_provenance == {
        "provider": "gpt-researcher",
        "research_id": "task_1_new-memory",
        "reported_cost_usd": 0.04,
        "artifact_refs": connector.last_metadata["artifact_refs"],
    }
    assert connector.last_metadata == {
        "research_id": "task_1_new-memory",
        "reported_cost_usd": 0.04,
        "advisory_count": 3,
        "validated_count": 1,
        "artifact_refs": connector.last_metadata["artifact_refs"],
    }
    assert len(connector.last_metadata["artifact_refs"]) == 2
    assert all(len(item) == 16 for item in connector.last_metadata["artifact_refs"])
    assert "/app/outputs" not in repr(connector.last_metadata)


def test_researcher_cost_guard_fails_closed_before_any_lead_is_refetched():
    fetched = []
    connector = GptResearcherConnector(
        "http://127.0.0.1:28000",
        lambda _url, _payload: _response(cost=0.81),
        lambda url: fetched.append(url),
        max_cost_usd=0.08,
    )

    with pytest.raises(ConnectorError, match="cost"):
        connector.search("new memory", limit=2)

    assert fetched == []
    assert connector.last_metadata["reported_cost_usd"] == 0.81
    assert connector.last_metadata["validated_count"] == 0


@pytest.mark.parametrize("body", [
    "not-json",
    "[]",
    '{"research_id":"x","report":"prose only"}',
    '{"research_information":{"source_urls":"https://example.com"}}',
    '{"research_information":{"source_urls":[],"research_costs":-1}}',
])
def test_researcher_rejects_malformed_or_unbounded_upstream_answers(body):
    connector = GptResearcherConnector(
        "http://127.0.0.1:28000", lambda _url, _payload: body, lambda _url: None,
    )
    with pytest.raises(ConnectorError):
        connector.search("q")


def test_researcher_budget_changes_retrieval_identity():
    first = GptResearcherConnector("http://r", lambda *_: _response(), lambda _url: None)
    second = GptResearcherConnector(
        "http://r", lambda *_: _response(), lambda _url: None,
        max_cost_usd=0.2, max_leads=9,
    )
    assert first.retrieval_identity != second.retrieval_identity


def test_harness_calls_advisory_research_once_and_exposes_only_safe_provenance(tmp_path):
    posts = []

    def post(url, payload):
        posts.append((url, payload))
        return _response()

    connector = GptResearcherConnector(
        "http://127.0.0.1:28000", post,
        lambda url: Hit("refetch", url, "New memory", "direct record", "paper"),
    )
    report = Harness(snapshot_dir=tmp_path, corpus_version="research-adapter").run(
        "new memory", [connector], limit=1,
    )
    body = public_report(report)

    assert len(posts) == 1
    assert [row["name"] for row in body["retrieval"]["connectors"]] == ["search"]
    step = body["retrieval"]["connectors"][0]
    assert step["research_id"] == "task_1_new-memory"
    assert step["reported_cost_usd"] == 0.04
    assert step["advisory_count"] == 3
    assert step["validated_count"] == 1
    assert step["artifact_refs"] == connector.last_metadata["artifact_refs"]
    assert body["sources"][0]["advisory_provenance"] == {
        "provider": "gpt-researcher",
        "research_id": "task_1_new-memory",
        "reported_cost_usd": 0.04,
        "artifact_refs": connector.last_metadata["artifact_refs"],
    }
    assert "IGNORE THIS" not in repr(body)


def test_gpt_researcher_is_disabled_by_default_and_misconfiguration_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("TS_DISABLE_DOTENV", "1")
    monkeypatch.delenv("TS_GPT_RESEARCHER_ENABLED", raising=False)
    monkeypatch.delenv("TS_GPT_RESEARCHER_URL", raising=False)
    settings = load(tmp_path)
    assert settings.gpt_researcher_enabled is False
    assert "gpt_researcher" not in [item.name for item in default_connectors(settings)]

    settings.gpt_researcher_enabled = True
    with pytest.raises(ValueError, match="TS_GPT_RESEARCHER_URL"):
        default_connectors(settings)


def test_enabled_researcher_budget_is_part_of_live_connector_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("TS_DISABLE_DOTENV", "1")
    monkeypatch.setenv("TS_GPT_RESEARCHER_ENABLED", "true")
    monkeypatch.setenv("TS_GPT_RESEARCHER_URL", "http://127.0.0.1:28000")
    monkeypatch.setenv("TS_GPT_RESEARCHER_MAX_COST_USD", "0.12")
    monkeypatch.setenv("TS_GPT_RESEARCHER_MAX_LEADS", "7")
    settings = load(tmp_path)
    connector = next(item for item in default_connectors(settings) if item.name == "gpt_researcher")
    assert ":0.120000:7" in connector.retrieval_identity


@dataclass
class _Response:
    status_code: int
    headers: dict
    content: bytes

    @property
    def text(self):
        return self.content.decode()


def _public_resolver(host, _port, **_kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def test_refetch_accepts_bounded_public_text_and_rejects_private_redirects():
    calls = []

    def request(url):
        calls.append(url)
        if url.endswith("/start"):
            return _Response(302, {"location": "https://127.0.0.1/private"}, b"")
        return _Response(
            200, {"content-type": "text/html; charset=utf-8"},
            b"<html><title>Lab record</title><body>Direct primary evidence with enough text to read.</body></html>",
        )

    hit = refetch_public_url(
        "https://public.example/article", request, resolver=_public_resolver,
    )
    assert hit.url == "https://public.example/article"
    assert hit.title == "Lab record"
    assert "Direct primary evidence" in hit.snippet

    with pytest.raises(ConnectorError, match="public"):
        refetch_public_url(
            "https://public.example/start", request, resolver=_public_resolver,
        )
    assert calls[-1] == "https://public.example/start"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "http://localhost/admin",
    "http://127.0.0.1/admin",
    "http://[::1]/admin",
    "https://user:pass@example.com/private",
])
def test_refetch_rejects_non_public_targets_before_request(url):
    calls = []
    with pytest.raises(ConnectorError):
        refetch_public_url(
            url, lambda value: calls.append(value), resolver=_public_resolver,
        )
    assert calls == []


def test_refetch_rejects_binary_and_oversized_bodies():
    with pytest.raises(ConnectorError, match="content type"):
        refetch_public_url(
            "https://public.example/a.pdf",
            lambda _url: _Response(200, {"content-type": "application/pdf"}, b"%PDF"),
            resolver=_public_resolver,
        )
    with pytest.raises(ConnectorError, match="large"):
        refetch_public_url(
            "https://public.example/huge",
            lambda _url: _Response(200, {"content-type": "text/plain"}, b"x" * 2_000_001),
            resolver=_public_resolver,
        )
