"""LLM feature extraction: candidate text -> FeatureVector (statuses per P01..P18, counters M01..M06).

The LLM does not score. It fills a fixed checklist with a status and a one-line rationale per item;
the scorer (deterministic) turns that into label/confidence. Two modes:
- description: only technology/domain/companies text (eval-v1, TZ dataset). Statuses are capped at
  `supported` by the scorer — nothing is "verified" without a source fragment.
- ledger (W3): the prompt also receives numbered fragments; `verified` requires a fragment reference.
Results are cached by sha256(prompt_version|mode|model|system|text) under data/extractions/.
A reworded prompt misses the old cache. Same prompt reruns stay free.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ts.llm import LLMResponse, OpenRouterClient
from ts.scoring.assign import ORDER, assign_primary
from ts.scoring.scorer import COUNTER_IDS, PATTERN_IDS, FeatureVector, load_rules

PROMPT_VERSION = "extract-v3"
CACHE_DIR = Path("data/extractions")
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "pattern_registry.json"

_STATUS = {"type": "string", "enum": ["verified", "supported", "unknown", "absent"]}
_ITEM = {"type": "object", "additionalProperties": False, "required": ["code", "status", "why"],
         "properties": {"code": {"type": "string"}, "status": _STATUS, "why": {"type": "string"}}}
_COUNTER = {"type": "object", "additionalProperties": False, "required": ["code", "fired", "why"],
            "properties": {"code": {"type": "string"}, "fired": {"type": "boolean"}, "why": {"type": "string"}}}

SCHEMA = {
    "title": "feature_extraction",
    "type": "object", "additionalProperties": False,
    "required": ["primary_pattern", "secondary_patterns", "features", "counters", "transition",
                 "distinct_actors", "distinct_events", "one_line_ru", "scope"],
    "properties": {
        "primary_pattern": {"type": "string", "enum": list(PATTERN_IDS)},
        "secondary_patterns": {"type": "array", "items": {"type": "string", "enum": list(PATTERN_IDS)}, "maxItems": 3},
        "features": {"type": "array", "items": _ITEM, "minItems": 18, "maxItems": 18},
        "counters": {"type": "array", "items": _COUNTER, "minItems": 6, "maxItems": 6},
        "transition": {"type": "object", "additionalProperties": False, "required": ["status", "why"],
                       "properties": {"status": _STATUS, "why": {"type": "string"}}},
        "distinct_actors": {"type": "integer", "minimum": 0, "maximum": 50},
        "distinct_events": {"type": "integer", "minimum": 0, "maximum": 50},
        "one_line_ru": {"type": "string"},
        "scope": {"anyOf": [{"type": "integer", "enum": [1, 2]}, {"type": "null"}]},
    },
}


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return json.loads(path.read_text())


def _pattern_lines(registry: dict, rules: dict) -> str:
    by_id = {p["id"]: p for p in registry["patterns"]}
    lines = []
    for code, name in rules["patterns"].items():
        row = by_id.get(code, {})
        title = row.get("name") or name
        lines.append(f"- {code}: {title}")
        if row.get("supported_when"):
            lines.append(f"  узнал (supported): {row['supported_when']}")
        if row.get("verified_when"):
            lines.append(f"  подтвердил (verified): {row['verified_when']}")
        if row.get("absent_when"):
            lines.append(f"  не считается (absent): {row['absent_when']}")
        if row.get("primary_rule"):
            lines.append(f"  главный: {row['primary_rule']}")
    return "\n".join(lines)


def _assignment_lines() -> str:
    order = " → ".join(ORDER)
    return (
        "Признак один и тот же на любом языке источника. Смысл, не слово из списка: "
        "русская, английская, китайская и любая другая формулировка читаются одинаково. "
        "Главный признак — то, что ново, а не то, кто платит. "
        f"Если узнано несколько, приоритет такой: {order}. "
        "P06 не может быть главным, если узнан P01 или P02. "
        "P04 не может быть главным, если узнан P01, P02 или P07. "
        "P18 не может быть главным, если узнан P01. "
        "unknown по P04, P14, P15 и P18 — не контрдоказательство и не шум: "
        "научная работа без покупателя и без раунда остаётся научным признаком. "
        "Масштаб сдвига — отдельное поле scope, не один из P01–P18 и не допуск. "
        "2 — текст прямо говорит, что меняется общий механизм или физическое ограничение, "
        "от которого зависят несколько несвязанных производственных цепочек. "
        "1 — текст прямо говорит об изменении одного этапа или одной цепочки. "
        "null — текст масштаб не утверждает. Не повышай масштаб из громкого заголовка "
        "и не из слова на одном языке: тот же смысл на любом языке читается одинаково. "
        "M05 ставь только когда упоминаний много и нет ни одного первичного источника "
        "(статья, патент, документ регулятора). Первичная работа без продукта — "
        "исследовательская стадия, не хайп."
    )


def _system(rules: dict, mode: str, registry: dict | None = None) -> str:
    registry = registry if registry is not None else load_registry()
    pats = _pattern_lines(registry, rules)
    ctrs = "\n".join(f"- {k}: {v}" for k, v in rules["counters"].items())
    cap = ("Источников-документов нет: максимальный статус — supported (известно из открытых фактов), "
           "verified ставить НЕЛЬЗЯ." if mode == "description"
           else "verified — только если утверждение прямо подтверждено приведённым фрагментом; укажи его номер в why.")
    return f"""Ты аналитик технологических сигналов. Заполни чек-лист признаков для кандидата. Ты НЕ выносишь итоговый вердикт и не считаешь баллы — это делает детерминированная модель.

