"""Young phrases from this run's documents. Names are copied from titles, not invented."""
from __future__ import annotations

import calendar
import json
import re
from datetime import date
from urllib.parse import quote

from ts.sources.connectors import script_of

LANGS = ("en", "ru", "zh", "ja")
CLOSED = ("eLibrary", "CNKI", "Wanfang", "VIP", "ChinaXiv")
ARTICLE = "Q13442814"
DISAMBIGUATION = "Q4167410"
HUMAN = "Q5"
SINGULAR = "Q110786"
PLURAL = "Q146786"
CALL_CEILING = 400
_WORD = re.compile(r"[a-z0-9а-яё]{2,}(?:-[a-z0-9а-яё]{2,})*", re.IGNORECASE)
# An abbreviation is a short all-caps token, at most six characters. A long shouted word is a word.
_ABBREV = re.compile(r"\b(?=[A-Za-zА-Яа-яЁё0-9]{2,6}\b)[A-ZА-ЯЁ]{2,}[A-Za-zА-Яа-яЁё0-9]*")
_HAN = re.compile(r"[\u4e00-\u9fff]+")
_KATA = re.compile(r"[\u30a0-\u30ff]{2,}")
# A Han run bounded by kana, punctuation, space or the edge; in Japanese it may carry a trailing katakana word.
_HAN_RUN = re.compile(r"([\u4e00-\u9fff]+)([\u30a0-\u30ff]{2,})?")
# Every word, one letter up, so a one-letter closed-class word still marks a boundary.
_ANY_WORD = re.compile(r"[a-z0-9а-яё]+(?:-[a-z0-9а-яё]+)*", re.IGNORECASE)
# Closed-class words are chunk boundaries. Grammar, not a technology dictionary.
CLOSED_CLASS = {
    "en": frozenset("the a an of on for in to with from by and or at as its their into via between".split()),
    "ru": frozenset("и в на для с по из при о об к у от до за как".split()),
}
_CLOSED_ANY = frozenset().union(*CLOSED_CLASS.values())


def tokens(text: str) -> list[str]:
    """Latin and Cyrillic words from two letters, Han pairs, a katakana run."""
    found = [item.group(0) for item in _ABBREV.finditer(text or "")]
    found.extend(item.group(0).lower() for item in _WORD.finditer(text or ""))
    for run in _HAN.findall(text or ""):
        if len(run) == 1:
            found.append(run)
        else:
            found.extend(run[i : i + 2] for i in range(len(run) - 1))
    found.extend(_KATA.findall(text or ""))
    out = []
    seen = set()
    for item in found:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def direction(query: str, frame: list[str]) -> dict:
    """Wide, narrow, or empty. One plain word is a field. A hyphenated word is an object."""
    blocked = {word.lower() for word in frame}
    content = []
    for token in tokens(query or ""):
        if token.isdigit() or token.lower() in blocked:
            continue
        content.append(token)
    if not content:
        return {"mode": "no_direction", "tokens": [], "object": None}
    compound = len(content) == 1 and "-" in content[0]
    if len(content) >= 5 or (len(content) == 1 and not compound):
        mode = "wide"
    else:
        mode = "narrow"
    return {
        "mode": mode,
        "tokens": content,
        "object": " ".join(content) if mode == "narrow" else None,
    }


def keep_rare(n_old: int | None, n_new: int | None, n_field: int | None = None, cap_share: float | None = None) -> bool:
    if n_old is None or n_new is None:
        return False
    if n_new < 3 or n_new >= 200:
        return False
    grew = n_old <= 8 and n_old > 0 and n_new / n_old >= 2
    if not (n_old <= 5 or grew):
        return False
    if cap_share is not None and n_field:
        if n_new / n_field > cap_share:
            return False
    return True


def _share(row: dict) -> float:
    field = row.get("n_field") or 0
    if field:
        return row["n_new"] / field
    return float(row["n_new"])


def _overlap(left: str, right: str) -> bool:
    a, b = set(tokens(left)), set(tokens(right))
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) > 0.5


def phrases(titles: list[str], task_words: list[str], *, lang: str = "en", min_count: int = 2) -> list[str]:
    """Repeated wording from these titles. A token in a fifth of the titles is dropped."""
    return [gram for gram, _ in ranked_grams(titles, task_words, lang=lang, min_count=min_count)]


