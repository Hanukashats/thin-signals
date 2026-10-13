"""Viewer document and admin help. The desk does not score and does not replace rules-0.1."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from ts.extract import PROMPT_VERSION
from ts.fanout import _identity
from ts.nearest import nearest_lines
from ts.old_tech import search_old_tech_cards
from ts.plain import (
    LANG,
    OLD_TECH_DECISIONS,
    OLD_TECH_HOLDS,
    REASONS,
    TRUST,
    TYPES,
    VALUES,
    code_words,
    decision_line,
    say,
    scope_sentence,
    stopper_line,
)
from ts.potential import POTENTIAL_VERSION, rank_potential_cards
from ts.scoring.scorer import load_rules, thresholds_for
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
        "title": "Период — уточнение запроса",
        "who": "both",
        "what": "Даты добавляются в текст запроса; это не строгий фильтр источников.",
        "why": "Чтобы дать поиску временной контекст и сохранить его в документе.",
        "how": "Поставьте начало и конец. Проверяйте даты найденных источников отдельно.",
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
            "evidence": candidate_evidence(item),
        })
    return views


def candidate_groups(payload: dict) -> dict[str, list[dict]]:
    """Group existing verdicts for display without promoting or re-scoring a card."""
    groups: dict[str, list[dict]] = {
        "weak_signals": [],
        "watchlist": [],
        "needs_data": [],
        "other": [],
    }
    for item in payload.get("top") or []:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        if label == "weak_signal":
            groups["weak_signals"].append(item)
        elif label == "watchlist":
            groups["watchlist"].append(item)
        elif label in (None, ""):
            groups["needs_data"].append(item)
        else:
            groups["other"].append(item)
    return groups


def _plural_ru(count: int, one: str, few: str, many: str) -> str:
    value = abs(count) % 100
    tail = value % 10
    if 10 < value < 20:
        word = many
    elif tail == 1:
        word = one
    elif 2 <= tail <= 4:
        word = few
    else:
        word = many
    return f"{count} {word}"


def run_integrity(payload: dict, *, expected_checklist: str) -> dict:
    """Read-only run provenance and visible gaps; never derives a product verdict."""
    groups = candidate_groups(payload)
    parts = [
        _plural_ru(len(groups["weak_signals"]), "слабый сигнал", "слабых сигнала", "слабых сигналов"),
        _plural_ru(len(groups["watchlist"]), "наблюдение", "наблюдения", "наблюдений"),
    ]
    if groups["needs_data"]:
        parts.append(_plural_ru(len(groups["needs_data"]), "без решения", "без решения", "без решения"))
    if groups["other"]:
        parts.append(_plural_ru(len(groups["other"]), "прочая карточка", "прочие карточки", "прочих карточек"))

    top = [item for item in (payload.get("top") or []) if isinstance(item, dict)]
    inspected = [
        item for bucket in ("top", "exclusion_registry", "potential", "unread")
        for item in (payload.get(bucket) or []) if isinstance(item, dict)
        and isinstance(item.get("checklist"), dict)
    ]
    urls = {
        str(source.get("url") or "").strip()
        for item in top
        for source in (item.get("sources") or [])
        if isinstance(source, dict) and str(source.get("url") or "").strip()
    }
    versions = sorted({
        str((item.get("checklist") or {}).get("version") or "").strip()
        for item in inspected
        if isinstance(item.get("checklist"), dict)
        and str((item.get("checklist") or {}).get("version") or "").strip()
    })
    model_id = str(payload.get("model_id") or "").strip() or next((
        str((item.get("checklist") or {}).get("model_id") or "").strip()
        for item in inspected
        if str((item.get("checklist") or {}).get("model_id") or "").strip()
    ), "")
    provider = str(payload.get("provider") or "").strip()

    warnings: list[str] = []
    if (top or inspected) and expected_checklist and versions != [expected_checklist]:
        shown = ", ".join(versions) if versions else "не записана"
        warnings.append(f"Версия чек-листа у карточек: {shown}; ожидается {expected_checklist}.")
    if model_id and not provider:
        warnings.append("Provider не записан: маршрут модели нельзя подтвердить по этому результату.")
    if top and all(
        any(
            isinstance(row, dict)
            and row.get("code") == "IND"
            and row.get("value") in (0, 0.0, "0")
            for row in (item.get("predictors") or [])
        )
        for item in top
    ):
        warnings.append("Независимость источников не подтверждена ни у одной карточки.")

    counters = payload.get("counters") if isinstance(payload.get("counters"), dict) else {}
    run_id = str(payload.get("run_id") or payload.get("id") or "не записан")
    rules_version = str(payload.get("rules_version") or next((
        item.get("rules_version") for item in top if item.get("rules_version")
    ), "не записана"))
    checklist = ", ".join(versions) if versions else "не записан"
    provenance = (
        f"RUN {run_id} · rules {rules_version} · checklist {checklist} · "
        f"model {model_id or 'не запускалась'} · provider {provider or 'не записан'}"
    )
    return {
        "composition": " · ".join(parts),
        "selected_source_count": len(urls),
        "run_source_count": counters.get("sources", "—"),
        "provenance": provenance,
        "warnings": warnings,
        "groups": groups,
    }


def candidate_evidence(item: dict) -> dict[str, list[str]]:
    """Separate returned evidence, model hypotheses, checks and source references."""
    facts = [
        f"Фрагмент [{row.get('fragment', '—')}]: {str(row.get('text') or '').strip()}"
        for row in (item.get("evidence_fragments") or [])
        if isinstance(row, dict) and str(row.get("text") or "").strip()
    ]
    quote = item.get("case_quote") if isinstance(item.get("case_quote"), dict) else {}
    cited = {row.get("fragment") for row in (item.get("evidence_fragments") or []) if isinstance(row, dict)}
    if str(quote.get("text") or "").strip() and quote.get("fragment") not in cited:
        facts.append(f"Фрагмент [{quote.get('fragment', '—')}]: {str(quote['text']).strip()}")
    scale = scope_sentence(item.get("scope"))
    scale_why = str(item.get("scope_why") or "").strip()

    reach = item.get("reach") if isinstance(item.get("reach"), dict) else {}
    hypothesis_fields = (
        ("Что это", "plain"),
        ("Где может пригодиться", "sphere"),
        ("На что может повлиять", "moves"),
        ("Что ещё может задеть", "affects"),
        ("Потенциальный плюс", "plus"),
        ("Потенциальный минус", "minus"),
        ("Если подтвердится", "if_true"),
    )
    hypotheses = [
        f"{title}: {str(reach.get(key)).strip()}"
        for title, key in hypothesis_fields
        if str(reach.get(key) or "").strip()
    ]

    checklist = item.get("checklist") if isinstance(item.get("checklist"), dict) else {}
    label = LABELS.get(item.get("label"), item.get("label") or "решение не записано")
    confidence = item.get("confidence")
    checks = [
        f"Метка карточки: {label}; сумма признаков: {confidence if confidence is not None else 'не посчитана'}.",
        "Чек-лист: {version}; состояние: {status}.".format(
            version=checklist.get("version") or "не записан",
            status=checklist.get("status") or "не записано",
        ),
    ]
    if scale or scale_why:
        checks.append("Проверка масштаба: " + " ".join(part for part in (scale, scale_why) if part))
    if str(reach.get("open") or "").strip():
        checks.append(f"Открытый вопрос: {str(reach['open']).strip()}")
    if item.get("reason_codes"):
        checks.append("Коды проверки: " + ", ".join(map(str, item["reason_codes"])))

    sources = [
        _source_line(source)
        for source in (item.get("sources") or [])
        if isinstance(source, dict)
    ]
    return {"facts": facts, "hypotheses": hypotheses, "checks": checks, "sources": sources}


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


NEAR_MISS_FLOOR = 0.25
NEAR_MISS_CAP = 8
_NEAR_MISS_DROP = frozenset({
    "checklist_counter", "reader_failed", "reader_failed_replaced", "no_source_text", "no_source_text_replaced",
})


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def near_miss_cards(payload, *, rules: dict | None = None) -> list[dict]:
    """Scored cards just under the watchlist. They never fill the official TOP-15."""
    version = str((payload or {}).get("rules_version") or "rules-0.1") if isinstance(payload, dict) else "rules-0.1"
    active_rules = rules or load_rules(version)
    watchlist_threshold = thresholds_for(active_rules)["watchlist"]
    registry = (payload or {}).get("exclusion_registry") if isinstance(payload, dict) else None
    picked = []
    for card in registry or []:
        if not isinstance(card, dict):
            continue
        if (card.get("checklist") or {}).get("status") != "scored":
            continue
        if card.get("policy_reason") in _NEAR_MISS_DROP:
            continue
        confidence = card.get("confidence")
        if not _number(confidence) or not NEAR_MISS_FLOOR <= confidence < watchlist_threshold:
            continue
        picked.append(dict(card))
    picked.sort(key=lambda card: (-card["confidence"], str(card.get("technology") or "")))
    return picked[:NEAR_MISS_CAP]


def _predictor_brief(predictors) -> str:
    parts = []
    for row in predictors or []:
        if not isinstance(row, dict) or not _number(row.get("contribution")) or not row["contribution"]:
            continue
        parts.append(f"{code_words(row.get('code'))}: {row['contribution']:+g}")
        if len(parts) >= 3:
            break
    return "; ".join(parts)


def near_miss_board(payload: dict) -> dict:
    """Cards for «Близко к проходу». An old run without near_miss gets the same selection, without reach."""
    stored = payload.get("near_miss") if isinstance(payload, dict) else None
    saved = isinstance(stored, list)
    rows = [card for card in stored if isinstance(card, dict)] if saved else near_miss_cards(payload)
    cards = []
    for row in rows:
        reach = row.get("reach") if isinstance(row.get("reach"), dict) else {}
        plain = str(reach.get("plain") or "").strip()
        cards.append({
            "title": plain or row.get("technology") or "карточка",
            "technology": row.get("technology") or "",
            "confidence": row.get("confidence"),
            "why": say(REASONS, row.get("policy_reason"), "причина не названа"),
            "predictors": _predictor_brief(row.get("predictors")),
            "plain": plain,
            "sphere": str(reach.get("sphere") or "").strip(),
            "moves": str(reach.get("moves") or "").strip(),
            "plus": str(reach.get("plus") or "").strip(),
            "minus": str(reach.get("minus") or "").strip(),
        })
    pending = not saved and any(not card["plain"] or not card["sphere"] for card in cards)
    return {
        "cards": cards,
        "note": "Описание и сфера появятся после нового поиска." if pending else "",
    }


_POTENTIAL_REASON = {
    "near_gate": "близко к порогу допуска",
    "high_potential": "высокий индекс приоритета проверки по подтверждённым признакам",
}
_POTENTIAL_AXIS = {
    "technical": "технологическая новизна",
    "demand": "сигналы востребованности",
    "development": "динамика развития",
}


def potential_board(payload: dict) -> dict:
    """Present the separate review queue without calling an index a forecast."""
    stored = payload.get("potential") if isinstance(payload, dict) else None
    persisted = isinstance(stored, list)
    # Revalidate persisted data under the active contract; historical labels remain historical.
    rows = rank_potential_cards(payload)
    current_saved = {
        _identity(card): card for card in (stored or []) if isinstance(card, dict)
        and card.get("potential_version") == POTENTIAL_VERSION
    }
    cards = []
    for index, row in enumerate(rows, start=1):
        metrics = row.get("potential") if isinstance(row.get("potential"), dict) else {}
        saved = current_saved.get(_identity(row), {})
        reach = saved.get("reach") or row.get("reach")
        reach = reach if isinstance(reach, dict) else {}
        axes = []
        codes = metrics.get("evidence_codes") if isinstance(metrics.get("evidence_codes"), dict) else {}
        for axis in ("technical", "demand", "development"):
            score = metrics.get(axis)
            axes.append({
                "id": axis,
                "title": _POTENTIAL_AXIS[axis],
                "score": score if _number(score) else None,
                "evidence": [code_words(code) for code in (codes.get(axis) or [])],
            })
        fragments = []
        for fragment in row.get("evidence_fragments") or []:
            if isinstance(fragment, dict) and str(fragment.get("text") or "").strip():
                fragments.append({
                    "text": str(fragment["text"]).strip(),
                    "url": str(fragment.get("url") or "").strip(),
                })
        cards.append({
            "id": str(row.get("id") or row.get("technology") or index),
            "rank": index,
            "title": str(reach.get("plain") or row.get("technology") or "карточка"),
            "technology": str(row.get("technology") or ""),
            "review_priority": row.get("review_priority"),
            "potential_index": metrics.get("potential_index"),
            "gate_proximity": metrics.get("gate_proximity"),
            "gate_gap": row.get("gate_gap"),
            "gate_target": row.get("gate_target"),
            "checklist": dict(row.get("checklist") or {}),
            "selection_reasons": [
                _POTENTIAL_REASON.get(reason, str(reason))
                for reason in (row.get("selection_reasons") or [])
            ],
            "axes": axes,
            "coverage": metrics.get("evaluated_axes"),
            "why_not_admitted": (
                "наблюдение ниже порога слабого сигнала 0,60"
                if row.get("label") == "watchlist"
                else say(REASONS, row.get("policy_reason"), "причина не названа")
            ),
            "hypothesis": {
                key: str(reach.get(key) or "").strip()
                for key in ("plain", "sphere", "moves", "plus", "minus", "open")
            },
            "evidence": fragments,
            "sources": [
                _source_line(source)
                for source in (row.get("sources") or [])
                if isinstance(source, dict)
            ],
        })
    note = (
        "Очередь рассчитана из сохранённых проверенных признаков этого прогона. "
        if persisted
        else "Очередь пересчитана из наблюдений и реестра исключений. "
    )
    note += (
        "Индекс означает приоритет следующей проверки, а не вероятность успеха, "
        "рыночного спроса, внедрения или доходности. Старый чек-лист не участвует: нужен новый прогон. "
        "Близость сравнивается с порогом наблюдения 0,35; для наблюдений отдельно показано расстояние "
        "до слабого сигнала 0,60. Высокий потенциал ранжируется по собственному индексу."
    )
    return {"cards": cards, "note": note, "persisted": persisted}


OLD_TECH_SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "old_tech" / "snapshot_2026-09-29.json"


def _archive_date(as_of: str) -> str:
    parts = str(as_of).split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = parts
        return f"{day}.{month}.{year}"
    return str(as_of)


def old_tech_board(path: Path | None = None, query: str = "") -> dict:
    """Search the sealed research archive. It never fills the current-signal list."""
    target = OLD_TECH_SNAPSHOT if path is None else Path(path)
    empty = {
        "cards": [],
        "note": "Архив не загружен",
        "as_of": "",
        "fully_qualified_count": None,
        "query": str(query or "").strip(),
        "total": 0,
    }
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return empty
    if not isinstance(raw, dict) or not isinstance(raw.get("cards"), list):
        return empty
    cards = []
    for row in search_old_tech_cards(raw["cards"], query):
        if not isinstance(row, dict):
            continue
        holds = [say(OLD_TECH_HOLDS, code) for code in row.get("holds") or [] if str(code).strip()]
        lower = row.get("score_lower")
        upper = row.get("score_upper")
        cards.append({
            "id": row.get("id") or "",
            "name": row.get("name") or "карточка",
            "rank": row.get("rank"),
            "score_lower": lower,
            "score_upper": upper,
            "historical_year": row.get("historical_year"),
            "history_class": str(row.get("history_class") or "").strip(),
            "family": str(row.get("family") or "").strip(),
            "history": str(row.get("history") or "").strip(),
            "barrier_then": str(row.get("barrier_then") or "").strip(),
            "change_now": str(row.get("change_now") or "").strip(),
            "evidence": str(row.get("evidence") or "").strip(),
            "first_product": str(row.get("first_product") or "").strip(),
            "buyers": str(row.get("buyers") or "").strip(),
            "risk": str(row.get("risk") or "").strip(),
            "market_findings": str(row.get("market_findings") or "").strip(),
            "test": str(row.get("test") or "").strip(),
            "holds": holds,
            "decision": say(OLD_TECH_DECISIONS, row.get("decision")),
            "fully_qualified": bool(row.get("fully_qualified")),
            "search_score": row.get("search_score"),
            "matches": list(row.get("match_excerpts") or []),
            "sources": [
                {
                    "id": source.get("id") or "",
                    "title": source.get("title") or source.get("id") or "источник",
                    "url": source.get("url") or "",
                    "published": source.get("published"),
                    "supports": source.get("supports") or "",
                    "limitations": source.get("limitations") or "",
                }
                for source in (row.get("sources") or [])
                if isinstance(source, dict)
            ],
        })
    count = raw.get("fully_qualified_count")
    as_of = str(raw.get("as_of") or "")
    note = (
        f"Поиск по проверяемому архиву из 15 карточек, срез от {_archive_date(as_of)}. "
        f"Полностью прошедших коммерческую и правовую проверку карточек: {count}. "
        "Они не входят в список текущего поиска и пустые места не заполняют. "
        "Шкала 0–100 не сравнима с оценкой основного списка. Это поиск по архиву, не свежий веб-поиск."
    )
    return {
        "cards": cards,
        "note": note,
        "as_of": as_of,
        "fully_qualified_count": count,
        "query": str(query or "").strip(),
        "total": len(raw["cards"]),
    }


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
        f"Ссылок в сохранённой выборке: {sources}.",
    ]
    if any(_checklist_filled(item) for item in top):
        lines.append(f"С уверенностью выше 75%: {counters.get('confident', 0)}.")
    else:
        lines.append("Уверенность выше 75%: не применимо. Ни у одной карточки списка нет посчитанной суммы.")
    return lines


def saved_run_state(payload: dict) -> dict:
    """Decide whether a persisted run is safe to present as the current result.

    A reverted experimental run can remain in PostgreSQL after the code returns
    to a stable method.  The viewer must not silently call such a payload the
    current TOP-15 when its own counters contradict its rows.
    """
    top = [item for item in (payload.get("top") or []) if isinstance(item, dict)]
    counters = payload.get("counters") if isinstance(payload.get("counters"), dict) else {}
    admitted = counters.get("admitted")
    reported_shortfall = payload.get("shortfall")
    is_count = lambda value: isinstance(value, int) and not isinstance(value, bool) and value >= 0

    if not is_count(admitted):
        return {
            "safe_to_autoload": True,
            "displayed_shortfall": reported_shortfall if is_count(reported_shortfall) else "—",
            "message": "",
        }

    expected_shortfall = max(0, 15 - min(15, admitted))
    inconsistent = len(top) != admitted or (
        is_count(reported_shortfall) and reported_shortfall != expected_shortfall
    )
    if inconsistent:
        return {
            "safe_to_autoload": False,
            "displayed_shortfall": expected_shortfall,
            "message": (
                "Последний сохранённый прогон выглядит устаревшим: число строк, "
                "счётчик допуска и недобор противоречат друг другу. Он не показан "
                "как актуальный результат; запустите новый поиск."
            ),
        }
    return {
        "safe_to_autoload": True,
        "displayed_shortfall": reported_shortfall if is_count(reported_shortfall) else expected_shortfall,
        "message": "",
    }


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
    empty_run = payload.get("decision_scope") == "run_empty"
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
            "Ссылок в сохранённой выборке: {sources}. Допустили в список: {admitted}. "
            "Отсеяли: {excluded}. С высокой уверенностью: {confident}.".format(
                sources=counters.get("sources", "—"),
                admitted=counters.get("admitted", "—"),
                excluded=counters.get("excluded", "—"),
                confident=counters.get("confident", "—"),
            )
        )
    retrieval = payload.get("retrieval") if isinstance(payload.get("retrieval"), dict) else {}
    funnel = retrieval.get("funnel") if isinstance(retrieval.get("funnel"), dict) else {}
    if funnel:
        steps.append(
            "Воронка поиска: коннекторы вернули {found} записей; после объединения — "
            "{sources} уникальных ссылок и {events} событий; контрпоиск вернул "
            "{counter} записей; допущено {admitted}, исключено {excluded}, "
            "осталось непрочитанными {unread}.".format(
                found=funnel.get("discovery_items", "—"),
                sources=funnel.get("unique_sources", "—"),
                events=funnel.get("deduplicated_events", "—"),
                counter=funnel.get("countersearch_items", "—"),
                admitted=funnel.get("admitted", "—"),
                excluded=funnel.get("excluded", "—"),
                unread=funnel.get("unread", "—"),
            )
        )
    label = payload.get("signal_label")
    conclusion = (
        "список пуст: ни одна карточка не прошла допуск"
        if empty_run
        else LABELS.get(label, label or "вывода нет")
    )
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
        (
            "## Почему список пуст"
            if payload.get("decision_scope") == "run_empty"
            else f"## Как принято решение по карточке №1: {payload.get('decision_card') or 'название не записано'}"
        ),
        *[f"- {step}" for step in chain["steps"]],
        "",
        f"Вывод: {chain['conclusion']}",
        "",
        "## Как сложилось число",
        *[f"- {step}" for step in story["lines"]],
        "",
        story["disclaimer"],
        "",
        "## Отобранные находки",
        *([f"- {row}" for row in story["top"]] or ["- В список никто не прошёл. Пустые места не заполняются."]),
        "",
        "## Не прочитаны",
        *([f"- {item.get('technology') or 'карточка'}" for item in (payload.get("unread") or []) if isinstance(item, dict)]
          or ["- Непрочитанных нет."]),
        "",
        "## Ближайшие к допуску",
        near["note"],
        "",
        f"Отобранных карточек: {near['official_count']}. Ступеней допуска: {ladder}. Остановка: {near['stuck']}. {near['why']}",
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


def live_logic(rules_version: str | None = None) -> dict:
    rules = load_rules(rules_version or os.environ.get("TS_RULES_VERSION", "rules-0.1"))
    return {
        "rules_version": rules.get("version"),
        "prompt_version": PROMPT_VERSION,
        "thresholds": thresholds_for(rules),
        "description_thresholds": thresholds_for(rules, "description"),
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
