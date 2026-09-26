"""Viewer document and admin help. The desk does not score and does not replace rules-0.1."""
from __future__ import annotations

from pathlib import Path

import yaml

from ts.extract import PROMPT_VERSION
from ts.scoring.scorer import load_rules
from ts.ui_text import LABELS, panels

FIELDS = [
    {
        "id": "direction",
        "title": "Направление",
        "who": "both",
        "what": "О чём искать слабый сигнал: технология или задача.",
        "why": "Это текст, который уходит в поиск. Без него прогон не стартует.",
        "how": "Напишите коротко, как для коллеги. Длиннее 400 знаков вместе с правкой и периодом форма не примет.",
    },
    {
        "id": "correction",
        "title": "Небольшая правка",
        "who": "both",
        "what": "Уточнение к направлению: что добавить или отсечь.",
        "why": "Чтобы не переписывать всё направление ради одной оговорки.",
        "how": "Одна фраза. Пустое поле значит «без правки».",
    },
    {
        "id": "period",
        "title": "Период",
        "who": "both",
        "what": "Даты, внутри которых смотреть источники.",
        "why": "Чтобы прогон и документ помнили, за какой срок искали.",
        "how": "Поставьте начало и конец. Пустая дата останется в документе как «не задано».",
    },
    {
        "id": "run_status",
        "title": "Статус прогона",
        "who": "both",
        "what": "Дошёл ли поиск до конца: succeeded или ошибка.",
        "why": "Это про работу машины, не про силу сигнала.",
        "how": "Поле только для чтения. Его считает API.",
    },
    {
        "id": "signal_label",
        "title": "Метка сигнала",
        "who": "both",
        "what": "Вывод модели: слабый сигнал, наблюдение, зрелое или шум.",
        "why": "Это научное решение. Оно не равно статусу прогона.",
        "how": "Поле только для чтения. Чтобы изменить вывод, меняют правила отдельным файлом и прогоном eval, не этим экраном.",
    },
    {
        "id": "prompt_draft",
        "title": "Черновик промпта",
        "who": "admin",
        "what": "Текст, которым вы хотите поправить извлечение признаков.",
        "why": "Живой промпт закреплён версией extract-v1. Экран хранит черновик и не подменяет его втихую.",
        "how": "Напишите правку и сохраните. На поиск она не влияет, пока не выйдет новая версия промпта и отчёт eval.",
    },
    {
        "id": "logic_note",
        "title": "Заметка к логике",
        "who": "admin",
        "what": "Что вы хотите изменить в правилах: порог, вес, контр-признак.",
        "why": "Живые правила — файл rules-0.1. Заметка не двигает порог сама.",
        "how": "Опишите правку словами. Смена числа — новый файл правил, ADR и ts eval.",
    },
]


def field_help(field_id: str) -> str:
    row = next(item for item in FIELDS if item["id"] == field_id)
    return f"{row['what']} Зачем: {row['why']} Как менять: {row['how']}"


def compose_query(direction: str, correction: str, start: str, end: str) -> str:
    direction = (direction or "").strip()
    if len(direction) < 2:
        raise ValueError("направление короче двух знаков")
    parts = [direction]
    correction = (correction or "").strip()
    if correction:
        parts.append(correction)
    if (start or "").strip() or (end or "").strip():
        parts.append(f"период {(start or 'не задано').strip()} — {(end or 'не задано').strip()}")
    query = ". ".join(parts)
    if len(query) > 400:
        raise ValueError("запрос длиннее 400 знаков")
    return query


NOT_A_MARKET_FORECAST = (
    "Это не вероятность, что открытие станет стартапом, что вырастет спрос, "
    "что откроется цепочка поставок или что двинется акция. Такого числа модель не считает."
)