def pick_candidates(grams_with_counts, n_titles: int, limit: int = 25) -> list[str]:
    """Rare wording first. A gram in more than 2% of a real sample is a field word, not a signal."""
    items = dict(grams_with_counts)

    def order(gram: str) -> tuple:
        return (" " not in gram, -len(gram), gram)

    if n_titles < 80:
        return sorted(items, key=lambda gram: " " not in gram)[:limit]
    kept = {
        gram: count for gram, count in items.items()
        if count >= 2 and (count <= 4 or count / n_titles <= 0.02)
    }
    first = sorted((gram for gram, count in kept.items() if count <= 4), key=order)
    second = sorted((gram for gram, count in kept.items() if count >= 5), key=order)
    return (first + second)[:limit]


def _han_parts(title: str, lang: str) -> list[str]:
    """Whole Han runs, never a sliding window. A Japanese run may keep its trailing katakana word."""
    parts = []
    for found in _HAN_RUN.finditer(title):
        run, kata = found.group(1), found.group(2)
        parts.append(run)
        if lang == "ja" and kata:
            parts.append(run + kata)
    parts.extend(_KATA.findall(title))
    return parts


def _segments(title: str, blocked: set[str], lang: str) -> list[list[str]]:
    """Word runs between punctuation, closed-class words, digits, one-letter words and task words."""
    _ = lang  # Latin and Cyrillic closed words cannot collide, so both lists bound every title.
    closed = _CLOSED_ANY
    segments: list[list[str]] = []
    current: list[str] = []
    cursor = 0
    for found in _ANY_WORD.finditer(title):
        gap = title[cursor : found.start()]
        cursor = found.end()
        if re.search(r"[^\s]", gap) and current:
            segments.append(current)
            current = []
        word = found.group(0)
        boundary = (
            len(word) < 2 or word.isdigit() or word.lower() in closed or word.lower() in blocked
        )
        if boundary:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(word if _ABBREV.fullmatch(word) else word.lower())
    if current:
        segments.append(current)
    return segments


def _chunks(segments: list[list[str]], stop: set[str]) -> list[list[str]]:
    """A field word that sits in a fifth of the titles is a boundary too, as it was a filter before."""
    chunks: list[list[str]] = []
    for segment in segments:
        current: list[str] = []
        for word in segment:
            if word in stop:
                if current:
                    chunks.append(current)
                    current = []
                continue
            current.append(word)
        if current:
            chunks.append(current)
    return chunks


def ranked_grams(titles: list[str], task_words: list[str], *, lang: str = "en", min_count: int = 2) -> list[tuple[str, int]]:
    """The grams phrases() keeps, each with the number of titles it appears in.

    A gram is a run of words inside one grammar chunk. It counts only when at least one title
    holds it as a whole chunk between punctuation and closed-class words.
    """
    blocked = {word.lower() for word in task_words}
    cjk = lang in {"zh", "ja"}
    docs: list = []
    for title in titles:
        docs.append(_han_parts(title, lang) if cjk else _segments(title, blocked, lang))
    if not docs:
        return []
    token_docs: dict[str, int] = {}
    for doc in docs:
        words = set(doc) if cjk else {word for segment in doc for word in segment}
        for word in words:
            token_docs[word] = token_docs.get(word, 0) + 1
    stop = {word for word, count in token_docs.items() if count / len(docs) >= 0.2}
    counts: dict[str, int] = {}
    whole: set[str] = set()
    per_doc: list[set[str]] = []
    for doc in docs:
        grams: set[str] = set()
        if cjk:
            for part in doc:
                if part not in stop:
                    grams.add(part)
                    whole.add(part)
        else:
            for chunk in _chunks(doc, stop):
                whole.add(" ".join(chunk))
                for size in (1, 2, 3, 4):
                    grams.update(" ".join(chunk[i : i + size]) for i in range(len(chunk) - size + 1))
        per_doc.append(grams)
    for grams in per_doc:
        for gram in grams:
            if gram not in whole:
                continue
            counts[gram] = counts.get(gram, 0) + 1
    ranked = sorted(counts, key=lambda gram: (-counts[gram], -len(gram), gram))
    kept = []
    for gram in ranked:
        if counts[gram] < min_count:
            continue
        if min_count == 1 and " " not in gram and len(gram) < 4:
            continue
        if any(gram != other and gram in other and counts[other] >= counts[gram] for other in kept):
            continue
        kept.append(gram)
    return [(gram, counts[gram]) for gram in kept]


