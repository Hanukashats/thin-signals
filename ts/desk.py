"""Viewer document and admin help. The desk does not score and does not replace rules-0.1."""
from __future__ import annotations

from pathlib import Path

import yaml

from ts.extract import PROMPT_VERSION
from ts.nearest import nearest_lines
from ts.plain import LANG, TRUST, TYPES, VALUES, code_words, decision_line, say, scope_sentence, stopper_line
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
        "what": "Дошёл ли поиск до конца или остановился с ошибкой.",
        "why": "Это про работу поиска, не про силу находки.",
        "how": "Поле только для чтения. Его пишет сам прогон.",
    },
    {
        "id": "signal_label",
        "title": "Метка сигнала",
        "who": "both",
        "what": "Что решили по теме: ранний сигнал, наблюдение, уже зрелое или шум.",
        "why": "Это вывод по теме. Он не говорит, сломался ли поиск.",
        "how": "Поле только для чтения. Экран сам вывод не меняет.",
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


def _feature_line(row) -> str:
    if not isinstance(row, dict):
        return str(row)
    value = row.get("value", "—")
    shown = VALUES.get(str(value), value)
    return (
        f"{code_words(row.get('code'))}. "
        f"К числу добавилось {row.get('contribution', '—')} из {row.get('weight', '—')}. "
        f"Состояние: {shown}."
    )


def candidate_views(items: list) -> list[dict]:
    """Fields the screen shows on a card. No new verdict."""
    views = []
    for index, item in enumerate(items or [], start=1):
        if not isinstance(item, dict):
            continue
        reach = item.get("reach") if isinstance(item.get("reach"), dict) else {}
        sources = item.get("sources") or []
        url = ""
        for source in sources:
            if isinstance(source, dict) and source.get("url"):
                url = source["url"]
                break
        scale = scope_sentence(item.get("scope"))
        why = str(item.get("scope_why") or "").strip()
        views.append({
            "index": index,
            "title": item.get("technology") or "карточка",
            "theme": item.get("theme_title") or "",
            "plain": str(reach.get("plain") or "").strip(),
            "scale": " ".join(part for part in (scale, why) if part),
            "sphere": str(reach.get("sphere") or "").strip(),
            "moves": str(reach.get("moves") or "").strip(),
            "affects": str(reach.get("affects") or "").strip(),
            "plus": str(reach.get("plus") or "").strip(),
            "minus": str(reach.get("minus") or "").strip(),
            "terms": str(reach.get("terms") or "").strip(),
            "if_true": str(reach.get("if_true") or "").strip(),
            "open": str(reach.get("open") or "").strip(),
            "case": _case_line(item),
            "confidence_note": "" if _checklist_filled(item) else (
                "Прошла проверки допуска. Признаки слабого сигнала не оценивались, числа уверенности нет."
            ),
            "why_here": _why_here(item),
            "sources": [_source_line(source) for source in sources if isinstance(source, dict)][:3],
            "url": url,
            "label": LABELS.get(item.get("label"), item.get("label") or "—"),
            "confidence": item.get("confidence"),
        })
    return views


def _case_line(item: dict) -> str:
    quote = item.get("case_quote") if isinstance(item.get("case_quote"), dict) else None
    text = str((quote or {}).get("text") or "").strip()
    if text:
        return f"Цитата источника: {text}"
    return "Кейс в найденных источниках не назван."


def _why_here(item: dict) -> str:
    if not _checklist_filled(item):
        return (
            "В списке, потому что заголовок держит запрос и это не единственный пересказ. "
            "Ранний это тренд или уже зрелый, по признакам ещё не решено."
        )
    named = []
    for row in item.get("predictors") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("code") or "").startswith("P") and row.get("value") in ("verified", "supported"):
            named.append(code_words(row.get("code")))
    if not named:
        return "Чек-лист посчитан по фрагменту. Ранний признак в тексте не подтверждён."
    return f"По фрагменту названы признаки: {', '.join(named[:3])}. Сумма {item.get('confidence')}."


def _checklist_filled(item: dict) -> bool:
    confidence = item.get("confidence")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and confidence > 0:
        return True
    for row in item.get("predictors") or []:
        if isinstance(row, dict) and str(row.get("code") or "").startswith("P"):
            return True
    return False


def _source_line(source: dict) -> str:
    date = source.get("date") or source.get("date_unknown_reason") or "дата не указана"
    kind = say(TYPES, source.get("type"), "тип не указан") if source.get("type") else "тип не указан"
    language = say(LANG, source.get("language"), "язык не указан") if source.get("language") else "язык не указан"
    trust = say(TRUST, source.get("trust"), "доверие не разобрано") if source.get("trust") else "доверие не разобрано"
    name = source.get("name") or "источник"
    return f"{name} · {kind} · {language} · {trust} · {date} · {source.get('url') or 'ссылки нет'}"


def run_banner(payload: dict) -> list[str]:
    """Counts the brief asks for. Does not invent a confidence."""
    counters = payload.get("counters") or {}
    top = [item for item in (payload.get("top") or []) if isinstance(item, dict)]
    admitted = counters.get("admitted", len(top))
    sources = counters.get("sources", "—")
    lines = [
        f"Кандидатов в списке: {admitted}.",
        f"Источников в прогоне: {sources}.",
    ]
    if any(_checklist_filled(item) for item in top):
        lines.append(f"С уверенностью выше 75%: {counters.get('confident', 0)}.")
    else:
        lines.append("Уверенность выше 75%: не применимо. Ни у одной карточки списка нет посчитанной суммы.")
    return lines


