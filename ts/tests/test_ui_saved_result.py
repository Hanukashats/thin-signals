"""Saved-result recovery must not turn transport failure into a scientific verdict."""
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]


def saved_run(name="saved-card"):
    return {
        "run_id": name,
        "query": name,
        "run_status": "succeeded",
        "top": [{
            "technology": name,
            "label": "watchlist",
            "confidence": 0.4,
            "checklist": {"status": "scored", "version": "checklist-v15"},
            "sources": [],
        }],
        "counters": {"admitted": 1, "sources": 0},
        "shortfall": 14,
    }


def response(payload):
    return httpx.Response(
        200,
        json={"run": payload, "run_compatible": bool(payload), "issues": [], "revision": 1},
        request=httpx.Request("GET", "http://saved.test/v1/workspace/latest"),
    )


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "ui"))
    monkeypatch.setenv("TS_API_URL", "http://saved.test")
    monkeypatch.setenv("TS_ACCOUNTS", str(tmp_path / "no-accounts"))
    # No test may start a search or accidentally fall through to the real API.
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network operation")
    monkeypatch.setattr(httpx, "get", forbidden)
    monkeypatch.setattr(httpx, "post", forbidden)
    value = AppTest.from_file(str(ROOT / "ui/app.py"), default_timeout=15)
    value.session_state["role"] = "viewer"
    value.session_state["username"] = "test-viewer"
    return value


def cards(app):
    return [button.label for button in app.button if str(button.key).startswith("signal-card-")]


def unavailable(*args, **kwargs):
    raise httpx.ConnectError("temporary outage")


def test_failed_initial_load_recovers_on_next_rerun(app, monkeypatch):
    monkeypatch.setattr(httpx, "get", unavailable)
    app.run()
    assert app.warning
    assert cards(app) == []

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response(saved_run()))
    app.run()

    assert not app.exception
    assert cards(app) == ["01  saved-card"]
    assert "latest_issue" not in app.session_state


def test_explicit_refresh_loads_new_saved_run_without_starting_search(app, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response(saved_run("first")))
    app.run()
    app.session_state["latest_issue"] = "old failure"

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response(saved_run("second")))
    app.button(key="reload_saved_run").click().run()

    assert not app.exception
    assert cards(app) == ["01  second"]
    assert "latest_issue" not in app.session_state


@pytest.mark.parametrize("failure", [True, False])
def test_absent_result_is_not_reported_as_completed_empty_search(app, monkeypatch, failure):
    monkeypatch.setattr(httpx, "get", unavailable if failure else lambda *a, **kw: response(None))
    app.run()

    messages = " ".join(item.value for item in app.info)
    assert not app.exception
    assert "не прошла допуск" not in messages
    assert "Это результат проверки" not in messages
    assert "не загружен" in messages


def test_potential_displays_saved_result_load_problem(app, monkeypatch):
    app.session_state["active_module"] = "Потенциал"
    monkeypatch.setattr(httpx, "get", unavailable)
    app.run()

    assert not app.exception
    assert any("недоступен" in item.value for item in app.warning)


def test_refresh_failure_preserves_visible_saved_cards(app, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response(saved_run()))
    app.run()
    monkeypatch.setattr(httpx, "get", unavailable)
    app.button(key="reload_saved_run").click().run()

    assert not app.exception
    assert cards(app) == ["01  saved-card"]
    assert any("недоступен" in item.value for item in app.warning)


def test_logout_clears_saved_result_load_issue(app, monkeypatch):
    monkeypatch.setattr(httpx, "get", unavailable)
    app.run()
    app.session_state["latest_loaded"] = True
    next(button for button in app.button if button.label == "Выйти").click().run()

    assert not app.exception
    assert "latest_issue" not in app.session_state
    assert "latest_loaded" not in app.session_state
    assert "payload" not in app.session_state


def test_completed_empty_result_keeps_its_scientific_explanation(app, monkeypatch):
    empty = {**saved_run(), "top": [], "counters": {"admitted": 0}, "shortfall": 15}
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response(empty))
    app.run()

    assert not app.exception
    assert any("не прошла допуск" in item.value for item in app.info)
