"""Search connectors. `get` is injected so tests never touch the network.

Each parser understands one upstream shape. A connector that cannot parse raises
ConnectorError; the harness records the failure and continues with the others.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote

Get = Callable[[str], str]
Post = Callable[[str, dict], str]

ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}


def script_of(text: str) -> str:
    """Writing system, not a language and not a word list."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return ""
    checks = (
        ("cyr", lambda ch: "а" <= ch.lower() <= "я" or ch.lower() == "ё"),
        ("han", lambda ch: "\u4e00" <= ch <= "\u9fff"),
        ("hangul", lambda ch: "\uac00" <= ch <= "\ud7a3"),
        ("kana", lambda ch: "\u3040" <= ch <= "\u30ff"),
        ("arab", lambda ch: "\u0600" <= ch <= "\u06ff"),
        ("hebr", lambda ch: "\u0590" <= ch <= "\u05ff"),
        ("lat", lambda ch: "a" <= ch.lower() <= "z"),
    )
    best, share = "", 0.0
    for name, pred in checks:
        got = sum(1 for ch in letters if pred(ch)) / len(letters)
        if got > share:
            best, share = name, got
    return best if share > 0.3 else ""


_SCRIPT_LANG = {
    "cyr": "ru",
    "han": "zh",
    "hangul": "ko",
    "kana": "ja",
    "arab": "ar",
    "hebr": "he",
    "lat": "und",
}


class ConnectorError(RuntimeError):
    pass


@dataclass
class Hit:
    connector: str
    url: str
    title: str
    snippet: str
    source_type: str
    language: str = "und"
    published: str | None = None
    doi: str | None = None
    planned_for: str | None = None
    deployment: bool = False

    def __post_init__(self) -> None:
        self.language = _language(self.title + " " + self.snippet, self.language)
        self.planned_for, self.deployment = _roadmap(self.planned_for, self.deployment)


def _language(text: str, given: str) -> str:
    if given and given != "und":
        return given
    return _SCRIPT_LANG.get(script_of(text), "und")


def _roadmap(planned: str | None, deployment: bool) -> tuple[str | None, bool]:
    """A phrase in one language is not a plan and not an operation. The reader applies that concept."""
    if planned:
        return planned, False
    return None, deployment


def _get_json(get: Get, url: str) -> dict:
    try:
        return json.loads(get(url))
    except (json.JSONDecodeError, OSError, TimeoutError) as e:
        raise ConnectorError(str(e)) from e


class SearxConnector:
    name = "searxng"

    def __init__(self, base_url: str, get: Get):
        self.base_url = base_url.rstrip("/")
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"{self.base_url}/search?q={quote(query)}&format=json"
        data = _get_json(self.get, url)
        hits = []
        for row in (data.get("results") or [])[:limit]:
            if not row.get("url"):
                continue
            hits.append(Hit(
                connector=self.name, url=row["url"], title=row.get("title") or row["url"],
                snippet=(row.get("content") or "")[:500], source_type="web",
                published=_date(row.get("publishedDate")),
            ))
        return hits


class ArxivConnector:
    name = "arxiv"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://export.arxiv.org/api/query?search_query=all:{quote(query)}&max_results={limit}"
        try:
            root = ET.fromstring(self.get(url))
        except ET.ParseError as e:
            raise ConnectorError(str(e)) from e
        hits = []
        for entry in root.findall("a:entry", ARXIV_NS):
            title = _text(entry, "a:title")
            link = entry.find("a:id", ARXIV_NS)
            if link is None or not link.text:
                continue
            doi = entry.find("a:link[@title='doi']", ARXIV_NS)
            hits.append(Hit(
                connector=self.name, url=link.text.strip(), title=title,
                snippet=_text(entry, "a:summary")[:500], source_type="paper",
                published=_date(_text(entry, "a:published")),
                doi=(doi.attrib.get("href", "").rsplit("doi.org/", 1)[-1] or None) if doi is not None else None,
            ))
        return hits


class OpenAlexConnector:
    name = "openalex"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://api.openalex.org/works?search={quote(query)}&per-page={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in data.get("results") or []:
            landing = row.get("doi") or row.get("id")
            if not landing:
                continue
            hits.append(Hit(
                connector=self.name, url=landing, title=row.get("display_name") or landing,
                snippet=_openalex_abstract(row)[:500], source_type="paper",
                published=row.get("publication_date"),
                doi=(row.get("doi") or "").removeprefix("https://doi.org/") or None,
            ))
        return hits


class CrossrefConnector:
    name = "crossref"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://api.crossref.org/works?query={quote(query)}&rows={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in (data.get("message") or {}).get("items") or []:
            link = row.get("URL")
            if not link:
                continue
            title = " ".join(row.get("title") or []) or link
            hits.append(Hit(
                connector=self.name, url=link, title=title,
                snippet=_strip(row.get("abstract") or "")[:500], source_type="paper",
                published=_crossref_date(row), doi=row.get("DOI"),
            ))
        return hits


