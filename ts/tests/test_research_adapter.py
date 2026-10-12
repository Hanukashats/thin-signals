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
        "request_count": 1,
        "request_limit": 1,
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
        lambda _url: Hit(
            "refetch", "https://arxiv.org/abs/2601.00001",
            "New memory", "direct record", "paper",
            fetched_body=b"Direct primary record body.",
            fetched_text="Direct primary record body.",
            fetched_content_type="text/plain",
        ),
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
    assert body["sources"][0]["trust"] == "primary"
    assert body["sources"][0]["evidence"]["status"] == "preserved"
    assert body["sources"][0]["evidence"]["fragment"] == "Direct primary record body."
    assert "IGNORE THIS" not in repr(body)


def test_researcher_connector_instance_allows_only_one_billed_request():
    posts = []
    connector = GptResearcherConnector(
        "http://127.0.0.1:28000",
        lambda url, payload: posts.append((url, payload)) or _response(),
        lambda url: Hit("refetch", url, "New memory", "direct record", "paper"),
    )

    assert connector.stage_enabled("search") is True
    assert connector.search("first", limit=1)
    assert connector.stage_enabled("search") is False
    assert connector.search("second", limit=1) == []
    assert len(posts) == 1
    assert connector.public_metadata()["request_count"] == 1
    assert connector.public_metadata()["request_limit"] == 1


def test_wide_run_calls_researcher_once_and_preserves_only_refetched_evidence(
    monkeypatch, tmp_path,
):
    from contextlib import nullcontext
    from time import monotonic
    from types import SimpleNamespace

    from ts import live

    posts = []

    def post(url, payload):
        posts.append((url, payload))
        return _response()

    researcher = GptResearcherConnector(
        "http://127.0.0.1:28000",
        post,
        lambda _url: Hit(
            "refetch", "https://arxiv.org/abs/2601.00002",
            "alpha battery mechanism study", "validated primary text", "paper",
            fetched_body=b"Validated primary text from the original record.",
            fetched_text="Validated primary text from the original record.",
            fetched_content_type="text/plain",
        ),
    )

    class FixtureConnector:
        name = "fixture"
        search_stages = frozenset({"search"})

        def search(self, query: str, *, limit: int = 1):
            slug = query.split()[0]
            return [Hit(
                self.name,
                f"https://arxiv.org/abs/{slug}",
                f"{query} study",
                "fixture primary text",
                "paper",
                doi=f"10.1/{slug}",
            )]

    monkeypatch.setattr(live, "load_report", lambda *_args: None)
    monkeypatch.setattr(live, "save_report", lambda *_args: None)
    monkeypatch.setattr(live, "_near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "_potential", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        live,
        "annotate_checklist",
        lambda top, overflow, _settings, query=None: {
            "top": top, "excluded": [], "overflow": overflow, "unread": [],
            "stats": {"read": 0},
        },
    )
    monkeypatch.setattr(live, "annotate_scopes", lambda cards, _settings: cards)
    monkeypatch.setattr(live, "annotate_reach", lambda cards, _settings: cards)
    settings = SimpleNamespace(
        rules_version="rules-0.1",
        search_max_workers=2,
        search_deadline_seconds=90,
        source_timeout_seconds=40,
        wide_search_deadline_seconds=540,
        snapshot_dir=tmp_path,
        evidence_fetch_limit=24,
    )
    plan = {
        "version": "research-budget-test",
        "frame": [],
        "themes": [
            {"id": "alpha", "title": "Alpha", "query": "alpha battery mechanism"},
            {"id": "beta", "title": "Beta", "query": "beta turbine mechanism"},
        ],
    }

    body = live._run_wide(
        "audit mission",
        plan,
        limit=1,
        extract=False,
        settings=settings,
        connectors=[researcher, FixtureConnector()],
        session_factory=lambda: nullcontext(None),
        day="2026-10-12",
        deadline_at=monotonic() + 10,
    )

    research_steps = [
        step for step in body["retrieval"]["connectors"]
        if step.get("connector") == "gpt_researcher"
    ]
    assert len(posts) == 1
    assert len(research_steps) == 1
    assert research_steps[0]["request_count"] == 1
    assert research_steps[0]["request_limit"] == 1
    source = next(
        item for item in body["sources"]
        if item.get("connector") == "gpt_researcher"
    )
    assert source["evidence"]["status"] == "preserved"
    assert source["trust"] == "primary"
    assert "IGNORE THIS GENERATED REPORT" not in repr(body)


def test_live_researcher_transport_timeout_inherits_global_deadline(monkeypatch, tmp_path):
    captured = []

    class Response:
        text = json.dumps({
            "research_id": "bounded-timeout",
            "report": "discarded",
            "research_information": {"source_urls": [], "research_costs": 0.01},
        })

        @staticmethod
        def raise_for_status():
            return None

    def post(_url, **kwargs):
        captured.append(kwargs["timeout"])
        return Response()

    monkeypatch.setattr("ts.live.httpx.post", post)
    monkeypatch.setenv("TS_DISABLE_DOTENV", "1")
    monkeypatch.setenv("TS_GPT_RESEARCHER_ENABLED", "true")
    monkeypatch.setenv("TS_GPT_RESEARCHER_URL", "http://127.0.0.1:28000")
    settings = load(tmp_path)
    settings.search_deadline_seconds = 0.05
    settings.source_timeout_seconds = 40
    connector = next(
        item for item in default_connectors(settings)
        if item.name == "gpt_researcher"
    )

    Harness(
        snapshot_dir=tmp_path,
        corpus_version="research-timeout",
        deadline_seconds=0.05,
    ).run("bounded research", [connector], limit=1)

    assert len(captured) == 1
    assert 0 < captured[0] <= 0.05


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
    assert hit.fetched_body.startswith(b"<html>")
    assert "Direct primary evidence" in hit.fetched_text
    assert hit.fetched_content_type == "text/html"

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