def score_story(payload: dict) -> dict:
    """Plain chain of the contributions the scorer already returned. No new verdict."""
    predictors = payload.get("predictors") or []
    confidence = payload.get("confidence")
    lines = []
    if confidence is None:
        lines.append("Стоппер остановил сумму. Процент не считается, ниже видна причина.")
    else:
        lines.append(
            "Число складывается по порядку: главный признак, затем дополнительные, "
            "затем независимость источников, затем смена стадии. Сумма обрезается от 0 до 1."
        )
        lines.append(f"Итог суммы: {confidence}.")
    for row in predictors:
        lines.append(_feature_line(row))
    brief = []
    top = []
    cards = candidate_views(payload.get("top") or [])
    for view in cards:
        head = view["title"] + (f" · {view['theme']}" if view["theme"] else "")
        block = [f"{view['index']}. {head}"]
        if view["scale"]:
            block.append(view["scale"])
        guessed = [
            line for line in (
                view["plain"] and f"Что это: {view['plain']}",
                view["sphere"] and f"Где может пригодиться: {view['sphere']}",
                view["moves"] and f"На что может повлиять: {view['moves']}",
                view["plus"] and f"Плюс: {view['plus']}",
                view["minus"] and f"Минус: {view['minus']}",
                view["terms"] and f"Сложные слова: {view['terms']}",
            ) if line
        ]
        if guessed:
            block.append("Гипотеза модели, в тексте не проверено.")
            block.extend(guessed)
        elif view["theme"]:
            block.append("Гипотеза применения не названа.")
        if len(block) > 1:
            brief.append("\n".join(block))
        if view["confidence_note"]:
            top.append(f"{head}: {view['confidence_note']}")
        else:
            top.append(f"{head}: {view['label']}, уверенность {view['confidence']}")
    return {"lines": lines, "disclaimer": NOT_A_MARKET_FORECAST, "brief": brief, "cards": cards, "top": top}


def reasoning(payload: dict) -> dict:
    """Visible chain from fields the API already returned. No new verdict."""
    steps = []
    reason = payload.get("policy_reason")
    action = payload.get("policy_action")
    if reason or action:
        steps.append(decision_line(action, reason))
    stop = stopper_line(payload.get("reason_codes") or [])
    if stop:
        steps.append(stop)
    for row in payload.get("predictors") or []:
        if isinstance(row, dict) and (row.get("note") or row.get("status")):
            steps.append(f"{code_words(row.get('code'))}: {row.get('note') or row.get('status')}")
        else:
            steps.append(_feature_line(row))
    counters = payload.get("counters") or {}
    if counters:
        steps.append(
            "Нашли источников: {sources}. Допустили в список: {admitted}. "
            "Отсеяли: {excluded}. С высокой уверенностью: {confident}.".format(
                sources=counters.get("sources", "—"),
                admitted=counters.get("admitted", "—"),
                excluded=counters.get("excluded", "—"),
                confident=counters.get("confident", "—"),
            )
        )
    label = payload.get("signal_label")
    conclusion = LABELS.get(label, label or "вывода нет")
    link = payload.get("chain_link") or {}
    if link.get("sentence"):
        steps.append(link["sentence"])
    scale = scope_sentence(payload.get("scope"))
    if scale:
        steps.append(scale)
    if not steps:
        steps.append("Цепочка пуста: прогон не вернул причины.")
    return {"steps": steps, "conclusion": conclusion}


def document(payload: dict, direction: str, correction: str, start: str, end: str) -> str:
    view = panels(payload)
    chain = reasoning(payload)
    story = score_story(payload)
    near = nearest_lines(payload)
    ladder = "не выведена" if near["ladder_percent"] is None else f"{near['ladder_percent']}%"
    lines = [
        "# Тонкие сигналы",
        "",
        f"Направление: {direction.strip()}",
        f"Правка: {correction.strip() or 'нет'}",
        f"Период: {(start or 'не задано').strip()} — {(end or 'не задано').strip()}",
        f"Статус прогона: {view['run_status']}",
        f"Метка сигнала: {view['signal_label']}",
        f"Пустых мест в списке из 15: {view['shortfall']}",
        *run_banner(payload),
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
        *([f"- {row}" for row in story["top"]] or ["- В список никто не прошёл. Пустые места не заполняются."]),
        "",
        "## Не прочитаны",
        *([f"- {item.get('technology') or 'карточка'}" for item in (payload.get("unread") or []) if isinstance(item, dict)]
          or ["- Непрочитанных нет."]),
        "",
        "## Ближайшие к допуску",
        near["note"],
        "",
        f"Официальный список: {near['official_count']}. Ступеней допуска: {ladder}. Остановка: {near['stuck']}. {near['why']}",
        f"В окне {near['shown']} из {near['found']}.",
        *([f"- {row}" for row in near["lines"]] or ["- Ближайших находок нет: поиск ничего не вернул."]),
        "",
        "## Источники",
        *([f"- {row}" for row in view["sources"]] or ["- Источников нет."]),
        "",
        "## Почему не вошло в список",
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
