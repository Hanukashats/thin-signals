"""Thin Signals operator workbench: three real modules, one evidence contract."""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import streamlit as st
from theme import FAVICON_PATH, apply_theme, brand_header
from views import (
    old_tech_detail,
    old_tech_list,
    potential_detail,
    potential_list,
    signal_detail,
    signal_list,
)

from ts.access import can_admin, load_accounts, role_for
from ts.checklist import CHECKLIST_VERSION
from ts.desk import (
    compose_query,
    document,
    field_help,
    live_logic,
    load_draft,
    old_tech_board,
    potential_board,
    reasoning,
    run_integrity,
    save_draft,
    saved_run_state,
    score_story,
)
from ts.ui_text import panels

API = os.environ.get("TS_API_URL", "http://127.0.0.1:8095")
ACCOUNTS = Path(os.environ.get("TS_ACCOUNTS", "/opt/thin-signals/.secrets/accounts.yaml"))
DRAFT = Path(os.environ.get("TS_DRAFT", "/opt/thin-signals/.secrets/draft.yaml"))
LOGIN_WINDOW_SECONDS = 60
LOGIN_MAX_FAILURES = 5

st.set_page_config(
    page_title="Тонкие сигналы",
    page_icon=FAVICON_PATH,
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
brand_header()


def require_login() -> None:
    """Keep the workbench closed and slow repeated guesses within one UI session."""
    if st.session_state.get("role"):
        return
    st.subheader("Вход в рабочий стол")
    st.caption("Поиск, архив и доказательства доступны после входа.")
    if not ACCOUNTS.exists():
        st.error("Файл учётных записей на хосте не найден.")
        st.stop()
    now = time.monotonic()
    failures = [
        stamp for stamp in st.session_state.get("login_failures", [])
        if isinstance(stamp, (int, float)) and now - stamp < LOGIN_WINDOW_SECONDS
    ]
    st.session_state["login_failures"] = failures
    if len(failures) >= LOGIN_MAX_FAILURES:
        wait = max(1, int(LOGIN_WINDOW_SECONDS - (now - failures[0])))
        st.error(f"Слишком много попыток. Повторите через {wait} сек.")
        st.stop()
    username = st.text_input("Имя")
    password = st.text_input("Пароль", type="password")
    if st.button("Войти", type="primary"):
        try:
            role = role_for(load_accounts(ACCOUNTS), username, password)
        except (ValueError, TypeError):
            st.error("Файл учётных записей повреждён.")
            st.stop()
        if role is None:
            st.session_state["login_failures"] = [*failures, now]
            st.error("Неверное имя или пароль.")
            st.stop()
        st.session_state["role"] = role
        st.session_state["username"] = username.strip()
        st.session_state.pop("login_failures", None)
        st.rerun()
    st.stop()


def session_bar() -> None:
    st.write(f"Сейчас вошли как **{st.session_state['username']}**.")
    if st.button("Выйти"):
        for key in ("role", "username", "payload", "meta", "latest_checked"):
            st.session_state.pop(key, None)
        st.rerun()


def load_latest_once() -> None:
    """Load only a self-consistent saved run; never promote incompatible history."""
    if st.session_state.get("latest_checked"):
        return
    st.session_state["latest_checked"] = True
    try:
        response = httpx.get(f"{API}/v1/runs/latest", timeout=5)
        response.raise_for_status()
        latest = response.json().get("run")
    except (httpx.HTTPError, ValueError):
        st.session_state["latest_issue"] = (
            "Последний прогон сейчас недоступен. Новый поиск можно запустить в первом модуле."
        )
        return
    if not latest:
        return
    state = saved_run_state(latest)
    if not state["safe_to_autoload"]:
        st.session_state["latest_issue"] = state["message"]
        return
    st.session_state["payload"] = latest
    st.session_state["meta"] = {
        "direction": latest.get("query") or "",
        "correction": "",
        "start": "",
        "end": "",
    }
    st.session_state.setdefault("direction_input", latest.get("query") or "")
    st.session_state["latest_loaded"] = True


def admin_panel() -> None:
    if not can_admin(st.session_state.get("role")):
        return
    st.markdown("### Админка")
    st.caption("Здесь хранится черновик. Живые правила и промпт он не подменяет.")
    logic = live_logic()
    st.write(f"Правила: `{logic['rules_version']}` · промпт: `{logic['prompt_version']}`")
    st.json({
        "пороги": logic["thresholds"],
        "пороги описания": logic["description_thresholds"],
        "веса": logic["weights"],
    })
    draft = load_draft(DRAFT)
    prompt_draft = st.text_area(
        "Черновик промпта",
        value=draft["prompt_draft"],
        help=field_help("prompt_draft"),
    )
    logic_note = st.text_area(
        "Заметка к логике",
        value=draft["logic_note"],
        help=field_help("logic_note"),
    )
    if st.button("Сохранить черновик"):
        save_draft(DRAFT, prompt_draft, logic_note)
        st.success("Черновик сохранён на хосте. На скоринг он не встал.")


def submit_search() -> None:
    """Render module-one controls and replace state only after a valid response."""
    st.markdown("### Новый прогон")
    with st.form("thin-signals-search"):
        direction = st.text_input(
            "Направление",
            help=field_help("direction"),
            key="direction_input",
        )
        correction = st.text_input(
            "Небольшая правка",
            help=field_help("correction"),
            key="correction_input",
        )
        start = st.text_input(
            "Период с · контекст запроса",
            placeholder="2026-01-01",
            help=field_help("period"),
            key="period_start",
        )
        end = st.text_input(
            "Период по · контекст запроса",
            placeholder="2026-09-29",
            help=field_help("period"),
            key="period_end",
        )
        launched = st.form_submit_button("Запустить поиск", type="primary", use_container_width=True)
    if not launched:
        return
    try:
        query = compose_query(direction, correction, start, end)
    except ValueError as exc:
        st.error(str(exc))
        return
    try:
        with st.spinner("Ищем, читаем и сверяем доказательства…"):
            response = httpx.post(
                f"{API}/v1/runs",
                json={"query": query, "limit": 3, "extract": False},
                timeout=600,
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        st.error("Прогон не завершён. Сохранённый результат не заменён.")
        return
    state = saved_run_state(payload)
    if not state["safe_to_autoload"]:
        st.session_state["latest_issue"] = state["message"]
        st.warning(state["message"], icon="⚠️")
        return
    st.session_state["payload"] = payload
    st.session_state["meta"] = {
        "direction": direction,
        "correction": correction,
        "start": start,
        "end": end,
    }
    st.session_state["signal_selected"] = 0
    st.session_state["potential_selected"] = 0
    st.session_state.pop("latest_issue", None)
    st.session_state.pop("latest_loaded", None)
    st.rerun()


def integrity_strip(payload: dict) -> None:
    view = panels(payload)
    state = saved_run_state(payload)
    integrity = run_integrity(payload, expected_checklist=CHECKLIST_VERSION)
    a, b, c, d = st.columns(4)
    a.metric("Состояние задачи", view["run_status"], help=field_help("run_status"))
    b.metric("Состав списка", integrity["composition"])
    c.metric(
        "Ссылки у выбранных",
        integrity["selected_source_count"],
        help=(
            "Уникальные ссылки у допущенных карточек. "
            f"В сохранённой выборке: {integrity['run_source_count']}."
        ),
    )
    d.metric("Пустых мест из 15", state["displayed_shortfall"])
    st.caption(integrity["provenance"])
    if integrity["warnings"]:
        st.warning(" ".join(integrity["warnings"]), icon="⚠️")


def run_explanation(payload: dict) -> None:
    chain = reasoning(payload)
    if payload.get("decision_scope") == "run_empty":
        title = "Почему список пуст"
    else:
        legacy_card = next(
            (
                str(card.get("technology") or "").strip()
                for card in (payload.get("top") or [])
                if isinstance(card, dict) and str(card.get("technology") or "").strip()
            ),
            "название не записано",
        )
        title = f"Как принято решение по карточке №1: {payload.get('decision_card') or legacy_card}"
    with st.expander(title):
        for step in chain["steps"]:
            st.write(f"- {step}")
        st.write(f"**Вывод:** {chain['conclusion']}")


def thin_signals_module() -> None:
    st.title("Тонкие сигналы")
    st.caption("Новый механизм → проверяемые источники → допуск → карточка доказательств.")
    payload = st.session_state.get("payload")
    issue = st.session_state.get("latest_issue")
    if issue:
        st.warning(issue, icon="⚠️")
    elif st.session_state.get("latest_loaded"):
        st.info("Показан последний совместимый сохранённый прогон.")
    if payload:
        state = saved_run_state(payload)
        if not state["safe_to_autoload"]:
            st.warning(state["message"], icon="⚠️")
            payload = None
        else:
            integrity_strip(payload)
            run_explanation(payload)

    left, middle, detail = st.columns([1.05, 2.35, 2.8], gap="small")
    with left:
        submit_search()
        if payload:
            meta = st.session_state.get("meta") or {}
            text = document(
                payload,
                meta.get("direction", ""),
                meta.get("correction", ""),
                meta.get("start", ""),
                meta.get("end", ""),
            )
            st.download_button(
                "Скачать отчёт",
                text,
                file_name="thin-signals.md",
                mime="text/markdown",
                use_container_width=True,
            )
            with st.expander("Диагностика прогона"):
                view = panels(payload)
                st.write(f"Исключено: {len(view['excluded'])}")
                st.write(f"Не прочитано: {len(payload.get('unread') or [])}")
                st.write(f"Ссылок в сохранённой выборке: {len(view['sources'])}")
    story = score_story(payload or {})
    with middle:
        selected = signal_list(story.get("cards") or [])
    with detail:
        signal_detail(selected, empty_chain=reasoning(payload or {}) if payload else None)


def potential_module() -> None:
    st.title("Потенциал")
    st.caption(
        "Отдельная очередь карточек, которые не прошли ворота, но близки к ним или имеют "
        "подтверждённые признаки технического, спросового либо развивающего потенциала."
    )
    payload = st.session_state.get("payload") or {}
    board = potential_board(payload)
    cards = board["cards"]
    close = sum("близко к порогу допуска" in card["selection_reasons"] for card in cards)
    high = sum(
        "высокий индекс приоритета проверки по подтверждённым признакам" in card["selection_reasons"]
        for card in cards
    )
    a, b, c, d = st.columns(4)
    a.metric("В очереди", len(cards))
    b.metric("Близко к воротам", close)
    c.metric("Высокий потенциал", high)
    d.metric("Источник", "текущий прогон" if payload else "нет прогона")
    left, middle, detail = st.columns([1.05, 2.35, 2.8], gap="small")
    with left:
        st.markdown("### Фильтр")
        query = st.text_input("Найти в очереди", key="potential_filter")
        st.caption(board["note"])
        st.markdown("**Оси**")
        st.write("Технология · востребованность · развитие")
        st.caption("Неоценённая ось остаётся неизвестной и не превращается в ноль.")
    if query.strip():
        needle = query.casefold().strip()
        cards = [
            card for card in cards
            if needle in f"{card.get('title', '')} {card.get('technology', '')}".casefold()
        ]
    with middle:
        selected = potential_list(cards)
    with detail:
        potential_detail(selected)


def old_tech_module() -> None:
    st.title("Новая жизнь")
    st.caption(
        "Старые технологии, чьи прежние ограничения могли быть сняты новыми материалами, "
        "вычислениями или производственными процессами."
    )
    query = str(st.session_state.get("old_tech_query") or "")
    chosen = list(st.session_state.get("old_tech_families") or [])
    whole = old_tech_board()
    archive = old_tech_board(query=query)
    cards = archive["cards"]
    if chosen:
        cards = [card for card in cards if card.get("family") in chosen]
    selection_key = (query, tuple(chosen))
    if st.session_state.get("old_selection_key") != selection_key:
        st.session_state["old_selection_key"] = selection_key
        st.session_state["old_selected"] = 0
    a, b, c, d = st.columns(4)
    a.metric("В архиве", whole["total"])
    b.metric("Найдено", len(cards))
    c.metric("Полностью проверено", whole["fully_qualified_count"])
    d.metric("Срез", whole["as_of"])
    left, middle, detail = st.columns([1.05, 2.35, 2.8], gap="small")
    with left:
        st.markdown("### Поиск по архиву")
        st.text_input(
            "Технология, барьер, продукт или покупатель",
            key="old_tech_query",
        )
        families = sorted({card["family"] for card in whole["cards"] if card.get("family")})
        st.multiselect("Области", families, key="old_tech_families")
        st.caption(whole["note"])
        st.info("Свежий веб-поиск здесь пока не заявлен готовым: сейчас ищем по проверяемому срезу.")
    with middle:
        selected = old_tech_list(cards)
    with detail:
        old_tech_detail(selected)


require_login()
load_latest_once()

module = st.radio(
    "Модуль",
    ("Тонкие сигналы", "Потенциал", "Новая жизнь"),
    horizontal=True,
    label_visibility="collapsed",
    key="active_module",
)
if module == "Тонкие сигналы":
    thin_signals_module()
elif module == "Потенциал":
    potential_module()
else:
    old_tech_module()

with st.sidebar:
    st.markdown("## Режим оператора")
    session_bar()
    admin_panel()
