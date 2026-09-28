"""Finance and supply-chain emphasis never opens the list by itself."""
from ts.harness import rank
from ts.scoring.relevance import chain_link


def test_science_without_market_words_stays_in_review():
    link = chain_link("перовскитный датчик влажности, лабораторный образец")
    assert link["score"] == 0
    assert link["families"] == []
    assert "не отказ" in link["sentence"]


def test_direct_sales_without_a_middleman_is_a_supply_chain_touch():
    link = chain_link("CATL direct-sales platform cuts out middlemen")
    assert "цепочка поставок или производство" in link["families"]
    assert "не прогноз" in link["sentence"]


def test_market_and_chain_words_are_named_and_are_not_a_forecast():
    link = chain_link("платёжный чип для цепочки поставщиков нефтедобычи")
    assert "финансовый рынок" in link["families"]
    assert "цепочка поставок или производство" in link["families"]
    assert "клиентская отрасль" in link["families"]
    assert "не прогноз" in link["sentence"]
    assert link["score"] == 1


def test_scale_ranks_a_wide_shift_above_a_local_one_and_does_not_admit():
    from ts.scoring.order import sort_admitted

    wide = {
        "technology": "общий механизм для сетей, двигателей и вычислений",
        "policy_action": "RANK_ELIGIBLE",
        "subject_hits": 3,
        "scope": 2,
        "sources": [{"date": "2020-01-01"}],
        "predictors": [{"code": "P01", "value": "supported"}],
        "chain_link": {"score": 0},
    }
    local = {
        "technology": "покрытие катода на четыре процента лучше",
        "policy_action": "RANK_ELIGIBLE",
        "subject_hits": 3,
        "scope": 1,
        "sources": [{"date": "2026-06-01"}],
        "predictors": [{"code": "P01", "value": "supported"}],
        "chain_link": {"score": 0},
    }
    unread = {
        "technology": "текст не читали",
        "policy_action": "RANK_ELIGIBLE",
        "subject_hits": 3,
        "scope": None,
        "sources": [{"date": "2026-08-01"}],
        "predictors": [{"code": "P01", "value": "supported"}],
        "chain_link": {"score": 0},
    }
    closer = {**unread, "technology": "ближе к запросу", "subject_hits": 6, "sources": [{"date": "2019-01-01"}]}
    top, excluded = rank([local, unread, wide])
    assert excluded == []
    assert [row["technology"] for row in top] == [
        wide["technology"], local["technology"], unread["technology"],
    ]
    assert [row["technology"] for row in sort_admitted([wide, closer])][0] == "ближе к запросу"


def test_chain_words_reorder_only_after_the_same_evidence():
    weak = {
        "technology": "без рынка",
        "policy_action": "RANK_ELIGIBLE",
        "label": "weak_signal",
        "predictors": [{"code": "P01", "value": "verified"}],
        "chain_link": chain_link("лабораторный датчик"),
    }
    linked = {
        "technology": "с рынком",
        "policy_action": "RANK_ELIGIBLE",
        "label": "weak_signal",
        "predictors": [{"code": "P01", "value": "verified"}],
        "chain_link": chain_link("кредит для цепочки поставщиков"),
    }
    noise = {
        "technology": "шум про банк",
        "policy_action": "WATCHLIST",
        "label": "noise",
        "predictors": [],
        "chain_link": chain_link("банк биржа клиринг"),
    }
    top, excluded = rank([weak, noise, linked])
    assert [row["technology"] for row in top] == ["с рынком", "без рынка"]
    assert [row["technology"] for row in excluded] == ["шум про банк"]
