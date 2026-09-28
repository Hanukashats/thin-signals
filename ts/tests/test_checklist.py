"""Checklist after the list is chosen. A stand-in reader, no live model."""
from __future__ import annotations

from ts.checklist import _case_quote, apply_checklist, score_card, vector_for
from ts.desk import candidate_views, run_banner
from ts.fanout import _identity
from ts.harness import RunReport
from ts.persist import public_report
from ts.scoring.scorer import load_rules, score


def _rules():
    return load_rules()


def _card(name="proton cell", *, theme="a", url="https://arxiv.org/abs/2401.00001", snippet="A fragment about the cell."):
    return {
        "technology": name,
        "theme": theme,
        "policy_action": "WATCHLIST",
        "policy_reason": "evidence_gates_passed",
        "label": "noise",
        "confidence": 0,
        "reason_codes": [],
        "predictors": [],
        "events": 1,
        "planned_not_deployment": [],
        "scope": 2,
        "scope_why": "как было",
        "sources": [{"name": "Paper", "url": url, "snippet": snippet}],
    }


def _out(*, primary="P01", verified=(), counters=(), transition="supported", p03_why="", events=10, actors=10):
    verified = set(verified)
    features = []
    for index in range(1, 19):
        code = f"P{index:02d}"
        status = "verified" if code in verified or code == primary else "absent"
        why = p03_why if code == "P03" and p03_why else "по фрагменту"
        features.append({"code": code, "status": status, "why": why})
    fired = dict(counters)
    rows = []
    for code in ("M01", "M02", "M03", "M04", "M05", "M06"):
        why = fired.get(code, "")
        rows.append({"code": code, "fired": bool(why), "why": why})
    return {
        "features": features,
        "counters": rows,
        "transition": {"status": transition, "why": "стадия"},
        "primary_pattern": primary,
        "secondary_patterns": [f"P{index:02d}" for index in range(1, 19)],
        "distinct_actors": actors,
        "distinct_events": events,
    }


def _read(out, fragments=None, urls=None):
    return {
        "output": out,
        "meta": {"model_id": "fake", "cached": False},
        "fragments": fragments or ["первый фрагмент", "второй фрагмент"],
        "urls": urls or ["https://a/1", "https://a/2"],
    }


def test_scored_card_uses_rules_01_and_keeps_admission():
    rules = _rules()
    card = _card()
    out = _out(verified={"P01"}, transition="supported")

    def reader(_card_in):
        return _read(out)

    judged = score_card(card, reader, rules)
    assert judged["keep"] is True
    assert judged["card"]["policy_action"] == "WATCHLIST"
    assert judged["card"]["checklist"]["status"] == "scored"
    assert judged["card"]["confidence"] == score(vector_for(card, out), rules).confidence


def test_lone_find_capped_at_080_and_ignores_model_counts():
    rules = _rules()
    card = _card()
    verified = {f"P{index:02d}" for index in range(1, 19)}
    out = _out(verified=verified, transition="verified", events=10, actors=10)
    judged = score_card(card, lambda _c: _read(out), rules)
    ind = next(row for row in judged["card"]["predictors"] if row["code"] == "IND")
    assert ind["value"] == 0
    assert judged["card"]["confidence"] <= 0.80
    assert judged["card"]["confidence"] == 0.8


def test_counter_drops_with_quote():
    rules = _rules()
    card = _card()
    out = _out(counters={"M01": "уже есть лидеры"})
    result = apply_checklist([card], [], lambda _c: _read(out), rules)
    assert result["top"] == []
    assert result["excluded"][0]["policy_reason"] == "checklist_counter"
    assert result["excluded"][0]["checklist_quote"] == "уже есть лидеры"


def test_reader_m04_ignored():
    rules = _rules()
    card = _card()
    out = _out(verified={"P01"}, counters={"M04": "только пересказ"}, transition="supported")
    judged = score_card(card, lambda _c: _read(out), rules)
    assert judged["keep"] is True
    assert judged["card"]["confidence"] is not None
    assert "M04" not in judged["card"]["reason_codes"]


def test_below_watchlist_drops_with_reason():
    rules = _rules()
    card = _card()
    out = _out(primary="P01", verified=(), transition="unknown")
    # primary P01 is forced verified by _out when code == primary. Override to absent.
    for feature in out["features"]:
        feature["status"] = "absent"
    result = apply_checklist([card], [], lambda _c: _read(out), rules)
    assert result["top"] == []
    assert result["excluded"][0]["policy_reason"] == "checklist_below_watchlist"


