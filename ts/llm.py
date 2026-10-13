"""OpenRouter client with the organizer-approved data policy (ARCHITECTURE §7, LLM-01).

Invariants enforced here, not by convention:
- every request carries provider policy {"zdr": true, "data_collection": "deny"} (+ TS_LLM_PROVIDER_POLICY);
- only TZ-listed model ids are accepted (Settings.allowed_models);
- the provider named in the response must be in OpenRouter's /endpoints/zdr list for that model,
  otherwise the response is rejected (ZDRViolation) — product mode never sees it;
- provider + model_id + usage are returned for the `runs` log.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import math
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from ts.settings import Settings, load

ZDR_CACHE_TTL_S = 6 * 3600
CACHE_POLICY_VERSION = "zdr-deny-v1"
MANDATORY_PROVIDER_POLICY = {"zdr": True, "data_collection": "deny"}
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class _AsyncRequestLoop:
    """One bounded event-loop worker; coroutine cancellation prevents late dispatch."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        threading.Thread(
            target=self._serve,
            name="thin-signals-http-loop",
            daemon=True,
        ).start()
        self._ready.wait()

    def _serve(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_default_executor(ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="thin-signals-dns",
        ))
        self._loop = loop
        self._ready.set()
        loop.run_forever()

    def run(self, coroutine, timeout_seconds: float):
        loop = self._loop
        if loop is None:
            raise RuntimeError("HTTP request loop did not start")
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=timeout_seconds + 0.025)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            # Ensure the loop observes cancellation before the caller proceeds;
            # a DNS executor may finish later, but its cancelled task cannot POST.
            barrier = asyncio.run_coroutine_threadsafe(asyncio.sleep(0), loop)
            try:
                barrier.result(timeout=0.025)
            except concurrent.futures.TimeoutError:
                barrier.cancel()
            raise TimeoutError("OpenRouter role deadline exceeded") from exc


_REQUEST_LOOP: _AsyncRequestLoop | None = None
_REQUEST_LOOP_LOCK = threading.Lock()


def _request_loop() -> _AsyncRequestLoop:
    global _REQUEST_LOOP
    if _REQUEST_LOOP is None:
        with _REQUEST_LOOP_LOCK:
            if _REQUEST_LOOP is None:
                _REQUEST_LOOP = _AsyncRequestLoop()
    return _REQUEST_LOOP


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
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.s = settings or load()
        if not self.s.openrouter_key:
            raise LLMError("OpenRouter key missing: set TS_OPENROUTER_KEY_FILE")
        if transport is not None and not isinstance(transport, httpx.AsyncBaseTransport):
            raise TypeError("OpenRouter transport must support asynchronous cancellation")
        self._base_url = self.s.openrouter_url
        self._headers = {
            "Authorization": f"Bearer {self.s.openrouter_key}",
            "HTTP-Referer": "https://thin-signals.local",
            "X-Title": "Thin Signals",
        }
        self._transport = transport
        self._resolved: tuple[float, str] | None = None
        self._resolved_lock = threading.Lock()
        self._zdr: dict[str, set[str]] | None = None
        self._zdr_at = 0.0

    async def _resolved_target(self, path: str) -> tuple[str, dict[str, str], dict]:
        """Resolve once before dispatch so cancelled DNS cannot later send a request."""
        parsed = urlsplit(self._base_url)
        if self._transport is not None:
            target_path = f"{parsed.path.rstrip('/')}/{path.lstrip('/')}"
            return urlunsplit((parsed.scheme, parsed.netloc, target_path, "", "")), {}, {}
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host:
            raise LLMError("OpenRouter URL must be absolute HTTP(S)")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        now = time.monotonic()
        with self._resolved_lock:
            cached = self._resolved
        if cached is not None and cached[0] > now:
            address = cached[1]
        else:
            rows = await asyncio.get_running_loop().getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            if not rows:
                raise LLMError("OpenRouter host did not resolve")
            address = rows[0][4][0]
            with self._resolved_lock:
                self._resolved = (time.monotonic() + 300.0, address)
        netloc = f"[{address}]" if ":" in address else address
        if port != (443 if parsed.scheme == "https" else 80):
            netloc = f"{netloc}:{port}"
        target_path = f"{parsed.path.rstrip('/')}/{path.lstrip('/')}"
        host_header = host
        if port != (443 if parsed.scheme == "https" else 80):
            host_header = f"{host}:{port}"
        return (
            urlunsplit((parsed.scheme, netloc, target_path, "", "")),
            {"Host": host_header},
            {"sni_hostname": host},
        )

    async def _request_json_async(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float,
        body: dict | None = None,
    ) -> tuple[int, dict]:
        timeout = httpx.Timeout(
            timeout_seconds,
            connect=min(15.0, timeout_seconds),
        )
        async with asyncio.timeout(timeout_seconds):
            target, target_headers, extensions = await self._resolved_target(path)
            async with httpx.AsyncClient(
                headers=self._headers,
                timeout=timeout,
                transport=self._transport,
            ) as client, client.stream(
                method,
                target,
                json=body,
                headers=target_headers,
                extensions=extensions,
            ) as response:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise LLMError("OpenRouter response is too large")
                return response.status_code, json.loads(raw)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float | None,
        body: dict | None = None,
    ) -> tuple[int, dict]:
        if timeout_seconds is None:
            timeout_seconds = 120.0
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise TimeoutError("OpenRouter role deadline exceeded")
        return _request_loop().run(
            self._request_json_async(
                method,
                path,
                timeout_seconds=float(timeout_seconds),
                body=body,
            ),
            float(timeout_seconds),
        )

    # -- ZDR endpoint registry ------------------------------------------------------------------
    def zdr_providers(
        self,
        force: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, set[str]]:
        """model_id -> set(provider_name) for endpoints OpenRouter marks as ZDR."""
        if self._zdr is None or force or time.time() - self._zdr_at > ZDR_CACHE_TTL_S:
            status_code, data = self._request_json(
                "GET",
                "/endpoints/zdr",
                timeout_seconds=timeout_seconds,
            )
            if status_code >= 400 or "error" in data:
                raise LLMError(
                    f"OpenRouter {status_code}: "
                    f"{json.dumps(data.get('error', data), ensure_ascii=False)[:400]}"
                )
            reg: dict[str, set[str]] = {}
            for e in data.get("data", []):
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
        started = time.monotonic()
        deadline_at = (
            started + timeout_seconds if timeout_seconds is not None else None
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
        request_timeout = remaining()
        try:
            status_code, data = self._request_json(
                "POST",
                "/chat/completions",
                timeout_seconds=request_timeout,
                body=body,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("OpenRouter role deadline exceeded") from exc
        if status_code >= 400 or "error" in data:
            raise LLMError(f"OpenRouter {status_code}: {json.dumps(data.get('error', data), ensure_ascii=False)[:400]}")
        provider = data.get("provider", "")
        model_id = data.get("model", model)
        if model_id != model:
            raise ModelNotAllowed(
                f"response model {model_id!r} does not match requested model {model!r}"
            )
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
            latency_s=round(time.monotonic() - started, 3),
            raw=data,
        )

    def probe(self, model: str | None = None) -> LLMResponse:
        return self.chat(
            [{"role": "user", "content": "Ответь одним словом без знаков препинания: столица Франции?"}],
            model,
            max_tokens=20,
        )