def concepts(rows: list[dict], *, cap: int = 12, narrow: bool = False, object_text: str | None = None, child_cap: int = 8) -> list[dict]:
    """One seat per notion. A language with a survivor keeps one seat. The rest follow rarity."""
    grouped: list[dict] = []
    for row in rows:
        placed = False
        for item in grouped:
            same_lang = item["language"] == row["language"] and _overlap(item["phrase"], row["phrase"])
            same_id = row.get("qid") and row.get("qid") == item.get("qid")
            if same_lang or same_id:
                if _share(row) < _share(item):
                    item.update(phrase=row["phrase"], n_old=row["n_old"], n_new=row["n_new"], n_field=row.get("n_field"), qid=row.get("qid"), language=row["language"])
                placed = True
                break
        if not placed:
            grouped.append(dict(row))
    grouped.sort(key=_share)
    floors = []
    seen_lang = set()
    for item in grouped:
        if item["language"] in seen_lang:
            continue
        seen_lang.add(item["language"])
        floors.append(item)
    rest = [item for item in grouped if item not in floors]
    pool = floors + rest
    concepts.last_cut = [
        {"phrase": item["phrase"], "language": item["language"], "n_old": item["n_old"], "n_new": item["n_new"]}
        for item in pool[cap:]
    ]
    chosen = pool[:cap]
    if narrow:
        chosen = chosen[:child_cap]
    out = []
    for item in chosen:
        phrase = item["phrase"]
        query = phrase
        if narrow and object_text and object_text.lower() not in phrase.lower():
            query = f"{object_text} {phrase}"
        out.append({
            "id": phrase,
            "title": phrase,
            "query": query,
            "language": item["language"],
            "n_old": item["n_old"],
            "n_new": item["n_new"],
        })
    return out


def old_theme_leak(phrases_found: list[str], titles: list[str], old: list[str]) -> list[str]:
    """A standing theme string may appear only when this run's titles contain it."""
    blob = "\n".join(titles).lower()
    leaked = []
    for phrase in phrases_found:
        if phrase.lower() in {item.lower() for item in old} and phrase.lower() not in blob:
            leaked.append(phrase)
    return leaked


def month_starts(as_of: date, count: int) -> list[tuple[date, date]]:
    year, month = as_of.year, as_of.month
    windows = []
    for _ in range(count):
        last = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = min(date(year, month, last), as_of)
        if start <= as_of:
            windows.append((start, end))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    windows.reverse()
    return windows


def openalex_sample_url(label: str, lang: str, start: date, end: date, seed: int, api_key: str | None, per_page: int = 80) -> str:
    filt = f"title.search:{label},language:{lang},from_publication_date:{start.isoformat()},to_publication_date:{end.isoformat()}"
    url = f"https://api.openalex.org/works?filter={quote(filt)}&sample={per_page}&seed={seed}&per-page={per_page}"
    if api_key:
        url += f"&api_key={quote(api_key)}"
    return url


def _own_lang(text: str) -> str:
    return {"cyr": "ru", "han": "zh", "kana": "ja", "lat": "en"}.get(script_of(text), "en")


def _json(get, url: str) -> dict:
    return json.loads(get(url))


def _packed_labels(entity: dict, qid: str, match: str) -> dict:
    labels = entity.get("labels") or {}
    packed = {"en": None, "ru": None, "zh": None, "ja": None, "qid": qid, "match": match}
    for lang in ("en", "ru", "ja"):
        packed[lang] = (labels.get(lang) or {}).get("value")
    for key in ("zh-cn", "zh-hans", "zh"):
        value = (labels.get(key) or {}).get("value")
        if value:
            packed["zh"] = value
            break
    return packed


def _kinds(entity: dict) -> list[str]:
    return [item.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for item in (entity.get("claims") or {}).get("P31") or []]


def _entity(get, ident: str, props: str) -> dict | None:
    url = ("https://www.wikidata.org/w/api.php?action=wbgetentities"
           f"&ids={ident}&props={props}&format=json")
    try:
        return (_json(get, url).get("entities") or {}).get(ident) or {}
    except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
        return None


