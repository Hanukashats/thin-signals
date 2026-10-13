"""LLM-01 invariants: ZDR policy on every request, TZ allowlist, provider must be ZDR-listed."""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest

from ts import llm as llm_mod
from ts.settings import Settings

ZDR = {"data": [
    {"model_id": "qwen/qwen3.6-35b-a3b", "provider_name": "DeepInfra"},
    {"model_id": "qwen/qwen3.6-35b-a3b", "provider_name": "Venice"},
    {"model_id": "openai/gpt-5.6-luna", "provider_name": "Azure"},
    {"model_id": "qwen/qwen3-235b-a22b-2507", "provider_name": "Novita"},
    {"model_id": "openai/gpt-4.1", "provider_name": "Azure"},
]}


def settings(tmp_path: Path) -> Settings:
    key = tmp_path / "k"
    key.write_text("sk-test")
    return Settings(root=tmp_path, profile="laptop", database_url="postgresql+psycopg://ts@x/db", pg_password=None,
                    rules_version="rules-0.1", snapshot_dir=tmp_path, openrouter_url="https://or.test/api/v1",
                    openrouter_key="sk-test", llm_primary="qwen/qwen3.6-35b-a3b", llm_judge="openai/gpt-5.6-luna",
                    llm_fallback="qwen/qwen3-235b-a22b-2507",
                    llm_provider_policy={"zdr": True, "data_collection": "deny"})


def make_client(tmp_path, provider="Venice", model="qwen/qwen3.6-35b-a3b", seen: list | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/endpoints/zdr"):
            return httpx.Response(200, json=ZDR)
        body = json.loads(req.content)
        if seen is not None:
            seen.append(body)
        return httpx.Response(200, json={"model": model, "provider": provider,
                                         "choices": [{"message": {"content": "Париж"}}],
                                         "usage": {"total_tokens": 12}})
    return llm_mod.OpenRouterClient(settings(tmp_path), transport=httpx.MockTransport(handler))


def test_policy_sent_on_every_request(tmp_path):
    seen: list = []
    c = make_client(tmp_path, seen=seen)
    r = c.probe()
    assert r.provider == "Venice" and r.model_id == "qwen/qwen3.6-35b-a3b" and r.content == "Париж"
    assert seen[0]["provider"] == {"zdr": True, "data_collection": "deny", "require_parameters": False}
    assert seen[0]["reasoning"] == {"enabled": False, "exclude": True}


def test_security_policy_cannot_be_weakened_from_settings(tmp_path):
    seen: list = []
    c = make_client(tmp_path, seen=seen)
    c.s.llm_provider_policy = {
        "zdr": False,
        "data_collection": "allow",
        "allow_fallbacks": False,
    }

    c.probe()

    assert seen[0]["provider"] == {
        "zdr": True,
        "data_collection": "deny",
        "allow_fallbacks": False,
        "require_parameters": False,
    }


def test_model_outside_tz_list_rejected(tmp_path):
    c = make_client(tmp_path)
    with pytest.raises(llm_mod.ModelNotAllowed):
        c.chat([{"role": "user", "content": "x"}], model="openrouter/auto")


def test_unallowed_model_returned_by_provider_is_rejected_before_zdr_lookup(tmp_path):
    c = make_client(tmp_path, model="untrusted/surprise-model")
    lookups = 0

    def zdr_once(force=False, timeout_seconds=None):
        _ = force, timeout_seconds
        nonlocal lookups
        lookups += 1
        if lookups > 1:
            raise AssertionError("returned unallowed model reached provider ZDR lookup")
        return {"qwen/qwen3.6-35b-a3b": {"Venice"}}

    c.zdr_providers = zdr_once

    with pytest.raises(llm_mod.ModelNotAllowed):
        c.probe()
    assert lookups == 1


def test_role_timeout_covers_registry_and_completion_requests(tmp_path):
    timeouts = []

    def handler(req: httpx.Request) -> httpx.Response:
        timeouts.append(dict(req.extensions.get("timeout") or {}))
        if req.url.path.endswith("/endpoints/zdr"):
            return httpx.Response(200, json=ZDR)
        return httpx.Response(200, json={
            "model": "qwen/qwen3.6-35b-a3b",
            "provider": "Venice",
            "choices": [{"message": {"content": "Париж"}}],
            "usage": {"total_tokens": 12},
        })

    client = llm_mod.OpenRouterClient(
        settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    client.chat(
        [{"role": "user", "content": "x"}],
        timeout_seconds=0.5,
    )

    assert len(timeouts) == 2
    assert all(timeout for timeout in timeouts)
    assert all(
        0 < value <= 0.5
        for timeout in timeouts
        for value in timeout.values()
        if value is not None
    )


def test_registry_time_consumes_the_shared_role_deadline(tmp_path, monkeypatch):
    ticks = iter((0.0, 0.1, 0.6))
    paths = []

    class Clock:
        @staticmethod
        def monotonic():
            return next(ticks)

        @staticmethod
        def time():
            return 0.0

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return httpx.Response(200, json=ZDR)

    monkeypatch.setattr(llm_mod, "time", Clock)
    client = llm_mod.OpenRouterClient(
        settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(TimeoutError, match="role deadline"):
        client.chat(
            [{"role": "user", "content": "x"}],
            timeout_seconds=0.5,
        )

    assert paths == ["/api/v1/endpoints/zdr"]


class SlowStream(httpx.SyncByteStream):
    def __init__(self, payload: bytes, delay_seconds: float = 0.02):
        self.payload = payload
        self.delay_seconds = delay_seconds

    def __iter__(self):
        for byte in self.payload:
            time.sleep(self.delay_seconds)
            yield bytes([byte])


def test_registry_slow_stream_is_abandoned_at_absolute_deadline(tmp_path):
    payload = json.dumps(ZDR).encode()

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=SlowStream(payload))

    client = llm_mod.OpenRouterClient(
        settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="role deadline"):
        client.zdr_providers(timeout_seconds=0.05)

    assert time.monotonic() - started < 0.15


def test_completion_slow_stream_is_abandoned_at_absolute_deadline(tmp_path):
    payload = json.dumps({
        "model": "qwen/qwen3.6-35b-a3b",
        "provider": "Venice",
        "choices": [{"message": {"content": "Париж"}}],
        "usage": {"total_tokens": 12},
    }).encode()

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=SlowStream(payload))

    client = llm_mod.OpenRouterClient(
        settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    client._zdr = {"qwen/qwen3.6-35b-a3b": {"Venice"}}
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="role deadline"):
        client.chat(
            [{"role": "user", "content": "x"}],
            timeout_seconds=0.05,
        )

    assert time.monotonic() - started < 0.15


def test_non_zdr_provider_in_response_rejected(tmp_path):
    c = make_client(tmp_path, provider="SomeLogger")
    with pytest.raises(llm_mod.ZDRViolation):
        c.probe()


def test_json_schema_strict(tmp_path):
    seen: list = []
    c = make_client(tmp_path, seen=seen)
    schema = {"title": "x", "type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"],
              "additionalProperties": False}
    c.chat([{"role": "user", "content": "x"}], json_schema=schema)
    rf = seen[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True and rf["json_schema"]["name"] == "x"


def test_gpt5_gets_no_temperature_or_reasoning_block(tmp_path):
    seen: list = []
    c = make_client(tmp_path, seen=seen, provider="Azure", model="openai/gpt-5.6-luna")
    c.chat([{"role": "user", "content": "x"}], model="openai/gpt-5.6-luna")
    assert "temperature" not in seen[0] and "reasoning" not in seen[0]
