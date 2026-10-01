"""Three-pane Streamlit views. Decisions and rankings arrive from backend helpers."""
from __future__ import annotations

import streamlit as st


def _choose(state_key: str, index: int) -> None:
    st.session_state[state_key] = index


def _selected(cards: list[dict], state_key: str) -> dict | None:
    if not cards:
        st.session_state.pop(state_key, None)
        return None
    index = st.session_state.get(state_key, 0)
    if not isinstance(index, int) or index < 0 or index >= len(cards):
        index = 0
        st.session_state[state_key] = 0
    return cards[index]


def signal_list(cards: list[dict]) -> dict | None:
    st.markdown("### Рейтинг находок")
    st.caption("Порядок приходит из проверенного прогона; интерфейс его не пересчитывает.")
    if not cards:
        st.info("Ни одна карточка не прошла допуск. Причины показаны справа.")
        return None
    for index, card in enumerate(cards):
        title = card.get("plain") or card.get("title") or "карточка"
        label = card.get("label") or "без метки"
        score = card.get("confidence")
        suffix = "без суммы" if score is None else f"сумма {score:g}"
        st.button(
            f"{index + 1:02d}  {title}",
            key=f"signal-card-{index}",
            use_container_width=True,
            type="primary" if st.session_state.get("signal_selected", 0) == index else "secondary",
            on_click=_choose,
            args=("signal_selected", index),
        )
        st.caption(f"{label} · {suffix}")
    return _selected(cards, "signal_selected")


def signal_detail(card: dict | None, *, empty_chain: dict | None = None) -> None:
    st.markdown("### Инспектор доказательств")
    if card is None:
        st.info("Список пуст. Это результат проверки, а не ошибка интерфейса.")
        if empty_chain:
            for line in empty_chain.get("steps") or []:
                st.write(f"- {line}")
        return
    title = card.get("plain") or card.get("title") or "карточка"
    st.markdown(f"#### {title}")
    if card.get("plain") and card.get("title"):
        st.caption(f"Название источника: {card['title']}")
    st.caption(
        f"Метка: {card.get('label') or '—'} · "
        + (
            f"сумма признаков {card['confidence']} (не вероятность)"
            if card.get("confidence") is not None
            else "сумма не посчитана"
        )
    )
    facts, hypotheses, checks, sources = st.tabs(["Факты", "Гипотезы", "Проверки", "Источники"])
    evidence = card.get("evidence") or {}
    with facts:
        st.caption("Только сохранённые фрагменты источников.")
        rows = evidence.get("facts") or []
        for row in rows:
            st.write(f"- {row}")
        if not rows:
            st.info("Сохранённой цитаты для показа нет.")
    with hypotheses:
        st.caption("Текст модели; это не подтверждённые факты.")
        rows = evidence.get("hypotheses") or []
        for row in rows:
            st.write(f"- {row}")
        if not rows:
            st.info("Гипотезы применения не сформированы.")
    with checks:
        st.write(f"**Почему в списке.** {card.get('why_here') or 'Не записано.'}")
        for row in evidence.get("checks") or []:
            st.write(f"- {row}")
    with sources:
        rows = evidence.get("sources") or []
        for row in rows:
            st.caption(row)
        if card.get("url"):
            st.link_button("Открыть первый источник", card["url"])
        elif not rows:
            st.info("Ссылка на источник не записана.")


def potential_list(cards: list[dict]) -> dict | None:
    st.markdown("### Приоритет проверки")
    st.caption("Рейтинг учитывает близость к воротам и три отдельные оси доказательств.")
    if not cards:
        st.info("Карточек для дополнительной проверки нет.")
        return None
    for index, card in enumerate(cards):
        priority = card.get("review_priority")
        shown = "—" if priority is None else f"{priority:g}/100"
        reasons = " · ".join(card.get("selection_reasons") or [])
        st.button(
            f"{index + 1:02d}  {card.get('title') or 'карточка'}",
            key=f"potential-card-{index}",
            use_container_width=True,
            type="primary" if st.session_state.get("potential_selected", 0) == index else "secondary",
            on_click=_choose,
            args=("potential_selected", index),
        )
        st.caption(f"приоритет {shown} · {reasons}")
    return _selected(cards, "potential_selected")


