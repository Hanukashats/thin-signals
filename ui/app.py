"""Russian operator viewer. Scoring stays in the API; the UI never changes a verdict."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import streamlit as st

from ts.access import can_admin, load_accounts, role_for
from ts.desk import (
    compose_query,
    document,
    field_help,
    live_logic,
    load_draft,
    nearest_lines,
    reasoning,
    run_banner,
    save_draft,
    saved_run_state,
    score_story,
)
from ts.ui_text import panels
from ui.theme import apply_theme, brand_header

API = os.environ.get("TS_API_URL", "http://127.0.0.1:8095")
ACCOUNTS = Path(os.environ.get("TS_ACCOUNTS", "/opt/thin-signals/.secrets/accounts.yaml"))
DRAFT = Path(os.environ.get("TS_DRAFT", "/opt/thin-signals/.secrets/draft.yaml"))

st.set_page_config(
    page_title="Тонкие сигналы",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
brand_header()


def optional_login() -> None:
    """Login is not required to run or read a signal."""
    with st.expander("Вход для админки, не обязателен"):
        if st.session_state.get("role"):
            st.write(f"Сейчас вошли как **{st.session_state['username']}**.")
            if st.button("Выйти"):
                st.session_state.pop("role", None)
                st.session_state.pop("username", None)
                st.rerun()
            return
        if not ACCOUNTS.exists():
            st.caption("Файл учётных записей на хосте не найден. Смотровой экран от этого не зависит.")
            return
        username = st.text_input("Имя")
        password = st.text_input("Пароль", type="password")
        if st.button("Войти"):
            try:
                role = role_for(load_accounts(ACCOUNTS), username, password)
            except (ValueError, TypeError):
                st.error("Файл учётных записей повреждён.")
                return
            if role is None:
                st.error("Неверное имя или пароль.")
                return
            st.session_state["role"] = role
            st.session_state["username"] = username.strip()
            st.rerun()


def load_latest_once() -> None:
    """Load only a self-consistent saved run; keep incompatible history out of the live view."""
    if st.session_state.get("latest_checked"):
        return
    st.session_state["latest_checked"] = True
    try:
        response = httpx.get(f"{API}/v1/runs/latest", timeout=5)
        response.raise_for_status()
        latest = response.json().get("run")
    except (httpx.HTTPError, ValueError):
        st.session_state["latest_issue"] = (
            "Последний прогон сейчас недоступен. Новый поиск можно запустить ниже."
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
        st.caption("Вход и настройки не нужны, чтобы запустить поиск и увидеть результат.")
        return
    st.markdown("### Админка")
    st.caption("Экран хранит только черновик. Живые правила и промпт он не подменяет.")
    logic = live_logic()
    st.write(f"Правила: `{logic['rules_version']}` · промпт: `{logic['prompt_version']}`")
    st.json({"пороги": logic["thresholds"], "пороги описания": logic["description_thresholds"], "веса": logic["weights"]})
    draft = load_draft(DRAFT)
    prompt_draft = st.text_area("Черновик промпта", value=draft["prompt_draft"], help=field_help("prompt_draft"))
    logic_note = st.text_area("Заметка к логике", value=draft["logic_note"], help=field_help("logic_note"))
    if st.button("Сохранить черновик"):
        save_draft(DRAFT, prompt_draft, logic_note)
        st.success("Черновик сохранён на хосте. На скоринг он не встал.")


load_latest_once()

st.title("Очередь сигналов")
st.caption(
    "Задайте направление обычными словами. Экран отдельно показывает, дошёл ли поиск до конца, "
    "и какое решение принято по найденной теме."
)

latest_issue = st.session_state.get("latest_issue")
if latest_issue:
    st.warning(latest_issue, icon="⚠️")
elif st.session_state.get("latest_loaded"):
    st.info("Показан последний совместимый сохранённый прогон. Новый запуск заменит его в этом окне.")

with st.container(border=True):
    st.subheader("Новый поиск")
    direction = st.text_input("Направление", help=field_help("direction"), key="direction_input")
    correction = st.text_input("Небольшая правка", help=field_help("correction"), key="correction_input")
    left, right = st.columns(2)
    start = left.text_input("Период с", placeholder="2026-01-01", help=field_help("period"), key="period_start")
    end = right.text_input("Период по", placeholder="2026-09-26", help=field_help("period"), key="period_end")

    if st.button("Запустить поиск", type="primary", use_container_width=False):
        try:
            query = compose_query(direction, correction, start, end)
        except ValueError as exc:
            st.error(str(exc))
        else:
            try:
                with st.spinner("Ищем и сверяем источники…"):
                    response = httpx.post(
                        f"{API}/v1/runs",
                        json={"query": query, "limit": 3, "extract": False},
                        timeout=180,
                    )
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError):
                st.error(
                    "Сервис поиска не завершил запрос. Сохранённый результат не заменён; "
                    "проверьте соединение и повторите запуск."
                )
            else:
                state = saved_run_state(payload)
                if not state["safe_to_autoload"]:
                    st.session_state["latest_issue"] = state["message"]
                    st.warning(state["message"], icon="⚠️")
                else:
                    st.session_state["payload"] = payload
                    st.session_state["meta"] = {
                        "direction": direction,
                        "correction": correction,
                        "start": start,
                        "end": end,
                    }
                    st.session_state.pop("latest_issue", None)
                    st.session_state.pop("latest_loaded", None)

payload = st.session_state.get("payload")
meta = st.session_state.get("meta") or {}
if payload:
    state = saved_run_state(payload)
    if not state["safe_to_autoload"]:
        st.session_state["latest_issue"] = state["message"]
        st.session_state.pop("payload", None)
        st.session_state.pop("meta", None)
        st.warning(state["message"], icon="⚠️")
        payload = None

if payload:
    view = panels(payload)
    state = saved_run_state(payload)

    counters = payload.get("counters") if isinstance(payload.get("counters"), dict) else {}
    admitted = counters.get("admitted", len(payload.get("top") or []))
    status_col, label_col, count_col, shortfall_col = st.columns(4)
    status_col.metric("Статус поиска", view["run_status"], help=field_help("run_status"))
    label_col.metric("Решение по теме", view["signal_label"], help=field_help("signal_label"))
    count_col.metric("В списке", admitted)
    shortfall_col.metric("Пустых мест из 15", state["displayed_shortfall"])
    st.caption(" · ".join(run_banner(payload)))

    chain = reasoning(payload)
    story = score_story(payload)
    with st.expander("Как принято решение"):
        for step in chain["steps"]:
            st.write(f"- {step}")
        st.write(f"**Вывод:** {chain['conclusion']}")
        st.markdown("#### Как сложилось число")
        for step in story["lines"]:
            st.write(f"- {step}")
        st.caption(story["disclaimer"])

    official_tab, nearest_tab = st.tabs(["Официальный ТОП-15", "Ближайшие к допуску"])
    with official_tab:
        st.subheader("Кандидаты")
        st.caption(
            "Пустые места не заполняются. Масштаб — только то, что сказано в тексте; "
            "остальное помечено как гипотеза."
        )
        cards = story.get("cards") or []
        if not cards:
            st.info("В список никто не прошёл. Запустите новый поиск или откройте ближайшие находки.")
        unread = [item for item in (payload.get("unread") or []) if isinstance(item, dict)]
        if unread:
            with st.expander(f"Не прочитаны · {len(unread)}"):
                st.caption("Текста источника нет. Числа уверенности нет. Это не ноль и не отказ.")
                for item in unread:
                    st.write(f"- {item.get('technology') or 'карточка'}")
        for card in cards:
            title = card["plain"] or card["title"]
            with st.expander(f"{card['index']}. {title}"):
                bits = [bit for bit in (card["theme"], card["title"] if card["plain"] else "") if bit]
                if bits:
                    st.caption(" · ".join(bits))
                if card["plain"]:
                    st.caption("Русское резюме сгенерировано моделью; оригинальное название указано выше.")
                st.caption(
                    f"Состояние: {card['label']}"
                    + (f" · сумма {card['confidence']}" if card["confidence"] is not None else "")
                )
                if card["confidence_note"]:
                    st.write(card["confidence_note"])
                if card.get("why_here"):
                    st.write(card["why_here"])
                if card["scale"]:
                    st.write(f"**Масштаб.** {card['scale']}")
                if card["sphere"]:
                    st.write(f"**Где может пригодиться.** {card['sphere']}")
                if card["moves"]:
                    st.write(f"**На что может повлиять.** {card['moves']}")
                if card["affects"]:
                    st.write(f"**Что ещё может задеть.** {card['affects']}")
                if card["plus"]:
                    st.write(f"**Плюс.** {card['plus']}")
                if card["minus"]:
                    st.write(f"**Минус.** {card['minus']}")
                if card["terms"]:
                    st.write(f"**Сложные слова.** {card['terms']}")
                if card["if_true"]:
                    st.write(f"**Если это подтвердится.** {card['if_true']}")
                if card["open"]:
                    st.write(f"**Чего текст не закрывает.** {card['open']}")
                st.write(f"**Кейс.** {card['case']}")
                if card["sources"]:
                    st.write("**Источники карточки**")
                    for line in card["sources"]:
                        st.caption(line)

    near = nearest_lines(payload)
    ladder = "не выведена" if near["ladder_percent"] is None else f"{near['ladder_percent']}%"
    with nearest_tab:
        st.caption(near["note"])
        st.write(
            f"Официальный список: {near['official_count']}. "
            f"Ступеней допуска пройдено: {ladder}. Остановка: {near['stuck']}. {near['why']}"
        )
        st.write("\n".join(f"- {row}" for row in near["lines"]) or "Ближайших находок нет.")
        if near["official_count"] < 15:
            st.caption(
                f"Показано {near['shown']} из {near['found']}. "
                "Пустые строки в официальный список не дописываются."
            )

    with st.expander(f"Источники прогона · {len(view['sources'])}"):
        st.write("\n".join(f"- {row}" for row in view["sources"]) or "Источников нет.")
    with st.expander(f"Исключения · {len(view['excluded'])}"):
        st.write("\n".join(f"- {row}" for row in view["excluded"]) or "Исключений нет.")

    text = document(
        payload,
        meta.get("direction", ""),
        meta.get("correction", ""),
        meta.get("start", ""),
        meta.get("end", ""),
    )
    st.download_button("Скачать отчёт", text, file_name="thin-signals.md", mime="text/markdown")

with st.sidebar:
    st.markdown("## Режим оператора")
    optional_login()
    admin_panel()
