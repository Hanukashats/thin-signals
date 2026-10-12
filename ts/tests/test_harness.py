"""W3 harness: connectors parse fixtures, dedup, roadmap, rank, idempotent rerun."""
from __future__ import annotations

import time
from pathlib import Path

from ts.harness import Harness, dedup, markers
from ts.persist import public_report
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


def test_a_long_query_word_missing_from_the_title_sorts_last_and_stays():
    hits = [
        Hit("arxiv", "https://arxiv.org/abs/1", "Three Phase Bidirectional Onboard Charger", "a", "paper"),
        Hit("arxiv", "https://arxiv.org/abs/2", "Real Time Bidirectional Onboard Charger", "b", "paper"),
        Hit("arxiv", "https://arxiv.org/abs/3", "Gallium nitride bidirectional onboard charger", "c", "paper"),
    ]
    report = Harness(corpus_version="term").run(
        "gallium nitride bidirectional onboard charger", [Scripted("arxiv", hits)],
    )
    titles = [row["technology"] for row in report.top]
    assert titles[0] == "Gallium nitride bidirectional onboard charger"
    assert len(titles) == 3
    assert not [row for row in report.exclusion_registry if row.get("policy_reason") == "query_term_missing"]


def test_words_in_the_snippet_raise_the_card():
    titled = Hit("arxiv", "https://arxiv.org/abs/1", "Bidirectional onboard charger", "silicon", "paper")
    written = Hit(
        "arxiv", "https://arxiv.org/abs/2", "Monolithic bidirectional switch",
        "A gallium nitride device for an onboard charger", "paper",
    )
    report = Harness(corpus_version="snippet-subject").run(
        "gallium nitride bidirectional onboard charger",
        [Scripted("arxiv", [titled, written])],
    )
    assert report.top[0]["technology"] == "Monolithic bidirectional switch"
    assert report.top[0]["subject_hits"] > report.top[1]["subject_hits"]


def test_trust_levels():
    assert classify("https://arxiv.org/abs/1", "paper") == "primary"
    assert classify("https://github.com/a/b", "repository") == "primary"
    assert classify("https://github.com/a/b", "web") == "indicator"
    assert classify("https://techcrunch.com/x", "web") == "professional"
    assert classify("https://random-blog.example/post", "web") == "indicator"
    assert classify("https://www.cnesa.org/a", "web") == "primary"
    assert classify("https://www.hkexnews.hk/a", "web") == "primary"
    assert classify("https://www.cninfo.com.cn/a", "web") == "primary"
    assert classify("https://www.scmp.com/a", "web") == "professional"
    assert classify("https://www.reuters.com/a", "web") == "professional"
    assert classify("https://www.sciencedirect.com/science/article/abs/pii/S1", "web") == "primary"
    assert classify("https://advanced.onlinelibrary.wiley.com/doi/10.1002/aelm.1", "web") == "primary"
    assert classify("https://www.mdpi.com/2072-666X/17/8/931", "web") == "primary"
    assert classify("https://www.researchgate.net/publication/1", "web") == "indicator"
    assert classify("https://passive-components.eu/hzo", "web") == "indicator"
    assert classify("https://unknown-journal.example/doi/10.1000/abc", "web") == "indicator"


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
    assert ev["type"] == "observed" and ev["deployment_confirmed"] is False and ev["planned_for"] is None
    chinese = Hit("searxng", "https://vendor.example/zh", "光子芯片路线图", "计划于2027年", "web")
    german = Hit("searxng", "https://vendor.example/de", "Photonischer Chip", "geplant für 2027", "web")
    assert chinese.planned_for is None and chinese.deployment is False
    assert german.planned_for is None and german.deployment is False
    assert chinese.language == "zh"
    assert german.language == "und"


def test_snapshot_repeat_does_not_create_a_second_file(tmp_path: Path):
    body = b"same-bytes"
    first = save_snapshot(tmp_path, "https://example.com/a", body)
    second = save_snapshot(tmp_path, "https://example.com/a", body)
    assert first["created"] is True and second["created"] is False
    assert first["content_hash"] == second["content_hash"]
    assert len([p for p in (tmp_path / "blobs").rglob("*") if p.is_file()]) == 1


