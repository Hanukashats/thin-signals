"""W3 harness: connectors parse fixtures, dedup, roadmap, rank, idempotent rerun."""
from __future__ import annotations

from pathlib import Path

from ts.harness import Harness, dedup
from ts.snapshots import save_snapshot
from ts.sources.connectors import (
    ArxivConnector,
    CrossrefConnector,
    GithubConnector,
    Hit,
    OpenAlexConnector,
    SearxConnector,
)
from ts.sources.trust import classify

DOI = "10.1000/example.85"


class Boom:
    name = "boom"

    def search(self, query: str, *, limit: int = 5):
        raise TimeoutError(query)


class Scripted:
    def __init__(self, name: str, hits: list[Hit]):
        self.name = name
        self.hits = hits
        self.calls = 0

    def search(self, query: str, *, limit: int = 5):
        self.calls += 1
        return self.hits


def test_trust_levels():
    assert classify("https://arxiv.org/abs/1", "paper") == "primary"
    assert classify("https://github.com/a/b", "repository") == "primary"
    assert classify("https://github.com/a/b", "web") == "indicator"
    assert classify("https://techcrunch.com/x", "web") == "professional"
    assert classify("https://random-blog.example/post", "web") == "indicator"


def test_connectors_parse_fixtures():
    searx = SearxConnector("http://searx", lambda url: '{"results":[{"title":"Optical","url":"https://example.com/a","content":"light"}]}')
    assert searx.search("q")[0].url.endswith("/a")
    arxiv_xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <id>https://arxiv.org/abs/1234.5</id><title>Stacked memory</title><summary>abstract</summary>
      <published>2025-11-12T00:00:00Z</published>
      <link title="doi" href="https://doi.org/10.1000/example.85"/></entry></feed>"""
    assert ArxivConnector(lambda url: arxiv_xml).search("q")[0].doi == DOI
    ox = '{"results":[{"display_name":"Stacked memory","doi":"https://doi.org/10.1000/example.85","publication_date":"2025-11-12","id":"https://openalex.org/W1"}]}'
    assert OpenAlexConnector(lambda url: ox).search("q")[0].doi == DOI
    cr = '{"message":{"items":[{"title":["Stacked memory"],"URL":"https://doi.org/10.1000/example.85","DOI":"10.1000/example.85","issued":{"date-parts":[[2025,11,12]]}}]}}'
    assert CrossrefConnector(lambda url: cr).search("q")[0].published == "2025-11-12"
    partial = '{"message":{"items":[{"title":["Only year"],"URL":"https://doi.org/10.1/y","DOI":"10.1/y","issued":{"date-parts":[[2024,null]]}}]}}'
    assert CrossrefConnector(lambda url: partial).search("q")[0].published == "2024-01-01"
    gh = '{"items":[{"full_name":"org/mem","html_url":"https://github.com/org/mem","description":"code","updated_at":"2025-11-12T00:00:00Z"}]}'
    hit = GithubConnector(lambda url: gh).search("q")[0]
    assert hit.source_type == "repository" and hit.published == "2025-11-12"


def test_same_experiment_is_one_event_and_roadmap_is_not_deployment():
    paper = Hit("arxiv", "https://arxiv.org/abs/1", "Stacked memory", "experiment", "paper", doi=DOI, published="2025-11-12")
    repo = Hit("github", "https://github.com/org/mem", "org/mem", "code for the same experiment", "repository", doi=DOI)
    press = Hit("searxng", "https://siliconangle.com/x", "Stacked memory", "funding", "industry_media", doi=DOI)
    events = dedup([paper, repo, press])
    assert len(events) == 1 and events[0]["dedup_status"] == "merged" and len(events[0]["urls"]) == 3
    roadmap = Hit("searxng", "https://vendor.example/roadmap", "Photonic chip roadmap", "planned for 2027", "web")
    ev = dedup([roadmap])[0]
    assert ev["type"] == "planned_for" and ev["deployment_confirmed"] is False and ev["planned_for"] == "2027-01-01"


def test_snapshot_repeat_does_not_create_a_second_file(tmp_path: Path):
    body = b"same-bytes"
    first = save_snapshot(tmp_path, "https://example.com/a", body)
    second = save_snapshot(tmp_path, "https://example.com/a", body)
    assert first["created"] is True and second["created"] is False
    assert first["content_hash"] == second["content_hash"]
    assert len([p for p in (tmp_path / "blobs").rglob("*") if p.is_file()]) == 1


def test_failed_connector_does_not_abort_and_rerun_is_free(tmp_path: Path):
    hit = Hit("arxiv", "https://arxiv.org/abs/9", "New mechanism", "three labs replicated", "paper",
              published="2026-01-01", doi="10.9/new")
    good = Scripted("arxiv", [hit, Hit("arxiv", "https://doi.org/10.9/b", "Second event", "pilot", "paper", doi="10.9/b"),
                              Hit("arxiv", "https://doi.org/10.9/c", "Third event", "grant", "paper", doi="10.9/c")])
    harness = Harness(snapshot_dir=tmp_path, corpus_version="test")
    report = harness.run("new memory", [Boom(), good], fetch_body=lambda url: b"body")
    assert any(s["status"] == "failed" and s["connector"] == "boom" for s in report.steps)
    assert good.calls == 2  # search + countersearch
    again = harness.run("new memory", [Boom(), good])
    assert again.repeated is True and again.id == report.id and good.calls == 2
    assert report.shortfall == 15
    assert report.exclusion_registry
    assert report.sources[0]["trust"] == "primary"
    assert report.sources[0]["date"] == "2026-01-01"


def test_mass_adoption_marker_excludes_from_top():
    mature = Hit("crossref", "https://doi.org/10.1/std", "Widget", "industry standard since 2019", "paper", doi="10.1/std")
    src = Scripted("crossref", [mature])
    report = Harness(corpus_version="mature").run("widget", [src])
    assert report.card["label"] in {"mature", "noise"}
    assert report.top == []
    assert report.exclusion_registry[0]["policy_action"] != "RANK_ELIGIBLE"


def test_unknown_date_is_explicit():
    hit = Hit("searxng", "https://example.com/n", "No date", "note", "web")
    report = Harness(corpus_version="date").run("x", [Scripted("searxng", [hit])])
    assert report.sources[0]["date"] is None
    assert report.sources[0]["date_unknown_reason"]