class GithubConnector:
    name = "github"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://api.github.com/search/repositories?q={quote(query)}&per_page={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in data.get("items") or []:
            if not row.get("html_url"):
                continue
            hits.append(Hit(
                connector=self.name, url=row["html_url"], title=row.get("full_name") or row["html_url"],
                snippet=(row.get("description") or "")[:500], source_type="repository",
                published=_date(row.get("updated_at")),
            ))
        return hits


class EuropePmcConnector:
    name = "europepmc"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
               f"?query={quote(query)}&format=json&pageSize={limit}&resultType=core")
        data = _get_json(self.get, url)
        hits = []
        for row in ((data.get("resultList") or {}).get("result") or [])[:limit]:
            pmid, source = row.get("id"), (row.get("source") or "MED")
            link = f"https://europepmc.org/article/{source}/{pmid}" if pmid else None
            if not link:
                continue
            hits.append(Hit(
                connector=self.name, url=link, title=_strip(row.get("title") or link),
                snippet=_strip(row.get("abstractText") or "")[:500], source_type="paper",
                published=_date(row.get("firstPublicationDate")), doi=row.get("doi"),
            ))
        return hits


class DoajConnector:
    name = "doaj"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://doaj.org/api/search/articles/{quote(query)}?pageSize={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in (data.get("results") or [])[:limit]:
            bib = row.get("bibjson") or {}
            doi = next((item.get("id") for item in bib.get("identifier") or [] if item.get("type") == "doi"), None)
            link = f"https://doi.org/{doi}" if doi else next((item.get("url") for item in bib.get("link") or [] if item.get("url")), None)
            if not link:
                continue
            year = bib.get("year")
            hits.append(Hit(
                connector=self.name, url=link, title=bib.get("title") or link,
                snippet=_strip(bib.get("abstract") or "")[:500], source_type="paper",
                published=f"{year}-01-01" if str(year).isdigit() else None, doi=doi,
            ))
        return hits


class HalConnector:
    name = "hal"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = ("https://api.archives-ouvertes.fr/search/"
               f"?q={quote(query)}&wt=json&rows={limit}&fl=title_s,uri_s,producedDate_tdate,abstract_s")
        data = _get_json(self.get, url)
        hits = []
        for row in ((data.get("response") or {}).get("docs") or [])[:limit]:
            link = row.get("uri_s")
            if not link:
                continue
            title = row.get("title_s") or link
            abstract = row.get("abstract_s") or ""
            hits.append(Hit(
                connector=self.name, url=link, title=_first(title),
                snippet=_first(abstract)[:500], source_type="paper",
                published=_date(row.get("producedDate_tdate")),
            ))
        return hits


class OpenReviewConnector:
    name = "openreview"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://api2.openreview.net/notes/search?term={quote(query)}&limit={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in (data.get("notes") or [])[:limit]:
            note_id = row.get("id") or row.get("forum")
            if not note_id:
                continue
            content = row.get("content") or {}
            hits.append(Hit(
                connector=self.name, url=f"https://openreview.net/forum?id={note_id}",
                title=_value(content.get("title")) or note_id,
                snippet=_value(content.get("abstract"))[:500], source_type="paper",
                published=_date(row.get("cdate") and _ms_date(row.get("cdate"))),
            ))
        return hits


class NsfConnector:
    name = "nsf"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://api.nsf.gov/services/v1/awards.json?keyword={quote(query)}&rpp={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in ((data.get("response") or {}).get("award") or [])[:limit]:
            award_id = row.get("id")
            if not award_id:
                continue
            hits.append(Hit(
                connector=self.name, url=f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award_id}",
                title=row.get("title") or str(award_id),
                snippet=(row.get("abstractText") or "")[:500], source_type="registry",
                published=_us_date(row.get("date")),
            ))
        return hits


class NihConnector:
    name = "nih"

    def __init__(self, post: Post):
        self.post = post

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        raw = self.post("https://api.reporter.nih.gov/v2/projects/search", {
            "criteria": {"advanced_text_search": {
                "operator": "and", "search_field": "abstracttext", "search_text": query,
            }},
            "limit": limit, "offset": 0,
        })
        data = _loads(raw)
        hits = []
        for row in (data.get("results") or [])[:limit]:
            appl = row.get("appl_id")
            if not appl:
                continue
            hits.append(Hit(
                connector=self.name, url=f"https://reporter.nih.gov/project-details/{appl}",
                title=row.get("project_title") or str(appl),
                snippet=(row.get("abstract_text") or "")[:500], source_type="registry",
                published=_date(row.get("project_start_date")),
            ))
        return hits


