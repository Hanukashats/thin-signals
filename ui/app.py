"""Two Russian screens. Viewer for a run, admin for notes. Scoring stays in the API."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import streamlit as st

from ts.access import can_admin, load_accounts, role_for
from ts.desk import compose_query, document, field_help, live_logic, load_draft, reasoning, save_draft
from ts.ui_text import panels

API = os.environ.get("TS_API_URL", "http://127.0.0.1:8095")
ACCOUNTS = Path(os.environ.get("TS_ACCOUNTS", "/opt/thin-signals/.secrets/accounts.yaml"))
DRAFT = Path(os.environ.get("TS_DRAFT", "/opt/thin-signals/.secrets/draft.yaml"))

st.set_page_config(page_title="Тонкие сигналы", layout="wide")
st.title("Тонкие сигналы")
st.caption("Поиск по открытым источникам. Метка сигнала и статус прогона — разные поля.")


def login() -> None:
    st.subheader("Вход")
    if not ACCOUNTS.exists():
        st.error("Файл учётных записей на хосте не найден. Пароли в репозиторий не кладутся.")
        st.stop()
    username = st.text_input("Имя", help="admin, hanuka, yana — полные права. user1, user2, user3 — только просмотр и запуск.")
    password = st.text_input("Пароль", type="password", help="Пароль сверяется с хэшем на хосте. В чат и в git он не пишется.")
    if st.button("Войти", type="primary"):
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
    st.stop()


if "role" not in st.session_state:
    login()

st.write(f"Вы вошли как **{st.session_state['username']}** ({'админ' if can_admin(st.session_state['role']) else 'пользователь'}).")
if st.button("Выйти"):
    st.session_state.clear()
    st.rerun()

st.subheader("Смотровой экран")
direction = st.text_input("Направление", help=field_help("direction"))
correction = st.text_input("Небольшая правка", help=field_help("correction"))
left, right = st.columns(2)
start = left.text_input("Период с", placeholder="2026-01-01", help=field_help("period"))
end = right.text_input("Период по", placeholder="2026-09-26", help=field_help("period"))
extract = st.checkbox("Извлечь признаки через OpenRouter (запрет сохранения и обучения)", value=False)

if st.button("Запустить", type="primary"):
    try:
        query = compose_query(direction, correction, start, end)
    except ValueError as exc:
        st.error(str(exc))
    else:
        with st.spinner("Идёт поиск…"):
            response = httpx.post(
                f"{API}/v1/runs",
                json={"query": query, "limit": 3, "extract": extract},
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
    st.metric("Недобор до ТОП-15", view["shortfall"])
    chain = reasoning(payload)
    st.subheader("Что учтено и к чему пришли")
    for step in chain["steps"]:
        st.write(f"- {step}")
    st.write(f"**Вывод:** {chain['conclusion']}")
    st.subheader("Источники")
    st.write("\n".join(f"- {row}" for row in view["sources"]) or "Источников нет.")
    st.subheader("Реестр исключений")
    st.write("\n".join(f"- {row}" for row in view["excluded"]) or "Пусто.")
    text = document(payload, meta.get("direction", ""), meta.get("correction", ""), meta.get("start", ""), meta.get("end", ""))
    st.download_button("Скачать документ", text, file_name="thin-signals.md", mime="text/markdown")
    st.caption("Письмо на почту появится, когда будет ящик для отправки. Сейчас результат — этот документ.")

if can_admin(st.session_state["role"]):
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
    st.caption("Админка скрыта: у этой учётной записи только смотровой экран.")
