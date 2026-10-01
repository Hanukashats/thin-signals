"""The reader names the scale of a card that is already in the list.

It does not admit, reject or change a weight. A loud title is not a wide shift:
the same rubric as the checklist says null when the text does not state the scale.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import httpx

from ts.llm import CACHE_POLICY_VERSION, cache_attestation, cached_response_is_current
from ts.sources.connectors import _openalex_abstract

CACHE = Path(os.environ.get("TS_CACHE_ROOT", "data")) / "scopes"
SYSTEM = (
    "Ты читаешь уже отобранную находку и называешь только масштаб сдвига. "
    "Допуск, балл и список ты не решаешь. "
    "2 — текст прямо говорит, что меняется общий механизм или физическое ограничение, "
    "от которого зависят несколько несвязанных производственных цепочек. "
    "1 — текст прямо говорит об изменении одного этапа или одной цепочки. "
    "null — текст масштаб не утверждает. Не повышай масштаб из громкого заголовка. "
    "Смысл один на любом языке. why — одно предложение по-русски."
)
SCHEMA = {
    "title": "shift_scope",
    "type": "object",
    "additionalProperties": False,
    "required": ["scope", "why"],
    "properties": {
        "scope": {"anyOf": [{"type": "integer", "enum": [1, 2]}, {"type": "null"}]},
        "why": {"type": "string"},
    },
}


def _doi(card: dict) -> str:
    for source in card.get("sources") or []:
        url = str(source.get("url") or "")
        found = re.search(r"10\.\d{4,9}/[^\s?#]+", url)
        if found:
            return found.group(0).rstrip(").,")
    return ""


def _snippet(card: dict) -> str:
    parts = []
    for source in card.get("sources") or []:
        text = str(source.get("snippet") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)[:1500]


def _openalex_by_doi(doi: str) -> str:
    try:
        response = httpx.get(
            f"https://api.openalex.org/works/https://doi.org/{doi}",
            timeout=20,
            headers={"User-Agent": "thin-signals/0.1 (research scan)"},
        )
        if response.status_code != 200:
            return ""
        return _openalex_abstract(response.json())
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return ""


def _epmc_abstract(source: str, record_id: str) -> str:
    """Search results omit the abstract unless the record is requested in full."""
    try:
        response = httpx.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": f"EXT_ID:{record_id} AND SRC:{source}",
                "resultType": "core",
                "format": "json",
                "pageSize": 1,
            },
            timeout=20,
            headers={"User-Agent": "thin-signals/0.1 (research scan)"},
        )
        if response.status_code != 200:
            return ""
        rows = ((response.json() or {}).get("resultList") or {}).get("result") or []
        if not rows:
            return ""
        return str(rows[0].get("abstractText") or "").strip()
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return ""


def _cordis_text(project_id: str) -> str:
    try:
        response = httpx.get(
            f"https://cordis.europa.eu/project/id/{project_id}?format=json",
            timeout=20,
            headers={"User-Agent": "thin-signals/0.1 (research scan)", "Accept": "application/json"},
        )
        if response.status_code != 200:
            return ""
        body = response.json() or {}
        return str(body.get("objective") or body.get("teaser") or "").strip()
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return ""


def _arxiv_summary(arxiv_id: str) -> str:
    try:
        response = httpx.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id},
            timeout=20,
            headers={"User-Agent": "thin-signals/0.1 (research scan)"},
        )
        if response.status_code != 200:
            return ""
        root = ET.fromstring(response.text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        summary = root.find(".//a:summary", ns)
        return str(summary.text or "").strip() if summary is not None else ""
    except (httpx.HTTPError, ET.ParseError, ValueError, TypeError):
        return ""


def _work_doi(doi: str) -> str:
    """A supplementary file is not a second work. /mm3 is the attachment of the paper."""
    return re.sub(r"/mm\d+$", "", doi, flags=re.IGNORECASE)


def _crossref_abstract(doi: str) -> str:
    from ts.sources.connectors import _strip

    try:
        response = httpx.get(
            f"https://api.crossref.org/works/{quote(doi, safe='')}",
            timeout=20,
            headers={"User-Agent": "thin-signals/0.1 (research scan)"},
        )
        if response.status_code != 200:
            return ""
        raw = str(((response.json() or {}).get("message") or {}).get("abstract") or "")
        return _strip(raw)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return ""


def _record_text(source: dict) -> str:
    url = str(source.get("url") or "")
    doi = str(source.get("doi") or "").strip() or _doi({"sources": [source]})
    arxiv = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", url, re.IGNORECASE)
    if arxiv:
        text = _arxiv_summary(arxiv.group(1))
        if text:
            return text
    article = re.search(r"europepmc\.org/article/([^/]+)/([^/?#]+)", url, re.IGNORECASE)
    if article:
        text = _epmc_abstract(article.group(1), article.group(2))
        if text:
            return text
    project = re.search(r"cordis\.europa\.eu/project/id/(\d+)", url, re.IGNORECASE)
    if project:
        text = _cordis_text(project.group(1))
        if text:
            return text
    if not doi:
        nature = re.search(r"nature\.com/articles/(s\d[^/?#]+)", url, re.IGNORECASE)
        if nature:
            doi = "10.1038/" + nature.group(1)
    if doi:
        doi = _work_doi(doi)
        text = _openalex_by_doi(doi)
        if text:
            return text
        return _crossref_abstract(doi)
    return ""


def fetch_abstract(card: dict) -> str:
    """Official-record text when the stored card kept no snippet.

    A title is not a fragment. A closed publisher record with no abstract stays empty.
    """
    for source in card.get("sources") or []:
        if not isinstance(source, dict):
            continue
        text = _record_text(source)
        if text:
            return text[:1500]
    return ""


def _scope_value(raw) -> int | None:
    if raw in (1, 2):
        return int(raw)
    return None


def make_reader(settings):
    from ts.llm import OpenRouterClient

    client = OpenRouterClient(settings)
    model = settings.llm_judge
    CACHE.mkdir(parents=True, exist_ok=True)

    def reader(card: dict) -> tuple[int | None, str, str | None]:
        fragment = _snippet(card) or fetch_abstract(card)
        text = f"Заголовок: {card.get('technology') or ''}\nФрагмент: {fragment or 'фрагмента нет, только заголовок'}"
        key = hashlib.sha256(
            f"{CACHE_POLICY_VERSION}|scope-v1|{model}|{SYSTEM}|{text}".encode()
        ).hexdigest()
        path = CACHE / f"{key}.json"
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                saved = None
            if isinstance(saved, dict) and cached_response_is_current(client, saved.get("meta"), model):
                meta = saved["meta"]
                return _scope_value(saved.get("scope")), str(saved.get("why") or ""), meta.get("model_id")
        response = client.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
            model,
            json_schema=SCHEMA,
            max_tokens=400,
            temperature=0.0,
            reasoning=True,
        )
        out = response.json()
        scope = _scope_value(out.get("scope"))
        why = str(out.get("why") or "").strip()[:400]
        path.write_text(
            json.dumps(
                {"scope": scope, "why": why, "meta": cache_attestation(response)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return scope, why, response.model_id

    return reader


def apply_reader(cards: list[dict], reader) -> list[dict]:
    """Same cards, with scope filled where the reader could read the text."""
    model_id = None
    annotated = []
    for card in cards:
        row = dict(card)
        try:
            scope, why, used = reader(row)
        except Exception:  # noqa: BLE001 — optional reader failure must not reorder/drop a card
            scope, why, used = None, "", None
        row["scope"] = _scope_value(scope)
        if why:
            row["scope_why"] = str(why).strip()[:400]
        if used:
            model_id = used
        annotated.append(row)
    if model_id:
        for row in annotated:
            row.setdefault("scope_model", model_id)
    return annotated


def annotate_scopes(cards: list[dict], settings) -> list[dict]:
    return apply_reader(cards, make_reader(settings))
