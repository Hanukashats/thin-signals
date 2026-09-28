"""A mission sentence fans out. A named object does not. Weights stay put."""
from __future__ import annotations

from sqlalchemy import delete, select

from ts.db.models import Candidate, Decision, Run
from ts.fanout import is_wide, load_theme_plan, merge_theme_reports
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
    monkeypatch.setattr("ts.live.load_theme_plan", lambda: plan)
    monkeypatch.setattr(
        "ts.live.annotate_checklist",
        lambda top, overflow, settings, query=None: order.append("checklist") or {
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
    real_run = Harness.run

    def wrapped(self, *args, **kwargs):
        seen.append(kwargs.get("extractor", "missing"))
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
        assert len(first["top"]) == 4
        assert first["shortfall"] == 11
        assert second["repeated"] is True
        assert echo.queries == searched
        assert order == ["checklist", "scope", "reach"]
        assert seen and all(item is None for item in seen)
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
