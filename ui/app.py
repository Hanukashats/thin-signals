"""Thin Signals operator workbench: three real modules, one evidence contract."""
from __future__ import annotations

import os
import time
from html import escape
from pathlib import Path

import httpx
import streamlit as st
from state import (
    open_saved_example,
    record_demo_archive,
    record_demo_run,
    remember_draft,
    restore_workspace,
    start_demo,
    stop_demo,
    sync_draft_widget,
)
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
        st.session_state.clear()
        st.rerun()


def request_saved_reload() -> None:
    st.session_state.pop("latest_checked", None)


def load_latest_once() -> None:
    """Restore shared results without mutating them; failed reads remain retryable."""
    pending = st.session_state.pop("pending_workspace", None)
    if pending is not None:
        kind = st.session_state.pop("pending_workspace_kind", "run")
        if "demo_session" in st.session_state and kind == "archive":
            record_demo_archive(st.session_state, pending)
        else:
            restore_workspace(st.session_state, pending)
            response = st.session_state.pop("pending_run_response", None)
            if response is not None:
                record_demo_run(st.session_state, response)
        return
    if "demo_session" in st.session_state:
        return
    if st.session_state.get("latest_checked"):
        return
    try:
        response = httpx.get(f"{API}/v1/workspace/latest", timeout=5)
        response.raise_for_status()
        latest = response.json()
    except (httpx.HTTPError, ValueError):
        st.session_state["latest_issue"] = (
            "Последний прогон сейчас недоступен. Нажмите «Загрузить последний результат», "
            "чтобы повторить загрузку сохранённых карточек."
        )
        return
    restore_workspace(st.session_state, latest)


def show_demo_ledger() -> None:
    demo = st.session_state.get("demo_session")
    counts = (
        f'<p>Открыто результатов в этом показе: {len(demo["viewed_run_ids"])}<br>'
        f'Поисков по архиву в этом показе: {demo["archive_submissions"]}</p>'
        if demo is not None else '<p>Начните показ с чистого экрана, сохранив всю историю исследований.</p>'
    )
    status = ""
    if demo is not None:
        status = demo.get("notice") or "Результат ещё не выбран."
    st.markdown(
        '<section class="ts-demo-ledger" aria-label="Демонстрационный сеанс">'
        '<div><h2>Демонстрационный сеанс</h2>' + counts + '</div>'
        f'<p class="ts-demo-ledger__status">{escape(status)}</p></section>',
        unsafe_allow_html=True,
    )
    if demo is None:
        st.button("Начать новый показ", key="start_demo", on_click=start_demo, args=(st.session_state,))
        return
    left, middle, right = st.columns([1.5, 1, 1])
    with left:
        st.button("Открыть сохранённый пример", key="open_saved_example", type="primary",
                  on_click=open_saved_example, args=(st.session_state,), use_container_width=True)
    with middle:
        st.button("К новому поиску", key="demo_search", on_click=select_search, use_container_width=True)
    with right:
        st.button("Начать новый показ", key="start_demo", on_click=start_demo,
                  args=(st.session_state,), use_container_width=True)
    st.caption(
        "Счётчики относятся к этому показу в браузере, а не к истории исследований. "
        "История не исключает карточки из следующих поисков. Тот же точный текст запроса, "
        "версии корпуса/чек-листа и правил в тот же UTC-день могут повторно открыть завершённый прогон."
    )
    st.button("Вернуться к рабочему столу", key="stop_demo", on_click=stop_demo, args=(st.session_state,))


def select_search() -> None:
    st.session_state["active_module"] = "Тонкие сигналы"


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
    sync_draft_widget(st.session_state, "direction_input", (st.session_state.get("payload") or {}).get("query", ""))
    for key in ("correction_input", "period_start", "period_end"):
        sync_draft_widget(st.session_state, key, "")
    st.markdown("### Новый прогон")
    direction = st.text_input(
        "Направление", help=field_help("direction"), key="direction_input",
        on_change=remember_draft, args=(st.session_state, "direction_input"),
    )
    correction = st.text_input(
        "Небольшая правка", help=field_help("correction"), key="correction_input",
        on_change=remember_draft, args=(st.session_state, "correction_input"),
    )
    start = st.text_input(
        "Период с · контекст запроса", placeholder="2026-01-01",
        help=field_help("period"), key="period_start",
        on_change=remember_draft, args=(st.session_state, "period_start"),
    )
    end = st.text_input(
        "Период по · контекст запроса", placeholder="2026-09-29",
        help=field_help("period"), key="period_end",
        on_change=remember_draft, args=(st.session_state, "period_end"),
    )
    launched = st.button("Запустить поиск", key="start_search", type="primary", use_container_width=True)
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
        st.error(
            "Ответ прогона не получен. Сервер мог продолжить работу. "
            "Нажмите «Загрузить последний результат» перед повторным запуском."
        )
        return
    state = saved_run_state(payload)
    if not state["safe_to_autoload"]:
        st.session_state["latest_issue"] = state["message"]
        st.warning(state["message"], icon="⚠️")
        return
    # The workspace projection does not carry the POST replay flag.
    record_demo_run(st.session_state, payload, viewed=False)
    try:
        response = httpx.get(f"{API}/v1/workspace/latest", timeout=5)
        response.raise_for_status()
        snapshot = response.json()
    except (httpx.HTTPError, ValueError):
        st.error("Результат получен, но сохранённый экран пока не загружен. Нажмите «Загрузить последний результат».")
        return
    if (snapshot.get("run") or {}).get("run_id") != payload.get("run_id"):
        st.session_state["workspace_notice"] = (
            "Новый ответ не заменил общий результат: проверьте доступность источников или более поздний прогон."
        )
        if "demo_session" in st.session_state:
            st.session_state["workspace"] = snapshot
            st.rerun()
    st.session_state["pending_run_response"] = payload
    st.session_state["pending_workspace"] = snapshot
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
    elif st.session_state.get("latest_loaded") and "demo_session" not in st.session_state:
        st.info("Показан последний завершённый сохранённый результат общего рабочего стола.")
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
        if payload:
            selected = signal_list(story.get("cards") or [])
        else:
            st.markdown("### Рейтинг находок")
            if "demo_session" in st.session_state:
                st.info("Результат ещё не выбран. Откройте сохранённый пример или запустите поиск слева.")
            else:
                st.info("Сохранённый результат не загружен. Нажмите «Загрузить последний результат».")
    with detail:
        if payload:
            signal_detail(selected, empty_chain=reasoning(payload))
        else:
            st.markdown("### Инспектор доказательств")
            st.info("Доказательства появятся после загрузки результата.")