def lexeme_labels(text: str, lang: str, get) -> dict | None:
    """An inflected word maps to a lexeme; its sense points at the item. Forms come from the lexeme.

    One form string can belong to several lexemes (энергетике: энергетик, энергетика). The lexeme
    whose item is described in the most Wikipedias wins; ties keep the search order.
    """
    search = ("https://www.wikidata.org/w/api.php?action=wbsearchentities"
              f"&search={quote(text)}&language={lang}&type=form&format=json&limit=5")
    try:
        hits = _json(get, search).get("search") or []
    except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
        return None
    matched: dict[str, str] = {}
    for hit in hits:
        ident = hit.get("id") or ""
        if ident.startswith("L") and "-" in ident:
            matched.setdefault(ident.rsplit("-", 1)[0], ident)
    best = None
    for lexeme_id, form_id in list(matched.items())[:3]:
        packed = _lexeme_pack(lexeme_id, lang, get, form_id=form_id)
        if packed and (best is None or packed["sitelinks"] > best["sitelinks"]):
            best = packed
    if best:
        best.pop("sitelinks", None)
    return best


def _lexeme_pack(lexeme_id: str, lang: str, get, form_id: str | None = None) -> dict | None:
    """Lemma, forms, and the item behind the sense. `form_id` is the form the operator's word hit.

    When that form is singular, plural forms are left out: the needle keeps the lemma and the
    singular case forms. Labels of the chosen item are not touched.
    """
    lexeme = _entity(get, lexeme_id, "lemmas|forms|senses|claims")
    if not lexeme:
        return None
    lemmas = lexeme.get("lemmas") or {}
    lemma = (lemmas.get(lang) or {}).get("value")
    if not lemma and lemmas:
        lemma = (next(iter(lemmas.values())) or {}).get("value")
    all_forms = lexeme.get("forms") or []
    hit_features = next((set(form.get("grammaticalFeatures") or []) for form in all_forms
                         if form_id and form.get("id") == form_id), set())
    singular_only = SINGULAR in hit_features
    forms: list[str] = []
    seen = set()
    for word in [lemma] + [((form.get("representations") or {}).get(lang) or {}).get("value")
                           for form in all_forms
                           if not (singular_only and PLURAL in (form.get("grammaticalFeatures") or []))]:
        if not word or word.casefold() in seen or len(forms) >= 8:
            continue
        seen.add(word.casefold())
        forms.append(word)
    items: list[str] = []
    for sense in lexeme.get("senses") or []:
        for claim in (sense.get("claims") or {}).get("P5137") or []:
            qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if qid and qid not in items:
                items.append(qid)
    packed = None
    alt = []
    for qid in items:
        if packed is not None and len(alt) >= 2:
            break
        entity = _entity(get, qid, "labels|claims|sitelinks")
        if entity is None:
            continue
        if {ARTICLE, DISAMBIGUATION, HUMAN} & set(_kinds(entity)):
            continue
        labels = _packed_labels(entity, qid, "lexeme")
        if packed is None:
            packed = labels
            packed["sitelinks"] = len(entity.get("sitelinks") or {})
        else:
            alt.append({"qid": qid, "en": labels["en"], "ru": labels["ru"]})
    if packed is None:
        return None
    packed["lexeme"] = lexeme_id
    packed["lemma"] = lemma
    packed["forms"] = forms
    packed["labels_alt"] = alt
    return packed


def wikidata_labels(text: str, get, *, lexeme: bool = True) -> dict:
    """Labels already stored on one concept. A paper hit and a missing label stay empty."""
    found = {"en": None, "ru": None, "zh": None, "ja": None, "qid": None}
    search = ("https://www.wikidata.org/w/api.php?action=wbsearchentities"
              f"&search={quote(text)}&language={_own_lang(text)}&format=json&limit=5")
    try:
        hits = (_json(get, search).get("search") or [])
    except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
        return found
    fallback = None
    for hit in hits:
        qid = hit.get("id")
        if not qid:
            continue
        entity = _entity(get, qid, "labels|aliases|claims")
        if entity is None or ARTICLE in _kinds(entity):
            continue
        aliases = [item.get("value") or "" for item in (entity.get("aliases") or {}).get(_own_lang(text)) or []]
        forms = {(hit.get("label") or "").casefold(), ((hit.get("match") or {}).get("text") or "").casefold()}
        forms.update(item.casefold() for item in aliases)
        packed = _packed_labels(entity, qid, "search")
        if text.casefold() in forms:
            packed["match"] = "exact"
            return packed
        if fallback is None:
            fallback = packed
    if lexeme:
        via_lexeme = lexeme_labels(text, _own_lang(text), get)
        if via_lexeme:
            return via_lexeme
    return fallback or found