def potential_detail(card: dict | None) -> None:
    st.markdown("### Карта потенциала")
    if card is None:
        st.info("Запустите поиск: модуль использует реестр исключений того же прогона.")
        return
    st.markdown(f"#### {card.get('title') or 'карточка'}")
    if card.get("technology") and card.get("technology") != card.get("title"):
        st.caption(f"Название источника: {card['technology']}")
    st.warning(
        "Это приоритет следующей проверки, не прогноз спроса, успеха, внедрения или доходности.",
        icon="⚠️",
    )
    a, b, c = st.columns(3)
    values = {axis["id"]: axis for axis in card.get("axes") or []}
    for column, axis in zip((a, b, c), ("technical", "demand", "development"), strict=True):
        row = values.get(axis) or {}
        value = row.get("score")
        column.metric(row.get("title") or axis, "не оценено" if value is None else f"{value:g}/100")
    st.write("**Почему здесь.** " + "; ".join(card.get("selection_reasons") or ["не записано"]))
    st.write(f"**Почему не прошла.** {card.get('why_not_admitted') or 'не записано'}")
    st.caption(
        f"Индекс приоритета: {card.get('review_priority', '—')} · "
        f"индекс потенциала: {card.get('potential_index', '—')} · "
        f"близость к воротам: {card.get('gate_proximity', '—')}"
    )
    evidence, hypotheses, sources = st.tabs(["Доказательства", "Гипотезы", "Источники"])
    with evidence:
        for axis in card.get("axes") or []:
            codes = axis.get("evidence") or []
            st.write(f"**{axis.get('title')}.** " + ("; ".join(codes) if codes else "не оценено"))
        for fragment in card.get("evidence") or []:
            st.write(f"- {fragment.get('text')}")
    with hypotheses:
        st.caption("Сгенерировано моделью и не влияет на рейтинг.")
        for title, key in (
            ("Что это", "plain"),
            ("Где применимо", "sphere"),
            ("Что сдвигает", "moves"),
            ("Плюс", "plus"),
            ("Минус", "minus"),
            ("Что проверить", "open"),
        ):
            value = (card.get("hypothesis") or {}).get(key)
            if value:
                st.write(f"**{title}.** {value}")
    with sources:
        for row in card.get("sources") or []:
            st.caption(row)
        if not card.get("sources"):
            st.info("Ссылки в сохранённой карточке отсутствуют.")


def old_tech_list(cards: list[dict]) -> dict | None:
    st.markdown("### Архивный рейтинг")
    st.caption("Исходные баллы исследования не меняются от поискового запроса.")
    if not cards:
        st.info("В проверяемом архиве совпадений нет.")
        return None
    for index, card in enumerate(cards):
        lower = card.get("score_lower")
        upper = card.get("score_upper")
        band = f"{lower:g}–{upper:g}" if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) else "—"
        st.button(
            f"{card.get('rank', '—'):>02}  {card.get('name') or 'карточка'}",
            key=f"old-card-{card.get('id') or index}",
            use_container_width=True,
            type="primary" if st.session_state.get("old_selected", 0) == index else "secondary",
            on_click=_choose,
            args=("old_selected", index),
        )
        st.caption(f"архивная шкала {band}/100")
    return _selected(cards, "old_selected")


def old_tech_detail(card: dict | None) -> None:
    st.markdown("### Исторический разбор")
    if card is None:
        st.info("Измените запрос или очистите поле, чтобы увидеть весь архив.")
        return
    st.markdown(f"#### {card.get('name') or 'карточка'}")
    year = card.get("historical_year") or "год не указан"
    st.caption(f"{card.get('family') or 'область не указана'} · {year} · {card.get('history_class') or 'класс не указан'}")
    st.write(f"**Барьер тогда.** {card.get('barrier_then') or 'не записан'}")
    st.write(f"**Что изменилось сейчас.** {card.get('change_now') or 'не записано'}")
    st.write(f"**Первый продукт.** {card.get('first_product') or 'не определён'}")
    st.write(f"**Кому может быть нужен.** {card.get('buyers') or 'не проверено'}")
    st.warning("Ни одна архивная карточка пока не прошла полную коммерческую и правовую проверку.", icon="⚠️")
    evidence, diligence, sources = st.tabs(["Доказательства", "Проверки", "Источники"])
    with evidence:
        if card.get("history"):
            st.write(f"**История.** {card['history']}")
        if card.get("evidence"):
            st.write(f"**Что подтверждено.** {card['evidence']}")
        for match in card.get("matches") or []:
            st.caption(f"Совпадение ({match.get('field')}): {match.get('text')}")
    with diligence:
        st.write(f"**Риск.** {card.get('risk') or 'не записан'}")
        st.write(f"**Решающий тест.** {card.get('test') or 'не задан'}")
        holds = card.get("holds") or []
        st.write("**Открытые ворота.** " + ("; ".join(holds) if holds else "не записаны"))
    with sources:
        for source in card.get("sources") or []:
            title = source.get("title") or source.get("id") or "источник"
            url = source.get("url") or ""
            st.markdown(f"- [{title}]({url})" if url else f"- {title}")
            if source.get("supports"):
                st.caption(source["supports"])
        if not card.get("sources"):
            st.info("Источники для карточки не записаны.")
