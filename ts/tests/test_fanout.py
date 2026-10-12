"""A mission sentence fans out. A named object does not. Weights stay put."""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from ts.db.models import Candidate, Decision, Run
from ts.fanout import (
    aggregate_theme_candidate,
    explicit_origin_groups,
    is_wide,
    load_theme_plan,
    merge_theme_reports,
)
from ts.scale import apply_reader
from ts.scoring.scorer import load_rules
from ts.sources.connectors import Hit

MISSION = "2026 scientific discoveries and technological changes that reshape production chains and markets"
RUSSIAN = "новые научные механизмы и технологические сдвиги в энергетике материалах вычислениях и производстве"


def test_mission_sentences_are_wide_and_a_named_object_is_not():
    plan = load_theme_plan()
    assert is_wide(MISSION, plan)
    assert is_wide(RUSSIAN, plan)
    assert is_wide("early discoveries in computing energy materials manufacturing transport and medicine", plan)
    assert not is_wide("proton exchange membrane electrolyzer", plan)
    assert not is_wide("small modular nuclear reactor", plan)
    assert not is_wide("твердооксидный топливный элемент", plan)
    assert not is_wide("ядерная энергия", plan)
    queries = [theme["query"] for theme in plan["themes"]]
    assert "logistics" not in " ".join(queries)
    assert "startup" not in " ".join(queries)
    assert load_rules()["weights"]["primary"] == 0.35
    assert load_rules()["thresholds"]["weak_signal"] == 0.60


def test_live_repeat_key_changes_with_retrieval_fingerprint():
    from ts.live import _key

    first = _key("query", "rules-0.1", day="2026-10-12", retrieval="aaa")
    changed = _key("query", "rules-0.1", day="2026-10-12", retrieval="bbb")

    assert first != changed


def test_theme_plan_fingerprint_tracks_version_order_and_query_without_exposing_query():
    from ts.fanout import theme_plan_fingerprint

    plan = {
        "version": "one",
        "themes": [
            {"id": "a", "query": "alpha private phrase"},
            {"id": "b", "query": "beta private phrase"},
        ],
    }
    first = theme_plan_fingerprint(plan)
    reordered = theme_plan_fingerprint({**plan, "themes": list(reversed(plan["themes"]))})
    changed_version = theme_plan_fingerprint({**plan, "version": "two"})
    changed_query = theme_plan_fingerprint({
        **plan,
        "themes": [{"id": "a", "query": "new phrase"}, plan["themes"][1]],
    })

    assert len({first, reordered, changed_version, changed_query}) == 4
    assert "private" not in first and "phrase" not in first


def test_themes_take_turns_and_a_read_wide_shift_goes_first():
    alpha = {"id": "a", "title": "Альфа", "query": "alpha cell"}
    beta = {"id": "b", "title": "Бета", "query": "beta blade"}
    cards_a = [
        {"technology": "alpha one", "sources": [{"url": "https://a/1"}], "scope": None},
        {"technology": "alpha two", "sources": [{"url": "https://a/2"}], "scope": None},
    ]
    cards_b = [
        {"technology": "beta wide", "sources": [{"url": "https://b/1"}], "scope": 2},
        {"technology": "beta two", "sources": [{"url": "https://b/2"}], "scope": None},
    ]
    merged = merge_theme_reports([(alpha, cards_a), (beta, cards_b)], limit=3)
    assert [row["technology"] for row in merged["top"]] == ["beta wide", "alpha one", "alpha two"]
    assert merged["overflow"][0]["technology"] == "beta two"
    assert merged["overflow"][0]["policy_reason"] == "theme_quota"
    assert [note["taken"] for note in merged["themes"]] == [2, 1]


def test_theme_merge_uses_doi_and_url_as_joint_aliases_without_false_merges():
    alpha = {"id": "a", "title": "Alpha", "query": "alpha cell"}
    beta = {"id": "b", "title": "Beta", "query": "beta blade"}
    cards_a = [{
        "technology": "same event with DOI",
        "sources": [{"url": "https://source.test/shared", "doi": "10.1000/shared"}],
    }]
    cards_b = [
        {
            "technology": "same event without DOI",
            "sources": [{"url": "https://source.test/shared"}],
        },
        {
            "technology": "same DOI at a mirror",
            "sources": [{"url": "https://mirror.test/shared", "doi": "10.1000/shared"}],
        },
        {
            "technology": "unrelated event",
            "sources": [{"url": "https://source.test/other", "doi": "10.1000/other"}],
        },
    ]

    merged = merge_theme_reports([(alpha, cards_a), (beta, cards_b)], limit=10)

    assert [card["technology"] for card in merged["top"]] == [
        "same event with DOI",
        "unrelated event",
    ]
    assert merged["overflow"] == []