def score_story(payload: dict) -> dict:
    """Plain chain of the contributions the scorer already returned. No new verdict."""
    predictors = payload.get("predictors") or []
    confidence = payload.get("confidence")
    lines = []
    if confidence is None:
        lines.append("Контр-признак остановил сумму. Процент не считается, видна причина.")
    else:
        lines.append(
            "Уверенность складывается по порядку: главный признак, затем дополнительные, "
            "затем независимость источников, затем смена стадии. Сумма обрезается от 0 до 1."
        )
        lines.append(f"Итог суммы: {confidence}.")
    for row in predictors:
        if isinstance(row, dict):
            lines.append(
                f"{row.get('code', '—')}: вклад {row.get('contribution', '—')}, "
                f"вес {row.get('weight', '—')}, значение {row.get('value', '—')}"
            )
        else:
            lines.append(str(row))
    top = []
    for item in payload.get("top") or []:
        if isinstance(item, dict):
            label = LABELS.get(item.get("label"), item.get("label") or "—")
            top.append(f"{item.get('technology') or 'карточка'}: {label}, уверенность {item.get('confidence')}")
        else:
            top.append(str(item))
    return {"lines": lines, "disclaimer": NOT_A_MARKET_FORECAST, "top": top}


def reasoning(payload: dict) -> dict:
    """Visible chain from fields the API already returned. No new verdict."""
    steps = []
    reason = payload.get("policy_reason")
    action = payload.get("policy_action")
    if reason or action:
        steps.append(f"Политика: {action or '—'} — {reason or 'причина не пришла'}")
    for code in payload.get("reason_codes") or []:
        steps.append(f"Код причины: {code}")
    for row in payload.get("predictors") or []:
        if isinstance(row, dict):
            steps.append(f"Признак {row.get('code', '—')}: {row.get('note') or row.get('status') or row}")
        else:
            steps.append(f"Признак: {row}")
    counters = payload.get("counters") or {}
    if counters:
        steps.append(
            "Счётчики: источников {sources}, допущено {admitted}, исключено {excluded}, уверенных {confident}".format(
                sources=counters.get("sources", "—"),
                admitted=counters.get("admitted", "—"),
                excluded=counters.get("excluded", "—"),
                confident=counters.get("confident", "—"),
            )
        )
    label = payload.get("signal_label")
    conclusion = LABELS.get(label, label or "вывода нет")
    if not steps:
        steps.append("Цепочка пуста: прогон не вернул причины.")
    return {"steps": steps, "conclusion": conclusion}


def document(payload: dict, direction: str, correction: str, start: str, end: str) -> str:
    view = panels(payload)
    chain = reasoning(payload)
    story = score_story(payload)
    lines = [
        "# Тонкие сигналы",
        "",
        f"Направление: {direction.strip()}",
        f"Правка: {correction.strip() or 'нет'}",
        f"Период: {(start or 'не задано').strip()} — {(end or 'не задано').strip()}",
        f"Статус прогона: {view['run_status']}",
        f"Метка сигнала: {view['signal_label']}",
        f"Недобор до ТОП-15: {view['shortfall']}",
        "",
        "## Что учтено",
        *[f"- {step}" for step in chain["steps"]],
        "",
        f"Вывод: {chain['conclusion']}",
        "",
        "## Как сложилось число",
        *[f"- {step}" for step in story["lines"]],
        "",
        story["disclaimer"],
        "",
        "## Список до ТОП-15",
        *([f"- {row}" for row in story["top"]] or ["- В список никто не прошёл. Недобор выше честный, места не заполняются."]),
        "",
        "## Источники",
        *([f"- {row}" for row in view["sources"]] or ["- Источников нет."]),
        "",
        "## Реестр исключений",
        *([f"- {row}" for row in view["excluded"]] or ["- Пусто."]),
        "",
    ]
    return "\n".join(lines)


def live_logic() -> dict:
    rules = load_rules("rules-0.1")
    return {
        "rules_version": rules.get("version"),
        "prompt_version": PROMPT_VERSION,
        "thresholds": rules.get("thresholds"),
        "description_thresholds": (rules.get("modes") or {}).get("description", {}).get("thresholds"),
        "weights": rules.get("weights"),
        "note": "Экран эти числа не меняет. Смена — новый файл правил и отчёт eval.",
    }


def load_draft(path: Path) -> dict:
    file = Path(path)
    if not file.exists():
        return {"prompt_draft": "", "logic_note": ""}
    data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    return {
        "prompt_draft": str(data.get("prompt_draft") or ""),
        "logic_note": str(data.get("logic_note") or ""),
    }


def save_draft(path: Path, prompt_draft: str, logic_note: str) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        yaml.safe_dump(
            {"prompt_draft": prompt_draft, "logic_note": logic_note, "applied_to_scorer": False},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