def potential_module() -> None:
    st.title("Потенциал")
    st.caption(
        "Отдельная очередь карточек, которые ещё не стали слабым сигналом, но близки к порогу или имеют "
        "подтверждённые признаки технического, спросового либо развивающего потенциала."
    )
    if st.session_state.get("latest_issue"):
        st.warning(st.session_state["latest_issue"], icon="⚠️")
    payload = st.session_state.get("payload") or {}
    if payload:
        integrity = run_integrity(payload, expected_checklist=CHECKLIST_VERSION)
        st.caption(integrity["provenance"])
        if integrity["warnings"]:
            st.warning(" ".join(integrity["warnings"]), icon="⚠️")
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
    workspace = st.session_state.get("workspace") or {}
    whole = old_tech_board()
    archive = workspace.get("archive") or whole
    demo = st.session_state.get("demo_session")
    awaiting_demo_search = demo is not None and demo["archive_submissions"] == 0
    if st.session_state.get("latest_issue"):
        st.warning(st.session_state["latest_issue"])
    cards = [] if awaiting_demo_search else archive["cards"]
    sync_draft_widget(st.session_state, "old_tech_query", archive.get("query", ""))
    sync_draft_widget(st.session_state, "old_tech_families", [
        family for family in archive.get("families") or []
        if family in {card["family"] for card in whole["cards"]}
    ])
    if awaiting_demo_search:
        st.info("Поиск в этом показе ещё не выполнялся. В архиве доступны 15 исследовательских карточек.")
    else:
        st.caption(f"Сохранённый запрос: {archive.get('query') or 'весь архив'}.")
    st.caption("Явный поиск сохраняется для всех пользователей; выбор карточки остаётся только у вас.")
    a, b, c, d = st.columns(4)
    a.metric("В архиве", whole["total"])
    b.metric("Найдено", "—" if awaiting_demo_search else len(cards))
    c.metric("Полностью проверено", whole["fully_qualified_count"])
    d.metric("Срез", whole["as_of"])
    left, middle, detail = st.columns([1.05, 2.35, 2.8], gap="small")
    with left:
        st.markdown("### Поиск по архиву")
        families = sorted({card["family"] for card in whole["cards"] if card.get("family")})
        query = st.text_input(
            "Технология, барьер, продукт или покупатель", key="old_tech_query",
            on_change=remember_draft, args=(st.session_state, "old_tech_query"),
        )
        chosen = st.multiselect(
            "Области", families, key="old_tech_families",
            on_change=remember_draft, args=(st.session_state, "old_tech_families"),
        )
        submitted = st.button("Найти и сохранить", key="save_archive", type="primary", use_container_width=True)
        if submitted:
            try:
                response = httpx.post(f"{API}/v1/workspace/archive", json={
                    "query": query, "families": chosen,
                    "expected_revision": workspace.get("revision", 0),
                }, timeout=10)
                if response.status_code == 409:
                    st.warning("Общий результат уже изменился. Обновите сохранённое и повторите поиск.")
                else:
                    response.raise_for_status()
                    st.session_state["pending_workspace"] = response.json()
                    st.session_state["pending_workspace_kind"] = "archive"
                    st.rerun()
            except (httpx.HTTPError, ValueError):
                st.error("Подтверждение сохранения не получено. Обновите сохранённое перед повтором.")
        st.caption(whole["note"])
        st.info("Свежий веб-поиск здесь пока не заявлен готовым: сейчас ищем по проверяемому срезу.")
    with middle:
        if awaiting_demo_search:
            st.markdown("### Архивный рейтинг")
            st.info("Результаты появятся после нажатия «Найти и сохранить».")
        else:
            selected = old_tech_list(cards)
    with detail:
        if not awaiting_demo_search:
            old_tech_detail(selected)


require_login()
load_latest_once()
show_demo_ledger()
if "demo_session" not in st.session_state:
    st.button(
        "Загрузить последний результат",
        key="reload_saved_run",
        help="Повторно открыть сохранённый прогон без нового поиска.",
        on_click=request_saved_reload,
    )

if st.session_state.get("workspace_notice"):
    st.warning(st.session_state.pop("workspace_notice"))

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