def discover(query: str, plan: dict, as_of: str, get, api_key: str | None = None) -> dict:
    """Sample titles inside the named field and keep the rare repeated phrases."""
    frame = list(plan.get("frame") or [])
    found = direction(query, frame)
    knives = {"df": 0, "n_new": 0, "n_old": 0, "cap": 0, "no_count": 0}
    report = {
        "direction": found,
        "concepts": [],
        "knives": knives,
        "sample": {},
        "labels": {},
        "qid": None,
        "closed_sources": list(CLOSED),
        "error": None,
    }
    if found["mode"] == "no_direction":
        return report
    if not api_key:
        report["error"] = "no_key"
        return report
    text = " ".join(found["tokens"])
    own = _own_lang(text)
    own_text = text
    labels = wikidata_labels(text, get)
    match = labels.get("match")
    report["labels_match"] = match
    if match not in {"exact", "lexeme"}:
        labels = {"en": None, "ru": None, "zh": None, "ja": None, "qid": None, "match": match}
    labels[own] = labels.get(own) or own_text
    forms = [item for item in labels.get("forms") or [] if item] if match == "lexeme" else []
    report["labels"] = {lang: labels.get(lang) for lang in LANGS}
    report["labels_alt"] = list(labels.get("labels_alt") or [])
    report["forms"] = list(forms)
    report["qid"] = labels.get("qid")
    report["operator_text"] = own_text
    day = date.fromisoformat(as_of)
    seed = int(day.strftime("%Y%m%d"))
    cap_share = (plan.get("rarity") or {}).get("cap_share")
    within = found["object"] if found["mode"] == "narrow" else None
    rows = []
    calls = 0
    sample_calls = sample_failed = 0
    count_tried = count_failed = 0
    mined_by_lang = {}
    field_n = {}
    months = month_starts(day, 18)
    windows = [(group[0][0], group[-1][1]) for group in (months[i : i + 3] for i in range(0, len(months), 3)) if group]
    for lang in LANGS:
        label = labels.get(lang) or (own_text if lang == own else None)
        if not label:
            continue
        if lang == own:
            label = _own_label(label, found, forms)
        titles = []
        sources = ["openalex"]
        for start, end in windows:
            url = openalex_sample_url(label, lang, start, end, seed, api_key, per_page=200)
            calls += 1
            sample_calls += 1
            try:
                payload = _json(get, url)
            except (json.JSONDecodeError, OSError, TimeoutError, ValueError, Exception):
                knives["no_count"] += 1
                sample_failed += 1
                continue
            for row in payload.get("results") or []:
                title = row.get("display_name") or ""
                if title and _script_ok(lang, title):
                    titles.append(title)
        if lang == "en":
            sources.append("crossref")
            titles.extend(_crossref_titles(label, windows[0][0], day, get))
        report["sample"][lang] = {"titles": len(titles), "sources": sources, "label": label}
        field_n[lang] = max(len(titles), 1)
        floor = 1 if len(titles) < 80 else 2
        grams = ranked_grams(titles, frame, lang=lang, min_count=floor)
        mined_by_lang[lang] = pick_candidates(grams, len(titles), limit=25)
    queues = {lang: list(items) for lang, items in mined_by_lang.items()}
    while any(queues.values()) and calls < CALL_CEILING:
        for lang, queue in list(queues.items()):
            if not queue or calls >= CALL_CEILING:
                continue
            phrase = queue.pop(0)
            count_lang = lang
            count_tried += 1
            counted = _count_phrase(phrase, count_lang, day, get, api_key, within=within)
            calls += counted["calls"]
            if lang != "en" and counted["n_new"] is not None and counted["n_new"] < 3:
                sibling = _exact_en(phrase, get)
                if sibling:
                    counted = _count_phrase(sibling, "en", day, get, api_key, within=within)
                    calls += counted["calls"]
                    phrase = sibling
                    count_lang = "en"
            if counted["n_new"] is None:
                knives["no_count"] += 1
                count_failed += 1
                continue
            if not keep_rare(counted["n_old"], counted["n_new"], field_n.get(count_lang), cap_share):
                if (counted["n_new"] or 0) < 3:
                    knives["n_new"] += 1
                elif counted["n_new"] >= 200:
                    knives["cap"] += 1
                else:
                    knives["n_old"] += 1
                continue
            rows.append({
                "phrase": phrase, "language": count_lang, "n_old": counted["n_old"],
                "n_new": counted["n_new"], "n_field": field_n.get(count_lang),
            })
    left = sum(len(queue) for queue in queues.values())
    if left:
        knives["budget"] = left
    report["concepts"] = concepts(
        rows, narrow=found["mode"] == "narrow", object_text=found["object"],
    )
    report["cut_by_cap12"] = list(getattr(concepts, "last_cut", []))
    report["calls"] = calls
    titles_total = sum(item["titles"] for item in report["sample"].values())
    if sample_calls and sample_failed == sample_calls and titles_total == 0:
        report["error"] = "network"
    elif count_tried and count_failed == count_tried:
        report["error"] = "network"
    return report


