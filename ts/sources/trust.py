"""Map a URL to a trust level from data/source_trust.yaml (TZ-07)."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "source_trust.yaml"
PROFESSIONAL_TYPES = frozenset({"industry_media", "analyst_report"})


def load_trust(path: Path = DEFAULT_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def classify(url: str, source_type: str, table: dict | None = None) -> str:
    """primary / professional / indicator. Unknown host follows the yaml rules block."""
    table = table or load_trust()
    host = _host(url)
    for level, spec in table["levels"].items():
        for domain in spec.get("domains", []):
            domain = domain.split("(", 1)[-1].rstrip(") ").strip() if "(" in domain else domain.strip()
            if host == domain or host.endswith("." + domain):
                if domain == "github.com" and source_type != "repository":
                    return "indicator"
                return level
    if source_type in PROFESSIONAL_TYPES:
        return "professional"
    return "indicator"
