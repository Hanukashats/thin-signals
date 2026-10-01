"""Russian labels for the analyst screen. The UI does not score; it only renders the API payload."""
from __future__ import annotations

from ts.plain import ACTIONS, LANG, REASONS, RUN, TRUST, TYPES, decision_line, say, scope_sentence

LABELS = {
    "weak_signal": "слабый сигнал",
    "watchlist": "наблюдение",
    "mature": "зрелое",
    "noise": "шум",
}


def _confidence_line(payload: dict) -> str:
    if payload.get("confidence") is not None:
        return str(payload.get("confidence"))
    top = [item for item in (payload.get("top") or []) if isinstance(item, dict)]
    status = ""
    if top:
        status = str((top[0].get("checklist") or {}).get("status") or "")
    if not top or status in {"", "no_fragment", "reader_failed"}:
        return "не оценивалась: текст источника не прочитан"
    return "нет числа, сработал контр-признак"


def _list_without_checklist(payload: dict) -> bool:
    top = [item for item in (payload.get("top") or []) if isinstance(item, dict)]
    if not top:
        return False
    for item in top:
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and confidence > 0:
            return False
        for row in item.get("predictors") or []:
            if isinstance(row, dict) and str(row.get("code") or "").startswith("P"):
                return False
    return True


def shown_label(payload: dict) -> str:
    if _list_without_checklist(payload):
        return "признаки не оценивались"
    label = payload.get("signal_label")
    return LABELS.get(label, label or "—")


def screen(payload: dict) -> dict:
    lines = [
        f"Запрос: {payload.get('query', '')}",
        f"Статус прогона: {say(RUN, payload.get('run_status'), 'статус не пришёл')}",
        f"Метка сигнала: {shown_label(payload)}",
        decision_line(payload.get("policy_action"), payload.get("policy_reason")),
        f"Уверенность: {_confidence_line(payload)}",
        f"Отобрано карточек: {len(payload.get('top') or [])}, недобор до 15: {payload.get('shortfall', '—')}",
        f"Модель: {payload.get('model_id') or 'извлечение не запускалось'}",
    ]
    fanout = payload.get("fanout") or {}
    if fanout.get("themes"):
        lines.append(
            "Широкая фраза разобрана на темы. Читатель назвал масштаб у карточек общего списка "
            "и не менял допуск. Сначала более широкий сдвиг, если текст его прямо назвал. "
            "Гипотеза применения пишется после этого и порядок не меняет."
        )
        for theme in fanout["themes"]:
            lines.append(
                f"{theme.get('title')}: {theme.get('query')} — "
                f"в теме {theme.get('admitted', 0)}, в общем списке {theme.get('taken', 0)}"
            )
    sources = []
    for src in payload.get("sources") or []:
        date = src.get("date") or src.get("date_unknown_reason") or "дата не указана"
        kind = say(TYPES, src.get("type"), "тип не указан") if src.get("type") else "тип не указан"
        language = say(LANG, src.get("language"), "язык не указан") if src.get("language") else "язык не указан"
        trust = say(TRUST, src.get("trust"), "доверие не разобрано") if src.get("trust") else "доверие не разобрано"
        sources.append(f"{src.get('name')} · {kind} · {language} · {trust} · {date} · {src.get('url')}")
    excluded = []
    for row in payload.get("exclusion_registry") or []:
        name = row.get("technology", payload.get("query"))
        label_words = LABELS.get(row.get("label"), row.get("label") or "без метки")
        action = say(ACTIONS, row.get("policy_action")) if row.get("policy_action") else "решение не пришло"
        reason = say(REASONS, row.get("policy_reason")) if row.get("policy_reason") else "причина не пришла"
        line = f"{name}: {label_words}. {action}. {reason}."
        sentence = (row.get("chain_link") or {}).get("sentence")
        scale = scope_sentence(row.get("scope"))
        if scale:
            line = f"{line} {scale}"
        if sentence:
            line = f"{line} {sentence}"
        excluded.append(line)
    return {"lines": lines, "sources": sources, "excluded": excluded}


def panels(payload: dict) -> dict:
    """Four facts the analyst screen must show apart. No scoring."""
    view = screen(payload)
    return {
        "run_status": say(RUN, payload.get("run_status"), "статус не пришёл"),
        "signal_label": shown_label(payload),
        "sources": view["sources"],
        "shortfall": payload.get("shortfall", "—"),
        "excluded": view["excluded"],
    }