def test_failed_connector_does_not_abort_and_rerun_is_free(tmp_path: Path):
    hit = Hit("arxiv", "https://arxiv.org/abs/9", "New memory mechanism", "three labs replicated", "paper",
              published="2026-01-01", doi="10.9/new")
    good = Scripted("arxiv", [hit, Hit("arxiv", "https://doi.org/10.9/b", "Second memory event", "pilot", "paper", doi="10.9/b"),
                              Hit("arxiv", "https://doi.org/10.9/c", "Third memory event", "grant", "paper", doi="10.9/c")])
    harness = Harness(snapshot_dir=tmp_path, corpus_version="test")
    report = harness.run("new memory", [Boom(), good], fetch_body=lambda url: b"body")
    assert report.status == "degraded"
    body = public_report(report)
    assert body["run_status"] == "degraded"
    assert body["run_contract_version"] == "run-status-0.2"
    assert body["retrieval"]["connectors"]
    assert all("elapsed_ms" in row for row in body["retrieval"]["connectors"])
    assert body["retrieval"]["failures"] >= 1
    assert body["retrieval"]["stages"][0]["name"] == "search"
    assert body["retrieval"]["funnel"] == {
        "discovery_items": 3,
        "unique_sources": 3,
        "deduplicated_events": 3,
        "countersearch_items": 3,
        "admitted": 3,
        "excluded": 0,
        "unread": 0,
    }
    assert any(s["status"] == "failed" and s["connector"] == "boom" for s in report.steps)
    assert good.calls == 2  # search + countersearch
    again = harness.run("new memory", [Boom(), good])
    assert again.repeated is True and again.id == report.id and good.calls == 2
    assert len(report.top) == 3
    assert report.shortfall == 12
    assert report.sources[0]["trust"] == "primary"
    assert report.sources[0]["date"] == "2026-01-01"


def test_retrieval_configuration_is_part_of_repeat_identity():
    connector = Scripted("arxiv", [])
    harness = Harness(corpus_version="fingerprint")

    first = harness.run("same query", [connector], limit=2)
    changed_limit = harness.run("same query", [connector], limit=5)

    assert first.retrieval_fingerprint
    assert changed_limit.retrieval_fingerprint
    assert first.retrieval_fingerprint != changed_limit.retrieval_fingerprint
    assert changed_limit.repeated is False
    assert public_report(first)["retrieval"]["fingerprint"] == first.retrieval_fingerprint


def test_retrieval_funnel_counts_unique_urls_not_connector_rows():
    shared = Hit(
        "first", "https://example.org/same", "Shared result", "prototype", "web",
    )
    report = Harness(corpus_version="unique-funnel").run(
        "shared result",
        [Scripted("first", [shared]), Scripted("second", [shared])],
    )

    assert len(report.sources) == 2
    assert public_report(report)["retrieval"]["funnel"]["unique_sources"] == 1


def test_total_connector_failure_is_a_failed_run():
    report = Harness(corpus_version="all-failed").run("new memory", [Boom()])

    assert report.status == "failed"
    body = public_report(report)
    assert body["run_status"] == "failed"
    assert body["run_contract_version"] == "run-status-0.2"
    assert report.top == []


def test_failed_countersearch_degrades_and_blocks_admission():
    hit = Hit(
        "arxiv", "https://arxiv.org/abs/10", "New memory mechanism", "prototype",
        "paper", doi="10.9/counter", published="2026-01-01",
    )

    class CountersearchFails:
        name = "arxiv"

        def search(self, query: str, *, limit: int = 5):
            if "mass adoption industry standard" in query:
                raise TimeoutError(query)
            return [hit]

    report = Harness(corpus_version="counter-failed").run(
        "new memory mechanism", [CountersearchFails()],
    )

    assert report.status == "degraded"
    assert report.top == []
    assert report.exclusion_registry[0]["policy_action"] == "COUNTERSEARCH"


