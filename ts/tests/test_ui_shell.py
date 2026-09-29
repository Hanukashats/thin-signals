from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inconsistent_saved_run_is_not_auto_loaded():
    from ts.desk import saved_run_state

    payload = {
        "top": [{"technology": f"row-{index}"} for index in range(15)],
        "shortfall": 0,
        "counters": {"admitted": 1},
    }

    state = saved_run_state(payload)

    assert state["safe_to_autoload"] is False
    assert state["displayed_shortfall"] == 14
    assert "устарев" in state["message"].lower()


def test_consistent_saved_run_keeps_reported_shortfall():
    from ts.desk import saved_run_state

    payload = {
        "top": [{"technology": f"row-{index}"} for index in range(3)],
        "shortfall": 12,
        "counters": {"admitted": 3},
    }

    state = saved_run_state(payload)

    assert state == {
        "safe_to_autoload": True,
        "displayed_shortfall": 12,
        "message": "",
    }


def test_ui_theme_uses_approved_dusk_tokens_and_mobile_wrap():
    from ui.theme import LOGO_PATH, THEME_CSS

    streamlit_theme = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")

    for token in ("#E5ECEE", "#D8E5E9", "#EDF2F2", "#F5F7F6", "#B7C4C5", "#142226", "#087A84"):
        assert token in THEME_CSS
    assert "@media (max-width: 700px)" in THEME_CSS
    assert "overflow-wrap" in THEME_CSS
    assert LOGO_PATH.is_file()
    assert 'primaryColor = "#087A84"' in streamlit_theme
    assert 'backgroundColor = "#E5ECEE"' in streamlit_theme
    assert 'secondaryBackgroundColor = "#F5F7F6"' in streamlit_theme


def test_large_diagnostic_sections_are_progressively_disclosed():
    text = (ROOT / "ui/app.py").read_text(encoding="utf-8")

    assert "saved_run_state" in text
    assert 'st.expander("Как принято решение")' in text
    assert 'st.expander(f"Источники прогона · {len(view[\'sources\'])}")' in text
    assert 'st.expander(f"Исключения · {len(view[\'excluded\'])}")' in text
    assert 'st.expander(f"Не прочитаны · {len(unread)}")' in text
    assert 'st.session_state.pop("payload", None)' in text
