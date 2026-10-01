"""Nearest finds when the selected list is short. Does not fill those slots.

The percent is how many checks passed. It is not confidence and not a market forecast.
"""
from __future__ import annotations

from ts.plain import REASONS, TRUST, say, stopper_line

STAGES = (
    ("доступность источника", "unresolved_availability", "нет датированного доступного источника"),
    ("критичное опровержение", "verified_fatal_claim", "есть проверенное опровержение"),
    ("слабое отрицание", "weak_negative_not_terminal", "отрицание слабое, его ещё надо проверить"),
    ("критичные утверждения", "critical_unknown", "критичное утверждение не разобрано"),
    ("зрелость", "mature_parent", "тема уже зрелая, это не слабый сигнал"),
    ("ясность зрелости", "maturity_unclear", "неясно, новая это тема или уже известная"),
    ("контрпоиск", "missing_falsification", "контрпоиск не выполнен"),
    ("один источник", "one_origin_result", "находка с одного источника, повторения нет"),
    ("независимость", "insufficient_independence", "событий меньше трёх или независимых источников меньше двух"),
    ("ветки проверки", "incomplete_relevant_checks", "выбранные проверки не закрыты"),
    ("смена стадии", "no_verified_change", "нет подтверждённой смены стадии или механизма"),
)

TRUST_RANK = {"primary": 3, "professional": 2, "indicator": 1}
NEAREST_LIMIT = 15
NOTE = (
    "Это не отобранный список и не вероятность, что тема станет стартапом, "
    "вырастет спрос или двинется акция. Процент — доля пройденных проверок. "
    "Пустые места основного списка этим окном не заполняются."
)


def stuck_stage(payload: dict) -> dict:
    reason = payload.get("policy_reason") or ""
    if reason == "evidence_gates_passed":
        why = say(REASONS, reason)
        label = payload.get("signal_label")
        if label and label != "weak_signal":
            why += ". В список слабых сигналов пускает только ранний сигнал"
        stage = {"title": "все ступени допуска", "why": why, "passed": len(STAGES), "percent": 100}
    else:
        found = next((i for i, item in enumerate(STAGES) if item[1] == reason), None)
        if found is None:
            shown = reason or payload.get("policy_action") or "пусто"
            stage = {
                "title": "ступень не названа",
                "why": f"Причина остановки не из знакомого списка ({shown})",
                "passed": None,
                "percent": None,
            }
        else:
            title, code, _why = STAGES[found]
            stage = {
                "title": title,
                "why": say(REASONS, code),
                "passed": found,
                "percent": round(100 * found / len(STAGES)),
            }
    if payload.get("confidence") is None:
        codes = [str(code) for code in (payload.get("reason_codes") or [])]
        prefix = stopper_line(codes) or "Стоппер сработал"
        prefix += " Из-за этого процент уверенности не считается."
        stage["why"] = prefix + " " + stage["why"]
        if stage["title"] != "ступень не названа":
            stage["title"] = "Стоппер, затем " + stage["title"]
    return stage


def _checks(source: dict) -> list[tuple[bool, str]]:
    trust = source.get("trust") or "неизвестно"
    return [
        (bool(source.get("url")), "нет адреса"),
        (bool(source.get("date")), source.get("date_unknown_reason") or "дата не указана"),
        (trust in {"primary", "professional"}, f"доверие «{trust}» ниже профессионального"),
    ]


def _card_rows(payload: dict) -> list[dict]:
    rows = []
    for card in payload.get("exclusion_registry") or []:
        if not isinstance(card, dict) or not card.get("technology"):
            continue
        stage = stuck_stage({
            "policy_reason": card.get("policy_reason") or payload.get("policy_reason"),
            "policy_action": card.get("policy_action"),
            "signal_label": card.get("label"),
            "confidence": card.get("confidence"),
            "reason_codes": card.get("reason_codes") or [],
        })
        link = card.get("chain_link") or {}
        sources = [item for item in (card.get("sources") or []) if isinstance(item, dict)]
        trust = sources[0].get("trust") if sources else "не разбиралось по источникам"
        sentence = link.get("sentence")
        rows.append({
            "name": card["technology"],
            "approach_percent": stage["percent"],
            "trust": trust or "неизвестно",
            "stuck": stage["title"],
            "why": stage["why"],
            "gaps": [sentence] if sentence else [],
            "url": sources[0].get("url") if sources else None,
            "chain_score": float(link.get("score") or 0),
        })
    rows.sort(key=lambda row: (
        -row["chain_score"],
        -(row["approach_percent"] if isinstance(row["approach_percent"], int) else -1),
        -TRUST_RANK.get(row["trust"], 0),
        row["name"],
    ))
    return rows


def build_nearest(payload: dict, limit: int = NEAREST_LIMIT) -> dict:
    stage = stuck_stage(payload)
    rows = _card_rows(payload)
    if rows:
        found = len(rows)
        rows = rows[:limit]
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        official = len(payload.get("top") or [])
        return {
            "official_count": official,
            "shortfall": payload.get("shortfall"),
            "ladder_percent": stage["percent"],
            "stuck": stage["title"],
            "why": stage["why"],
            "found": found,
            "shown": len(rows),
            "rows": rows,
            "note": NOTE,
        }
    for source in payload.get("sources") or []:
        if not isinstance(source, dict):
            continue
        checks = _checks(source)
        passed = sum(1 for ok, _gap in checks if ok)
        rows.append({
            "name": source.get("name") or source.get("url") or "без названия",
            "approach_percent": round(100 * passed / len(checks)),
            "trust": source.get("trust") or "неизвестно",
            "stuck": stage["title"],
            "why": stage["why"],
            "gaps": [gap for ok, gap in checks if not ok],
            "url": source.get("url"),
        })
    if not rows:
        for card in payload.get("exclusion_registry") or []:
            if not isinstance(card, dict):
                continue
            rows.append({
                "name": card.get("technology") or payload.get("query") or "карточка",
                "approach_percent": stage["percent"],
                "trust": "не разбиралось по источникам",
                "stuck": stage["title"],
                "why": stage["why"],
                "gaps": ["поиск не принёс отдельных находок"],
                "url": None,
            })
    rows.sort(key=lambda row: (
        -(row["approach_percent"] if isinstance(row["approach_percent"], int) else -1),
        -TRUST_RANK.get(row["trust"], 0),
        row["name"],
    ))
    found = len(rows)
    rows = rows[:limit]
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    official = len(payload.get("top") or [])
    return {
        "official_count": official,
        "shortfall": payload.get("shortfall"),
        "ladder_percent": stage["percent"],
        "stuck": stage["title"],
        "why": stage["why"],
        "found": found,
        "shown": len(rows),
        "rows": rows,
        "note": NOTE,
    }


def nearest_lines(payload: dict) -> dict:
    board = build_nearest(payload)
    lines = []
    for row in board["rows"]:
        percent = "процент проверок не выведен" if row["approach_percent"] is None else f"{row['approach_percent']}% проверок"
        gap = "; ".join(row["gaps"]) if row["gaps"] else "своих дыр нет, держит общая остановка прогона"
        trust = say(TRUST, row["trust"]) if row["trust"] in TRUST else (row["trust"] or "не разобрано")
        lines.append(
            f"{row['rank']}. {row['name']} — {percent}, доверие: {trust}. "
            f"Где остановились: {row['stuck']}. Почему: {row['why']}. У находки: {gap}."
        )
    board["lines"] = lines
    return board