def _own_label(label: str, found: dict, forms: list[str]) -> str:
    """The operator's own-language needle. Lexeme forms replace one inflected word, not a sentence."""
    tokens_ = found["tokens"]
    words = [token for token in tokens_ if len(token) >= 4] if found["mode"] == "wide" and len(tokens_) >= 2 else []
    if len(words) >= 2:
        return "(" + " OR ".join(words) + ")"
    if forms and (len(tokens_) == 1 or words):
        return "(" + " OR ".join(forms) + ")"
    if words:
        return "(" + " OR ".join(words) + ")"
    return label


def count_url(phrase: str, lang: str, start: date, end: date, per_page: int, api_key: str, within: str | None = None) -> str:
    needle = phrase.replace('"', "")
    if lang == "en":
        needle = f'"{needle}"'
        if within:
            needle = f'"{within.replace(chr(34), "")}" AND {needle}'
    filt = f"title.search:{needle},language:{lang},from_publication_date:{start.isoformat()},to_publication_date:{end.isoformat()}"
    return f"https://api.openalex.org/works?filter={quote(filt)}&per-page={per_page}&api_key={quote(api_key)}"


def _count_phrase(phrase: str, lang: str, as_of: date, get, api_key: str, within: str | None = None) -> dict:
    new_end = as_of
    new_start = month_starts(as_of, 18)[0][0]
    old_end = date.fromordinal(new_start.toordinal() - 1)
    old_start = month_starts(old_end, 24)[0][0]
    calls = 0

    def fetch(start: date, end: date, per_page: int) -> dict | None:
        nonlocal calls
        url = count_url(phrase, lang, start, end, per_page, api_key, within)
        calls += 1
        try:
            return _json(get, url)
        except (json.JSONDecodeError, OSError, TimeoutError, ValueError, Exception):
            return None

    if lang != "en":
        payload = fetch(old_start, new_end, 200)
        if payload is None:
            return {"n_new": None, "n_old": None, "calls": calls}
        new_n = old_n = 0
        for row in payload.get("results") or []:
            title = (row.get("display_name") or "").casefold()
            if phrase.casefold() not in title:
                continue
            if within and within.casefold() not in title:
                continue
            published = (row.get("publication_date") or "")[:10]
            if published >= new_start.isoformat():
                new_n += 1
            else:
                old_n += 1
        if len(payload.get("results") or []) >= 200 and new_n >= 200:
            new_n = 200
        return {"n_new": new_n, "n_old": old_n, "calls": calls}
    payload = fetch(new_start, new_end, 1)
    if payload is None:
        return {"n_new": None, "n_old": None, "calls": calls}
    n_new = int((payload.get("meta") or {}).get("count") or 0)
    if n_new < 3 or n_new >= 200:
        return {"n_new": n_new, "n_old": 0, "calls": calls}
    older = fetch(old_start, old_end, 1)
    n_old = int((older.get("meta") or {}).get("count") or 0) if older else None
    return {"n_new": n_new, "n_old": n_old, "calls": calls}


def _exact_en(phrase: str, get) -> str | None:
    """English label only when Wikidata matches this phrase itself."""
    found = wikidata_labels(phrase, get, lexeme=False)
    label = found.get("en")
    if found.get("match") == "exact" and label and label.casefold() != phrase.casefold():
        return label
    return None


def _script_ok(lang: str, title: str) -> bool:
    script = script_of(title)
    if lang == "en":
        return script in {"", "lat"}
    if lang == "ru":
        return script == "cyr"
    return True


def _crossref_titles(label: str, start: date, end: date, get) -> list[str]:
    url = ("https://api.crossref.org/works?query.bibliographic="
           f"{quote(label)}&filter=from-pub-date:{start.isoformat()},until-pub-date:{end.isoformat()}"
           "&rows=100")
    try:
        payload = _json(get, url)
    except (json.JSONDecodeError, OSError, TimeoutError, ValueError, Exception):
        return []
    titles = []
    for row in ((payload.get("message") or {}).get("items") or []):
        title = " ".join(row.get("title") or [])
        if title and _script_ok("en", title):
            titles.append(title)
    return titles
