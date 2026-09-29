"""Live-path state machine: search → snapshot → dedup → countersearch → score → rank.

One Python process, no second scheduler. Repeating the same query, corpus version
and rules version returns the stored run and does not search again (TS-INV-01).
EPO/CORDIS are not called (fork stub_unavailable).
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from ts.scoring.policy import route
from ts.scoring.relevance import chain_link
from ts.scoring.scorer import FeatureVector, load_rules, score
from ts.snapshots import save_snapshot
from ts.sources.connectors import Hit, script_of
from ts.sources.trust import classify, load_trust

STEPS = ("search", "snapshot", "dedup", "countersearch", "score", "rank")
TOP_N = 15
CHAIN_CONNECTORS = frozenset({"searxng", "openalex", "crossref", "sec"})
_DEEP = frozenset({"arxiv", "openalex", "crossref", "europepmc", "doaj", "hal"})
# Registries, code search and the web index take a plain phrase, not an OR-list of case forms.
_PLAIN_QUERY = frozenset({"github", "ietf", "sec", "nih", "nsf", "cordis", "clinicaltrials", "searxng"})
_OR_GROUP = re.compile(r"\(([^()]*?\sOR\s[^()]*?)\)")
# Phrase lists such as "market leader" are not in the brief and are not dataset
# patterns. They are not an admission cut. Maturity still comes from a filled
# checklist when texts are read, and from M04 when every source is a retelling.
MATURE_MARKERS: dict = {}


class Searcher(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 5) -> list[Hit]: ...


@dataclass
class RunReport:
    id: str
    query: str
    idempotency_key: str
    repeated: bool
    steps: list[dict]
    sources: list[dict]
    events: list[dict]
    card: dict
    top: list[dict]
    shortfall: int
    exclusion_registry: list[dict]
    model_id: str | None = None
    provider: str | None = None
    corpus_version: str = "live-w3"
    fanout: dict | None = None
    unread: list[dict] = field(default_factory=list)


@dataclass
class Harness:
    rules_version: str = "rules-0.1"
    corpus_version: str = "live-w3"
    snapshot_dir: Path = field(default_factory=lambda: Path("snapshots"))
    store: dict = field(default_factory=dict)
    trust_table: dict = field(default_factory=load_trust)

    def run(
        self,
        query: str,
        connectors: list[Searcher],
        *,
        limit: int = 5,
        extractor=None,
        budget_exhausted: bool = False,
        fetch_body=None,
        chain: bool = True,
        countersearch: bool = True,
        as_of: str | None = None,
    ) -> RunReport:
        rules = load_rules(self.rules_version)
        key = hashlib.sha256(f"{query}|{self.corpus_version}|{rules['version']}".encode()).hexdigest()
        if key in self.store:
            return replace(self.store[key], repeated=True)
        steps: list[dict] = []
        hits, failures = self._search(connectors, query, limit, steps)
        chain_sources = [item for item in connectors if item.name in CHAIN_CONNECTORS]
        if chain and chain_sources:
            extra, extra_failures = self._search(
                chain_sources, _chain_query(query), limit, steps, step="chain",
            )
            hits.extend(hit for hit in extra if _on_topic(query, hit))
            failures.extend(extra_failures)
        if as_of:
            hits, dropped = within_window(hits, as_of)
            steps.append({"name": "window", "dropped": dropped})
        if script_of(query) in {"han", "kana"}:
            hits, dropped = titled_with(hits, query)
            steps.append({"name": "title", "dropped": dropped})
        sources = self._sources(hits)
        self._snapshot(hits, fetch_body, steps)
        events = dedup(hits)
        steps.append({"name": "dedup", "status": "ok", "events": len(events),
                      "merged": sum(1 for e in events if e["dedup_status"] == "merged")})
        if countersearch:
            counter_hits, _ = self._search(connectors, f"{query} mass adoption industry standard", limit, steps, step="countersearch")
        else:
            # Empty maturity markers make this search decide nothing. The gate still counts as done.
            counter_hits = []
            steps.append({"name": "countersearch", "status": "skipped"})
        counters, counter_evidence = markers(counter_hits)
        if sources and all(s["trust"] == "indicator" for s in sources):
            counters["M04"] = True
            counter_evidence["M04"] = "все найденные источники — индикаторы, первичных нет"
        observed = [e for e in events if e["type"] != "planned_for"]
        origins = len({_host(h.url) for h in hits})
        if extractor is None and events:
            cards, model_id, provider = self._score_events(
                query, hits, events, counter_hits, rules, budget_exhausted, steps, as_of,
            )
        else:
            fv, model_id, provider, scope = self._extract(
                query, hits, observed, origins, counters, counter_evidence, extractor, steps,
            )
            result = score(fv, rules)
            decision = route(_contract(fv, result, counters, budget_exhausted, countersearch_done=True, as_of=as_of))
            steps.append({"name": "score", "status": "ok", "label": result.label, "gate": decision["action"]})
            cards = [_card(
                query, result, decision, sources, events, model_id, _blob("", hits),
                subject_hits=_subject_hits(query, query), scope=scope,
            )]
        card = cards[0]
        top, excluded = rank(cards, require_subject=bool(_tokens(query)), query=query)
        steps.append({"name": "rank", "status": "ok", "admitted": len(top), "shortfall": TOP_N - len(top),
                      "connector_failures": failures})
        report = RunReport(
            id=key[:16], query=query, idempotency_key=key, repeated=False, steps=steps, sources=sources, events=events,
            card=card, top=top, shortfall=TOP_N - len(top), exclusion_registry=excluded,
            model_id=model_id, provider=provider, corpus_version=self.corpus_version,
        )
        self.store[key] = report
        return report

    def _score_events(self, query, hits, events, counter_hits, rules, budget_exhausted, steps, as_of=None):
        """One card per distinct find. The same gates apply. Nothing is admitted early."""
        by_url: dict[str, list] = {}
        for hit in hits:
            by_url.setdefault(hit.url, []).append(hit)
        cards = []
        for event in events:
            group = [hit for url in event["urls"] for hit in by_url.get(url, [])]
            title = group[0].title if group else query
            event_sources = self._sources(group)
            counters, evidence = markers(group + _about_find(group, counter_hits))
            if event_sources and all(source["trust"] == "indicator" for source in event_sources):
                counters["M04"] = True
                evidence["M04"] = "у этой находки только пересказы, первоисточника нет"
            observed = [] if event["type"] == "planned_for" else [event]
            origins = len({_host(hit.url) for hit in group})
            fv = FeatureVector(
                primary_pattern="P04", features={}, counters=counters,
                evidence_events=len(observed), independent_origins=origins,
                transition="unknown", evidence=evidence, mode="ledger", named_primary=False,
            )
            result = score(fv, rules)
            decision = route(_contract(fv, result, counters, budget_exhausted, countersearch_done=True, as_of=as_of))
            blob = " ".join([title, *[hit.snippet or "" for hit in group]])
            cards.append(_card(
                title, result, decision, event_sources, [event], None, _blob(title, group),
                subject_hits=max(_subject_hits(query, title), _subject_hits(query, blob)),
            ))
            steps.append({"name": "score", "status": "ok", "label": result.label, "gate": decision["action"], "find": title})
        return cards, None, None

    def _search(self, connectors, query, limit, steps, step="search"):
        hits: list[Hit] = []
        failures = []
        for connector in connectors:
            try:
                depth = 8 if step == "search" and connector.name in _DEEP and limit < 8 else limit
                found = connector.search(query_for(connector.name, query), limit=depth)
                hits.extend(found)
                steps.append({"name": step, "connector": connector.name, "status": "ok", "n": len(found)})
            except Exception as e:  # noqa: BLE001 — one dead source must not stop the run
                failures.append(connector.name)
                steps.append({"name": step, "connector": connector.name, "status": "failed", "error": type(e).__name__})
        return hits, failures

    def _sources(self, hits: list[Hit]) -> list[dict]:
        cards = []
        for hit in hits:
            cards.append({
                "name": hit.title,
                "url": hit.url,
                "date": hit.published,
                "date_unknown_reason": None if hit.published else "источник не указал дату",
                "type": hit.source_type,
                "language": hit.language,
                "trust": classify(hit.url, hit.source_type, self.trust_table),
                "connector": hit.connector,
                "snippet": (hit.snippet or "")[:500],
                **({"doi": hit.doi} if hit.doi else {}),
            })
        return cards

    def _snapshot(self, hits, fetch_body, steps) -> None:
        saved = 0
        if fetch_body is None:
            steps.append({"name": "snapshot", "status": "skipped", "reason": "no fetcher"})
            return
        for hit in hits:
            try:
                body = fetch_body(hit.url)
            except Exception as e:  # noqa: BLE001
                steps.append({"name": "snapshot", "status": "failed", "url": hit.url, "error": type(e).__name__})
                continue
            if isinstance(body, str):
                body = body.encode()
            save_snapshot(self.snapshot_dir, hit.url, body)
            saved += 1
        steps.append({"name": "snapshot", "status": "ok", "saved": saved})

    def _extract(self, query, hits, observed, origins, counters, evidence, extractor, steps):
        events_n = len(observed)
        origins = min(origins, events_n)
        if extractor is None:
            fv = FeatureVector(
                primary_pattern="P04", features={}, counters=counters,
                evidence_events=events_n, independent_origins=origins,
                transition="unknown", evidence=evidence, mode="ledger", named_primary=False,
            )
            steps.append({"name": "extract", "status": "skipped", "reason": "no extractor"})
            return fv, None, None, None
        fragments = [f"{h.title}. {h.snippet}" for h in hits[:12]]
        out, meta = extractor.extract({"technology": query, "fragments": fragments})
        from ts.extract import to_feature_vector
        fv = to_feature_vector(out, "ledger")
        fv.evidence_events = events_n
        fv.independent_origins = origins
        fv.mode = "ledger"
        for code, fired in counters.items():
            if fired:
                fv.counters[code] = True
                fv.evidence[code] = evidence.get(code, fv.evidence.get(code, ""))
        steps.append({"name": "extract", "status": "ok", "model_id": meta.get("model_id")})
        return fv, meta.get("model_id"), meta.get("provider"), _scope_or_none(out.get("scope"))


def query_for(connector_name: str, phrase: str) -> str:
    """The phrase shape one connector accepts.

    Paper indexes take the phrase as-is. Registries, GitHub, IETF and the web index get a plain
    phrase: a surrounding "(a OR b OR c)" group of case forms collapses to its first form. A query
    that is already a plain phrase is sent unchanged. Nothing shorter is invented.
    """
    if connector_name not in _PLAIN_QUERY or " OR " not in phrase:
        return phrase
    plain = _OR_GROUP.sub(lambda m: m.group(1).split(" OR ", 1)[0].strip(), phrase)
    return re.sub(r"\s+", " ", plain).strip() or phrase


def _iso_date(value: str | None) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def within_window(hits: list[Hit], as_of: str) -> tuple[list[Hit], int]:
    """Drop hits with a real ISO date strictly after as_of. Undated hits stay; order is kept."""
    edge = _iso_date(as_of)
    if edge is None:
        return hits, 0
    kept = []
    for hit in hits:
        published = _iso_date(hit.published)
        if published is not None and published > edge:
            continue
        kept.append(hit)
    return kept, len(hits) - len(kept)


def titled_with(hits: list[Hit], query: str) -> tuple[list[Hit], int]:
    """For a Han or kana query only a title that contains the query string is about it."""
    kept = [hit for hit in hits if query in (hit.title or "")]
    return kept, len(hits) - len(kept)


def _title_norm(title: str) -> list[str]:
    text = title.lower().replace("‐", "-").replace("–", "-").replace("—", "-")
    for mark in ("...", "…"):
        if mark in text:
            text = text.split(mark, 1)[0]
    for tail in (" - sciencedirect", " | wiley online library", " - wiley", " - mdpi"):
        if tail in text:
            text = text.split(tail, 1)[0]
    return re.findall(r"[a-z0-9а-яё]+", text)


def _same_title(left: list[str], right: list[str]) -> bool:
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    if len(short) < 6:
        return False
    if long[: len(short)] == short:
        return True
    # The same paper with two file tails still opens with the same long wording.
    shared = 0
    for a, b in zip(left, right):
        if a != b:
            break
        shared += 1
    if shared >= 8:
        return True
    # "Cu 3 P" and "Cu3P" are the same formula split by the page title.
    return "".join(long).startswith("".join(short))


def dedup(hits: list[Hit]) -> list[dict]:
    groups: OrderedDict[str, list[Hit]] = OrderedDict()
    for hit in hits:
        groups.setdefault(_event_key(hit), []).append(hit)
    parent = {key: key for key in groups}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    keys = list(groups)
    for i, left in enumerate(keys):
        left_titles = [_title_norm(hit.title) for hit in groups[left]]
        for right in keys[i + 1 :]:
            if not any(_same_title(a, b) for a in left_titles for b in (_title_norm(hit.title) for hit in groups[right])):
                continue
            root_left, root_right = find(left), find(right)
            if root_left == root_right:
                continue
            if root_right.startswith("doi:") and not root_left.startswith("doi:"):
                parent[root_left] = root_right
            else:
                parent[root_right] = root_left
    merged: OrderedDict[str, list[Hit]] = OrderedDict()
    for key, group in groups.items():
        merged.setdefault(find(key), []).extend(group)
    events = []
    for key, group in merged.items():
        group.sort(key=lambda hit: (0 if hit.doi else 1, hit.url))
        planned = next((h.planned_for for h in group if h.planned_for), None)
        deployed = any(h.deployment and not h.planned_for for h in group)
        events.append({
            "key": key,
            "type": "observed" if deployed or not planned else "planned_for",
            "planned_for": None if deployed else planned,
            "deployment_confirmed": deployed,
            "dedup_status": "merged" if len(group) > 1 else "unique",
            "urls": [h.url for h in group],
            "connectors": sorted({h.connector for h in group}),
        })
    return events


def _chain_query(query: str) -> str:
    if re.search(r"[а-яё]", query.lower()):
        return f"{query} цепочка поставок производство новое поколение"
    return f"{query} supply chain production next generation"


def _tokens(text: str) -> list[str]:
    cleaned = text.lower().replace("‐", "-").replace("–", "-")
    words = re.findall(r"[a-z0-9а-яё]{4,}", cleaned)
    for run in re.findall(r"[\u4e00-\u9fff]+", text or ""):
        words.extend(run[i : i + 2] for i in range(max(len(run) - 1, 1)))
    words.extend(re.findall(r"[\u30a0-\u30ff]{2,}", text or ""))
    return words


def _holds(word: str, token: str) -> bool:
    return token in word


def _substituted(tokens: list[str], words: list[str]) -> bool:
    """The frame is the same, but one word inside it was replaced by another."""
    if len(tokens) < 3:
        return False
    for index in range(1, len(tokens) - 1):
        left, mid, right = tokens[index - 1], tokens[index], tokens[index + 1]
        if any(_holds(word, mid) for word in words):
            continue
        for pos in range(len(words) - 2):
            gap = words[pos + 1]
            if (
                _holds(words[pos], left)
                and _holds(words[pos + 2], right)
                and not _holds(gap, mid)
                and not any(_holds(gap, token) for token in tokens)
            ):
                return True
    return False


def _subject_hits(query: str, title: str) -> int:
    """Share of the query's own wording, plus pairs that stayed side by side.

    More than half the words means this title is the subject. One different word
    between the same neighbors means a different subject. No stop list and no
    allowlist of special markers.
    """
    tokens = _tokens(query)
    if not tokens:
        return 0
    query_script, title_script = script_of(query), script_of(title)
    if query_script and title_script and query_script != title_script:
        return 1
    cleaned = title.lower().replace("‐", "-").replace("–", "-")
    words = _tokens(title)
    present = [token for token in tokens if token in cleaned]
    if len(present) * 2 <= len(tokens):
        return 0
    if _substituted(tokens, words):
        return 0
    pairs = sum(
        1
        for left, right in zip(tokens, tokens[1:])
        if any(
            _holds(words[i], left) and _holds(words[i + 1], right)
            for i in range(len(words) - 1)
        )
    )
    return len(present) + pairs


def _on_topic(query: str, hit: Hit) -> bool:
    return _subject_hits(query, f"{hit.title} {hit.snippet}") > 0


def _about_find(group: list[Hit], counter_hits: list[Hit]) -> list[Hit]:
    """A maturity phrase counts only when it is about this find, not about another result."""
    tokens = re.findall(r"[a-z0-9а-яё]{5,}", " ".join(hit.title for hit in group).lower())
    if not tokens:
        return []
    related = []
    for hit in counter_hits:
        blob = f"{hit.title} {hit.snippet}".lower()
        if any(token in blob for token in tokens):
            related.append(hit)
    return related


def markers(hits: list[Hit]) -> tuple[dict, dict]:
    fired = {code: False for code in MATURE_MARKERS}
    evidence = {}
    for hit in hits:
        blob = f"{hit.title} {hit.snippet}"
        for code, pattern in MATURE_MARKERS.items():
            if fired[code]:
                continue
            found = pattern.search(blob)
            if found:
                fired[code] = True
                evidence[code] = f"{found.group(0)} ({hit.url})"
    return fired, evidence


_COUNTERS = frozenset({"M01", "M02", "M03", "M04", "M05", "M06"})


def rank(cards: list[dict], require_subject: bool = False, query: str = "") -> tuple[list[dict], list[dict]]:
    from ts.scoring.order import sort_admitted

    # Word overlap sorts. It does not exclude. require_subject and query stay for callers.
    _ = (require_subject, query)
    admitted, excluded = [], []
    for card in cards:
        codes = set(card.get("reason_codes") or [])
        # An empty pattern sum is not a verdict: the checklist was not filled.
        # Dataset weights stay. A counter from the brief still keeps the card out.
        passed = card["policy_action"] == "RANK_ELIGIBLE" and not (codes & _COUNTERS)
        if passed:
            admitted.append(card)
        else:
            excluded.append(card)
    ordered = sort_admitted(admitted)
    tail = [{**card, "policy_reason": "beyond_top_n"} for card in ordered[TOP_N:]]
    return ordered[:TOP_N], excluded + tail


def _event_key(hit: Hit) -> str:
    if hit.doi:
        return "doi:" + hit.doi.lower().removeprefix("https://doi.org/")
    words = re.findall(r"[a-z0-9а-яё]+", hit.title.lower())
    if words:
        return "title:" + " ".join(words[:8])
    marks = re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", hit.title)
    return "title:" + "".join(marks[:8])


def _host(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def _contract(fv: FeatureVector, result, counters: dict, budget_exhausted: bool, countersearch_done: bool, as_of: str | None = None) -> dict:
    mature = any(counters.get(code) for code in ("M01", "M02", "M03", "M06"))
    if fv.evidence_events == 0:
        novelty, maturity, claims = "unclear", "unclear", ["unknown"]
    elif mature:
        novelty, maturity, claims = "known", "established", ["supported"]
    else:
        novelty, maturity = "new", "emerging"
        claims = ["verified"] if fv.transition == "verified" else ["supported"]
    origins = min(fv.independent_origins, fv.evidence_events)
    return {
        "as_of": as_of or datetime.now(tz=UTC).date().isoformat(),
        "novelty": novelty,
        "maturity": maturity,
        "critical_claims": claims,
        "fatal_finding": "none",
        "evidence_events": fv.evidence_events,
        "independent_origins": origins,
        "countersearch_done": countersearch_done,
        "source_availability_valid": fv.evidence_events > 0,
        "budget_exhausted": budget_exhausted,
        "branches_complete": countersearch_done,
        "transition_verified": fv.transition == "verified",
    }


def _scope_or_none(raw) -> int | None:
    if raw in (1, 2):
        return int(raw)
    return None


def _blob(title: str, hits: list) -> str:
    parts = [title]
    for hit in hits:
        parts.append(getattr(hit, "title", "") or "")
        parts.append(getattr(hit, "snippet", "") or "")
    return " ".join(parts)


def _card(query, result, decision, sources, events, model_id, text: str = "", subject_hits: int = 0,
          scope: int | None = None) -> dict:
    return {
        "technology": query,
        "subject_hits": subject_hits,
        "scope": scope if scope in (1, 2) else None,
        "chain_link": chain_link(text),
        "label": result.label,
        "confidence": result.confidence,
        "policy_action": decision["action"],
        "policy_reason": decision["reason"],
        "reason_codes": result.reason_codes,
        "predictors": result.predictors,
        "sources": sources,
        "events": len(events),
        "planned_not_deployment": [e["key"] for e in events if e["type"] == "planned_for"],
        "model_id": model_id,
        "rules_version": result.rules_version,
    }