def test_countersearch_evidence_is_attached_to_the_matching_card():
    discovery = Hit(
        "custom", "https://lab.example/quantum-widget", "Quantum Widget Alpha",
        "early prototype", "paper", published="2026-01-01",
    )
    counter = Hit(
        "custom", "https://www.iso.org/standard/quantum-widget",
        "Quantum Widget industry standard", "mass adoption since 2020", "registry",
        published="2020-01-01",
    )

    class DiscoveryAndCountersearch:
        name = "custom"

        def search(self, query: str, *, limit: int = 5):
            if "mass adoption industry standard" in query:
                return [counter]
            return [discovery]

    report = Harness(corpus_version="counter-evidence").run(
        "quantum widget", [DiscoveryAndCountersearch()],
    )
    card = (report.top or report.exclusion_registry)[0]

    assert card["counter_sources"] == [
        {
            "name": "Quantum Widget industry standard",
            "url": "https://www.iso.org/standard/quantum-widget",
            "date": "2020-01-01",
            "date_unknown_reason": None,
            "type": "registry",
            "language": "und",
            "trust": "primary",
            "connector": "custom",
            "snippet": "mass adoption since 2020",
            "purpose": "countersearch",
        }
    ]


def test_countersearch_is_not_linked_by_one_generic_shared_word():
    discovery = Hit(
        "custom", "https://lab.example/battery", "Novel quantum battery electrode",
        "early electrochemistry prototype", "paper",
    )
    unrelated = Hit(
        "custom", "https://www.iso.org/standard/database",
        "Novel database engine standard", "mass adoption in enterprise databases",
        "registry",
    )

    class MixedSearch:
        name = "custom"

        def search(self, query: str, *, limit: int = 5):
            if "mass adoption industry standard" in query:
                return [unrelated]
            return [discovery]

    report = Harness(corpus_version="counter-unrelated").run(
        "quantum battery electrode", [MixedSearch()],
    )
    card = (report.top or report.exclusion_registry)[0]

    assert card["counter_sources"] == []


def test_connector_fanout_is_concurrent_timed_and_deterministically_ordered():
    class Delayed:
        def __init__(self, name: str, delay: float):
            self.name = name
            self.delay = delay

        def search(self, query: str, *, limit: int = 5):
            time.sleep(self.delay)
            return [Hit(
                self.name, f"https://{self.name}.example/item", self.name,
                query, "paper",
            )]

    harness = Harness(corpus_version="parallel-order", max_workers=3)
    steps = []
    started = time.monotonic()
    hits, failures = harness._search(
        [Delayed("slow", 0.06), Delayed("fast", 0.005), Delayed("middle", 0.025)],
        "parallel", 1, steps, deadline_at=time.monotonic() + 1,
    )
    elapsed = time.monotonic() - started

    assert failures == []
    assert [hit.connector for hit in hits] == ["slow", "fast", "middle"]
    assert [step["connector"] for step in steps] == ["slow", "fast", "middle"]
    assert all(step["elapsed_ms"] >= 0 for step in steps)
    assert all(step["queued_ms"] >= 0 for step in steps)
    assert elapsed < 0.11


def test_global_search_deadline_fails_closed_without_waiting_for_every_connector():
    class TooSlow:
        def __init__(self, name: str):
            self.name = name

        def search(self, query: str, *, limit: int = 5):
            time.sleep(0.2)
            return []

    harness = Harness(corpus_version="deadline", max_workers=2, deadline_seconds=0.02)
    started = time.monotonic()
    report = harness.run("deadline query", [TooSlow("one"), TooSlow("two")])
    elapsed = time.monotonic() - started

    assert elapsed < 0.12
    assert report.status == "failed"
    failed = [step for step in report.steps if step.get("status") == "failed"]
    assert failed
    assert all(step.get("error") == "deadline_exceeded" for step in failed)
    assert all("elapsed_ms" in step for step in failed)


