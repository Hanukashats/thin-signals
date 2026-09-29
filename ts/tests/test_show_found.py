from ts.persist import show_found


def _card(technology: str, url: str, confidence: float) -> dict:
    return {"technology": technology, "confidence": confidence, "sources": [{"url": url}]}


def _excluded() -> list[dict]:
    return [
        _card("solid-state battery", "https://example.org/a", 0.1),
        _card("perovskite cell", "https://example.org/b", 0.1),
    ]


def _unread() -> list[dict]:
    return [_card("sodium anode", "https://example.org/c", 0.9)]


def test_wide_shows_excluded_then_unread():
    body = {
        "top": [],
        "signal_label": "watchlist",
        "confidence": None,
        "shortfall": 15,
        "fanout": {"direction": {"mode": "wide"}},
        "exclusion_registry": _excluded(),
        "unread": _unread(),
    }
    shown = show_found(body)
    top = shown["top"]
    assert len(top) == 3
    assert [card["technology"] for card in top] == ["solid-state battery", "perovskite cell", "sodium anode"]
    assert [card["confidence"] for card in top] == [0.1, 0.1, None]
    assert top[0]["shown"] == "excluded"
    assert top[1]["shown"] == "excluded"
    assert shown["signal_label"] == "watchlist"
    assert shown["confidence"] is None
    assert shown["shortfall"] == 12
    assert len(shown["exclusion_registry"]) == 2
    assert len(shown["unread"]) == 1


def test_narrow_keeps_excluded_out_of_top():
    body = {
        "top": [],
        "signal_label": "watchlist",
        "confidence": None,
        "shortfall": 15,
        "exclusion_registry": _excluded(),
        "unread": _unread(),
    }
    shown = show_found(body)
    top = shown["top"]
    assert len(top) == 1
    assert top[0]["technology"] == "sodium anode"
    assert top[0]["confidence"] is None
    assert "shown" not in top[0]
    assert shown["shortfall"] == 14
