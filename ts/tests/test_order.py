"""Ordering never changes who is admitted."""
from ts.harness import rank
from ts.scoring.order import evidence_strength


def _card(name, action, label, predictors):
    return {
        "technology": name,
        "policy_action": action,
        "label": label,
        "predictors": predictors,
    }


def test_three_confirmed_signs_outrank_one_and_the_primary_label_does_not_matter():
    one = [{"code": "P01", "value": "verified", "kind": "primary"}]
    three = [
        {"code": "P09", "value": "supported", "kind": "secondary"},
        {"code": "P02", "value": "verified", "kind": "secondary"},
        {"code": "P06", "value": "verified", "kind": "primary"},
    ]
    assert evidence_strength(three) > evidence_strength(one)
    swapped = [
        {"code": "P06", "value": "verified", "kind": "secondary"},
        {"code": "P02", "value": "verified", "kind": "primary"},
        {"code": "P09", "value": "supported", "kind": "secondary"},
    ]
    assert evidence_strength(swapped) == evidence_strength(three)


def test_rank_keeps_noise_out_and_only_reorders_the_admitted():
    noise = _card("шум", "WATCHLIST", "noise", [{"code": "P01", "value": "verified"}])
    weak = _card("один", "RANK_ELIGIBLE", "weak_signal", [{"code": "P01", "value": "verified"}])
    stronger = _card("три", "RANK_ELIGIBLE", "weak_signal", [
        {"code": "P01", "value": "verified"},
        {"code": "P02", "value": "verified"},
        {"code": "P06", "value": "supported"},
    ])
    top, excluded = rank([noise, weak, stronger])
    assert [row["technology"] for row in top] == ["три", "один"]
    assert [row["technology"] for row in excluded] == ["шум"]
