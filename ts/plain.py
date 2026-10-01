"""Plain words for the screen. Codes stay in parentheses. This file does not score."""
from __future__ import annotations

ACTIONS = {
    "RANK_ELIGIBLE": "можно ставить в официальный список",
    "WATCHLIST": "пока только наблюдать, в список рано",
    "WATCHLIST_SINGLETON": "находка одна, повторения нет, в список рано",
    "REFRAME_CHILD": "тема уже взрослая, искать надо более узкий новый кусок",
    "REJECT_OR_REFRAME": "есть опровержение, тему надо отбросить или сузить",
    "HOLD": "проверка не закончена, решение отложено",
    "VERIFY_COUNTEREVIDENCE": "есть слабое возражение, его надо проверить",
    "TARGETED_RESEARCH": "важный факт не разобран, нужен точечный поиск",
    "MATURITY_RESEARCH": "неясно, новая это тема или уже известная",
    "COUNTERSEARCH": "не искали, не опровергает ли это кто-то",
    "EXECUTE_BRANCH": "выбранные проверки не закрыты",
}

REASONS = {
    "unresolved_availability": "нет источника с датой, который можно открыть",
    "verified_fatal_claim": "есть проверенное опровержение",
    "weak_negative_not_terminal": "отрицание слабое, его ещё надо проверить",
    "critical_unknown": "важное утверждение не разобрано",
    "mature_parent": "тема уже зрелая, это не ранний сигнал",
    "maturity_unclear": "неясно, новая это тема или уже известная",
    "missing_falsification": "не проверяли, нет ли опровержения",
    "one_origin_result": "находка с одного источника, повторения нет",
    "insufficient_independence": "мало независимых подтверждений",
    "incomplete_relevant_checks": "выбранные проверки не закрыты",
    "no_verified_change": "не видно, что способ работы реально сменился",
    "evidence_gates_passed": "проверки допуска пройдены",
    "off_topic_for_query": "заголовок не держит формулировку запроса: мало её слов или одно слово заменено другим",
    "theme_quota": "место этой темы в общем списке уже занято, карточка остаётся в запасе",
    "checklist_counter": "читатель назвал признак зрелости или шума, карточка вышла из списка",
    "checklist_below_watchlist": "сумма признаков ниже порога наблюдения",
    "no_source_text": "у этой находки нет текста источника, она не читалась и оценки не имеет",
    "no_source_text_replaced": "у этой находки нет текста источника, на её место взята следующая карточка той же темы",
    "reader_failed": "читатель не ответил, карточка не оценена и в список не встала",
    "reader_failed_replaced": "читатель не ответил, на её место взята следующая карточка той же темы",
    "query_term_missing": "в заголовке нет длинного слова запроса",
    "beyond_top_n": "находка есть, в первые пятнадцать по предварительному порядку она не вошла",
    "other_mechanism_after_read": "прочитанный текст описывает другой механизм, не предмет запроса",
}

OLD_TECH_HOLDS = {
    "commercial_diligence": "коммерческая занятость не проверена",
    "rights_diligence": "доступ к правам не подтверждён",
    "source_integrity_screen": "проверка источников на отзыв не закрыта",
    "incomplete_scores": "часть осей ещё не оценена",
    "system_comparison": "сравнение с действующей системой не подтверждено",
    "test_protocol": "решающий эксперимент не согласован",
    "bottleneck_not_yet_removed": "старый барьер ещё не снят",
    "historical_fit": "историческое соответствие ещё не подтверждено",
}

OLD_TECH_DECISIONS = {
    "priority_diligence": "приоритет выяснения неизвестного",
    "investigate": "исследовать",
    "watch": "наблюдать",
}

