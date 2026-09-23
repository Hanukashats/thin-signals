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

ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}
PLANNED_RE = re.compile(
    r"roadmap|planned for|will be available|expected in|анонс|к 20[2-9]\d|в 20[2-9]\d году",
    re.IGNORECASE,
)
DEPLOYED_RE = re.compile(
    r"commercially available|in production|widely deployed|в эксплуатации|серийно",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"20[2-9]\d")


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
        self.planned_for, self.deployment = _roadmap(self.title + " " + self.snippet, self.planned_for, self.deployment)


def _language(text: str, given: str) -> str:
    if given and given != "und":
        return given
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "und"
    cyr = sum(1 for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё")
    return "ru" if cyr / len(letters) > 0.3 else "en"


def _roadmap(text: str, planned: str | None, deployment: bool) -> tuple[str | None, bool]:
    if planned:
        return planned, False
    if PLANNED_RE.search(text):
        year = YEAR_RE.search(text)
        return (f"{year.group(0)}-01-01" if year else None), False
    if DEPLOYED_RE.search(text):
        return None, True
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
