"""LLM-01 invariants: ZDR policy on every request, TZ allowlist, provider must be ZDR-listed."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

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
PROXY_ENV_DISABLED = {
    name: ""
    for name in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    )
}


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


def test_different_but_allowed_response_model_is_rejected(tmp_path):
    client = make_client(
        tmp_path,
        provider="Azure",
        model="openai/gpt-4.1",
    )

    with pytest.raises(llm_mod.ModelNotAllowed, match="does not match requested"):
        client.chat(
            [{"role": "user", "content": "x"}],
            model="qwen/qwen3.6-35b-a3b",
        )


def test_missing_response_model_is_rejected(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/endpoints/zdr"):
            return httpx.Response(200, json=ZDR)
        return httpx.Response(200, json={
            "provider": "Venice",
            "choices": [{"message": {"content": "Париж"}}],
            "usage": {"total_tokens": 12},
        })

    client = llm_mod.OpenRouterClient(
        settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(llm_mod.ModelNotAllowed, match="missing response model"):
        client.chat([{"role": "user", "content": "x"}])


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


class SlowStream(httpx.AsyncByteStream):
    def __init__(self, payload: bytes, delay_seconds: float = 0.02):
        self.payload = payload
        self.delay_seconds = delay_seconds

    async def __aiter__(self):
        for byte in self.payload:
            await asyncio.sleep(self.delay_seconds)
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


def test_timeout_during_dns_cannot_dispatch_a_late_completion(tmp_path):
    release_dns = Event()
    posts: list[float] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_POST(self):
            posts.append(time.monotonic())
            self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.dumps({
                "model": "qwen/qwen3.6-35b-a3b",
                "provider": "Venice",
                "choices": [{"message": {"content": "late"}}],
                "usage": {"total_tokens": 12},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    configured = settings(tmp_path)
    configured.openrouter_url = f"http://late-dns.test:{server.server_port}/api/v1"
    client = llm_mod.OpenRouterClient(configured)
    client._zdr = {"qwen/qwen3.6-35b-a3b": {"Venice"}}
    client._zdr_at = time.time()
    original = socket.getaddrinfo

    def paused_dns(host, port, *args, **kwargs):
        assert host in ("late-dns.test", b"late-dns.test")
        assert release_dns.wait(2)
        return original("127.0.0.1", port, *args, **kwargs)

    try:
        started = time.monotonic()
        with patch.dict(os.environ, PROXY_ENV_DISABLED), patch("socket.getaddrinfo", paused_dns):
            with pytest.raises(TimeoutError, match="role deadline"):
                client.chat(
                    [{"role": "user", "content": "x"}],
                    timeout_seconds=0.05,
                )
            assert time.monotonic() - started < 0.15
            release_dns.set()
            time.sleep(0.2)
        assert posts == []
    finally:
        release_dns.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_native_http_tries_later_dns_address_after_connect_failure(tmp_path):
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_POST(self):
            requests.append(self.headers["Host"])
            self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.dumps({
                "model": "qwen/qwen3.6-35b-a3b",
                "provider": "Venice",
                "choices": [{"message": {"content": "fallback"}}],
                "usage": {"total_tokens": 12},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    configured = settings(tmp_path)
    configured.openrouter_url = f"http://fallback.test:{server.server_port}/api/v1"
    client = llm_mod.OpenRouterClient(configured)
    client._zdr = {"qwen/qwen3.6-35b-a3b": {"Venice"}}
    client._zdr_at = time.time()

    def two_addresses(host, port, *args, **kwargs):
        assert host in ("fallback.test", b"fallback.test")
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.2", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port)),
        ]

    try:
        with patch.dict(os.environ, PROXY_ENV_DISABLED), patch("socket.getaddrinfo", two_addresses):
            response = client.chat(
                [{"role": "user", "content": "x"}],
                timeout_seconds=1.0,
            )
        assert response.content == "fallback"
        assert requests == [f"fallback.test:{server.server_port}"]
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_native_http_preserves_hostname_for_no_proxy(tmp_path):
    origin_requests: list[str] = []
    proxy_requests: list[str] = []

    class OriginHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_POST(self):
            origin_requests.append(self.headers["Host"])
            self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.dumps({
                "model": "qwen/qwen3.6-35b-a3b",
                "provider": "Venice",
                "choices": [{"message": {"content": "direct"}}],
                "usage": {"total_tokens": 12},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    class ProxyHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_POST(self):
            proxy_requests.append(self.path)
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"unexpected proxy"}')

    origin = ThreadingHTTPServer(("127.0.0.1", 0), OriginHandler)
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
    origin_thread = Thread(target=origin.serve_forever, daemon=True)
    proxy_thread = Thread(target=proxy.serve_forever, daemon=True)
    origin_thread.start()
    proxy_thread.start()
    configured = settings(tmp_path)
    configured.openrouter_url = f"http://no-proxy.test:{origin.server_port}/api/v1"
    client = llm_mod.OpenRouterClient(configured)
    client._zdr = {"qwen/qwen3.6-35b-a3b": {"Venice"}}
    client._zdr_at = time.time()
    proxy_env = {
        **PROXY_ENV_DISABLED,
        "HTTP_PROXY": f"http://127.0.0.1:{proxy.server_port}",
        "http_proxy": f"http://127.0.0.1:{proxy.server_port}",
        "NO_PROXY": "no-proxy.test",
        "no_proxy": "no-proxy.test",
    }

    def origin_address(host, port, *args, **kwargs):
        assert host in ("no-proxy.test", b"no-proxy.test")
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))]

    try:
        with patch.dict(os.environ, proxy_env), patch("socket.getaddrinfo", origin_address):
            response = client.chat(
                [{"role": "user", "content": "x"}],
                timeout_seconds=1.0,
            )
        assert response.content == "direct"
        assert origin_requests == [f"no-proxy.test:{origin.server_port}"]
        assert proxy_requests == []
    finally:
        origin.shutdown()
        proxy.shutdown()
        origin.server_close()
        proxy.server_close()
        origin_thread.join(timeout=2)
        proxy_thread.join(timeout=2)


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
