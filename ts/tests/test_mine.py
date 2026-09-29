"""Offline checks for direction, rarity, and phrase seats. No network."""
import json
from datetime import date
from urllib.parse import unquote

from ts.fanout import load_theme_plan
from ts.mine import (
    _count_phrase,
    _lexeme_pack,
    concepts,
    direction,
    discover,
    keep_rare,
    old_theme_leak,
    openalex_sample_url,
    phrases,
    pick_candidates,
    ranked_grams,
    tokens,
    wikidata_labels,
)
from ts.sources.connectors import script_of


WIDE = "Слабые сигналы: модели, которые обучают другие модели, гибридные архитектуры, симбионты, системы на смыслах и состояниях"


def test_direction_modes():
    frame = load_theme_plan()["frame"]
    assert direction("слабые сигналы", frame)["mode"] == "no_direction"
    assert direction("слабые сигналы в энергетике", frame)["mode"] == "wide"
    assert direction("слабые сигналы в энергетике", frame)["tokens"] == ["энергетике"]
    assert direction("gallium nitride", frame)["mode"] == "narrow"
    assert direction("gallium nitride", frame)["object"] == "gallium nitride"
    assert direction("sodium-ion battery", frame)["mode"] == "narrow"
    assert "sodium-ion" in direction("sodium-ion battery", frame)["tokens"]
    assert direction(WIDE, frame)["mode"] == "wide"
    assert len(direction(WIDE, frame)["tokens"]) >= 5
    assert direction("ИИ", frame)["mode"] == "wide"
    assert direction("quiet-cell-repeat", frame)["mode"] == "narrow"


def test_tokens_keep_han_and_kana_apart():
    assert "光子" in tokens("光子芯片")
    assert "ナトリウム" in tokens("ナトリウム電池")
    assert script_of("ナトリウムイオン電池") == "kana"
    assert script_of("光子芯片路线图") == "han"


def test_a_long_shouted_word_is_a_word_not_an_abbreviation():
    found = tokens("ВОЗОБНОВЛЯЕМОЙ ЭНЕРГЕТИКЕ")
    assert "ВОЗОБНОВЛЯЕМОЙ" not in found and "ЭНЕРГЕТИКЕ" not in found
    assert "возобновляемой" in found and "энергетике" in found
    assert not any(item.isupper() for item in found)
    assert "HEMT" in tokens("GaN HEMT gate") and "MOSFET" in tokens("SiC MOSFET module")
    assert "SOLUTIONS" not in tokens("ENERGY SOLUTIONS for the grid")
    grams = [gram for gram, _ in ranked_grams(["ВОЗОБНОВЛЯЕМОЙ ЭНЕРГЕТИКЕ на острове", *FILLER], [], lang="ru", min_count=1)]
    assert "возобновляемой энергетике" in grams
    assert not any(gram.isupper() for gram in grams)


def test_rarity_knife_and_cap():
    assert keep_rare(2, 4)
    assert keep_rare(8, 16)
    assert not keep_rare(8, 10)
    assert not keep_rare(0, 2)
    assert not keep_rare(0, 200)
    assert not keep_rare(1, 4, n_field=10, cap_share=0.2)
    assert keep_rare(1, 4, n_field=100, cap_share=0.2)


def test_phrases_come_from_titles_and_old_themes_need_those_titles():
    titles = ["Sodium-ion battery anode", "Sodium-ion battery cathode"]
    titles += [f"Lithium-ion battery pack {index}" for index in range(10)]
    found = phrases(titles, [])
    assert any("sodium-ion" in item for item in found)
    old = ["proton exchange membrane electrolyzer"]
    assert old_theme_leak(old, titles, old) == old
    assert old_theme_leak(["sodium-ion battery anode"], titles, old) == []


FILLER = [f"filler{index} word{index}" for index in range(12)]


def test_grams_are_chunks_between_closed_words_and_punctuation():
    titles = ["on energy-environmental performance evidence", *FILLER]
    grams = [gram for gram, _ in ranked_grams(titles, [], min_count=1)]
    assert not any(gram.startswith("on ") or gram == "on" for gram in grams)
    assert "energy-environmental performance evidence" in grams
    titles = ["Затвор HEMT из нитрида галлия и канал", "Anode - cathode pair; Li's cell", *FILLER]
    grams = [gram for gram, _ in ranked_grams(titles, [], lang="ru", min_count=1)]
    assert "нитрида галлия" in grams and "канал" in grams
    assert not any("галлия и" in gram or "из нитрида" in gram for gram in grams)
    assert "anode" in grams and "cathode pair" in grams
    assert not any("anode cathode" in gram or "pair li" in gram for gram in grams)


