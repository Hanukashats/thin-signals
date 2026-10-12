"""Where a find might be used, as a hypothesis after the list is already chosen.

This does not admit, reject, score or sort. Scope stays what the text states.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from ts.llm import CACHE_POLICY_VERSION, cache_attestation, cached_response_is_current
from ts.scale import _snippet, fetch_abstract

CACHE = Path(os.environ.get("TS_CACHE_ROOT", "data")) / "reach"
SYSTEM = (
    "Список уже собран. Ты не отбираешь и не сортируешь. "
    "Пиши для человека без этой специальности. Короткие предложения, без формул в ответе. "
    "plain — что это такое обычными словами, одно-два предложения. "
    "sphere — где это может пригодиться. "
    "moves — на что в работе или в цепочке это может повлиять. "
    "affects — что ещё рядом может задеть. "
    "plus — какой практический плюс, если механизм верен. "
    "minus — какой практический минус или ограничение. "
    "terms — если в заголовке есть термин или формула, объясни её так: «слово — обычными словами». "
    "Иначе оставь terms пустым. "
    "if_true — что изменится в деле, если механизм подтвердится. Это предположение, не расчёт. "
    "open — чего текст не закрывает. "
    "Каждое поле — по-русски. Если без выдумки не сказать, оставь пустую строку. "
    "Не пиши проценты, деньги, годы и сроки. Не ставь балл и не говори, что статья это доказала."
)
SCHEMA = {
    "title": "reach_hypothesis",
    "type": "object",
    "additionalProperties": False,
    "required": ["plain", "sphere", "moves", "affects", "plus", "minus", "terms", "if_true", "open"],
    "properties": {
        name: {"type": "string"}
        for name in ("plain", "sphere", "moves", "affects", "plus", "minus", "terms", "if_true", "open")
    },
}
_FIELDS = ("plain", "sphere", "moves", "affects", "plus", "minus", "terms", "if_true", "open")
_LONG = {"plain", "plus", "minus", "terms"}
_BANNED = re.compile(r"%|\$|€|доллар|руб|млрд|млн|\b20\d{2}\b|\b19\d{2}\b", re.IGNORECASE)


def _line(text: str, *, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned or _BANNED.search(cleaned):
        return ""
    return cleaned[:limit]


def _pack(raw: dict) -> dict | None:
    packed = {name: _line(raw.get(name), limit=420 if name in _LONG else 220) for name in _FIELDS}
    if not any(packed.values()):
        return None
    return packed


def _text(card: dict) -> str:
    fragment = _snippet(card) or fetch_abstract(card)
    scope = card.get("scope")
    return (
        f"Заголовок: {card.get('technology') or ''}\n"
        f"Масштаб по тексту: {scope if scope in (1, 2) else 'не назван'}\n"
        f"Фрагмент: {fragment or 'фрагмента нет, только заголовок'}"
    )


def make_reader(settings):
    from ts.llm import OpenRouterClient

    client = OpenRouterClient(settings)
    model = settings.llm_judge
    CACHE.mkdir(parents=True, exist_ok=True)

    def reader(card: dict) -> tuple[dict | None, str | None]:
        text = _text(card)
        key = hashlib.sha256(
            f"{CACHE_POLICY_VERSION}|reach-v3|{model}|{SYSTEM}|{text}".encode()
        ).hexdigest()
        path = CACHE / f"{key}.json"
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                saved = None
            if isinstance(saved, dict) and cached_response_is_current(client, saved.get("meta"), model):
                return saved.get("reach"), saved["meta"].get("model_id")
        response = client.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
            model,
            json_schema=SCHEMA,
            max_tokens=900,
            temperature=0.0,
            reasoning=True,
        )
        out = response.json()
        reach = _pack(out)
        path.write_text(
            json.dumps(
                {"reach": reach, "meta": cache_attestation(response)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return reach, response.model_id

    return reader


def apply_reach(cards: list[dict], reader) -> list[dict]:
    """Same cards, same order. A failed reader leaves reach empty."""
    model_id = None
    annotated = []
    for card in cards:
        row = dict(card)
        try:
            reach, used = reader(row)
        except Exception:  # noqa: BLE001 — optional reader failure must not reorder/drop a card
            reach, used = None, None
        if isinstance(reach, dict):
            row["reach"] = _pack(reach)
        else:
            row["reach"] = None
        if used:
            model_id = used
        annotated.append(row)
    if model_id:
        for row in annotated:
            row.setdefault("reach_model", model_id)
    return annotated


def annotate_reach(cards: list[dict], settings) -> list[dict]:
    if not cards:
        return []
    return apply_reach(cards, make_reader(settings))
