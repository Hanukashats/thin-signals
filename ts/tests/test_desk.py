"""Viewer document, admin gate, and draft notes. No scoring."""
from __future__ import annotations

from ts.access import can_admin, hash_password, role_for, verify_password
from ts.desk import compose_query, document, field_help, load_draft, reasoning, save_draft, score_story

PAYLOAD = {
    "run_status": "succeeded",
    "signal_label": "noise",
    "policy_action": "WATCHLIST",
    "policy_reason": "no_verified_change",
    "reason_codes": ["M04"],
    "predictors": [],
    "sources": [],
    "exclusion_registry": [],
    "shortfall": 15,
    "counters": {"sources": 1, "admitted": 0, "excluded": 1, "confident": 0},
}


def test_document_keeps_run_status_and_label_apart():
    text = document(PAYLOAD, "фотонный процессор", "только пилоты", "2026-01-01", "2026-09-01")
    assert "Статус прогона: поиск дошёл до конца (succeeded)" in text
    assert "Метка сигнала: шум" in text
    assert "Направление: фотонный процессор" in text
    assert "Период: 2026-01-01 — 2026-09-01" in text
    chain = reasoning(PAYLOAD)
    assert chain["conclusion"] == "шум"
    assert any("no_verified_change" in step for step in chain["steps"])
    assert any("не видно, что способ работы реально сменился" in step for step in chain["steps"])
    assert any("нашлись только пересказы" in step for step in chain["steps"])
    unknown = reasoning({"policy_reason": "no_verified_change", "reason_codes": ["P04_unknown", "insufficient_evidence"], "signal_label": "noise"})
    blob = " ".join(unknown["steps"])
    assert "этот признак не разобран" in blob
    assert "фактов мало" in blob
    assert "служебный код без расшифровки" not in blob
    assert "succeeded" not in chain["conclusion"]


def test_every_field_has_what_why_and_how():
    for field_id in ("direction", "correction", "period", "run_status", "signal_label", "prompt_draft", "logic_note"):
        help_text = field_help(field_id)
        assert "Зачем:" in help_text
        assert "Как менять:" in help_text


def test_query_needs_a_direction_and_stays_short():
    assert "период" in compose_query("клетка", "", "2026-01-01", "")
    try:
        compose_query("x", "", "", "")
        raise AssertionError("one letter is not a direction")
    except ValueError:
        pass
    try:
        compose_query("а" * 401, "", "", "")
        raise AssertionError("overlong query must fail")
    except ValueError:
        pass


def test_viewer_cannot_open_admin_and_password_roundtrip(tmp_path):
    stored = hash_password("desk-test-secret")
    assert verify_password("desk-test-secret", stored)
    assert not verify_password("other", stored)
    accounts = {
        "user1": {"role": "viewer", "password_hash": stored},
        "admin": {"role": "admin", "password_hash": stored},
    }
    assert role_for(accounts, "user1", "desk-test-secret") == "viewer"
    assert role_for(accounts, "admin", "wrong") is None
    assert can_admin("viewer") is False
    assert can_admin("admin") is True
    path = tmp_path / "draft.yaml"
    save_draft(path, "новый чек-лист", "порог не трогать с экрана")
    loaded = load_draft(path)
    assert loaded["prompt_draft"] == "новый чек-лист"
    assert "applied_to_scorer: false" in path.read_text(encoding="utf-8")


def test_score_story_is_not_a_startup_probability():
    story = score_story({
        "confidence": 0.42,
        "predictors": [
            {"code": "P01", "contribution": 0.35, "weight": 0.35, "value": "verified"},
            {"code": "IND", "contribution": 0.07, "weight": 0.2, "value": 0.35},
        ],
        "top": [{"technology": "фотон", "label": "weak_signal", "confidence": 0.42}],
    })
    assert story["lines"][1] == "Итог суммы: 0.42."
    assert "(P01)" in story["lines"][2] and "новый механизм" in story["lines"][2]
    assert "(IND)" in story["lines"][3]
    assert "стартап" in story["disclaimer"]
    assert "акци" in story["disclaimer"]
    assert story["top"] == ["фотон: слабый сигнал, уверенность 0.42"]
    from ts.desk import candidate_views, run_banner
    bare = candidate_views([{"technology": "обзор", "confidence": 0, "label": "noise", "sources": [
        {"name": "Статья", "url": "https://example.org/a", "date": "2024-01-01", "type": "paper", "language": "en", "trust": "primary"},
    ]}])
    assert "не оценивались" in bare[0]["confidence_note"]
    story_bare = score_story({
        "top": [{"technology": "обзор", "confidence": 0, "label": "noise"}],
        "confidence": 0, "predictors": [],
    })
    assert "шум" not in story_bare["top"][0]
    assert "0.0" not in story_bare["top"][0]
    from ts.ui_text import shown_label
    assert shown_label({"signal_label": "noise", "top": [{"confidence": 0}]}) == "признаки не оценивались"
    assert "Дополнительно прочитать тексты" not in open("ui/app.py", encoding="utf-8").read()
    assert bare[0]["case"].startswith("Кейс")
    assert "https://example.org/a" in bare[0]["sources"][0]
    banner = run_banner({"top": [{"confidence": 0}], "counters": {"admitted": 1, "sources": 2, "confident": 0}})
    assert any("не применимо" in line for line in banner)
    stopped = score_story({"confidence": None, "predictors": [{"code": "M04", "contribution": -0.3, "weight": -0.3, "value": 1}]})
    assert stopped["lines"][0].startswith("Стоппер")
    text = document(PAYLOAD, "клетка", "", "", "")
    assert "не вероятность" in text
    assert "Статус прогона: поиск дошёл до конца (succeeded)" in text
    assert "Метка сигнала: шум" in text


