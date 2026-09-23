"""LLM feature extraction: candidate text -> FeatureVector (statuses per P01..P18, counters M01..M06).

The LLM does not score. It fills a fixed checklist with a status and a one-line rationale per item;
the scorer (deterministic) turns that into label/confidence. Two modes:
- description: only technology/domain/companies text (eval-v1, TZ dataset). Statuses are capped at
  `supported` by the scorer — nothing is "verified" without a source fragment.
- ledger (W3): the prompt also receives numbered fragments; `verified` requires a fragment reference.
Results are cached by sha256(prompt_version|model|text) under data/extractions/ so eval reruns are free.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ts.llm import LLMResponse, OpenRouterClient
from ts.scoring.scorer import COUNTER_IDS, PATTERN_IDS, FeatureVector, load_rules

PROMPT_VERSION = "extract-v1"
CACHE_DIR = Path("data/extractions")

_STATUS = {"type": "string", "enum": ["verified", "supported", "unknown", "absent"]}
_ITEM = {"type": "object", "additionalProperties": False, "required": ["code", "status", "why"],
         "properties": {"code": {"type": "string"}, "status": _STATUS, "why": {"type": "string"}}}
_COUNTER = {"type": "object", "additionalProperties": False, "required": ["code", "fired", "why"],
            "properties": {"code": {"type": "string"}, "fired": {"type": "boolean"}, "why": {"type": "string"}}}

SCHEMA = {
    "title": "feature_extraction",
    "type": "object", "additionalProperties": False,
    "required": ["primary_pattern", "secondary_patterns", "features", "counters", "transition",
                 "distinct_actors", "distinct_events", "one_line_ru"],
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
    },
}


def _system(rules: dict, mode: str) -> str:
    pats = "\n".join(f"- {k}: {v}" for k, v in rules["patterns"].items())
    ctrs = "\n".join(f"- {k}: {v}" for k, v in rules["counters"].items())
    cap = ("Источников-документов нет: максимальный статус — supported (известно из открытых фактов), "
           "verified ставить НЕЛЬЗЯ." if mode == "description"
           else "verified — только если утверждение прямо подтверждено приведённым фрагментом; укажи его номер в why.")
    return f"""Ты аналитик технологических сигналов. Заполни чек-лист признаков для кандидата. Ты НЕ выносишь итоговый вердикт и не считаешь баллы — это делает детерминированная модель.

Признаки зарождения (ровно 18, в порядке P01..P18):
{pats}

Контр-признаки зрелости/шума (ровно 6, M01..M06):
{ctrs}

Статусы признака: verified | supported | unknown | absent. absent — есть контрсвидетельство (например, «раунд» на деле valuation; анонс/roadmap выдан за внедрение; одна новость в 10 медиа = одно событие; контракт ≠ работающий объект; угроза ≠ решение; новизна применения ≠ новизна всей области). {cap}

primary_pattern — механизм, который лучше всего объясняет, почему это может быть ранний сигнал. transition — есть ли подтверждённое изменение стадии/механизма (исследование → пилот, пилот → контракт, старый метод → новая предпосылка). distinct_actors — число независимых организаций, действующих в этом направлении по известным тебе фактам; distinct_events — число независимых событий (раунды, пилоты, релизы, регуляторные акты), не пересказов. one_line_ru — одна строка на русском: что это и почему сигнал/не сигнал. Отвечай строго JSON по схеме, why — коротко, на русском, с датами/суммами, если знаешь."""


def candidate_text(row: dict) -> str:
    parts = [f"Технология: {row.get('technology', '').strip()}"]
    if row.get("domain"):
        parts.append(f"Область: {row['domain']}")
    if row.get("companies"):
        parts.append(f"Компании/акторы: {row['companies']}")
    if row.get("fragments"):
        parts.append("Фрагменты источников:")
        parts += [f"[{i + 1}] {f}" for i, f in enumerate(row["fragments"])]
    return "\n".join(parts)


def cache_key(text: str, model: str, mode: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}|{mode}|{model}|{text}".encode()).hexdigest()


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
    return FeatureVector(
        primary_pattern=out["primary_pattern"],
        secondary_patterns=[p for p in out["secondary_patterns"] if p != out["primary_pattern"]],
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
        key = cache_key(text, self.model, self.mode)
        path = self.cache_dir / f"{key}.json"
        if use_cache and path.exists():
            d = json.loads(path.read_text())
            return d["output"], {**d["meta"], "cached": True}
        resp: LLMResponse = self.client.chat(
            [{"role": "system", "content": _system(self.rules, self.mode)}, {"role": "user", "content": text}],
            self.model, json_schema=SCHEMA, max_tokens=3000, temperature=0.0,
        )
        out = resp.json()
        meta = {"model_id": resp.model_id, "provider": resp.provider, "usage": resp.usage,
                "latency_s": resp.latency_s, "prompt_version": PROMPT_VERSION, "mode": self.mode, "cached": False}
        path.write_text(json.dumps({"input": text, "output": out, "meta": meta}, ensure_ascii=False, indent=1))
        return out, meta
