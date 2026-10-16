"""A demo is a local viewing ledger, never a reset of scientific history."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from ts.checklist import CHECKLIST_VERSION

ROOT = Path(__file__).resolve().parents[2]


def snapshot():
    from ts.workspace import archive_result

    return {
        "revision": 8, "version": "workspace-v1", "run_compatible": True, "issues": [],
        "run": {
            "run_id": "real-saved-run", "query": "saved sodium query", "run_status": "succeeded",
            "top": [{"technology": "Real saved observation", "label": "watchlist", "confidence": 0.4,
                     "checklist": {"version": CHECKLIST_VERSION, "status": "scored"}, "sources": []}],
            "potential": [], "counters": {"admitted": 1, "sources": 0}, "shortfall": 14,
        },
        "archive": {**archive_result("Кнудсена", ["микрофлюидика"]), "compatible": True},
    }


def response(body):
    return httpx.Response(200, json=body, request=httpx.Request("GET", "http://test"))


@pytest.fixture
def desk(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "ui"))
    monkeypatch.setenv("TS_ACCOUNTS", str(tmp_path / "no-accounts"))
    get = Mock(return_value=response(snapshot()))
    post = Mock(side_effect=AssertionError("unexpected POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "ui/app.py"), default_timeout=15)
    app.session_state["role"] = "viewer"
    app.session_state["username"] = "demo-test"
    app.run()
    return app, get, post


def text(app):
    return " ".join(item.value for kind in (app.markdown, app.info, app.caption) for item in kind)


def test_reset_is_local_and_preserves_the_server_snapshot():
    from ui.state import start_demo

    server = snapshot()
    before = deepcopy(server)
    state = {"workspace": server, "payload": server["run"], "direction_input": "draft",
             "old_tech_query": "draft", "old_tech_families": ["микрофлюидика"],
             "potential_filter": "filter", "signal_selected": 9, "potential_selected": 7,
             "old_selected": 4, "input_drafts": {"direction_input": "draft"}}
    start_demo(state)

    assert server == before and state["workspace"] == before
    assert state["demo_saved_workspace"] == before
    assert state["demo_saved_workspace"] is not server
    assert not state.get("payload")
    assert state["direction_input"] == state["old_tech_query"] == state["potential_filter"] == ""
    assert state["old_tech_families"] == []
    assert state["demo_session"]["viewed_run_ids"] == []
    assert state["demo_session"]["archive_submissions"] == 0


def test_saved_example_is_opened_once_and_keeps_original_labels_and_counters():
    from ui.state import open_saved_example, start_demo

    server = snapshot()
    state = {"workspace": server}
    start_demo(state)
    open_saved_example(state)
    open_saved_example(state)

    assert state["demo_session"]["viewed_run_ids"] == ["real-saved-run"]
    assert state["payload"] == server["run"]
    assert state["payload"]["top"][0]["label"] == "watchlist"
    assert "новый поиск не запускался" in state["demo_session"]["notice"]
    assert state["demo_session"]["archive_submissions"] == 0


@pytest.mark.parametrize("repeated", [True, False])
def test_run_notice_distinguishes_exact_replay_from_pipeline_result(repeated):
    from ui.state import record_demo_run, start_demo

    state = {"workspace": snapshot()}
    start_demo(state)
    payload = {**snapshot()["run"], "repeated": repeated}
    record_demo_run(state, payload)
    record_demo_run(state, payload)

    assert state["demo_session"]["viewed_run_ids"] == [payload["run_id"]]
    notice = state["demo_session"]["notice"]
    assert ("Источники и модели повторно не запускались" in notice) is repeated
    assert ("могли использоваться повторно" in notice) is not repeated
    assert "новое открытие" not in notice.lower()


def test_normal_load_still_restores_latest_without_demo(desk):
    app, get, post = desk
    assert app.session_state["payload"]["run_id"] == "real-saved-run"
    assert "demo_session" not in app.session_state
    assert get.call_count == 1 and post.call_count == 0


def test_demo_reset_and_open_are_network_free_and_distinct_count_is_one(desk):
    app, get, post = desk
    get.side_effect = AssertionError("demo presentation action must not fetch")
    app.button(key="start_demo").click().run()
    assert not app.exception
    assert "Открыто результатов в этом показе: 0" in text(app)
    assert "Поисков по архиву в этом показе: 0" in text(app)
    assert "Результат ещё не выбран." in text(app)
    assert not app.session_state.get("payload")
    app.run()
    app.button(key="open_saved_example").click().run()
    app.button(key="open_saved_example").click().run()
    assert not app.exception
    assert "Открыто результатов в этом показе: 1" in text(app)
    assert "новый поиск не запускался" in text(app)
    assert app.session_state["payload"]["top"][0]["label"] == "watchlist"
    assert get.call_count == 1 and post.call_count == 0


def test_archive_zero_means_not_searched_this_demo_and_explicit_submit_counts_once(desk):
    app, get, post = desk
    app.button(key="start_demo").click().run()
    app.radio(key="active_module").set_value("Новая жизнь").run()
    assert "Поиск в этом показе ещё не выполнялся" in text(app)
    assert any(metric.label == "В архиве" and metric.value == "15" for metric in app.metric)
    assert all(metric.value == "—" for metric in app.metric if metric.label == "Найдено")
    assert not any("Кнудсена" in button.label for button in app.button)
    assert app.text_input(key="old_tech_query").value == ""
    assert post.call_count == 0
    post.side_effect = None
    post.return_value = response(snapshot())
    app.button(key="save_archive").click().run()
    app.run()
    assert not app.exception
    assert app.session_state["demo_session"]["archive_submissions"] == 1
    assert post.call_count == 1
    assert get.call_count == 1, "local demo reset and archive response need no implicit reload"
    assert not app.session_state.get("payload"), "archive save must not silently open the saved Run"


@pytest.mark.parametrize("repeated", [True, False])
def test_live_response_notice_survives_workspace_get_without_repeated_flag(desk, repeated):
    app, get, post = desk
    app.button(key="start_demo").click().run()
    app.text_input(key="direction_input").set_value("saved sodium query").run()
    post.side_effect = None
    post.return_value = response({**snapshot()["run"], "repeated": repeated})
    app.button(key="start_search").click().run()
    app.radio(key="active_module").set_value("Потенциал").run()

    assert not app.exception
    assert app.session_state["demo_session"]["viewed_run_ids"] == ["real-saved-run"]
    assert ("Источники и модели повторно не запускались" in text(app)) is repeated
    assert ("могли использоваться повторно" in text(app)) is not repeated
    assert get.call_count == 2 and post.call_count == 1


def test_demo_ledger_has_restrained_responsive_style():
    from ui.theme import THEME_CSS

    assert ".ts-demo-ledger" in THEME_CSS
    mobile = THEME_CSS.split("@media (max-width: 700px)", 1)[1]
    assert ".ts-demo-ledger" in mobile
    assert "overflow-wrap" in mobile
