"""LLM-01 invariants: ZDR policy on every request, TZ allowlist, provider must be ZDR-listed."""
from __future__ import annotations

import json
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


def test_model_outside_tz_list_rejected(tmp_path):
    c = make_client(tmp_path)
    with pytest.raises(llm_mod.ModelNotAllowed):
        c.chat([{"role": "user", "content": "x"}], model="openrouter/auto")


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
