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


def _domains(spec: dict) -> list[str]:
    domains = []
    for domain in spec.get("domains", []):
        domain = domain.split("(", 1)[-1].rstrip(") ").strip() if "(" in domain else domain.strip()
        if domain:
            domains.append(domain)
    return domains


def _host_in(host: str, domains: list[str]) -> str | None:
    for domain in domains:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def classify(url: str, source_type: str, table: dict | None = None) -> str:
    """primary / professional / indicator. Unknown host follows the yaml rules block."""
    table = table or load_trust()
    host = _host(url)
    path = (urlparse(url).path or "").lower()
    levels = table["levels"]
    # A named retelling site stays a retelling even when the path contains a DOI.
    if _host_in(host, _domains(levels.get("indicator", {}))):
        return "indicator"
    for level in ("primary", "professional"):
        matched = _host_in(host, _domains(levels.get(level, {})))
        if matched:
            if matched == "github.com" and source_type != "repository":
                return "indicator"
            return level
    # A publisher page we have not listed yet is still the article when the DOI is in the path.
    if "/doi/10." in path or "/doi/abs/" in path:
        return "primary"
    if source_type in PROFESSIONAL_TYPES:
        return "professional"
    return "indicator"
