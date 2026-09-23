"""One live query for the CLI and the API. OpenRouter is used only when extract=True, and only via the ZDR client."""
from __future__ import annotations

import hashlib

import httpx

from ts.harness import Harness
from ts.persist import load_report, public_report, save_report
from ts.settings import Settings, load
from ts.sources.connectors import (
    ArxivConnector,
    CrossrefConnector,
    GithubConnector,
    OpenAlexConnector,
    SearxConnector,
)


def _key(query: str, rules_version: str, corpus: str = "live-w3") -> str:
    return hashlib.sha256(f"{query}|{corpus}|{rules_version}".encode()).hexdigest()


def run_query(query: str, *, limit: int = 3, extract: bool = False, settings: Settings | None = None,
              connectors=None, session_factory=None) -> dict:
    s = settings or load()
    key = _key(query, s.rules_version)
    factory = session_factory
    if factory is None:
        from ts.db import session_factory as factory
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    report = Harness(rules_version=s.rules_version, snapshot_dir=s.snapshot_dir, corpus_version="live-w3").run(
        query, connectors if connectors is not None else default_connectors(s),
        limit=limit, extractor=_extractor(s) if extract else None,
    )
    with factory() as session:
        save_report(session, report)
    return public_report(report)


def default_connectors(s: Settings):
    def get(url: str) -> str:
        response = httpx.get(url, timeout=40, follow_redirects=True, headers={"User-Agent": "thin-signals/0.1"})
        response.raise_for_status()
        return response.text

    connectors = []
    if s.searxng_url:
        connectors.append(SearxConnector(s.searxng_url, get))
    connectors += [ArxivConnector(get), OpenAlexConnector(get), CrossrefConnector(get), GithubConnector(get)]
    return connectors


def _extractor(s: Settings):
    from ts.extract import Extractor
    from ts.llm import OpenRouterClient
    return Extractor(OpenRouterClient(s), model=s.llm_primary, mode="ledger")