CODES = {
    "P01": "появился новый механизм или явление",
    "P02": "преодолён порог эффективности",
    "P03": "есть переход к реальному применению",
    "P04": "ранние деньги сходятся на одной теме",
    "P05": "появляется отдельный продукт, а не только исследование",
    "P06": "зрелую технологию перенесли в новую среду и сняли её ограничение",
    "P07": "узкое место цепочки снимает другой компонент или маршрут",
    "P08": "появляются стандарты и совместимость",
    "P09": "новая угроза или новое правило подталкивает тему",
    "P10": "вычисления или данные переносят на другой край",
    "P11": "независимые группы приходят к похожему",
    "P12": "вокруг темы растёт круг разработчиков",
    "P13": "предмет двигается быстрее, чем о нём говорят",
    "P14": "появился новый способ получать пользу",
    "P15": "кто-то уже обязался это внедрять",
    "P16": "соединили то, что раньше шло отдельно",
    "P17": "возвращается направление, которое раньше не вышло",
    "P18": "есть грант или открытая исследовательская программа",
    "M01": "уже есть явные лидеры рынка",
    "M02": "стандарт или обязательная сертификация уже приняты",
    "M03": "это уже массово внедряют",
    "M04": "нашлись только пересказы, а не первоисточник",
    "M05": "много шумихи и нет первичного источника",
    "M06": "старая категория без нового способа",
    "IND": "насколько источники независимы друг от друга",
    "TR": "видна ли смена способа работы",
    "insufficient_evidence": "фактов мало, чтобы назвать это ранним сигналом",
    "below_tau": "число ниже порога, с которого тему хотя бы наблюдают",
    "singleton": "событие одно, второго подтверждения нет",
}

_STATUS = {
    "unknown": "этот признак не разобран",
    "absent": "этого признака нет",
}

TRUST = {
    "primary": "первоисточник",
    "professional": "профессиональное издание",
    "indicator": "пересказ или намёк",
}

RUN = {
    "succeeded": "поиск дошёл до конца",
    "failed": "поиск остановился с ошибкой",
}

TYPES = {
    "paper": "статья",
    "patent": "патент",
    "registry": "реестр",
    "repository": "код",
    "web": "страница в сети",
    "industry_media": "отраслевая новость",
    "analyst_report": "обзор аналитиков",
    "official_site": "сайт разработчика или ведомства",
}

LANG = {
    "ru": "русский",
    "en": "английский",
    "de": "немецкий",
    "fr": "французский",
    "zh": "китайский",
    "ja": "японский",
    "ko": "корейский",
    "ar": "арабский",
    "he": "иврит",
    "und": "алфавит не называет язык",
}

VALUES = {
    "verified": "проверено",
    "supported": "есть опора в тексте",
    "unknown": "не разобрано",
    "refuted": "опровергнуто",
}


def reach_lines(reach) -> list[str]:
    if not isinstance(reach, dict):
        return []
    labels = (
        ("plain", "Что это"),
        ("sphere", "Где может пригодиться"),
        ("moves", "На что может повлиять"),
        ("affects", "Что ещё может задеть"),
        ("plus", "Плюс"),
        ("minus", "Минус"),
        ("terms", "Сложные слова"),
        ("if_true", "Если механизм сработает"),
        ("open", "Чего текст не закрывает"),
    )
    lines = []
    for key, label in labels:
        text = " ".join(str(reach.get(key) or "").split())
        if text:
            lines.append(f"{label}: {text}")
    return lines


def reach_sentence(reach) -> str:
    lines = reach_lines(reach)
    if not lines:
        return ""
    return "Гипотеза модели, в тексте не проверено. " + " ".join(lines)


def scope_sentence(scope) -> str:
    if scope == 2:
        return (
            "Масштаб сдвига широкий: по тексту меняется общий механизм "
            "для нескольких несвязанных цепочек. Более узкая находка из-за этого не выпадает."
        )
    if scope == 1:
        return "Масштаб сдвига местный: по тексту меняется один этап или одна цепочка."
    return ""


def paren(words: str, code) -> str:
    if code is None or str(code).strip() == "":
        return words
    return f"{words} ({code})"


def say(table: dict, code, fallback: str = "служебный код без расшифровки") -> str:
    if code is None or str(code).strip() == "":
        return fallback
    text = table.get(str(code))
    if text:
        return paren(text, code)
    return paren(fallback, code)


def decision_line(action, reason) -> str:
    parts = []
    if action:
        parts.append("Решение: " + say(ACTIONS, action))
    if reason:
        parts.append("Почему: " + say(REASONS, reason))
    return ". ".join(parts) + "." if parts else "Решение не пришло."


def code_words(code) -> str:
    text = "" if code is None else str(code)
    if text in CODES:
        return paren(CODES[text], text)
    if "_" in text:
        base, status = text.rsplit("_", 1)
        if base in CODES and status in _STATUS:
            return paren(f"{CODES[base]} — {_STATUS[status]}", text)
    return say(CODES, code)


def stopper_line(codes) -> str | None:
    if not codes:
        return None
    parts = [code_words(code) for code in codes]
    return "Стоппер: " + "; ".join(parts) + "."