def test_no_fragment_leaves_the_seat_without_llm_call():
    rules = _rules()
    card = _card(snippet="", url="https://example.test/item")
    calls = []

    def reader(_c):
        calls.append(1)
        raise AssertionError("reader")

    result = apply_checklist([card], [], reader, rules)
    assert calls == []
    assert result["top"] == []
    assert result["excluded"] == []
    assert result["unread"][0]["policy_reason"] == "no_source_text"
    assert result["unread"][0]["confidence"] is None


def test_same_theme_card_with_text_takes_the_empty_seat():
    rules = _rules()
    calls = []

    def reader(card):
        calls.append(card["technology"])
        return _read(_out(verified={"P01"}, transition="supported"))

    empty = _card("poster", theme="a", url="https://example.test/poster", snippet="")
    silent = _card("also-empty", theme="a", url="https://example.test/empty", snippet="")
    nxt = _card("with-text", theme="a", url="https://arxiv.org/abs/1")
    other = _card("other-theme", theme="b", url="https://arxiv.org/abs/2")
    result = apply_checklist([empty], [silent, other, nxt], reader, rules)
    assert calls == ["with-text"]
    assert result["top"][0]["technology"] == "with-text"
    assert result["unread"][0]["seat_replaced"] is True
    assert [row["technology"] for row in result["overflow"]] == ["also-empty", "other-theme"]


def test_reader_exception_stays_unevaluated_not_noise():
    rules = _rules()
    card = _card()
    card["label"] = "watchlist"

    def reader(_c):
        raise RuntimeError("down")

    result = apply_checklist([card], [], reader, rules)
    assert result["top"][0]["checklist"]["status"] == "reader_failed"
    assert result["top"][0]["label"] is None
    assert result["top"][0]["confidence"] is None
    assert result["top"][0]["predictors"] == []


def test_backfill_same_theme_in_order():
    rules = _rules()
    calls = []

    def reader(card):
        calls.append(card["technology"])
        if card["technology"] == "drop-me":
            return _read(_out(counters={"M01": "лидеры"}))
        return _read(_out(verified={"P01"}, transition="supported"))

    top = [_card("drop-me", theme="a", url="https://arxiv.org/abs/1")]
    overflow = [
        _card("beta", theme="b", url="https://arxiv.org/abs/2"),
        _card("alpha-next", theme="a", url="https://arxiv.org/abs/3"),
    ]
    result = apply_checklist(top, overflow, reader, rules)
    assert "beta" not in calls
    assert result["top"][0]["technology"] == "alpha-next"
    assert result["overflow"][0]["technology"] == "beta"


def test_backfill_cap_5():
    rules = _rules()
    calls = []

    def reader(card):
        calls.append(card["technology"])
        return _read(_out(counters={"M01": "лидеры"}))

    top = [_card(f"top-{index}", theme=f"t{index}", url=f"https://arxiv.org/abs/t{index}") for index in range(15)]
    overflow = [_card(f"over-{index}", theme=f"t{index}", url=f"https://arxiv.org/abs/o{index}") for index in range(7)]
    result = apply_checklist(top, overflow, reader, rules)
    assert len(calls) == 20
    assert result["stats"]["backfill"] == 5
    assert result["top"] == []
    assert len(result["overflow"]) == 2


def test_empty_seat_replacement_respects_cap_before_pop():
    rules = _rules()
    empty = _card("poster", theme="a", url="https://example.test/poster", snippet="")
    nxt = _card("with-text", theme="a", url="https://arxiv.org/abs/1")
    result = apply_checklist([empty], [nxt], lambda _c: _read(_out(verified={"P01"})), rules, backfill_cap=0)
    assert result["top"] == []
    assert result["overflow"][0]["technology"] == "with-text"
    assert result["unread"][0]["confidence"] is None
    assert result["unread"][0].get("seat_replaced") is not True


def test_one_replacement_attempt_per_theme():
    rules = _rules()
    calls = []

    def reader(card):
        calls.append(card["technology"])
        return _read(_out(verified={"P01"}, transition="supported"))

    seats = [
        _card("empty-1", theme="a", url="https://example.test/1", snippet=""),
        _card("empty-2", theme="a", url="https://example.test/2", snippet=""),
    ]
    overflow = [
        _card("text-1", theme="a", url="https://arxiv.org/abs/1"),
        _card("text-2", theme="a", url="https://arxiv.org/abs/2"),
    ]
    result = apply_checklist(seats, overflow, reader, rules)
    assert calls == ["text-1"]
    assert [row["technology"] for row in result["overflow"]] == ["text-2"]


def test_no_duplicate_identity_across_top_and_exclusions():
    rules = _rules()
    card = _card("kept", url="https://arxiv.org/abs/same")
    copy = _card("copy", url="https://arxiv.org/abs/same")
    result = apply_checklist([card], [copy], lambda _c: _read(_out(verified={"P01"})), _rules())
    top_ids = {_identity(row) for row in result["top"]}
    for row in result["excluded"] + result["overflow"]:
        assert _identity(row) not in top_ids


