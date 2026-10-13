"""OpenRouter client with the organizer-approved data policy (ARCHITECTURE §7, LLM-01).

Invariants enforced here, not by convention:
- every request carries provider policy {"zdr": true, "data_collection": "deny"} (+ TS_LLM_PROVIDER_POLICY);
- only TZ-listed model ids are accepted (Settings.allowed_models);
- the provider named in the response must be in OpenRouter's /endpoints/zdr list for that model,
  otherwise the response is rejected (ZDRViolation) — product mode never sees it;
- provider + model_id + usage are returned for the `runs` log.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ts.settings import Settings, load

ZDR_CACHE_TTL_S = 6 * 3600
CACHE_POLICY_VERSION = "zdr-deny-v1"
MANDATORY_PROVIDER_POLICY = {"zdr": True, "data_collection": "deny"}


class LLMError(RuntimeError):
    pass


class ModelNotAllowed(LLMError):
    pass


class ZDRViolation(LLMError):
    pass


@dataclass
class LLMResponse:
    model_id: str
    provider: str
    content: str
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0
    raw: dict = field(default_factory=dict, repr=False)

    def json(self) -> Any:
        return json.loads(self.content)


def cache_attestation(response: LLMResponse) -> dict:
    """Metadata required before an LLM result may be reused without a new request."""
    return {
        "model_id": response.model_id,
        "provider": response.provider,
        "policy_version": CACHE_POLICY_VERSION,
        "provider_policy": dict(MANDATORY_PROVIDER_POLICY),
    }


def cached_response_is_current(client, meta: object, requested_model: str) -> bool:
    """Fail closed unless a cache proves the mandatory policy and its route is still allowed."""
    if not isinstance(meta, dict):
        return False
    if meta.get("policy_version") != CACHE_POLICY_VERSION:
        return False
    if meta.get("provider_policy") != MANDATORY_PROVIDER_POLICY:
        return False
    model_id = str(meta.get("model_id") or "")
    provider = str(meta.get("provider") or "")
    if not model_id or not provider or model_id != requested_model:
        return False
    try:
        client.validate_response_route(model_id, provider)
    except (LLMError, httpx.HTTPError, KeyError, TypeError, ValueError):
        return False
    return True


class OpenRouterClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None):
        self.s = settings or load()
        if not self.s.openrouter_key:
            raise LLMError("OpenRouter key missing: set TS_OPENROUTER_KEY_FILE")
        self._http = httpx.Client(
            base_url=self.s.openrouter_url,
            headers={
                "Authorization": f"Bearer {self.s.openrouter_key}",
                "HTTP-Referer": "https://thin-signals.local",
                "X-Title": "Thin Signals",
            },
            timeout=httpx.Timeout(120.0, connect=15.0),
            transport=transport,
        )
        self._zdr: dict[str, set[str]] | None = None
        self._zdr_at = 0.0

    # -- ZDR endpoint registry ------------------------------------------------------------------
    def zdr_providers(
        self,
        force: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, set[str]]:
        """model_id -> set(provider_name) for endpoints OpenRouter marks as ZDR."""
        if self._zdr is None or force or time.time() - self._zdr_at > ZDR_CACHE_TTL_S:
            options = {"timeout": timeout_seconds} if timeout_seconds is not None else {}
            r = self._http.get("/endpoints/zdr", **options)
            r.raise_for_status()
            reg: dict[str, set[str]] = {}
            for e in r.json().get("data", []):
                reg.setdefault(e["model_id"], set()).add(e["provider_name"])
            self._zdr, self._zdr_at = reg, time.time()
        return self._zdr

    def check_model(self, model: str, timeout_seconds: float | None = None) -> None:
        if model not in self.s.allowed_models:
            raise ModelNotAllowed(f"{model} is not in the TZ allowlist {self.s.allowed_models}")
        if model not in self.zdr_providers(timeout_seconds=timeout_seconds):
            raise ZDRViolation(f"{model} has no ZDR-capable endpoints on OpenRouter right now")

    def validate_response_route(
        self,
        model_id: str,
        provider: str,
        timeout_seconds: float | None = None,
    ) -> None:
        """Apply the same allowlist and live ZDR route check to network and cached responses."""
        if model_id not in self.s.allowed_models:
            raise ModelNotAllowed(f"response model {model_id!r} is not in the TZ allowlist {self.s.allowed_models}")
        allowed = self.zdr_providers(timeout_seconds=timeout_seconds).get(model_id, set())
        if provider not in allowed:
            raise ZDRViolation(f"response from provider {provider!r} for {model_id} is not in ZDR list {sorted(allowed)}")

    # -- chat -----------------------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        *,
        json_schema: dict | None = None,
        max_tokens: int = 2000,
        temperature: float | None = 0.0,
        reasoning: bool = False,
        require_parameters: bool = False,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        model = model or self.s.llm_primary
        deadline_at = (
            time.monotonic() + timeout_seconds if timeout_seconds is not None else None
        )

        def remaining() -> float | None:
            if deadline_at is None:
                return None
            value = deadline_at - time.monotonic()
            if value <= 0:
                raise TimeoutError("OpenRouter role deadline exceeded")
            return value

        try:
            self.check_model(model, timeout_seconds=remaining())
        except httpx.TimeoutException as exc:
            raise TimeoutError("OpenRouter role deadline exceeded") from exc
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "provider": {
                **self.s.llm_provider_policy,
                **MANDATORY_PROVIDER_POLICY,
                "require_parameters": require_parameters,
            },
        }
        if temperature is not None and not model.startswith("openai/gpt-5"):
            body["temperature"] = temperature
        if not reasoning and not model.startswith("openai/"):
            body["reasoning"] = {"enabled": False, "exclude": True}
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": json_schema.get("title", "result"), "strict": True, "schema": json_schema},
            }
        t0 = time.time()
        request_timeout = remaining()
        request_options = {"timeout": request_timeout} if request_timeout is not None else {}
        try:
            r = self._http.post("/chat/completions", json=body, **request_options)
        except httpx.TimeoutException as exc:
            raise TimeoutError("OpenRouter role deadline exceeded") from exc
        data = r.json()
        if r.status_code >= 400 or "error" in data:
            raise LLMError(f"OpenRouter {r.status_code}: {json.dumps(data.get('error', data), ensure_ascii=False)[:400]}")
        provider = data.get("provider", "")
        model_id = data.get("model", model)
        try:
            self.validate_response_route(
                model_id,
                provider,
                timeout_seconds=remaining(),
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("OpenRouter role deadline exceeded") from exc
        content = (data["choices"][0]["message"].get("content") or "").strip()
        return LLMResponse(
            model_id=model_id,
            provider=provider,
            content=content,
            usage=data.get("usage", {}),
            latency_s=round(time.time() - t0, 3),
            raw=data,
        )

    def probe(self, model: str | None = None) -> LLMResponse:
        return self.chat(
            [{"role": "user", "content": "Ответь одним словом без знаков препинания: столица Франции?"}],
            model,
            max_tokens=20,
        )