def test_same_url_with_conflicting_explicit_dois_remains_two_events():
    from ts.fanout import _identity_groups

    cards = [
        {
            "technology": "first work",
            "sources": [{"url": "https://source.test/shared", "doi": "10.1000/first"}],
        },
        {
            "technology": "second work",
            "sources": [{"url": "https://source.test/shared", "doi": "10.1000/second"}],
        },
    ]

    groups = _identity_groups(cards)
    merged = merge_theme_reports(
        [({"id": "a", "title": "Alpha", "query": "alpha"}, cards)],
        limit=10,
    )

    assert len(groups) == 2
    assert len(merged["top"]) == 2


def test_theme_documents_and_events_form_one_typed_candidate_without_mirror_inflation():
    theme = {"id": "memory", "title": "Memory", "query": "new memory mechanism"}
    cards = [
        {
            "technology": "Work A via OpenAlex",
            "events": 1,
            "sources": [{
                "url": "https://api.openalex.org/W1", "doi": "10.1000/a",
                "origin_ids": ["ror:lab-a"], "snippet": "first",
            }],
            "counter_sources": [],
        },
        {
            "technology": "Work A publisher mirror",
            "events": 1,
            "sources": [{
                "url": "https://doi.org/10.1000/a", "doi": "10.1000/a",
                "origin_ids": ["ror:lab-a"], "snippet": "first mirror",
            }],
            "counter_sources": [],
        },
        {
            "technology": "Work B",
            "events": 1,
            "sources": [{
                "url": "https://doi.org/10.1000/b", "doi": "10.1000/b",
                "origin_ids": ["ror:lab-b"], "snippet": "second",
            }],
            "counter_sources": [],
        },
    ]

    candidate = aggregate_theme_candidate(theme, cards)
    reversed_candidate = aggregate_theme_candidate(theme, list(reversed(cards)))

    assert candidate["technology"] == "new memory mechanism"
    assert candidate["candidate"] == {
        "version": "technology-candidate-0.1",
        "kind": "technology",
        "key": candidate["candidate"]["key"],
        "mechanism": "new memory mechanism",
        "document_groups": 2,
        "event_groups": 2,
        "origin_groups": ["ror:lab-a", "ror:lab-b"],
        "independence": "explicit",
    }
    assert candidate["candidate"] == reversed_candidate["candidate"]
    assert candidate["sources"] == reversed_candidate["sources"]
    assert candidate["events"] == 2


def test_multiple_hosts_without_explicit_origin_ids_do_not_invent_independence():
    cards = [{
        "technology": "mirrored work",
        "sources": [
            {"url": "https://one.example/work", "doi": "10.1000/a"},
            {"url": "https://two.example/work", "doi": "10.1000/a"},
        ],
    }]

    assert explicit_origin_groups(cards) == []
    assert aggregate_theme_candidate(
        {"id": "a", "title": "A", "query": "same mechanism"}, cards,
    )["candidate"]["independence"] == "unknown"


def test_doi_less_view_does_not_bridge_conflicting_doi_anchors():
    from ts.fanout import _identity_groups

    cards = [
        {"technology": "first", "sources": [{
            "url": "https://source.test/shared", "doi": "10.1000/first",
        }]},
        {"technology": "ambiguous", "sources": [{
            "url": "https://source.test/shared",
        }]},
        {"technology": "second", "sources": [{
            "url": "https://source.test/shared", "doi": "10.1000/second",
        }]},
    ]

    forward = sorted((identity for identity, _members in _identity_groups(cards)), key=repr)
    reverse = sorted((
        identity for identity, _members in _identity_groups(list(reversed(cards)))
    ), key=repr)

    assert len(forward) == 3
    assert forward == reverse


def test_source_metadata_prefers_doi_and_preserves_explicit_conflicts():
    from ts.live import _deduplicate_sources

    records = [
        {"url": "https://source.test/work", "name": "without DOI"},
        {"url": "https://source.test/work", "name": "second", "doi": "10.1000/b"},
        {"url": "https://source.test/work", "name": "first", "doi": "10.1000/a"},
    ]

    selected = _deduplicate_sources(records)
    reversed_selected = _deduplicate_sources(list(reversed(records)))

    assert [source["doi"] for source in selected] == ["10.1000/a", "10.1000/b"]
    assert selected == reversed_selected