def test_case_quote_only_from_cited_fragment():
    quoted = _case_quote(
        _out(verified={"P03"}, primary="P03", p03_why="подтверждено [2]"),
        ["первый", "второй фрагмент"],
        ["https://a/1", "https://a/2"],
    )
    assert quoted["text"] == "второй фрагмент"
    assert quoted["url"] == "https://a/2"
    supported = _out(primary="P01", verified={"P01"})
    for feature in supported["features"]:
        if feature["code"] == "P03":
            feature["status"] = "supported"
            feature["why"] = "без ссылки"
    assert _case_quote(supported, ["первый"], ["https://a/1"]) is None
    views = candidate_views([{
        "technology": "имя",
        "reach": {"plain": "в гипотезе назван кейс"},
        "case_quote": {"text": "второй фрагмент"},
    }])
    assert views[0]["case"] == "Цитата источника: второй фрагмент"
    bare = candidate_views([{"technology": "имя", "reach": {"plain": "в гипотезе назван кейс"}}])
    assert bare[0]["case"].startswith("Кейс")


def test_checklist_does_not_touch_scope():
    card = _card()
    result = apply_checklist([card], [], lambda _c: _read(_out(verified={"P01"})), _rules())
    assert result["top"][0]["scope"] == 2
    assert result["top"][0]["scope_why"] == "как было"


def test_confident_counts_only_scored_above_075():
    report = RunReport(
        id="x", query="q", idempotency_key="k", repeated=False, steps=[], sources=[], events=[],
        card={
            "label": "noise", "confidence": 0, "policy_action": "WATCHLIST",
            "policy_reason": "evidence_gates_passed", "reason_codes": [], "predictors": [],
            "rules_version": "rules-0.1",
        },
        top=[
            {"confidence": 0.78, "checklist": {"status": "scored"}, "predictors": [{"code": "P01"}]},
            {"confidence": 0.62, "checklist": {"status": "scored"}},
            {"confidence": 0.9, "checklist": {"status": "no_fragment"}},
            {"confidence": 0.99},
        ],
        shortfall=11, exclusion_registry=[],
    )
    body = public_report(report)
    assert body["counters"]["confident"] == 1
    shown = run_banner(body)
    assert any("75%" in line and "1" in line for line in shown)
    hidden = run_banner({"top": [{"confidence": 0}], "counters": {"admitted": 1, "sources": 1, "confident": 0}})
    assert any("не применимо" in line for line in hidden)


def test_reader_marks_a_different_mechanism_after_the_text():
    card = _card()
    out = _out(verified={"P01"}, transition="supported")
    out["one_line_ru"] = "ДРУГОЙ_МЕХАНИЗМ: это про цинк, не про натрий"
    judged = score_card(card, lambda _c: _read(out), _rules())
    assert judged["keep"] is False
    assert judged["card"]["policy_reason"] == "other_mechanism_after_read"


def test_a_line_without_the_marker_keeps_the_card():
    card = _card()
    out = _out(verified={"P01"}, transition="supported")
    out["one_line_ru"] = "тот же механизм, другие слова"
    judged = score_card(card, lambda _c: _read(out), _rules())
    assert judged["keep"] is True


def test_operator_query_is_absent_from_dataset_text():
    from ts.extract import candidate_text

    bare = candidate_text({"technology": "ячейка", "fragments": ["текст"]})
    assert "Запрос оператора" not in bare
    asked = candidate_text({"technology": "ячейка", "fragments": ["текст"], "query": "натриевая ячейка"})
    assert "Запрос оператора" in asked and "ДРУГОЙ_МЕХАНИЗМ" in asked


def test_untitled_theme_may_take_more_than_one_replacement():
    calls = []

    def reader(card):
        calls.append(card["technology"])
        return _read(_out(verified={"P01"}, transition="supported"))

    seats = [
        _card("empty-1", theme=None, url="https://example.test/1", snippet=""),
        _card("empty-2", theme=None, url="https://example.test/2", snippet=""),
    ]
    overflow = [
        _card("text-1", theme=None, url="https://arxiv.org/abs/1"),
        _card("text-2", theme=None, url="https://arxiv.org/abs/2"),
    ]
    result = apply_checklist(seats, overflow, reader, _rules())
    assert calls == ["text-1", "text-2"]
    assert [row["technology"] for row in result["top"]] == ["text-1", "text-2"]


def test_weights_thresholds_unchanged():
    rules = _rules()
    assert rules["weights"]["primary"] == 0.35
    assert rules["thresholds"]["weak_signal"] == 0.60
    assert rules["thresholds"]["watchlist"] == 0.35
    assert rules["modes"]["description"]["thresholds"]["weak_signal"] == 0.30
