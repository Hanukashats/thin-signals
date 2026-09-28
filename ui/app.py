"""Two Russian screens. Viewer for a run, admin for notes. Scoring stays in the API."""
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
    score_story,
)
from ts.ui_text import panels

API = os.environ.get("TS_API_URL", "http://127.0.0.1:8095")
ACCOUNTS = Path(os.environ.get("TS_ACCOUNTS", "/opt/thin-signals/.secrets/accounts.yaml"))
DRAFT = Path(os.environ.get("TS_DRAFT", "/opt/thin-signals/.secrets/draft.yaml"))

st.set_page_config(page_title="Тонкие сигналы", layout="wide")
st.title("Тонкие сигналы")
st.caption("Напишите, что искать. Ниже будет сказано обычными словами, дошёл ли поиск до конца и почему тема не попала в список.")


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


st.subheader("Что искать")
if "payload" not in st.session_state:
    try:
        latest = httpx.get(f"{API}/v1/runs/latest", timeout=5).json().get("run")
    except httpx.HTTPError:
        latest = None
    if latest:
        st.session_state["payload"] = latest
        st.session_state["meta"] = {
            "direction": latest.get("query") or "",
            "correction": "",
            "start": "",
            "end": "",
        }
        st.caption("Показан последний сохранённый прогон. Новый запуск ниже его заменит.")
direction = st.text_input("Направление", help=field_help("direction"))
correction = st.text_input("Небольшая правка", help=field_help("correction"))
left, right = st.columns(2)
start = left.text_input("Период с", placeholder="2026-01-01", help=field_help("period"))
end = right.text_input("Период по", placeholder="2026-09-26", help=field_help("period"))

if st.button("Запустить", type="primary"):
    try:
        query = compose_query(direction, correction, start, end)
    except ValueError as exc:
        st.error(str(exc))
    else:
        with st.spinner("Идёт поиск…"):
            response = httpx.post(
                f"{API}/v1/runs",
                json={"query": query, "limit": 3, "extract": False},
                timeout=180,
            )
            response.raise_for_status()
            st.session_state["payload"] = response.json()
            st.session_state["meta"] = {"direction": direction, "correction": correction, "start": start, "end": end}

payload = st.session_state.get("payload")
meta = st.session_state.get("meta") or {}
if payload:
    view = panels(payload)
    left, right = st.columns(2)
    left.metric("Статус прогона", view["run_status"], help=field_help("run_status"))
    right.metric("Метка сигнала", view["signal_label"], help=field_help("signal_label"))
    st.caption("Статус прогона говорит, отработал ли поиск. Метка говорит, что решили по теме. Это разные вещи.")
    st.metric("Пустых мест в списке из 15", view["shortfall"])
    st.caption("Официальный список — 15 мест. Пустые места не заполняются. Число выше — сколько мест осталось пустыми.")
    for line in run_banner(payload):
        st.write(line)
    chain = reasoning(payload)
    st.subheader("Что учтено и к чему пришли")
    for step in chain["steps"]:
        st.write(f"- {step}")
    st.write(f"**Вывод:** {chain['conclusion']}")
    story = score_story(payload)
    st.subheader("Как сложилось число")
    for step in story["lines"]:
        st.write(f"- {step}")
    st.caption(story["disclaimer"])
    official_tab, nearest_tab = st.tabs(["Официальный ТОП-15", "Ближайшие к допуску"])
    with official_tab:
        st.subheader("Найденные кандидаты")
        st.caption(
            "Сначала обычными словами, что это и на что может повлиять. "
            "Масштаб — только то, что сказано в тексте. Остальное — гипотеза, не допуск и не прогноз цены."
        )
        cards = story.get("cards") or []
        if not cards:
            st.write("В список никто не прошёл. Пустые места не заполняются.")
        unread = [item for item in (payload.get("unread") or []) if isinstance(item, dict)]
        if unread:
            st.subheader("Не прочитаны")
            st.caption("Текста источника нет. Числа уверенности нет. Это не ноль и не отказ.")
            for item in unread:
                st.write(f"- {item.get('technology') or 'карточка'}")
        for card in cards:
            with st.container(border=True):
                title = card["plain"] or card["title"]
                st.markdown(f"**{card['index']}. {title}**")
                bits = [bit for bit in (card["theme"], card["title"] if card["plain"] else "") if bit]
                if bits:
                    st.caption(" · ".join(bits))
                if card["plain"]:
                    st.caption("Русское резюме, сгенерировано моделью. Оригинальное название — в строке источника.")
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
                    st.write("**Источники на карточке**")
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
        st.write("\n".join(f"- {row}" for row in near["lines"]) or "Ближайших находок нет: поиск ничего не вернул.")
        if near["official_count"] < 15:
            st.caption(
                f"В окне {near['shown']} из {near['found']}. "
                "Дальше 15 не показываю. Пустые строки в официальный список не дописываю."
            )
    st.subheader("Источники")
    st.write("\n".join(f"- {row}" for row in view["sources"]) or "Источников нет.")
    st.subheader("Почему не вошло в список")
    st.write("\n".join(f"- {row}" for row in view["excluded"]) or "Пусто.")
    text = document(payload, meta.get("direction", ""), meta.get("correction", ""), meta.get("start", ""), meta.get("end", ""))
    st.download_button("Скачать документ", text, file_name="thin-signals.md", mime="text/markdown")
    st.caption("Письмо на почту появится, когда будет ящик для отправки. Сейчас результат — этот документ.")

optional_login()

if can_admin(st.session_state.get("role")):
    st.subheader("Админка")
    st.caption("Живые правила и промпт экран не подменяет. Здесь видны числа и черновик правки.")
    logic = live_logic()
    st.write(f"Версия правил: `{logic['rules_version']}`. Версия промпта: `{logic['prompt_version']}`.")
    st.write(logic["note"])
    st.json({"пороги": logic["thresholds"], "пороги описания": logic["description_thresholds"], "веса": logic["weights"]})
    draft = load_draft(DRAFT)
    prompt_draft = st.text_area("Черновик промпта", value=draft["prompt_draft"], help=field_help("prompt_draft"))
    logic_note = st.text_area("Заметка к логике", value=draft["logic_note"], help=field_help("logic_note"))
    if st.button("Сохранить черновик"):
        save_draft(DRAFT, prompt_draft, logic_note)
        st.success("Черновик сохранён на хосте. На скоринг он не встал.")
else:
    st.caption("Вход и настройки не нужны, чтобы запустить поиск и увидеть результат. Они в конце очереди.")
