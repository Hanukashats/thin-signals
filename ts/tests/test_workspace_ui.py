from copy import deepcopy


def saved():
    return {
        "revision": 7, "version": "workspace-v1", "run_compatible": True, "issues": [],
        "run": {"run_id": "parent", "query": "stored direction", "top": [], "potential": [],
                "shortfall": 15, "counters": {"admitted": 0}},
        "archive": {"query": "Кнудсена", "families": ["Насосы"], "cards": [{"id": "T01"}]},
    }


def test_fresh_session_restores_all_three_modules_from_one_snapshot():
    from ui.state import restore_workspace

    state = {}
    result = saved()
    restore_workspace(state, result)
    assert state["payload"] == result["run"]
    assert state["workspace"]["revision"] == 7
    assert state["old_tech_query"] == "Кнудсена"
    assert state["old_tech_families"] == ["Насосы"]
    assert state["direction_input"] == "stored direction"
    assert state["latest_checked"] is True
    assert result == saved(), "restoration must not alter the server snapshot"


def test_loading_new_snapshot_resets_selection_but_keeps_server_result_immutable():
    from ui.state import restore_workspace

    state = {"signal_selected": 9, "potential_selected": 6, "old_selected": 12}
    restore_workspace(state, saved())
    assert state["signal_selected"] == state["potential_selected"] == state["old_selected"] == 0
    assert state["workspace"]["archive"]["cards"] == [{"id": "T01"}]


def test_incompatible_snapshot_is_not_presented_as_current_scored_run():
    from ui.state import restore_workspace

    result = deepcopy(saved())
    result["run_compatible"] = False
    result["issues"] = ["Версия отличается"]
    state = {}
    restore_workspace(state, result)
    assert not state.get("payload")
    assert "Версия отличается" in state["latest_issue"]


def app_test(monkeypatch, result):
    from pathlib import Path

    import httpx
    from streamlit.testing.v1 import AppTest

    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "ui"))
    monkeypatch.setattr("httpx.get", lambda *a, **k: httpx.Response(
        200, json=result, request=httpx.Request("GET", "http://test/v1/workspace/latest"),
    ))
    app = AppTest.from_file(str(root / "ui/app.py"))
    app.session_state["role"] = "viewer"
    app.session_state["username"] = "test-viewer"
    app.run()
    return app


def test_module_navigation_restores_missing_widget_state_without_overwriting_edits(monkeypatch):
    result = saved()
    result["archive"] = {"query": "Кнудсена", "families": [], "cards": []}
    app = app_test(monkeypatch, result)
    assert not app.exception
    assert app.text_input(key="direction_input").value == "stored direction"
    for module in ("Новая жизнь", "Потенциал", "Новая жизнь", "Тонкие сигналы"):
        app.radio(key="active_module").set_value(module).run()
        assert not app.exception
        if module == "Новая жизнь":
            assert app.text_input(key="old_tech_query").value == "Кнудсена"
    assert app.text_input(key="direction_input").value == "stored direction"
    app.text_input(key="direction_input").set_value("draft query").run()
    assert app.text_input(key="direction_input").value == "draft query"


def test_potential_discloses_incompatible_saved_result(monkeypatch):
    result = saved()
    result["run_compatible"] = False
    result["issues"] = ["Версия отличается"]
    app = app_test(monkeypatch, result)
    app.radio(key="active_module").set_value("Потенциал").run()
    assert not app.exception
    assert any("Версия отличается" in warning.value for warning in app.warning)


def test_restored_widgets_send_their_values_to_a_fresh_browser(monkeypatch):
    result = saved()
    result["archive"].update(families=["микрофлюидика"], available_families=["микрофлюидика"])
    app = app_test(monkeypatch, result)
    direction = app.text_input(key="direction_input")
    assert direction.proto.value == "stored direction" and direction.proto.set_value
    app.radio(key="active_module").set_value("Новая жизнь").run()
    query = app.text_input(key="old_tech_query")
    families = app.multiselect(key="old_tech_families")
    assert query.proto.value == "Кнудсена" and query.proto.set_value
    assert families.proto.set_value
    assert list(families.proto.raw_values) == ["микрофлюидика"]


def test_active_drafts_survive_hidden_widget_cleanup_on_module_navigation(monkeypatch):
    result = saved()
    result["archive"].update(families=[], available_families=["микрофлюидика"])
    app = app_test(monkeypatch, result)
    app.text_input(key="direction_input").set_value("my active direction").run()
    app.radio(key="active_module").set_value("Новая жизнь").run()
    app.text_input(key="old_tech_query").set_value("my archive draft").run()
    app.multiselect(key="old_tech_families").set_value(["микрофлюидика"]).run()
    app.radio(key="active_module").set_value("Потенциал").run()
    app.radio(key="active_module").set_value("Тонкие сигналы").run()
    assert app.text_input(key="direction_input").value == "my active direction"
    app.radio(key="active_module").set_value("Новая жизнь").run()
    assert app.text_input(key="old_tech_query").value == "my archive draft"
    assert app.multiselect(key="old_tech_families").value == ["микрофлюидика"]
    assert app.session_state["workspace"]["archive"]["query"] == "Кнудсена"