def test_inherited_deadline_records_actual_stage_wait_not_local_default():
    class TooSlow:
        name = "slow"

        def search(self, query: str, *, limit: int = 5):
            time.sleep(0.2)
            return []

    harness = Harness(corpus_version="inherited-deadline", deadline_seconds=90)
    steps = []
    harness._search(
        [TooSlow()], "deadline", 1, steps,
        deadline_at=time.monotonic() + 0.02,
    )

    assert steps[0]["error"] == "deadline_exceeded"
    assert 0 <= steps[0]["elapsed_ms"] < 500


def test_connector_result_completed_after_deadline_is_discarded():
    import sys
    import time

    class LateCpu:
        name = "late-cpu"

        def search(self, query: str, *, limit: int = 5):
            until = time.monotonic() + 0.06
            while time.monotonic() < until:
                pass
            return [Hit("late-cpu", "https://example.test/late", query, "late", "paper")]

    harness = Harness(corpus_version="late-result", deadline_seconds=0.02)
    steps = []
    previous = sys.getswitchinterval()
    try:
        sys.setswitchinterval(0.2)
        hits, failures = harness._search(
            [LateCpu()], "late result", 1, steps,
            deadline_at=time.monotonic() + 0.02,
        )
    finally:
        sys.setswitchinterval(previous)

    assert hits == []
    assert failures == ["late-cpu"]
    assert steps[0]["status"] == "failed"
    assert steps[0]["error"] == "deadline_exceeded"


def test_default_http_transport_timeout_is_capped_by_remaining_budget(monkeypatch):
    from types import SimpleNamespace

    from ts.live import default_connectors

    seen = []

    class Response:
        text = '{"results": []}'

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, **kwargs):
        seen.append(kwargs["timeout"])
        return Response()

    monkeypatch.setattr("ts.live.httpx.get", fake_get)
    connector = default_connectors(SimpleNamespace(searxng_url="http://searx"))[0]
    harness = Harness(corpus_version="transport-budget", deadline_seconds=0.05)
    steps = []

    harness._search(
        [connector], "budget", 1, steps, deadline_at=time.monotonic() + 0.05,
    )

    assert len(seen) == 1
    assert 0 < seen[0] <= 0.05


def test_query_words_do_not_invent_a_market_link():
    hit = Hit("arxiv", "https://arxiv.org/abs/1", "Lab humidity sensor", "prototype", "paper",
              doi="10.1/h", published="2026-01-01")
    report = Harness(corpus_version="blob").run(
        "цепочка поставок нефтедобычи платёж", [Scripted("arxiv", [hit])],
    )
    shown = report.top or report.exclusion_registry
    assert shown[0]["chain_link"]["families"] == []


def test_success_phrases_do_not_mark_a_find_mature():
    hit = Hit("crossref", "https://doi.org/10.1/std", "Widget", "industry standard since 2019",
              "paper", doi="10.1/std")
    fired, evidence = markers([hit])
    assert fired == {}
    assert evidence == {}


def test_one_shared_word_does_not_outrank_the_query_phrase():
    from ts.harness import _subject_hits
    query = "anode-free sodium metal pouch cell"
    assert _subject_hits(query, "Sodium borate additive for calcium anodes") < _subject_hits(
        query, "Anode-free sodium metal pouch cell with Cu3P nanowires")


def test_journal_page_without_a_date_is_not_thrown_out_as_a_retelling():
    hit = Hit(
        "searxng",
        "https://www.sciencedirect.com/science/article/abs/pii/S2211285525003702",
        "Hafnium oxide ferroelectric memcapacitor array",
        "neuromorphic",
        "web",
    )
    report = Harness(corpus_version="journal").run(
        "ferroelectric hafnium oxide memory capacitor", [Scripted("searxng", [hit])],
    )
    assert report.top
    assert "M04" not in report.top[0]["reason_codes"]
    assert report.top[0]["subject_hits"] >= 1


