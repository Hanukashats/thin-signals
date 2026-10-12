"""Bounded adapter for the pinned GPT Researcher synchronous API.

The generated report is deliberately discarded.  Its URLs are discovery leads
only; a caller-supplied re-fetch/validation function must turn a lead into a
``Hit`` before the harness can see it.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import replace

from ts.sources.connectors import ConnectorError, Hit, Post

Refetch = Callable[[str], Hit | None]
ADAPTER_VERSION = "gpt-researcher-advisory-0.1"


def _safe_research_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError("GPT Researcher response has no research id")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())[:128]
    if not cleaned:
        raise ConnectorError("GPT Researcher response has an invalid research id")
    return cleaned


def _cost(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConnectorError("GPT Researcher response has no numeric research cost")
    result = float(value)
    if result < 0 or not math.isfinite(result):
        raise ConnectorError("GPT Researcher response has an invalid research cost")
    return result


def _artifact_refs(data: dict) -> list[str]:
    refs = []
    for key in ("docx_path", "pdf_path"):
        value = data.get(key)
        if isinstance(value, str) and value:
            refs.append(hashlib.sha256(value.encode()).hexdigest()[:16])
    return refs


class GptResearcherConnector:
    """One synchronous research request with post-run spend enforcement.

    The upstream v3.7.0 API has no request-level hard cost parameter.  The
    configured ceiling therefore fails closed on the reported cost and prevents
    any lead from entering the product; the global transport deadline remains
    the hard runtime bound.
    """

    name = "gpt_researcher"
    search_stages = frozenset({"search"})

    def __init__(
        self,
        base_url: str,
        post: Post,
        refetch: Refetch,
        *,
        max_cost_usd: float = 0.08,
        max_leads: int = 12,
    ):
        if max_cost_usd <= 0 or not math.isfinite(max_cost_usd):
            raise ValueError("max_cost_usd must be finite and positive")
        if max_leads < 1:
            raise ValueError("max_leads must be positive")
        self.base_url = base_url.rstrip("/")
        self.post = post
        self.refetch = refetch
        self.max_cost_usd = float(max_cost_usd)
        self.max_leads = int(max_leads)
        endpoint_hash = hashlib.sha256(self.base_url.encode()).hexdigest()[:8]
        self.retrieval_identity = (
            f"{self.name}:{ADAPTER_VERSION}:{endpoint_hash}:"
            f"{self.max_cost_usd:.6f}:{self.max_leads}"
        )
        self.last_metadata: dict = {}

    def search(self, query: str, *, limit: int = 5) -> list[Hit]:
        self.last_metadata = {}
        raw = self.post(
            f"{self.base_url}/report/",
            {
                "task": query,
                "report_type": "research_report",
                "report_source": "web",
                "tone": "Objective",
                "headers": {},
                "repo_name": "",
                "branch_name": "",
                "generate_in_background": False,
            },
        )
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ConnectorError("GPT Researcher returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ConnectorError("GPT Researcher answer is not an object")
        info = data.get("research_information")
        if not isinstance(info, dict):
            raise ConnectorError("GPT Researcher response has no research information")
        urls = info.get("source_urls")
        if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
            raise ConnectorError("GPT Researcher source URLs are invalid")
        research_id = _safe_research_id(data.get("research_id"))
        reported_cost = _cost(info.get("research_costs"))
        unique_urls = list(dict.fromkeys(url.strip() for url in urls if url.strip()))[: self.max_leads]
        artifacts = _artifact_refs(data)
        self.last_metadata = {
            "research_id": research_id,
            "reported_cost_usd": reported_cost,
            "advisory_count": len(unique_urls),
            "validated_count": 0,
            "artifact_refs": artifacts,
        }
        if reported_cost > self.max_cost_usd:
            raise ConnectorError("GPT Researcher reported cost exceeds configured limit")

        provenance = {
            "provider": "gpt-researcher",
            "research_id": research_id,
            "reported_cost_usd": reported_cost,
            "artifact_refs": artifacts,
        }
        accepted = []
        for url in unique_urls[: max(0, limit)]:
            try:
                hit = self.refetch(url)
            except (ConnectorError, OSError, TimeoutError, ValueError):
                hit = None
            if not isinstance(hit, Hit):
                continue
            accepted.append(replace(
                hit,
                connector=self.name,
                advisory_provenance=dict(provenance),
            ))
        self.last_metadata["validated_count"] = len(accepted)
        return accepted

    def public_metadata(self) -> dict:
        return dict(self.last_metadata)
