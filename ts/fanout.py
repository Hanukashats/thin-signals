"""A mission sentence is not a search string. It runs the standing theme queries.

Each theme keeps the ordinary word gate and the ordinary order. The official list
takes one card from each theme before a second card from any theme. A read scale
of 2 or 1 moves ahead of unread cards. Unread cards are not labeled fundamental.
Score weights are not touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ts.harness import TOP_N, _tokens
from ts.scoring.order import _published_rank, scope_rank

PLAN_PATH = Path(__file__).resolve().parents[1] / "data" / "theme_plan.yaml"


def load_theme_plan(path: Path = PLAN_PATH) -> dict:
    plan = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    plan["frame"] = [str(word).lower() for word in plan.get("frame") or []]
    plan["themes"] = list(plan.get("themes") or [])
    plan["version"] = str(plan.get("version") or "themes-0")
    return plan


def is_wide(query: str, plan: dict) -> bool:
    """True when the sentence names the assignment and almost no object."""
    text = (query or "").strip().lower()
    if not text:
        return False
    if text in {str(theme.get("query") or "").strip().lower() for theme in plan["themes"]}:
        return False
    tokens = _tokens(text)
    if len(tokens) < 4:
        return False
    frame = set(plan["frame"])
    distinctive = [token for token in tokens if token not in frame and not token.isdigit()]
    return len(distinctive) < 2


def _identity(card: dict) -> tuple:
    aliases = _identity_aliases(card)
    dois = tuple(value for kind, value in sorted(aliases) if kind == "doi")
    if dois:
        return ("doi", *dois)
    urls = tuple(value for kind, value in sorted(aliases) if kind == "url")
    if urls:
        return ("url", *urls)
    return ("title", next(value for kind, value in aliases if kind == "title"))


def _normalise_doi(value: object) -> str:
    doi = str(value or "").strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi.removeprefix(prefix).strip()
    return doi


def _identity_aliases(card: dict) -> frozenset[tuple[str, str]]:
    """Return every stable source alias; repeats inside one card count once."""
    aliases: set[tuple[str, str]] = set()
    for source in card.get("sources") or []:
        if not isinstance(source, dict):
            continue
        doi = _normalise_doi(source.get("doi"))
        if doi:
            aliases.add(("doi", doi))
        url = str(source.get("url") or "").strip()
        if url:
            aliases.add(("url", url))
    if aliases:
        return frozenset(aliases)
    title = " ".join(str(card.get("technology") or "").casefold().split())
    return frozenset({("title", title)})


def _identity_groups(cards: list[dict]) -> list[tuple[tuple, list[dict]]]:
    """Partition cards by DOI/URL aliases without merging conflicting DOI anchors.

    A DOI-bearing record and a DOI-less record for the same URL are one event.
    Explicitly different DOI records stay separate even if a URL conflicts. A
    DOI-less URL component joins an anchored component only when that anchor is
    unambiguous. The canonical key is therefore input-order invariant.
    """
    if not cards:
        return []
    parents = list(range(len(cards)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        parents[max(left_root, right_root)] = min(left_root, right_root)

    aliases_by_index = [_identity_aliases(card) for card in cards]
    dois_by_index = [
        {value for kind, value in aliases if kind == "doi"}
        for aliases in aliases_by_index
    ]
    urls_by_index = [
        {value for kind, value in aliases if kind == "url"}
        for aliases in aliases_by_index
    ]

    # DOI is the strong anchor. A card may deliberately carry more than one
    # DOI, so its DOI aliases belong to one anchored component.
    doi_owner: dict[str, int] = {}
    title_owner: dict[str, int] = {}
    for index, aliases in enumerate(aliases_by_index):
        for kind, value in aliases:
            if kind == "doi":
                previous = doi_owner.setdefault(value, index)
                union(index, previous)
            elif kind == "title":
                previous = title_owner.setdefault(value, index)
                union(index, previous)

    # First connect URL-only observations to each other. Their full component
    # is considered before it is allowed to join a DOI anchor.
    url_only_owner: dict[str, int] = {}
    for index, urls in enumerate(urls_by_index):
        if dois_by_index[index]:
            continue
        for url in urls:
            previous = url_only_owner.setdefault(url, index)
            union(index, previous)

    anchored_by_url: dict[str, set[int]] = {}
    for index, urls in enumerate(urls_by_index):
        if not dois_by_index[index]:
            continue
        for url in urls:
            anchored_by_url.setdefault(url, set()).add(find(index))

    unanchored_urls: dict[int, set[str]] = {}
    for index, urls in enumerate(urls_by_index):
        if dois_by_index[index]:
            continue
        unanchored_urls.setdefault(find(index), set()).update(urls)
    for root, urls in sorted(unanchored_urls.items()):
        anchors = {
            find(anchor)
            for url in urls
            for anchor in anchored_by_url.get(url, set())
        }
        if len(anchors) == 1:
            union(root, next(iter(anchors)))

    members_by_root: dict[int, list[int]] = {}
    for index in range(len(cards)):
        members_by_root.setdefault(find(index), []).append(index)
    groups = []
    for indices in sorted(members_by_root.values(), key=lambda values: values[0]):
        aliases = sorted({
            alias
            for index in indices
            for alias in aliases_by_index[index]
        })
        groups.append((("aliases", *aliases), [cards[index] for index in indices]))
    return groups


def _identity_map(cards: list[dict]) -> dict[int, tuple]:
    return {
        id(card): identity
        for identity, members in _identity_groups(cards)
        for card in members
    }


def _identity_representative(cards: list[dict]) -> dict:
    """Keep the richest member while retaining first-seen order for exact ties."""
    return max(cards, key=lambda card: (
        sum(kind == "doi" for kind, _value in _identity_aliases(card)),
        len(_identity_aliases(card)),
        len([source for source in card.get("sources") or [] if isinstance(source, dict)]),
        len(card.get("evidence_fragments") or []),
    ))


def theme_plan_fingerprint(plan: dict) -> str:
    """Hash ordered theme semantics without putting raw queries in cache metadata."""
    payload = {
        "version": str(plan.get("version") or "themes-0"),
        "themes": [
            {
                "id": str(theme.get("id") or ""),
                "query_hash": hashlib.sha256(
                    str(theme.get("query") or "").strip().encode()
                ).hexdigest()[:16],
            }
            for theme in plan.get("themes") or []
            if isinstance(theme, dict)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def _newer_first(cards: list[dict]) -> list[dict]:
    """Among cards that hold the query words, the newer date goes first.

    A card without a date stays in the queue, after the dated ones. Cards without
    the query words keep their own order behind them.
    """
    def key(card: dict) -> tuple:
        if int(card.get("subject_hits") or 0) > 0:
            return (0, -_published_rank(card))
        return (1, 0)
    return sorted(cards, key=key)


def merge_theme_reports(
    parts: list[tuple[dict, list[dict]]],
    *,
    limit: int = TOP_N,
    global_identity_groups: list[tuple[tuple, list[dict]]] | None = None,
) -> dict:
    """parts are (theme, already admitted cards in that theme's own order)."""
    queues: list[list[dict]] = []
    inherited = {
        id(card): identity
        for identity, members in (global_identity_groups or [])
        for card in members
    }
    identities: dict[int, tuple] = {}
    notes = []
    for theme, cards in parts:
        tagged = []
        for card in _newer_first(cards):
            tagged_card = {
                **card,
                "theme": theme.get("id"),
                "theme_title": theme.get("title"),
                "theme_query": theme.get("query"),
            }
            tagged.append(tagged_card)
            if id(card) in inherited:
                identities[id(tagged_card)] = inherited[id(card)]
        queues.append(tagged)
        notes.append({
            "id": theme.get("id"),
            "title": theme.get("title"),
            "query": theme.get("query"),
            "admitted": len(tagged),
            "taken": 0,
        })
    tagged_cards = [card for queue in queues for card in queue]
    fallback = _identity_map(tagged_cards)
    for card in tagged_cards:
        identities.setdefault(id(card), fallback[id(card)])
    picked: list[dict] = []
    overflow: list[dict] = []
    seen: set[tuple] = set()
    while len(picked) < limit and any(queues):
        for index, queue in enumerate(queues):
            if len(picked) >= limit:
                break
            while queue:
                card = queue.pop(0)
                ident = identities[id(card)]
                if ident in seen:
                    continue
                seen.add(ident)
                picked.append(card)
                notes[index]["taken"] += 1
                break
    for queue in queues:
        for card in queue:
            ident = identities[id(card)]
            if ident in seen:
                continue
            seen.add(ident)
            overflow.append({**card, "policy_reason": "theme_quota"})
    picked = sorted(picked, key=scope_rank, reverse=True)
    return {"top": picked, "overflow": overflow, "themes": notes}