def test_a_dated_on_topic_paper_sorts_above_a_fresh_off_topic_grant():
    paper = Hit(
        "crossref", "https://doi.org/10.1/hfo2",
        "Fatigue-resistant ferroelectric hafnium oxide", "grain boundaries", "paper",
        doi="10.1/hfo2", published="2026-07-03",
    )
    grant = Hit(
        "nsf", "https://www.nsf.gov/awardsearch/showAward?AWD_ID=1",
        "Collaborative Research: fine-tuning of large language models", "award", "registry",
        published="2026-08-14",
    )
    report = Harness(corpus_version="order").run(
        "ferroelectric hafnium oxide memory capacitor",
        [Scripted("crossref", [paper]), Scripted("nsf", [grant])],
    )
    titles = [row["technology"] for row in report.top]
    assert titles[0].startswith("Fatigue-resistant")
    grant_card = report.top[1]
    assert grant_card["subject_hits"] == 0
    assert "M04" not in grant_card["reason_codes"]


def test_indicator_only_is_not_called_a_mature_theme():
    hit = Hit("searxng", "https://blog.example/post", "Press note", "funding round", "web")
    report = Harness(corpus_version="indicator").run("press note", [Scripted("searxng", [hit])])
    card = report.exclusion_registry[0]
    assert card["policy_reason"] != "mature_parent"
    assert "M04" in card["reason_codes"]
    assert report.top == []


def test_success_phrase_does_not_keep_a_primary_source_out():
    hit = Hit("crossref", "https://doi.org/10.1/std", "Widget", "industry standard since 2019", "paper", doi="10.1/std")
    report = Harness(corpus_version="mature").run("widget", [Scripted("crossref", [hit])])
    assert report.top
    assert "M02" not in report.top[0]["reason_codes"]


def test_distinct_finds_are_separate_cards_and_still_miss_the_list():
    hits = [
        Hit("arxiv", "https://arxiv.org/abs/1", "Первый способ", "lab", "paper", doi="10.1/a", published="2026-01-01"),
        Hit("arxiv", "https://arxiv.org/abs/2", "Второй способ", "grant", "paper", doi="10.1/b", published="2026-02-01"),
        Hit("arxiv", "https://arxiv.org/abs/3", "Третий способ", "draft", "paper", doi="10.1/c", published="2026-03-01"),
    ]
    report = Harness(corpus_version="split").run("способ", [Scripted("arxiv", hits)])
    names = [row["technology"] for row in report.top]
    assert report.shortfall == 12
    assert set(names) == {"Первый способ", "Второй способ", "Третий способ"}
    assert all(row["label"] != "weak_signal" for row in report.top)
    assert all("P04_unknown" not in row["reason_codes"] for row in report.top)


def test_countersearch_does_not_mature_an_unrelated_find():
    paper = Hit("arxiv", "https://arxiv.org/abs/1", "Sodium sensor lab", "prototype", "paper",
                doi="10.1/a", published="2026-01-01")

    class Split:
        name = "arxiv"

        def search(self, query, *, limit=5):
            if "industry standard" in query:
                return [Hit("arxiv", "https://arxiv.org/abs/9", "Unrelated widget", "industry standard",
                            "paper", doi="10.9/z", published="2020-01-01")]
            return [paper]

    report = Harness(corpus_version="counter-split").run("sodium sensor", [Split()])
    assert report.top
    assert "M02" not in report.top[0]["reason_codes"]


def test_chain_pass_keeps_the_topic_and_drops_a_stray_title():
    topic = Hit("openalex", "https://openalex.org/W1", "Sodium battery cell", "prototype cell",
                "paper", doi="10.2/na", published="2026-04-01")
    stray = Hit("openalex", "https://openalex.org/W2", "Gesture recognition", "camera model",
                "paper", doi="10.2/gesture", published="2026-04-02")

    class Mixed:
        name = "openalex"

        def search(self, query, *, limit=5):
            if "next generation" in query:
                return [topic, stray]
            return [topic]

    report = Harness(corpus_version="chain-filter").run("sodium battery", [Mixed()])
    names = [row["technology"] for row in report.top]
    assert "Sodium battery cell" in names
    assert "Gesture recognition" not in names


