"""Product wiring for the default-off bounded adversarial review."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace

from ts.llm import MANDATORY_PROVIDER_POLICY, LLMError, OpenRouterClient
from ts.review.arbiter import ARBITER_RULE_VERSION
from ts.review.contracts import EvidenceItem, RoleName
from ts.review.prompts import REVIEW_PROMPT_VERSION
from ts.review.runner import (
    REVIEW_CONTRACT_VERSION,
    OpenRouterRoleGateway,
    ReviewModels,
    ReviewRound,
    RoleBudget,
    run_review,
)

REVIEW_INTEGRATION_VERSION = "review-integration-0.1"
_ORIGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/() -]{0,127}$")


def review_configuration_fingerprint(settings, *, enabled: bool | None = None) -> str:
    """Hash every review setting that changes run semantics, never a secret."""
    body = {
        "version": REVIEW_INTEGRATION_VERSION,
        "contract": REVIEW_CONTRACT_VERSION,
        "prompt": REVIEW_PROMPT_VERSION,
        "arbiter": ARBITER_RULE_VERSION,
        "enabled": (
            bool(getattr(settings, "adversarial_review_enabled", False))
            if enabled is None else bool(enabled)
        ),
        "primary_model": str(getattr(settings, "llm_primary", "")),
        "judge_model": str(getattr(settings, "llm_judge", "")),
        "time_seconds": repr(getattr(settings, "review_time_seconds", 45.0)),
        "max_output_tokens": repr(getattr(settings, "review_max_output_tokens", 1200)),
        "max_cost_usd": repr(getattr(settings, "review_max_cost_usd", 0.03)),
        "evidence_limit": repr(getattr(settings, "review_evidence_limit", 12)),
        "mandatory_provider_policy": MANDATORY_PROVIDER_POLICY,
        "configured_provider_policy": getattr(settings, "llm_provider_policy", None),
        "allowed_models": sorted(str(row) for row in getattr(settings, "allowed_models", ())),
        "openrouter_url": str(getattr(settings, "openrouter_url", "")),
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _safe_origin(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _ORIGIN_ID.fullmatch(value) else None


def _source_urls(source: Mapping) -> set[str]:
    urls = {str(source.get("url") or "")}
    evidence = source.get("evidence")
    if isinstance(evidence, Mapping):
        urls.add(str(evidence.get("fetched_url") or ""))
    return {url for url in urls if url}


def _explicit_origin(candidate: Mapping, url: str) -> str | None:
    """Use only explicit DOI/ROR/work identity; never infer independence by hostname."""
    for bucket in ("sources", "counter_sources"):
        for source in candidate.get(bucket) or []:
            if not isinstance(source, Mapping) or url not in _source_urls(source):
                continue
            origin_ids = source.get("origin_ids")
            if isinstance(origin_ids, Sequence) and not isinstance(origin_ids, (str, bytes)):
                for origin_id in origin_ids:
                    safe = _safe_origin(origin_id)
                    if safe:
                        return safe
            doi = str(source.get("doi") or "").strip().lower()
            for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
                if doi.startswith(prefix):
                    doi = doi[len(prefix):]
                    break
            safe_doi = _safe_origin(f"doi:{doi}") if doi else None
            if safe_doi:
                return safe_doi
    return None


class CandidateEvidenceProvider:
    """Replays the exact checklist-attested bundle equally to every role."""

    def __init__(self, candidate: Mapping):
        self.candidate = candidate

    def retrieve(
        self,
        role: RoleName,
        candidate: Mapping,
        budget: RoleBudget,
    ) -> Sequence[EvidenceItem]:
        _ = role, budget
        if candidate is not self.candidate and dict(candidate) != dict(self.candidate):
            raise ValueError("review evidence provider candidate mismatch")
        fragments = candidate.get("evidence_fragments")
        if not isinstance(fragments, list):
            raise TypeError("candidate has no typed checklist evidence bundle")
        rows = []
        for index, fragment in enumerate(fragments, start=1):
            if not isinstance(fragment, Mapping):
                raise TypeError("candidate evidence fragment is malformed")
            quote = fragment.get("text")
            url = fragment.get("url")
            if not isinstance(quote, str) or not quote.strip() or not isinstance(url, str) or not url:
                raise ValueError("candidate evidence fragment lacks text or URL")
            raw_provenance = fragment.get("provenance")
            provenance = (
                raw_provenance
                if raw_provenance in {"preserved_primary", "preserved_non_primary"}
                else "snippet_only"
            )
            snapshot_ref = fragment.get("snapshot_ref")
            if not isinstance(snapshot_ref, str):
                snapshot_ref = None
            if provenance == "preserved_primary" and snapshot_ref is None:
                raise ValueError("primary review evidence lacks snapshot attestation")
            identity = {
                "version": REVIEW_INTEGRATION_VERSION,
                "index": index,
                "quote_hash": hashlib.sha256(quote.encode()).hexdigest(),
                "url": url,
                "snapshot_ref": snapshot_ref,
            }
            evidence_id = "evidence-" + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(),
            ).hexdigest()[:40]
            rows.append(EvidenceItem(
                evidence_id=evidence_id,
                quote=quote,
                url=url,
                provenance=provenance,
                snapshot_ref=snapshot_ref,
                origin_group_id=_explicit_origin(candidate, url),
            ))
        return rows


class _UnavailableGateway:
    """Turn local client configuration failure into the normal four-event HOLD."""

    def call(self, *_args, **_kwargs):
        raise LLMError("review gateway unavailable")


def _role_budget(settings) -> RoleBudget:
    return RoleBudget(
        time_seconds=float(getattr(settings, "review_time_seconds", 45.0)),
        max_output_tokens=int(getattr(settings, "review_max_output_tokens", 1200)),
        max_cost_usd=float(getattr(settings, "review_max_cost_usd", 0.03)),
        evidence_limit=int(getattr(settings, "review_evidence_limit", 12)),
    )


def attach_candidate_review(
    report,
    settings,
    *,
    gateway=None,
    evidence_provider=None,
):
    """Return a report with one review round, or an explicit safe skip."""
    if not bool(getattr(settings, "adversarial_review_enabled", False)):
        return replace(
            report,
            review=None,
            review_enabled=False,
            review_status="disabled",
        )
    if not report.top:
        return replace(
            report,
            review=None,
            review_enabled=True,
            review_status="skipped_no_candidate",
        )
    if gateway is None:
        try:
            gateway = OpenRouterRoleGateway(OpenRouterClient(settings))
        except Exception:  # noqa: BLE001 - local construction failures become HOLD
            gateway = _UnavailableGateway()
    try:
        budget = _role_budget(settings)
    except (TypeError, ValueError, OverflowError):
        gateway = _UnavailableGateway()
        budget = RoleBudget(
            time_seconds=1.0,
            max_output_tokens=1,
            max_cost_usd=0.000001,
            evidence_limit=1,
        )
    evidence_provider = evidence_provider or CandidateEvidenceProvider(report.card)
    round_ = run_review(
        run_id=report.id,
        candidate=report.card,
        gateway=gateway,
        evidence_provider=evidence_provider,
        budget=budget,
        models=ReviewModels(
            primary=str(getattr(settings, "llm_primary", "")),
            judge=str(getattr(settings, "llm_judge", "")),
        ),
    )
    return replace(
        report,
        review=round_,
        review_enabled=True,
        review_status="completed",
    )


def public_review_trace(report) -> dict:
    """Safe activity view: no prompts, prose payloads, quotes, URLs or reasoning."""
    body = {
        "enabled": bool(getattr(report, "review_enabled", False)),
        "status": str(getattr(report, "review_status", "disabled")),
    }
    review = getattr(report, "review", None)
    if not isinstance(review, ReviewRound):
        return body
    body.update({
        "verdict": review.decision.verdict,
        "ledger_revision": review.ledger_revision,
        "blocking_ids": list(review.decision.blocking_ids),
        "reason_codes": list(review.decision.reason_codes),
        "events": [
            {
                "event_id": event.event_id,
                "role": event.role,
                "state": event.state,
                "tool_category": "deterministic" if event.role == "arbiter" else "model",
                "model_id": event.model_id,
                "provider": event.provider,
                "evidence_ids": list(event.evidence_ids),
                "duration_ms": event.duration_ms,
                "prompt_tokens": event.prompt_tokens,
                "completion_tokens": event.completion_tokens,
                "total_tokens": event.total_tokens,
                "cost_usd": event.cost_usd,
                "error_code": event.error_code,
            }
            for event in review.events
        ],
    })
    return body