def test_checklist_route_keeps_model_and_provider_from_the_same_card():
    from ts.live import _checklist_route

    checked = {
        "top": [{"checklist": {"model_id": "model-a", "provider": "ProviderA"}}],
        "excluded": [{"checklist": {"model_id": "model-b", "provider": "ProviderB"}}],
        "unread": [],
    }

    assert _checklist_route(checked) == ("model-a", "ProviderA")
    assert _checklist_route({"top": [], "excluded": checked["excluded"], "unread": []}) == (
        "model-b",
        "ProviderB",
    )
    assert _checklist_route({"top": [], "excluded": [], "unread": []}) == (None, None)


def test_wide_run_status_preserves_theme_failures():
    from ts.live import _wide_status

    assert _wide_status(["succeeded", "succeeded"]) == "succeeded"
    assert _wide_status(["succeeded", "degraded"]) == "degraded"
    assert _wide_status(["succeeded", "failed"]) == "degraded"
    assert _wide_status(["failed", "failed"]) == "failed"
    assert _wide_status([]) == "failed"


def test_wide_retrieval_telemetry_is_bounded_and_marks_cached_work():
    from ts.harness import RunReport
    from ts.persist import public_report

    report = RunReport(
        id="wide", query="mission", idempotency_key="wide-key", repeated=False,
        steps=[
            {
                "name": "search", "connector": "openalex", "status": "ok", "n": 3,
                "elapsed_ms": 40, "queued_ms": 2, "theme": "one", "cached": False,
                "raw_prompt": "must never leave the process",
            },
            {
                "name": "search", "connector": "openalex", "status": "failed",
                "error": "ReadTimeout", "elapsed_ms": 90, "queued_ms": 1,
                "theme": "two", "cached": True, "raw_response": "private",
            },
        ],
        sources=[{"url": "https://example.test/work"}], events=[],
        card={
            "label": None, "confidence": None, "policy_action": "HOLD",
            "policy_reason": "no_admitted_cards", "reason_codes": [],
            "predictors": [], "rules_version": "rules-0.1",
        },
        top=[], shortfall=15, exclusion_registry=[], status="degraded",
        fanout={
            "deadline_skipped": [], "discovered_events": 2,
            "theme_runs": [
                {"id": "one", "status": "succeeded", "repeated": False},
                {"id": "two", "status": "degraded", "repeated": True},
            ],
        },
    )

    retrieval = public_report(report)["retrieval"]

    assert all("raw_prompt" not in step and "raw_response" not in step for step in retrieval["connectors"])
    assert retrieval["stages"][0]["executed"] == 1
    assert retrieval["stages"][0]["cached"] == 1
    assert retrieval["stages"][0]["wall_ms"] == 42
    assert retrieval["theme_degraded"] == 1
    assert retrieval["deadline_exhausted"] is False
    assert retrieval["funnel"]["deduplicated_events"] == 2


def test_empty_run_has_its_own_verdict_and_summarizes_exclusions():
    from ts.live import _empty_card

    card = _empty_card(
        "rules-0.1",
        [
            {"policy_reason": "checklist_below_watchlist"},
            {"policy_reason": "checklist_below_watchlist"},
            {"policy_reason": "other_mechanism_after_read"},
        ],
        [{"technology": "без текста"}],
    )

    assert card["policy_action"] == "HOLD"
    assert card["policy_reason"] == "no_admitted_cards"
    assert card["label"] is None and card["confidence"] is None
    assert "никто не допущен" in card["chain_link"]["sentence"]
    assert "— 2" in card["chain_link"]["sentence"]
    assert "нет доступного текста" in card["chain_link"]["sentence"]


class _Echo:
    name = "arxiv"

    def __init__(self):
        self.queries: list[str] = []

    def search(self, query: str, *, limit: int = 5):
        self.queries.append(query)
        if "supply chain" in query or "mass adoption" in query or "цепочка поставок" in query:
            return []
        hits = []
        for index in (1, 2):
            hits.append(Hit(
                "arxiv",
                f"https://arxiv.org/abs/{query}-{index}",
                f"{query} study {index}",
                "experiment",
                "paper",
                published="2026-03-01",
                doi=f"10.9/{abs(hash(query)) % 100000}-{index}",
            ))
        return hits


