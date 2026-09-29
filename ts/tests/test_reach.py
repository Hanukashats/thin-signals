"""Application hypothesis is attached after admission and does not sort."""
from __future__ import annotations

from ts.fanout import load_theme_plan
from ts.plain import reach_sentence
from ts.reach import apply_reach
from ts.scoring.order import sort_admitted
from ts.scoring.scorer import load_rules


def test_plan_version_is_the_reach_slice_and_weights_stay():
    assert load_theme_plan()["version"] == "themes-5"
    assert load_rules()["weights"]["primary"] == 0.35
    assert load_rules()["thresholds"]["weak_signal"] == 0.60


def test_reach_keeps_order_scope_and_drops_a_forecast():
    cards = [
        {"technology": "local step", "scope": 1, "subject_hits": 2, "sources": [{"url": "https://a"}]},
        {"technology": "wide mechanism", "scope": None, "subject_hits": 4, "sources": [{"url": "https://b"}]},
    ]

    def reader(card):
        if card["technology"].startswith("local"):
            return {
                "plain": "Обычными словами: мембрана, через которую проходит водород.",
                "sphere": "рынок вырастет на 20% к 2030",
                "moves": "мембрана электролизера",
                "affects": "смежные электролизеры",
                "plus": "проще отделить водород",
                "minus": "мембрана изнашивается",
                "terms": "электролизёр — прибор, который током разлагает воду",
                "if_true": "меньше ограничений на аноде",
                "open": "срок службы не назван",
            }, "openai/gpt-5.6-luna"
        raise RuntimeError("reader down")

    from ts.desk import score_story

    out = apply_reach(cards, reader)
    assert [row["technology"] for row in out] == ["local step", "wide mechanism"]
    assert out[0]["scope"] == 1 and out[1]["scope"] is None
    assert out[0]["reach"]["sphere"] == ""
    assert out[0]["reach"]["plain"].startswith("Обычными словами")
    assert out[0]["reach"]["plus"] == "проще отделить водород"
    assert "электролизёр" in out[0]["reach"]["terms"]
    story = score_story({"top": out, "confidence": 0, "predictors": []})
    assert story["cards"][0]["plain"].startswith("Обычными словами")
    assert story["cards"][0]["minus"] == "мембрана изнашивается"
    assert "Гипотеза модели" not in story["top"][0]
    assert "Гипотеза модели, в тексте не проверено" in reach_sentence(out[0]["reach"])
    assert reach_sentence(None) == ""
    ranked = sort_admitted(out)
    assert ranked[0]["technology"] == "wide mechanism"