Признаки зарождения (ровно 18, в порядке P01..P18). «Узнал» — supported. «Подтвердил» — verified. «Не считается» — absent:
{pats}

Контр-признаки зрелости/шума (ровно 6, M01..M06):
{ctrs}

Статусы признака: verified | supported | unknown | absent. absent — есть контрсвидетельство из строки «не считается» (например, «раунд» на деле valuation; анонс/roadmap выдан за внедрение; одна новость в 10 медиа = одно событие; контракт ≠ работающий объект; угроза ≠ решение; новизна применения ≠ новизна всей области). {cap}

{_assignment_lines()}

primary_pattern — механизм по правилу выше. Код всё равно перепроверит приоритет, но заполни статусы честно. transition — есть ли подтверждённое изменение стадии/механизма (исследование → пилот, пилот → контракт, старый метод → новая предпосылка). distinct_actors — число независимых организаций, действующих в этом направлении по известным тебе фактам; distinct_events — число независимых событий (раунды, пилоты, релизы, регуляторные акты), не пересказов. one_line_ru — одна строка на русском: что это и почему сигнал/не сигнал. Отвечай строго JSON по схеме, why — коротко, на русском, с датами/суммами, если знаешь."""


def candidate_text(row: dict) -> str:
    parts = [f"Технология: {row.get('technology', '').strip()}"]
    asked = str(row.get("query") or "").strip()
    if asked:
        parts.append(f"Запрос оператора: «{asked}».")
        parts.append(
            "Если этот текст описывает другой механизм или объект, чем запрос "
            "(не то же самое другими словами, сокращением, на другом языке или составным словом), "
            "начни one_line_ru со слова ДРУГОЙ_МЕХАНИЗМ: ."
        )
    if row.get("domain"):
        parts.append(f"Область: {row['domain']}")
    if row.get("companies"):
        parts.append(f"Компании/акторы: {row['companies']}")
    if row.get("fragments"):
        parts.append("Фрагменты источников:")
        parts += [f"[{i + 1}] {f}" for i, f in enumerate(row["fragments"])]
    return "\n".join(parts)


def cache_key(text: str, model: str, mode: str, system: str) -> str:
    """The rules text is part of the key, so a reworded prompt cannot reuse an old answer."""
    return hashlib.sha256(f"{PROMPT_VERSION}|{mode}|{model}|{system}|{text}".encode()).hexdigest()


def to_feature_vector(out: dict, mode: str, companies: str | None = None) -> FeatureVector:
    features = {it["code"]: it["status"] for it in out["features"] if it["code"] in PATTERN_IDS}
    counters = {c["code"]: bool(c["fired"]) for c in out["counters"] if c["code"] in COUNTER_IDS}
    evidence = {it["code"]: it["why"] for it in out["features"]}
    evidence.update({c["code"]: c["why"] for c in out["counters"] if c["fired"]})
    evidence["TR"] = out["transition"]["why"]
    # independence proxies in description mode: actors from the companies field (deterministic) or LLM count
    actors_from_text = len([x for x in re.split(r"[,;/]| и ", companies or "") if x.strip()]) if companies else 0
    origins = max(actors_from_text, out.get("distinct_actors", 0)) if mode == "description" else out.get("distinct_actors", 0)
    events = max(out.get("distinct_events", 0), origins if mode == "description" else 0)
    primary, secondary = assign_primary(features, out["primary_pattern"], out.get("secondary_patterns") or [])
    return FeatureVector(
        primary_pattern=primary,
        secondary_patterns=secondary,
        features=features, counters=counters,
        evidence_events=events, independent_origins=origins,
        transition=out["transition"]["status"], evidence=evidence, mode=mode,
    )


class Extractor:
    def __init__(self, client: OpenRouterClient, model: str | None = None, mode: str = "description",
                 rules: dict | None = None, cache_dir: Path = CACHE_DIR):
        self.client = client
        self.model = model or client.s.llm_primary
        self.mode = mode
        self.rules = rules or load_rules()
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract(self, row: dict, use_cache: bool = True) -> tuple[dict, dict]:
        """Return (llm_output, meta). meta has model_id/provider/usage/latency/cached."""
        text = candidate_text(row)
        system = _system(self.rules, self.mode)
        key = cache_key(text, self.model, self.mode, system)
        path = self.cache_dir / f"{key}.json"
        if use_cache and path.exists():
            d = json.loads(path.read_text())
            return d["output"], {**d["meta"], "cached": True}
        resp: LLMResponse = self.client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": text}],
            self.model, json_schema=SCHEMA, max_tokens=3000, temperature=0.0,
            reasoning=self.model.startswith("openai/"),
        )
        out = resp.json()
        meta = {"model_id": resp.model_id, "provider": resp.provider, "usage": resp.usage,
                "latency_s": resp.latency_s, "prompt_version": PROMPT_VERSION, "mode": self.mode, "cached": False}
        path.write_text(json.dumps({"input": text, "output": out, "meta": meta}, ensure_ascii=False, indent=1))
        return out, meta