def test_doi_card_and_truncated_web_title_are_one_event():
    full = "Anode-free sodium metal pouch cells enabled by Cu3P nanowire arrays on copper current collectors"
    paper = Hit("crossref", "https://doi.org/10.1016/j.ensm.2025.1", full, "pouch", "paper", doi="10.1016/j.ensm.2025.1")
    web = Hit(
        "searxng", "https://www.sciencedirect.com/science/article/pii/S1",
        "Anode-free sodium metal pouch cells enabled by ...", "pouch", "web",
    )
    events = dedup([paper, web])
    assert len(events) == 1
    assert events[0]["dedup_status"] == "merged"
    assert events[0]["key"].startswith("doi:")
    assert events[0]["urls"][0].startswith("https://doi.org/")
    report = Harness(corpus_version="merge").run(
        "anode-free sodium metal pouch cell", [Scripted("crossref", [paper]), Scripted("searxng", [web])],
    )
    assert len(report.top) == 1
    assert report.top[0]["technology"].startswith("Anode-free sodium metal pouch cells enabled")
    assert {source["url"] for source in report.top[0]["sources"]} == {paper.url, web.url}
    assert "M04" not in report.top[0]["reason_codes"]


def test_two_files_of_one_long_title_are_one_work():
    stem = "Performance analysis of a rare-earth-free axial flux permanent magnet motor using a pcb stator"
    video = Hit("crossref", "https://doi.org/10.1/mp4", f"{stem}_supp3-3669789.mp4", "video", "paper", doi="10.1/mp4")
    notes = Hit("crossref", "https://doi.org/10.1/docx", f"{stem}_supp4-3669789.docx", "notes", "paper", doi="10.1/docx")
    assert len(dedup([video, notes])) == 1


def test_short_shared_prefix_does_not_merge_two_papers():
    review = Hit("crossref", "https://doi.org/10.1/rev", "Anode-free sodium metal batteries: a review", "review", "paper", doi="10.1/rev")
    pouch = Hit("crossref", "https://doi.org/10.1/pouch", "Anode-free sodium metal pouch cell with Cu3P", "cell", "paper", doi="10.1/pouch")
    assert len(dedup([review, pouch])) == 2
    short = Hit("arxiv", "https://arxiv.org/abs/1", "Sodium battery cell", "a", "paper", doi="10.1/s")
    long = Hit("arxiv", "https://arxiv.org/abs/2", "Sodium battery cell degradation at low temperature", "b", "paper", doi="10.1/l")
    assert len(dedup([short, long])) == 2
    spaced = Hit("crossref", "https://doi.org/10.1/cu",
                 "Anode-free sodium metal pouch cell using Cu 3 P nanowires in situ grown on current collector",
                 "cell", "paper", doi="10.1/cu")
    glued = Hit("searxng", "https://advanced.onlinelibrary.wiley.com/doi/10.1/cu",
                "Anode-free sodium metal pouch cell using Cu3P nanowires in ...", "cell", "web")
    assert len(dedup([spaced, glued])) == 1


def test_generic_pair_needs_the_distinctive_word():
    from ts.harness import _subject_hits
    query = "anode-free sodium metal pouch cell"
    assert _subject_hits(query, "Design strategies for anode-free zinc metal batteries") == 0
    assert _subject_hits(query, "Practical anode-free lithium metal pouch cells") == 0
    assert _subject_hits(query, "Anode-free sodium metal pouch cell with Cu3P nanowires") >= 3


def test_off_topic_card_leaves_the_list_with_its_own_reason():
    sodium = Hit("crossref", "https://doi.org/10.1/na", "Anode-free sodium metal pouch cell", "pouch", "paper",
                 doi="10.1/na", published="2024-01-04")
    zinc = Hit("crossref", "https://doi.org/10.1/zn", "Design strategies for anode-free zinc metal batteries", "zinc",
               "paper", doi="10.1/zn", published="2024-01-04")
    report = Harness(corpus_version="topic").run(
        "anode-free sodium metal pouch cell", [Scripted("crossref", [sodium, zinc])],
    )
    assert [row["technology"] for row in report.top] == [
        "Anode-free sodium metal pouch cell",
        "Design strategies for anode-free zinc metal batteries",
    ]
    assert report.exclusion_registry == []