def test_a_gram_counts_only_when_some_title_holds_it_as_a_whole_chunk():
    titles = ["Sulfide solid electrolyte for sodium cells", "Solid electrolyte with garnet", *FILLER]
    counted = dict(ranked_grams(titles, [], min_count=1))
    assert counted["solid electrolyte"] == 2
    assert "sulfide solid electrolyte" in counted
    assert "sulfide solid" not in counted
    assert "electrolyte sodium" not in counted


def test_cjk_grams_are_whole_han_runs_not_windows():
    fill = [f"其他{mark}" for mark in "一二三四五六七八"]
    ja = [gram for gram, _ in ranked_grams(["分散型再生可能エネルギーの導入", *fill], [], lang="ja", min_count=1)]
    assert "分散型再生可能エネルギー" in ja
    assert "分散型再生可" not in ja
    assert not any(len(gram) == 6 and gram in "分散型再生可能" for gram in ja)
    zh = [gram for gram, _ in ranked_grams(["钠离子电池负极材料研究", "光子芯片路线图", *fill], [], lang="zh", min_count=1)]
    assert "钠离子电池负极材料研究" in zh and "光子芯片路线图" in zh
    assert "钠离子" not in zh


def test_concepts_keep_one_seat_per_language_and_the_object():
    rows = [
        {"phrase": "alpha cell", "language": "en", "n_old": 1, "n_new": 4, "n_field": 100},
        {"phrase": "beta blade", "language": "en", "n_old": 1, "n_new": 3, "n_field": 100},
        {"phrase": "натрий ион", "language": "ru", "n_old": 0, "n_new": 3, "n_field": 20},
    ]
    chosen = concepts(rows, cap=2, narrow=True, object_text="gallium nitride")
    assert len(chosen) == 2
    langs = {item["language"] for item in chosen}
    assert "ru" in langs
    assert all("gallium nitride" in item["query"] for item in chosen)


def test_cjk_titles_without_a_doi_stay_apart():
    from ts.harness import _event_key
    from ts.sources.connectors import Hit

    left = Hit("openalex", "https://example.org/a", "光子芯片路线图", "", "paper")
    right = Hit("openalex", "https://example.org/b", "钠离子电池负极", "", "paper")
    assert _event_key(left) != _event_key(right)
    assert _event_key(left) != "title:"


def test_sample_url_uses_title_filter_and_the_day_seed():
    url = unquote(openalex_sample_url("energy", "en", date(2022, 9, 1), date(2022, 9, 29), 20220929, "secret"))
    assert "title.search:energy" in url
    assert "language:en" in url
    assert "seed=20220929" in url
    assert "api_key=secret" in url


def test_pick_candidates_puts_rare_grams_before_common_ones():
    grams = {"battery pack": 50, "solid electrolyte": 2, "anode": 3, "cathode coating": 7, "one-off": 1}
    picked = pick_candidates(grams, 1000)
    assert "solid electrolyte" in picked
    assert "battery pack" not in picked
    assert "one-off" not in picked
    assert picked.index("solid electrolyte") < picked.index("anode")
    assert picked.index("anode") < picked.index("cathode coating")
    small = pick_candidates({"anode": 1, "solid electrolyte": 1}, 20)
    assert small[0] == "solid electrolyte"


def _lexeme_get(url: str) -> str:
    if "type=form" in url:
        return json.dumps({"search": [{"id": "L182432-F6", "label": "энергетике"}, {"id": "L182433-F3", "label": "энергетике"}]})
    if "action=wbsearchentities" in url:
        return json.dumps({"search": []})
    if "ids=L182432" in url:
        return json.dumps({"entities": {"L182432": {
            "lemmas": {"ru": {"value": "энергетик"}},
            "forms": [{"representations": {"ru": {"value": "энергетике"}}}],
            "senses": [{"claims": {"P5137": [{"mainsnak": {"datavalue": {"value": {"id": "Q2878105"}}}}]}}],
        }}})
    if "ids=Q2878105" in url:
        return json.dumps({"entities": {"Q2878105": {
            "labels": {"en": {"value": "energy engineer"}, "ru": {"value": "энергетик"}},
            "claims": {}, "sitelinks": {"enwiki": {}, "ruwiki": {}},
        }}})
    if "ids=L182433" in url:
        return json.dumps({"entities": {"L182433": {
            "lemmas": {"ru": {"value": "энергетика"}},
            "forms": [
                {"representations": {"ru": {"value": "энергетика"}}},
                {"representations": {"ru": {"value": "энергетики"}}},
                {"representations": {"ru": {"value": "энергетике"}}},
            ],
            "senses": [
                {"claims": {"P5137": [{"mainsnak": {"datavalue": {"value": {"id": "Q2151621"}}}}]}},
                {"claims": {"P5137": [{"mainsnak": {"datavalue": {"value": {"id": "Q11379"}}}}]}},
            ],
        }}})
    if "ids=Q2151621" in url:
        return json.dumps({"entities": {"Q2151621": {
            "labels": {"en": {"value": "energy industry"}, "ru": {"value": "энергетика"}, "zh-hans": {"value": "能源产业"}},
            "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q268592"}}}}]},
            "sitelinks": {f"{code}wiki": {} for code in ("en", "ru", "de", "fr", "ja")},
        }}})
    if "ids=Q11379" in url:
        return json.dumps({"entities": {"Q11379": {"labels": {"en": {"value": "energy"}, "ru": {"value": "энергия"}}, "claims": {}}}})
    raise AssertionError(url)


