"""Russian labels for the analyst screen. The UI does not score; it only renders the API payload."""
from __future__ import annotations

LABELS = {
    "weak_signal": "слабый сигнал",
    "watchlist": "наблюдение",
    "mature": "зрелое",
    "noise": "шум",
}


def screen(payload: dict) -> dict:
    label = payload.get("signal_label")
    lines = [
        f"Запрос: {payload.get('query', '')}",
        f"Статус прогона: {payload.get('run_status', '—')}",
        f"Метка сигнала: {LABELS.get(label, label or '—')}",
        f"Решение политики: {payload.get('policy_action', '—')} — {payload.get('policy_reason', '')}",
        f"Уверенность: {payload.get('confidence') if payload.get('confidence') is not None else 'нет числа, сработал контр-признак'}",
        f"В ТОП-15: {len(payload.get('top') or [])}, недобор: {payload.get('shortfall', '—')}",
        f"Модель: {payload.get('model_id') or 'извлечение не запускалось'}",
    ]
    sources = []
    for src in payload.get("sources") or []:
        date = src.get("date") or src.get("date_unknown_reason") or "дата не указана"
        sources.append(f"{src.get('name')} · {src.get('type')} · {src.get('language')} · {src.get('trust')} · {date} · {src.get('url')}")
    excluded = [
        f"{row.get('technology', payload.get('query'))}: {row.get('label')} / {row.get('policy_action')} — {row.get('policy_reason')}"
        for row in payload.get("exclusion_registry") or []
    ]
    return {"lines": lines, "sources": sources, "excluded": excluded}
