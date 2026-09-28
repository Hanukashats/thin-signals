"""Order cards that already passed the gates. This module does not admit or reject."""
from __future__ import annotations

ROC3 = (11 / 18, 5 / 18, 1 / 9)
_STATUS = {"verified": 1.0, "supported": 0.5, "unknown": 0.0, "absent": 0.0}


def evidence_strength(predictors) -> float:
    """Three strongest confirmed signs, heaviest first. The model's 'primary' label is ignored."""
    values: list[float] = []
    for row in predictors or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "")
        if not code.startswith("P"):
            continue
        raw = row.get("value")
        if isinstance(raw, str):
            values.append(_STATUS.get(raw, 0.0))
        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
            values.append(max(0.0, min(1.0, float(raw))))
        else:
            values.append(0.0)
    values.sort(reverse=True)
    return sum(weight * value for weight, value in zip(ROC3, values))


def _published_rank(card: dict) -> int:
    """YYYYMMDD, or 0 when the source did not give a date. Newer sorts first."""
    best = 0
    for source in card.get("sources") or []:
        if not isinstance(source, dict):
            continue
        digits = "".join(ch for ch in str(source.get("date") or "") if ch.isdigit())[:8]
        if len(digits) >= 4:
            best = max(best, int(digits.ljust(8, "0")))
    return best


def scope_rank(card: dict) -> int:
    """2 wide, 1 local, 0 when the text was not read. Never invent a wide shift."""
    raw = card.get("scope")
    if raw in (1, 2):
        return int(raw)
    return 0


def sort_admitted(cards: list[dict]) -> list[dict]:
    """Same cards, stable order. Topic stays ahead of scale. Scale stays ahead of date."""
    return sorted(
        cards,
        key=lambda card: (
            -evidence_strength(card.get("predictors")),
            -int(card.get("subject_hits") or 0),
            -scope_rank(card),
            -_published_rank(card),
            -float((card.get("chain_link") or {}).get("score") or 0),
            str(card.get("technology") or card.get("id") or ""),
        ),
    )