def test_reader_names_scale_and_does_not_drop_a_card():
    from ts.scoring.order import scope_rank

    cards = [
        {"technology": "local step", "sources": [{"url": "https://a/1"}]},
        {"technology": "wide mechanism", "sources": [{"url": "https://b/1"}]},
    ]

    def reader(card):
        if "wide" in card["technology"]:
            return 2, "текст говорит о нескольких цепочках", "openai/gpt-5.6-luna"
        if card["technology"].startswith("local"):
            raise RuntimeError("reader down")
        return 1, "одна цепочка", "openai/gpt-5.6-luna"

    out = apply_reader(cards, reader)
    assert [row["technology"] for row in out] == ["local step", "wide mechanism"]
    assert out[0]["scope"] is None
    ordered = sorted(out, key=scope_rank, reverse=True)
    assert ordered[0]["technology"] == "wide mechanism"
    assert ordered[0]["scope_why"].startswith("текст")


def test_wide_query_searches_themes_and_a_repeat_does_not(monkeypatch):
    from ts.db import session_factory
    from ts.live import run_query

    plan = {
        "version": "themes-test",
        "frame": ["scientific", "discoveries", "technological", "changes", "reshape", "production", "chains", "markets"],
        "themes": [
            {"id": "a", "title": "Альфа", "query": "zzfanout alpha battery cell"},
            {"id": "b", "title": "Бета", "query": "zzfanout beta turbine blade"},
        ],
    }
    order = []
    asked = []
    monkeypatch.setattr("ts.live.load_theme_plan", lambda: plan)
    monkeypatch.setattr(
        "ts.live.annotate_checklist",
        lambda top, overflow, settings, query=None: order.append("checklist") or asked.append(query) or {
            "top": top, "excluded": [], "overflow": overflow, "unread": [], "stats": {"read": 0},
        },
    )
    monkeypatch.setattr(
        "ts.live.annotate_scopes",
        lambda cards, settings: order.append("scope") or cards,
    )
    monkeypatch.setattr(
        "ts.live.annotate_reach",
        lambda cards, settings: order.append("reach") or cards,
    )
    from ts.harness import Harness
    seen = []
    inherited_deadlines = []
    real_run = Harness.run

    def wrapped(self, *args, **kwargs):
        seen.append(kwargs.get("extractor", "missing"))
        inherited_deadlines.append(kwargs.get("deadline_at"))
        return real_run(self, *args, **kwargs)

    monkeypatch.setattr(Harness, "run", wrapped)
    echo = _Echo()
    factory = session_factory()
    mission = "scientific discoveries and technological changes reshape production chains markets"
    first = run_query(mission, limit=2, connectors=[echo], session_factory=factory)
    searched = list(echo.queries)
    second = run_query(mission, limit=2, connectors=[echo], session_factory=factory)
    try:
        assert mission not in searched
        assert "zzfanout alpha battery cell" in searched
        assert "zzfanout beta turbine blade" in searched
        assert [row["theme"] for row in first["top"][:2]] == ["a", "b"]
        assert len(first["top"]) == 2
        assert first["shortfall"] == 13
        assert all(row["candidate"]["version"] == "technology-candidate-0.1" for row in first["top"])
        assert all(row["candidate"]["event_groups"] == 2 for row in first["top"])
        assert second["repeated"] is True
        assert echo.queries == searched
        assert first["retrieval"]["connectors"]
        assert all(step.get("theme") in {"a", "b"} for step in first["retrieval"]["connectors"])
        assert first["retrieval"]["funnel"]["discovery_items"] >= 4
        assert first["retrieval"]["funnel"]["unique_sources"] >= 4
        assert order == ["checklist", "scope", "reach"]
        assert asked == [None]
        assert seen and all(item is None for item in seen)
        assert all(item is not None for item in inherited_deadlines)
        assert len(set(inherited_deadlines)) == 1
        assert "Альфа" in "\n".join(__import__("ts.ui_text", fromlist=["screen"]).screen(first)["lines"])
        with factory() as session:
            mission_row = session.scalar(select(Run).where(Run.query == mission))
            theme_row = session.scalar(select(Run).where(Run.query == "zzfanout alpha battery cell"))
            from ts.checklist import CHECKLIST_VERSION
            from ts.live import CORPUS
            assert mission_row.corpus_version == f"{CORPUS}+themes-test+{CHECKLIST_VERSION}"
            assert theme_row.corpus_version == CORPUS
    finally:
        with factory() as session:
            rows = session.scalars(select(Run).where(Run.query.in_([
                mission, "zzfanout alpha battery cell", "zzfanout beta turbine blade",
            ]))).all()
            ids = [row.id for row in rows]
            if ids:
                session.execute(delete(Decision).where(Decision.run_id.in_(ids)))
                session.execute(delete(Run).where(Run.id.in_(ids)))
                session.execute(delete(Candidate).where(Candidate.id.in_([f"live-{item}" for item in ids])))
                session.commit()