def test_wikidata_labels_reach_the_item_through_a_lexeme_form():
    found = wikidata_labels("энергетике", _lexeme_get)
    assert found["match"] == "lexeme"
    assert found["qid"] == "Q2151621"
    assert found["ru"] == "энергетика"
    assert found["en"] == "energy industry"
    assert found["zh"] == "能源产业"
    assert found["forms"] == ["энергетика", "энергетики", "энергетике"]
    assert found["labels_alt"] == [{"qid": "Q11379", "en": "energy", "ru": "энергия"}]


def _plural_get(url: str) -> str:
    def form(ident, word, *features):
        return {"id": f"L1-{ident}", "representations": {"ru": {"value": word}}, "grammaticalFeatures": list(features)}

    if "ids=L1" in url:
        return json.dumps({"entities": {"L1": {
            "lemmas": {"ru": {"value": "энергетика"}},
            "forms": [
                form("F1", "энергетика", "Q110786", "Q131105"),
                form("F2", "энергетики", "Q110786", "Q146233"),
                form("F3", "энергетике", "Q110786", "Q145599"),
                form("F4", "энергетик", "Q146786", "Q146233"),
                form("F5", "энергетиками", "Q146786", "Q192997"),
            ],
            "senses": [{"claims": {"P5137": [{"mainsnak": {"datavalue": {"value": {"id": "Q2151621"}}}}]}}],
        }}})
    if "ids=Q2151621" in url:
        return json.dumps({"entities": {"Q2151621": {
            "labels": {"en": {"value": "energy industry"}, "ru": {"value": "энергетика"}},
            "claims": {}, "sitelinks": {"enwiki": {}},
        }}})
    raise AssertionError(url)


def test_singular_hit_keeps_lemma_and_singular_forms_only():
    packed = _lexeme_pack("L1", "ru", _plural_get, form_id="L1-F3")
    assert packed["lemma"] == "энергетика"
    assert packed["forms"] == ["энергетика", "энергетики", "энергетике"]
    assert packed["en"] == "energy industry" and packed["ru"] == "энергетика"
    plural_hit = _lexeme_pack("L1", "ru", _plural_get, form_id="L1-F5")
    assert "энергетиками" in plural_hit["forms"] and "энергетик" in plural_hit["forms"]
    unknown = _lexeme_pack("L1", "ru", _plural_get)
    assert "энергетиками" in unknown["forms"]


def test_count_phrase_within_the_object_quotes_both_strings():
    seen = []

    def get(url: str) -> str:
        seen.append(unquote(url))
        return json.dumps({"meta": {"count": 1}, "results": []})

    counted = _count_phrase("hemt gate", "en", date(2026, 9, 29), get, "secret", within="gallium nitride")
    assert counted == {"n_new": 1, "n_old": 0, "calls": 1}
    assert '"gallium nitride" AND "hemt gate"' in seen[0]
    assert "api_key=secret" in seen[0]

    def get_ru(url: str) -> str:
        return json.dumps({"results": [
            {"display_name": "Нитрид галлия: затвор HEMT", "publication_date": "2026-05-01"},
            {"display_name": "Кремний: затвор HEMT", "publication_date": "2026-05-01"},
        ]})

    counted = _count_phrase("затвор", "ru", date(2026, 9, 29), get_ru, "secret", within="нитрид галлия")
    assert counted["n_new"] == 1


def test_discover_keeps_an_honest_empty_list_and_names_a_dead_network():
    plan = {"frame": [], "rarity": {}}

    def quiet(url: str) -> str:
        if "wikidata" in url:
            return json.dumps({"search": []})
        if "crossref" in url:
            return json.dumps({"message": {"items": []}})
        return json.dumps({"meta": {"count": 0}, "results": [
            {"display_name": f"Gallium nitride power switch {index}", "publication_date": "2026-05-01"} for index in range(3)
        ]})

    report = discover("gallium nitride", plan, "2026-09-29", quiet, api_key="secret")
    assert report["error"] is None
    assert report["labels_match"] is None
    assert report["labels"]["ru"] is None
    assert report["concepts"] == []

    def dead(url: str) -> str:
        if "wikidata" in url:
            return json.dumps({"search": []})
        raise OSError("down")

    assert discover("gallium nitride", plan, "2026-09-29", dead, api_key="secret")["error"] == "network"
