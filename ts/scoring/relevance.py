"""Does this find touch the bank's market, its clients, or a production chain.

This is not an admission gate and not a forecast of prices, credit losses or stocks.
A scientific find with no such words stays in the review.
"""
from __future__ import annotations

import re

_FAMILIES = (
    ("финансовый рынок", re.compile(
        r"банк|кредит|плат[её]ж|страхов|бирж|клиринг|финтех|ликвидн|"
        r"payment|credit|insurance|settlement|clearing|trading",
        re.IGNORECASE,
    )),
    ("клиентская отрасль", re.compile(
        r"ритейл|энергетик|нефт|металлург|агро|логистик|телеком|за[её]мщик|"
        r"retail|energy|oil|steel|telecom",
        re.IGNORECASE,
    )),
    ("цепочка поставок или производство", re.compile(
        r"поставщик|цепочк|производств|завод|сырь|компонент|посредник|"
        r"дистриб|прямые продажи|прямая продажа|"
        r"supplier|supply chain|manufactur|foundry|middleman|intermediary|direct[- ]sale",
        re.IGNORECASE,
    )),
)


def chain_link(text: str) -> dict:
    found = [name for name, pattern in _FAMILIES if pattern.search(text or "")]
    score = round(len(found) / len(_FAMILIES), 4)
    if not found:
        sentence = (
            "Связь с финансовым рынком, клиентской отраслью или цепочкой поставок "
            "в тексте находки не видна. Это не отказ: научная находка остаётся в разборе."
        )
    else:
        sentence = (
            "В тексте видно касание: " + ", ".join(found) + ". "
            "Это не прогноз, что рынок, кредит или акция сдвинутся."
        )
    return {"score": score, "families": found, "sentence": sentence}