def test_expired_wide_deadline_does_not_start_new_theme_tasks(monkeypatch):
    from sqlalchemy import delete

    from ts.db import session_factory
    from ts.db.models import Candidate, Decision, Run
    from ts.live import run_query
    from ts.settings import load

    plan = {
        "version": "themes-deadline-test",
        "frame": ["scientific", "discoveries", "technological", "changes"],
        "themes": [
            {"id": "a", "title": "Альфа", "query": "zzdeadline alpha cell"},
            {"id": "b", "title": "Бета", "query": "zzdeadline beta blade"},
        ],
    }
    monkeypatch.setattr("ts.live.load_theme_plan", lambda: plan)
    settings = load()
    settings.wide_search_deadline_seconds = 0
    echo = _Echo()
    factory = session_factory()
    mission = "scientific discoveries technological changes"

    report = run_query(
        mission, limit=1, settings=settings, connectors=[echo], session_factory=factory,
    )
    try:
        assert echo.queries == []
        assert report["run_status"] == "failed"
        assert report["fanout"]["deadline_skipped"] == ["a", "b"]
        assert report["retrieval"]["deadline_exhausted"] is True
        assert report["retrieval"]["failures"] == 0
        assert report["retrieval"]["theme_failures"] == 2
        assert report["retrieval"]["deadline_skipped_themes"] == ["a", "b"]
        assert report["retrieval"]["funnel"] is None
    finally:
        with factory() as session:
            row = session.scalar(select(Run).where(Run.query == mission))
            if row is not None:
                session.execute(delete(Decision).where(Decision.run_id == row.id))
                session.execute(delete(Run).where(Run.id == row.id))
                session.execute(delete(Candidate).where(Candidate.id == f"live-{row.id}"))
                session.commit()


def test_changed_wide_budget_does_not_reuse_a_deadline_failed_theme(monkeypatch):
    import copy
    import time

    from ts.live import run_query
    from ts.persist import public_report
    from ts.settings import load

    plan = {
        "version": "themes-budget-cache-test",
        "frame": ["scientific", "discoveries", "technological", "changes"],
        "themes": [{"id": "a", "title": "Альфа", "query": "zzbudget alpha cell"}],
    }
    monkeypatch.setattr("ts.live.load_theme_plan", lambda: plan)
    monkeypatch.setattr(
        "ts.live.annotate_checklist",
        lambda top, overflow, settings, query=None: {
            "top": top, "excluded": [], "overflow": overflow, "unread": [],
            "stats": {"read": 0},
        },
    )
    monkeypatch.setattr("ts.live.annotate_scopes", lambda cards, settings: cards)
    monkeypatch.setattr("ts.live.annotate_reach", lambda cards, settings: cards)

    stored = {}

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        "ts.live.load_report",
        lambda _session, key: copy.deepcopy(stored.get(key)),
    )
    monkeypatch.setattr(
        "ts.live.save_report",
        lambda _session, report: stored.__setitem__(report.idempotency_key, public_report(report)),
    )

    class SlowFirst(_Echo):
        def search(self, query: str, *, limit: int = 5):
            self.queries.append(query)
            if len(self.queries) == 1:
                time.sleep(0.15)
                return []
            return super().search(query, limit=limit)

    connector = SlowFirst()
    settings = load()
    settings.search_deadline_seconds = 1
    settings.wide_search_deadline_seconds = 0.05
    mission = "scientific discoveries technological changes zzbudget"

    first = run_query(
        mission, limit=1, settings=settings, connectors=[connector],
        session_factory=lambda: Session(),
    )
    calls_after_failure = len(connector.queries)
    settings.wide_search_deadline_seconds = 1
    second = run_query(
        mission, limit=1, settings=settings, connectors=[connector],
        session_factory=lambda: Session(),
    )

    assert first["run_status"] == "failed"
    assert calls_after_failure == 1
    assert second["repeated"] is False
    assert len(connector.queries) > calls_after_failure