def test_viewer_requires_login():
    from pathlib import Path
    text = Path("ui/app.py").read_text(encoding="utf-8")
    assert "def require_login()" in text
    assert "st.stop()" in text
    assert "не обязателен" not in text


def test_empty_chain_says_so():
    chain = reasoning({"signal_label": "weak_signal"})
    assert chain["steps"] == ["Цепочка пуста: прогон не вернул причины."]
    assert chain["conclusion"] == "слабый сигнал"


def _scored(name: str, confidence, reason: str = "checklist_below_watchlist") -> dict:
    return {
        "technology": name, "confidence": confidence, "policy_reason": reason,
        "checklist": {"status": "scored"},
        "predictors": [{"code": "P01", "contribution": 0.25, "weight": 0.25, "value": "supported"}],
    }


def test_near_miss_keeps_only_scored_cards_just_under_the_watchlist():
    from ts.desk import near_miss_cards

    registry = [
        _scored("низко", 0.175),
        _scored("уже высоко", 0.575),
        _scored("рядом", 0.325),
        _scored("контр", 0.3, reason="checklist_counter"),
        {"technology": "запас", "policy_reason": "theme_quota", "confidence": 0.3},
        {"technology": "без текста", "policy_reason": "no_source_text", "confidence": None,
         "checklist": {"status": "no_fragment"}},
        {"technology": "читатель упал", "policy_reason": "reader_failed", "confidence": 0.3,
         "checklist": {"status": "reader_failed"}},
        _scored("строка", "0.3"),
        _scored("порог", 0.35),
        _scored("пол", 0.25),
    ]
    names = [card["technology"] for card in near_miss_cards({"exclusion_registry": registry})]
    assert names == ["рядом", "пол"]

    many = [_scored(f"т{index}", 0.25 + index * 0.01) for index in range(10)]
    picked = near_miss_cards({"exclusion_registry": many})
    assert len(picked) == 8
    assert [card["confidence"] for card in picked] == sorted((c["confidence"] for c in picked), reverse=True)
    assert picked[0]["technology"] == "т9"
    tie = near_miss_cards({"exclusion_registry": [_scored("бета", 0.3), _scored("альфа", 0.3)]})
    assert [card["technology"] for card in tie] == ["альфа", "бета"]
    assert near_miss_cards({}) == [] and near_miss_cards({"exclusion_registry": None}) == []


def test_near_miss_board_falls_back_for_an_old_run_and_explains_reasons():
    from ts.desk import near_miss_board

    old = near_miss_board({"exclusion_registry": [_scored("рядом", 0.325)]})
    assert [card["title"] for card in old["cards"]] == ["рядом"]
    assert "после нового поиска" in old["note"]
    card = old["cards"][0]
    assert "сумма признаков ниже порога наблюдения" in card["why"]
    assert "P01" in card["predictors"] and "+0.25" in card["predictors"]

    fresh = near_miss_board({"near_miss": [{
        **_scored("raw title", 0.31),
        "reach": {"plain": "Понятное имя", "sphere": "склады", "moves": "логистику", "plus": "дешевле", "minus": ""},
    }]})
    assert fresh["note"] == ""
    assert fresh["cards"][0]["title"] == "Понятное имя"
    assert fresh["cards"][0]["sphere"] == "склады"
    assert near_miss_board({"near_miss": [], "exclusion_registry": [_scored("рядом", 0.3)]})["cards"] == []