def test_ordinary_words_of_the_query_still_decide_the_list():
    stray = Hit("arxiv", "https://arxiv.org/abs/1", "Garnet electrolyte interface", "solid", "paper",
                doi="10.1/g", published="2026-01-01")
    kept = Hit("arxiv", "https://arxiv.org/abs/2", "Sulfide solid-state battery electrolyte", "cell", "paper",
               doi="10.1/s", published="2026-02-01")
    report = Harness(corpus_version="generic-query").run(
        "solid state battery", [Scripted("arxiv", [stray, kept])],
    )
    assert [row["technology"] for row in report.top] == [
        "Sulfide solid-state battery electrolyte",
        "Garnet electrolyte interface",
    ]


def test_the_subject_is_the_query_phrase_on_a_new_topic():
    from ts.harness import _subject_hits

    motor = "rare-earth-free axial flux electric motor"
    assert _subject_hits(motor, "Rare-earth-free axial-flux permanent-magnet motor") > 0
    assert _subject_hits(motor, "Rare-earth-free radial flux motor") == 0
    rocket = "rotating detonation rocket engine methane"
    assert _subject_hits(rocket, "Rotating detonation rocket engine with methane") > _subject_hits(
        rocket, "Pulse detonation rocket engine")
    ammonia = "ammonia cracking catalyst hydrogen carrier"
    assert _subject_hits(ammonia, "Ammonia cracking catalyst as a hydrogen carrier") > 0
    assert _subject_hits(ammonia, "Methanol cracking catalyst") == 0
    memory = Hit("crossref", "https://doi.org/10.1/mem", "Ferroelectric oxide memory capacitor", "array",
                 "paper", doi="10.1/mem", published="2026-03-01")
    other = Hit("crossref", "https://doi.org/10.1/gar", "Garnet electrolyte interface", "solid",
                "paper", doi="10.1/gar", published="2026-04-01")
    report = Harness(corpus_version="phrase").run(
        "oxide memory capacitor", [Scripted("crossref", [memory, other])],
    )
    assert [row["technology"] for row in report.top] == [
        "Ferroelectric oxide memory capacitor",
        "Garnet electrolyte interface",
    ]


def test_another_script_is_not_a_wrong_subject():
    from ts.harness import _subject_hits

    assert _subject_hits("твердооксидный топливный элемент", "Solid oxide fuel cell") == 1
    assert _subject_hits("solid oxide fuel cell", "固体氧化物燃料电池") == 1
    assert _subject_hits(
        "anode-free sodium metal pouch cell",
        "Design strategies for anode-free zinc metal batteries",
    ) == 0
    paper = Hit("crossref", "https://doi.org/10.1/sofc", "Solid oxide fuel cell", "electrolyte", "paper",
                doi="10.1/sofc", published="2026-05-01")
    report = Harness(corpus_version="script").run(
        "твердооксидный топливный элемент", [Scripted("crossref", [paper])],
    )
    assert report.top
    assert report.top[0]["policy_reason"] != "off_topic_for_query"
    assert report.exclusion_registry == []


def test_a_word_later_in_the_title_is_not_replaced():
    from ts.harness import _subject_hits

    query = "silicon carbide traction inverter"
    title = (
        "Design and Simulation of a Silicon Carbide MOSFET Inverter "
        "for Electric Vehicle Traction Applications using Python"
    )
    assert _subject_hits(query, title) > 0
    assert _subject_hits(
        "anode-free sodium metal pouch cell",
        "Practical anode-free lithium metal pouch cells",
    ) == 0


def test_unknown_date_is_explicit():
    hit = Hit("searxng", "https://example.com/n", "No date", "note", "web")
    report = Harness(corpus_version="date").run("x", [Scripted("searxng", [hit])])
    assert report.sources[0]["date"] is None
    assert report.sources[0]["date_unknown_reason"]
