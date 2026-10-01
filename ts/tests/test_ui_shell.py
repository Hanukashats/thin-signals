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
    from ui.theme import LOGO_PATH, METALLIC_LOGO_PATH, THEME_CSS

    streamlit_theme = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")

    for token in ("#0A0F14", "#0D171F", "#101B24", "#14232D", "#29424D", "#EAF7F8", "#31D7E6"):
        assert token in THEME_CSS
    assert "@media (max-width: 700px)" in THEME_CSS
    assert "@media (max-width: 1180px)" in THEME_CSS
    assert "overflow-wrap" in THEME_CSS
    assert ":focus-visible" in THEME_CSS
    assert "#5B7782" in THEME_CSS
    assert LOGO_PATH.is_file()
    assert METALLIC_LOGO_PATH.is_file()
    assert 'base = "dark"' in streamlit_theme
    assert 'primaryColor = "#31D7E6"' in streamlit_theme
    assert 'backgroundColor = "#0A0F14"' in streamlit_theme
    assert 'secondaryBackgroundColor = "#101B24"' in streamlit_theme


def test_brand_uses_transparent_logo_and_compact_transparent_favicon():
    import inspect

    from PIL import Image

    from ui.theme import FAVICON_PATH, THEME_CSS, TRANSPARENT_LOGO_PATH, brand_header

    app = (ROOT / "ui/app.py").read_text(encoding="utf-8")

    assert "background: transparent" in THEME_CSS
    assert ".ts-brand__name { color: #F4F8F8" in THEME_CSS
    assert "TRANSPARENT_LOGO_PATH" in inspect.getsource(brand_header)
    assert "METALLIC_LOGO_PATH" not in inspect.getsource(brand_header)
    assert "page_icon=FAVICON_PATH" in app
    assert TRANSPARENT_LOGO_PATH.is_file()
    assert FAVICON_PATH.is_file()
    with Image.open(TRANSPARENT_LOGO_PATH) as logo:
        assert logo.mode == "RGBA" and logo.width >= 1000 and logo.height >= 800
        assert logo.getextrema()[-1] == (0, 255)
        assert logo.getpixel((0, 0))[-1] == 0
    with Image.open(FAVICON_PATH) as icon:
        assert icon.mode == "RGBA" and icon.width == icon.height and icon.width >= 256
        assert icon.getextrema()[-1] == (0, 255)


def test_large_diagnostic_sections_are_progressively_disclosed():
    text = (ROOT / "ui/app.py").read_text(encoding="utf-8")

    assert "from theme import FAVICON_PATH, apply_theme, brand_header" in text
    assert "saved_run_state" in text
    assert "with st.expander(title)" in text
    assert 'with st.expander("Диагностика прогона")' in text
    assert "Как принято решение по карточке №1" in text
    assert "Почему список пуст" in text
    assert "Ссылок в сохранённой выборке" in text


def test_result_shell_uses_honest_evidence_first_labels():
    text = (ROOT / "ui/app.py").read_text(encoding="utf-8")

    assert "Официальный ТОП-15" not in text
    assert "Решение по теме" not in text
    views = (ROOT / "ui/views.py").read_text(encoding="utf-8")
    assert "Рейтинг находок" in views
    assert "Инспектор доказательств" in views
    assert "Состав списка" in text
    assert '["Факты", "Гипотезы", "Проверки", "Источники"]' in views
    assert "Период с · контекст запроса" in text
    assert "Во всём прогоне счётчик источников" not in text
    assert '("Тонкие сигналы", "Потенциал", "Новая жизнь")' in text
    assert 'st.columns([1.05, 2.35, 2.8]' in text

    facts_block = views.split("with facts:", 1)[1].split("with hypotheses:", 1)[0]
    checks_block = views.split("with checks:", 1)[1].split("with sources:", 1)[0]
    assert "why_here" not in facts_block
    assert "why_here" in checks_block


def test_versioned_services_are_loopback_only_and_restart_on_failure():
    for name, port in (("thin-signals-api.service", "127.0.0.1 --port 8095"),
                       ("thin-signals-ui.service", "127.0.0.1 --server.port 8501")):
        unit = (ROOT / "deploy/systemd" / name).read_text(encoding="utf-8")
        assert "DynamicUser=yes" in unit
        assert "User=thin-signals-" in unit
        assert "Restart=on-failure" in unit
        assert "NoNewPrivileges=true" in unit
        assert "ProtectSystem=strict" in unit
        assert "CapabilityBoundingSet=" in unit
        assert "LoadCredential=" in unit
        assert port in unit
        assert "0.0.0.0" not in unit