def test_screen_has_the_near_miss_block():
    from pathlib import Path
    text = Path("ui/app.py").read_text(encoding="utf-8")
    assert "Близко к проходу" in text
    assert "near_miss_board(payload)" in text
    headings = [
        'st.subheader("Поиск тонких сигналов")',
        'st.subheader("Близко к проходу")',
        'st.subheader("Новая жизнь старых технологий")',
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    lines = text.splitlines()
    row = next(i for i, line in enumerate(lines) if headings[1] in line)
    assert lines[row] == "    " + headings[1]
    assert lines[row - 1] == "with st.container(border=True):"
    assert "Описание появится после поиска." in text
    block = text[positions[1]:positions[2]]
    assert "· сумма" not in block and "сумма {" not in block


def test_public_report_carries_near_miss():
    from ts.harness import RunReport
    from ts.persist import public_report

    card = {
        "label": None, "confidence": None, "policy_action": "WATCHLIST", "policy_reason": "no_verified_change",
        "reason_codes": [], "predictors": [], "rules_version": "rules-0.1",
    }
    base = dict(id="x", query="q", idempotency_key="k", repeated=False, steps=[], sources=[], events=[],
                card=card, top=[], shortfall=15, exclusion_registry=[])
    assert public_report(RunReport(**base))["near_miss"] == []
    near = [{**_scored("рядом", 0.325), "reach": {"plain": "что это"}}]
    assert public_report(RunReport(**base, near_miss=near))["near_miss"] == near


def test_live_run_stores_near_miss_and_reads_reach_on_the_short_list_only(monkeypatch):
    from ts import live
    from ts.harness import RunReport

    registry = [_scored("рядом", 0.325), _scored("низко", 0.175), _scored("контр", 0.3, reason="checklist_counter")]
    reached = []

    def fake_reach(cards, settings):
        reached.append([card["technology"] for card in cards])
        return [{**card, "reach": {"plain": "что это", "sphere": "где"}} for card in cards]

    monkeypatch.setattr(live, "annotate_reach", fake_reach)
    shown = live._near_miss(registry, settings=None)
    assert reached == [["рядом"]]
    assert shown[0]["reach"]["sphere"] == "где"
    assert "reach" not in registry[0]
    reached.clear()
    assert live._near_miss([_scored("низко", 0.175)], settings=None) == []
    assert reached == []
    assert RunReport.__dataclass_fields__["near_miss"].default_factory() == []


def test_old_tech_board_is_archive_only():
    import inspect
    import json
    from pathlib import Path

    from ts.desk import old_tech_board

    root = Path(__file__).resolve().parents[2]
    package = root / "docs/lineage/novaya-zhizn-staryh-tehnologiy/thin-signals-repro-2026-09-29-v1.0"
    snapshot_path = root / "data/old_tech/snapshot_2026-09-29.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ranking = json.loads((package / "research/ranking.json").read_text(encoding="utf-8"))
    manifest = json.loads((package / "MANIFEST.json").read_text(encoding="utf-8"))
    expected = {
        row["path"]: row["sha256"]
        for row in manifest["files"]
        if row["path"] in ("research/ranking.json", "research/candidates.json")
    }
    assert snapshot["source_sha256"] == expected
    assert snapshot["fully_qualified_count"] == 0
    assert sum(1 for card in snapshot["cards"] if card["fully_qualified"]) == 0
    left = {
        (card["id"], card["rank"], card["score_lower"], card["score_upper"], card["decision"], tuple(card["holds"]))
        for card in snapshot["cards"]
    }
    right = {
        (card["id"], card["rank"], card["score_lower"], card["score_upper"], card["decision"], tuple(card["holds"]))
        for card in ranking
    }
    assert left == right

    board = old_tech_board(snapshot_path)
    assert inspect.signature(old_tech_board).parameters.keys() == {"path"}
    assert len(board["cards"]) == 15
    assert board["fully_qualified_count"] == 0
    assert "0" in board["note"]
    assert "не входят в официальный ТОП-15" in board["note"]
    ranks = [card["rank"] for card in board["cards"]]
    assert ranks == sorted(ranks)
    for card in board["cards"]:
        assert card["barrier_then"] and card["change_now"]
        assert 0 <= card["score_lower"] <= card["score_upper"] <= 100
        assert card["fully_qualified"] is False
        assert card["holds"]
        assert "служебный код" not in " ".join(card["holds"])
        assert "приоритет инвестиций" not in card["decision"]

    missing = old_tech_board(root / "data/old_tech/missing.json")
    assert missing["cards"] == []
    assert missing["note"] == "Архив не загружен"

    screen = (root / "ui/app.py").read_text(encoding="utf-8")
    assert "Новая жизнь старых технологий" in screen
    call = next(line for line in screen.splitlines() if "old_tech_board()" in line)
    assert call.strip() == "archive = old_tech_board()"
    assert screen.index("Близко к проходу") < screen.index("old_tech_board()") < screen.index("with st.sidebar:")
    assert "partner_review_ready" not in screen
    assert "Почему не квалифицирована" not in screen