class CordisConnector:
    name = "cordis"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        q = quote(f"contenttype='project' AND {query}")
        url = f"https://cordis.europa.eu/search?q={q}&p=1&num={limit}&format=json"
        data = _get_json(self.get, url)
        hit = (data.get("hits") or {}).get("hit") or []
        hits = []
        for row in _as_list(hit)[:limit]:
            project = row.get("project") or {}
            project_id = project.get("id")
            if not project_id:
                continue
            title = project.get("title") or project.get("acronym") or str(project_id)
            hits.append(Hit(
                connector=self.name, url=f"https://cordis.europa.eu/project/id/{project_id}",
                title=title, snippet=_strip(project.get("teaser") or project.get("objective") or "")[:500],
                source_type="registry", published=_date(project.get("startDate")),
            ))
        return hits


class ClinicalTrialsConnector:
    name = "clinicaltrials"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://clinicaltrials.gov/api/v2/studies?query.term={quote(query)}&pageSize={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in (data.get("studies") or [])[:limit]:
            protocol = row.get("protocolSection") or {}
            ident = protocol.get("identificationModule") or {}
            nct = ident.get("nctId")
            if not nct:
                continue
            start = ((protocol.get("statusModule") or {}).get("startDateStruct") or {}).get("date")
            summary = (protocol.get("descriptionModule") or {}).get("briefSummary") or ""
            hits.append(Hit(
                connector=self.name, url=f"https://clinicaltrials.gov/study/{nct}",
                title=ident.get("briefTitle") or nct, snippet=_strip(summary)[:500],
                source_type="registry", published=_date(start),
            ))
        return hits


class IetfConnector:
    name = "ietf"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = f"https://datatracker.ietf.org/api/v1/doc/document/?format=json&title__icontains={quote(query)}&limit={limit}"
        data = _get_json(self.get, url)
        hits = []
        for row in (data.get("objects") or [])[:limit]:
            name = row.get("name")
            if not name:
                continue
            hits.append(Hit(
                connector=self.name, url=f"https://datatracker.ietf.org/doc/{name}/",
                title=row.get("title") or name, snippet=_strip(row.get("abstract") or "")[:500],
                source_type="registry", published=_date(row.get("time")),
            ))
        return hits


class SecConnector:
    name = "sec"

    def __init__(self, get: Get):
        self.get = get

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        url = ("https://efts.sec.gov/LATEST/search-index"
               f"?q={quote(query)}&forms=10-K,8-K&dateRange=all")
        data = _get_json(self.get, url)
        hits = []
        for row in (((data.get("hits") or {}).get("hits")) or [])[:limit]:
            src = row.get("_source") or {}
            link = _sec_url(src, row.get("_id"))
            if not link:
                continue
            names = src.get("display_names") or []
            title = f"{names[0]} {src.get('form') or ''}".strip() if names else (src.get("form") or link)
            hits.append(Hit(
                connector=self.name, url=link, title=title,
                snippet=(src.get("file_description") or src.get("form") or "")[:500],
                source_type="registry", published=_date(src.get("file_date")),
            ))
        return hits


def _text(entry: ET.Element, path: str) -> str:
    node = entry.find(path, ARXIV_NS)
    return re.sub(r"\s+", " ", (node.text or "")).strip() if node is not None else ""


def _date(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    return value[:10] if len(value) >= 10 and value[4] == "-" else None


def _crossref_date(row: dict) -> str | None:
    parts = ((row.get("issued") or {}).get("date-parts") or [[]])[0]
    nums = [p for p in parts if isinstance(p, int)]
    if not nums:
        return None
    y, m, d = nums[0], nums[1] if len(nums) > 1 else 1, nums[2] if len(nums) > 2 else 1
    return f"{y:04d}-{m:02d}-{d:02d}"


def _openalex_abstract(row: dict) -> str:
    inv = row.get("abstract_inverted_index") or {}
    if not inv:
        return ""
    words = sorted(((pos, word) for word, positions in inv.items() for pos in positions), key=lambda x: x[0])
    return " ".join(word for _, word in words)


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _loads(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConnectorError(str(e)) from e
    if not isinstance(data, dict):
        raise ConnectorError("answer is not an object")
    return data


def _first(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _value(field) -> str:
    if isinstance(field, dict):
        return _strip(str(field.get("value") or ""))
    return _strip(str(field or ""))


def _ms_date(value) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def _us_date(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        month, day, year = parts
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return _date(value)


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, dict) else []


def _sec_url(src: dict, row_id: str | None) -> str | None:
    ciks = src.get("ciks") or []
    adsh = src.get("adsh")
    name = (row_id or "").split(":", 1)[-1]
    if not ciks or not adsh or not name or name == row_id:
        return None
    try:
        cik = str(int(ciks[0]))
    except (TypeError, ValueError):
        return None
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{name}"