def test_plan_revision_does_not_reuse_a_failed_theme_run(monkeypatch):
    import copy

    from ts.live import run_query
    from ts.persist import public_report
    from ts.settings import load

    plan = {
        "version": "plan-one",
        "frame": ["scientific", "discoveries", "technological", "changes"],
        "themes": [{"id": "a", "title": "Alpha", "query": "zzplan alpha cell"}],
    }
    monkeypatch.setattr("ts.live.load_theme_plan", lambda: plan)
    stored = {}

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        "ts.live.load_report",
        lambda _session, key: copy.deepcopy(stored.get(key)),
    )
    monkeypatch.setattr(
        "ts.live.save_report",
        lambda _session, report: stored.__setitem__(report.idempotency_key, public_report(report)),
    )

    class Fails:
        name = "fails"

        def __init__(self):
            self.calls = 0

        def search(self, query: str, *, limit: int = 5):
            self.calls += 1
            raise TimeoutError(query)

    connector = Fails()
    settings = load()
    mission = "scientific discoveries technological changes zzplan"
    first = run_query(
        mission, limit=1, settings=settings, connectors=[connector],
        session_factory=lambda: Session(),
    )
    calls_after_first = connector.calls
    plan["version"] = "plan-two"
    second = run_query(
        mission, limit=1, settings=settings, connectors=[connector],
        session_factory=lambda: Session(),
    )

    assert first["run_status"] == "failed"
    assert second["run_status"] == "failed"
    assert second["repeated"] is False
    assert connector.calls > calls_after_first


