"""Choose the primary pattern from filled statuses.

The reader may name several signs. The primary is what is new, not who pays.
Unknown money, buyer, or grant fields do not erase a scientific sign.
"""
from __future__ import annotations

from ts.scoring.scorer import PATTERN_IDS

# Earlier in this list wins when more than one sign is supported or verified.
ORDER = (
    "P01", "P11", "P16", "P17",
    "P02",
    "P07", "P10", "P08", "P09",
    "P03", "P05", "P06",
    "P04", "P14", "P15", "P18", "P12", "P13",
)
_RECOGNIZED = frozenset({"supported", "verified"})


def banned_as_primary(recognized: set[str]) -> set[str]:
    """Signs that may stay secondary but must not be the primary."""
    banned: set[str] = set()
    if recognized & {"P01", "P02"}:
        banned.add("P06")
    if recognized & {"P01", "P02", "P07"}:
        banned.add("P04")
    if "P01" in recognized:
        banned.add("P18")
    return banned


def assign_primary(features: dict[str, str], proposed: str, secondary: list[str]) -> tuple[str, list[str]]:
    """Return (primary, secondary). If nothing is recognized, keep the proposal."""
    recognized = {code for code, status in features.items() if status in _RECOGNIZED and code in PATTERN_IDS}
    pool = recognized - banned_as_primary(recognized)
    if not pool:
        return proposed, [p for p in secondary if p in PATTERN_IDS and p != proposed][:3]
    primary = next(code for code in ORDER if code in pool)
    rest: list[str] = []
    for code in (proposed, *secondary):
        if code in PATTERN_IDS and code != primary and code not in rest:
            rest.append(code)
    for code in ORDER:
        if code in recognized and code != primary and code not in rest:
            rest.append(code)
        if len(rest) >= 3:
            break
    return primary, rest[:3]