@pytest.mark.parametrize(
    ("doi_by_theme", "duplicate_beta", "expected_discovery_items"),
    [
        ({"alpha": "10.1000/same", "beta": "10.1000/same"}, False, 2),
        ({"alpha": "10.1000/same", "beta": None}, False, 2),
        ({"alpha": None, "beta": "10.1000/same"}, False, 2),
        ({"alpha": None, "beta": None}, True, 3),
    ],
)
def test_wide_funnel_deduplicates_theme_events_and_keeps_child_exclusion(
    monkeypatch, doi_by_theme, duplicate_beta, expected_discovery_items,
):
    from contextlib import nullcontext
    from pathlib import Path
    from time import monotonic
    from types import SimpleNamespace

    from ts import live
    from ts.persist import public_report

    settings = SimpleNamespace(
        rules_version="rules-0.1",
        search_max_workers=2,
        search_deadline_seconds=90,
        source_timeout_seconds=40,
        wide_search_deadline_seconds=540,
        snapshot_dir=Path("/dev/null"),
    )
    plan = {
        "version": "global-event-funnel",
        "frame": [],
        "themes": [
            {"id": value, "title": value, "query": f"{value} battery"}
            for value in ("alpha", "beta")
        ],
    }

    class SameIndicator:
        name = "test-indicator"

        def search(self, query: str, *, limit: int = 1):
            if "mass adoption" in query:
                return []
            theme = "alpha" if "alpha" in query else "beta"
            hit = Hit(
                self.name,
                "https://untrusted.example/same",
                "Alpha beta battery study",
                "Battery experiment reported.",
                "web",
                doi=doi_by_theme[theme],
            )
            return [hit, hit] if duplicate_beta and theme == "beta" else [hit]

    saved = []
    monkeypatch.setattr(live, "load_report", lambda _session, _key: None)
    monkeypatch.setattr(
        live,
        "save_report",
        lambda _session, report: saved.append(public_report(report)),
    )
    monkeypatch.setattr(live, "_near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "_potential", lambda *_args, **_kwargs: [])

    out = live._run_wide(
        "audit mission",
        plan,
        limit=1,
        extract=False,
        settings=settings,
        connectors=[SameIndicator()],
        session_factory=lambda: nullcontext(None),
        day="2026-10-12",
        deadline_at=monotonic() + 10,
    )

    funnel = out["retrieval"]["funnel"]
    assert funnel["discovery_items"] == expected_discovery_items
    assert funnel["unique_sources"] == 1
    assert funnel["deduplicated_events"] == 1
    assert funnel["excluded"] == 1
    assert funnel["admitted"] == 0
    assert funnel["unread"] == 0
    assert len(out["exclusion_registry"]) == 1
    exclusion = out["exclusion_registry"][0]
    assert exclusion["reason_codes"] == ["M04"]
    if any(doi_by_theme.values()):
        assert any(
            source.get("doi") == "10.1000/same"
            for source in out["sources"]
        )
        assert any(
            source.get("doi") == "10.1000/same"
            for source in exclusion["sources"]
        )


@pytest.mark.parametrize(
    ("records", "expected_child_observations"),
    [
        (
            {
                "alpha": ("https://untrusted.example/same", "web", "10.1000/same"),
                "beta": ("https://github.com/example/same", "web", "10.1000/same"),
                "gamma": ("https://github.com/example/same", "repository", None),
            },
            2,
        ),
        (
            {
                "alpha": ("https://arxiv.org/abs/2601.01234", "web", "10.1000/same"),
                "beta": ("https://github.com/example/same", "repository", None),
                "gamma": ("https://github.com/example/same", "web", "10.1000/same"),
            },
            1,
        ),
    ],
)
def test_global_alias_bridge_deduplicates_admission_in_every_theme_order(
    monkeypatch, records, expected_child_observations,
):
    from contextlib import nullcontext
    from pathlib import Path
    from time import monotonic
    from types import SimpleNamespace

    from ts import live
    from ts.checklist import apply_checklist
    from ts.persist import public_report
    from ts.tests.test_checklist import _out, _read

    settings = SimpleNamespace(
        rules_version="rules-0.1",
        search_max_workers=2,
        search_deadline_seconds=90,
        source_timeout_seconds=40,
        wide_search_deadline_seconds=540,
        snapshot_dir=Path("/dev/null"),
    )

    class AliasBridge:
        name = "test-alias-bridge"

        def search(self, query: str, *, limit: int = 1):
            if "mass adoption" in query:
                return []
            theme = query.split()[0]
            url, source_type, doi = records[theme]
            return [Hit(
                self.name,
                url,
                "Alpha beta gamma battery study",
                "Battery experiment reported.",
                source_type,
                doi=doi,
            )]

    def reader(_card):
        return _read(_out(
            verified={"P01", "P02", "P03"}, transition="verified",
        ))
    outcomes = []
    event_keys = []
    monkeypatch.setattr(live, "load_report", lambda _session, _key: None)
    monkeypatch.setattr(live, "_near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "_potential", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "annotate_scopes", lambda cards, _settings: cards)
    monkeypatch.setattr(live, "annotate_reach", lambda cards, _settings: cards)
    monkeypatch.setattr(
        live,
        "annotate_checklist",
        lambda top, overflow, _settings, query=None: apply_checklist(
            top, overflow, reader, load_rules()
        ),
    )

    for order in (("alpha", "beta", "gamma"), ("beta", "alpha", "gamma")):
        plan = {
            "version": "alias-bridge-order",
            "frame": [],
            "themes": [
                {"id": value, "title": value, "query": f"{value} battery"}
                for value in order
            ],
        }
        saved = []
        monkeypatch.setattr(
            live,
            "save_report",
            lambda _session, report, saved=saved: saved.append((
                public_report(report), report.events,
            )),
        )
        outcomes.append(live._run_wide(
            "audit mission",
            plan,
            limit=1,
            extract=False,
            settings=settings,
            connectors=[AliasBridge()],
            session_factory=lambda: nullcontext(None),
            day="2026-10-12",
            deadline_at=monotonic() + 10,
        ))
        event_keys.append(saved[-1][1])

    for out in outcomes:
        funnel = out["retrieval"]["funnel"]
        assert funnel["deduplicated_events"] == 1
        assert funnel["admitted"] == 1
        assert funnel["excluded"] == 0
        assert out["fanout"]["child_exclusion_observations"] == expected_child_observations
        assert out["fanout"]["unique_child_exclusions"] == 1
    assert event_keys[0] == event_keys[1]


class _DatedEcho(_Echo):
    takes_since = True

    def __init__(self):
        super().__init__()
        self.calls: list[tuple[str, str | None]] = []

    def search(self, query: str, *, limit: int = 5, since: str | None = None):
        self.calls.append((query, since))
        return super().search(query, limit=limit)


def test_wide_run_is_fresh_each_utc_day_and_themes_ask_for_the_last_year(monkeypatch):
    from ts.db import session_factory
    from ts.live import run_query

    themes = ["zzfresh alpha battery cell", "zzfresh beta turbine blade"]
    plan = {
        "version": "themes-test",
        "frame": ["scientific", "discoveries", "technological", "changes", "reshape", "production", "chains", "markets"],
        "themes": [
            {"id": "a", "title": "Альфа", "query": themes[0]},
            {"id": "b", "title": "Бета", "query": themes[1]},
        ],
    }
    monkeypatch.setattr("ts.live.load_theme_plan", lambda: plan)
    monkeypatch.setattr(
        "ts.live.annotate_checklist",
        lambda top, overflow, settings, query=None: {
            "top": top, "excluded": [], "overflow": overflow, "unread": [], "stats": {"read": 0},
        },
    )
    monkeypatch.setattr("ts.live.annotate_scopes", lambda cards, settings: cards)
    monkeypatch.setattr("ts.live.annotate_reach", lambda cards, settings: cards)
    echo = _DatedEcho()
    factory = session_factory()
    mission = "scientific discoveries technological changes reshape production chains markets zzfresh"
    try:
        monkeypatch.setattr("ts.live._today", lambda: "2026-10-01")
        first = run_query(mission, limit=2, connectors=[echo], session_factory=factory)
        day_one = list(echo.calls)
        again = run_query(mission, limit=2, connectors=[echo], session_factory=factory)
        assert first.get("repeated") is not True
        assert again["repeated"] is True
        assert echo.calls == day_one
        searched = [since for query, since in day_one if query in themes]
        assert searched and all(since == "2025-10-01" for since in searched)
        assert all(since is None for query, since in day_one if "mass adoption" in query)

        monkeypatch.setattr("ts.live._today", lambda: "2026-10-02")
        next_day = run_query(mission, limit=2, connectors=[echo], session_factory=factory)
        assert next_day.get("repeated") is not True
        fresh = echo.calls[len(day_one):]
        assert {query for query, _ in fresh} >= set(themes)
        assert all(since == "2025-10-02" for query, since in fresh if query in themes)
    finally:
        with factory() as session:
            rows = session.scalars(select(Run).where(Run.query.in_([mission, *themes]))).all()
            ids = [row.id for row in rows]
            if ids:
                session.execute(delete(Decision).where(Decision.run_id.in_(ids)))
                session.execute(delete(Run).where(Run.id.in_(ids)))
                session.execute(delete(Candidate).where(Candidate.id.in_([f"live-{item}" for item in ids])))
                session.commit()


def test_a_connector_without_a_date_filter_is_called_as_before():
    from ts.harness import Harness

    echo = _Echo()
    Harness(since="2025-10-01").run("zzplain cell", [echo], limit=2)
    assert "zzplain cell" in echo.queries


def test_dated_connectors_put_the_date_in_their_native_filter():
    from urllib.parse import unquote

    from ts.sources.connectors import (
        ArxivConnector,
        CrossrefConnector,
        EuropePmcConnector,
        HalConnector,
        OpenAlexConnector,
    )

    empty = {
        "arxiv": '<feed xmlns="http://www.w3.org/2005/Atom"></feed>',
        "openalex": '{"results": []}',
        "crossref": '{"message": {"items": []}}',
        "europepmc": '{"resultList": {"result": []}}',
        "hal": '{"response": {"docs": []}}',
    }
    expected = {
        "arxiv": "(all:sodium cell) AND submittedDate:[202510010000 TO 209912312359]",
        "openalex": "filter=from_publication_date:2025-10-01",
        "crossref": "filter=from-pub-date:2025-10-01",
        "europepmc": "query=(sodium cell) AND FIRST_PDATE:[2025-10-01 TO 2099-12-31]",
        "hal": "fq=producedDate_tdate:[2025-10-01T00:00:00Z TO *]",
    }
    for cls in (ArxivConnector, OpenAlexConnector, CrossrefConnector, EuropePmcConnector, HalConnector):
        urls = []

        def get(url, name=cls.name, urls=urls):
            urls.append(url)
            return empty[name]

        connector = cls(get)
        assert connector.takes_since is True
        assert connector.search("sodium cell", limit=3, since="2025-10-01") == []
        assert connector.search("sodium cell", limit=3) == []
        assert connector.search("sodium cell", limit=3, since="2025-10-01&x=1") == []
        dated, plain, bad = (unquote(url.replace("+", " ")) for url in urls)
        assert expected[cls.name] in dated, (cls.name, dated)
        assert "2025-10-01" not in plain and "20251001" not in plain
        assert bad == plain


def test_theme_queue_prefers_the_newer_card_among_those_with_the_query_words():
    theme = {"id": "a", "title": "Альфа", "query": "alpha cell"}
    cards = [
        {"technology": "old match", "subject_hits": 2, "sources": [{"url": "https://a/old", "date": "2021-05-01"}]},
        {"technology": "no date", "subject_hits": 2, "sources": [{"url": "https://a/nodate", "date": None}]},
        {"technology": "new match", "subject_hits": 1, "sources": [{"url": "https://a/new", "date": "2026-06-01"}]},
        {"technology": "off words", "subject_hits": 0, "sources": [{"url": "https://a/off", "date": "2026-09-01"}]},
    ]
    merged = merge_theme_reports([(theme, cards)], limit=1)
    assert [row["technology"] for row in merged["top"]] == ["new match"]
    assert [row["technology"] for row in merged["overflow"]] == ["old match", "no date", "off words"]
