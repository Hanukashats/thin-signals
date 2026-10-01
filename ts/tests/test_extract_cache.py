from __future__ import annotations

import json

from ts.extract import Extractor
from ts.llm import LLMResponse

MODEL = "qwen/qwen3.6-35b-a3b"
SAFE_PROVIDER = "SafeZDR"


class _Settings:
    llm_primary = MODEL
    allowed_models = (MODEL,)


class _Client:
    def __init__(self, payload: dict, *, fail_chat: bool = False):
        self.s = _Settings()
        self.payload = payload
        self.fail_chat = fail_chat
        self.chat_calls = 0
        self.route_checks: list[tuple[str, str]] = []

    def chat(self, *_args, **_kwargs):
        self.chat_calls += 1
        if self.fail_chat:
            raise AssertionError("a valid cache should not call the provider")
        return LLMResponse(
            model_id=MODEL,
            provider=SAFE_PROVIDER,
            content=json.dumps(self.payload),
        )

    def validate_response_route(self, model_id: str, provider: str) -> None:
        self.route_checks.append((model_id, provider))
        if model_id != MODEL or provider != SAFE_PROVIDER:
            raise RuntimeError("route is not currently allowed")


def _extractor(tmp_path, client: _Client) -> Extractor:
    return Extractor(client, model=MODEL, mode="ledger", cache_dir=tmp_path)


def test_new_cache_attests_the_enforced_provider_policy(tmp_path):
    _, meta = _extractor(tmp_path, _Client({"fresh": True})).extract({"technology": "x"})

    assert meta["policy_version"] == "zdr-deny-v1"
    assert meta["provider_policy"] == {"zdr": True, "data_collection": "deny"}


def test_legacy_or_hostile_cache_is_replaced_instead_of_returned(tmp_path):
    first = _extractor(tmp_path, _Client({"first": True}))
    first.extract({"technology": "x"})
    cache_path = next(tmp_path.glob("*.json"))
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    cached["output"] = {"stale": True}
    cached["meta"].pop("policy_version", None)
    cached["meta"].pop("provider_policy", None)
    cached["meta"]["provider"] = "SomeLogger"
    cache_path.write_text(json.dumps(cached), encoding="utf-8")

    fresh_client = _Client({"fresh": True})
    output, meta = _extractor(tmp_path, fresh_client).extract({"technology": "x"})

    assert output == {"fresh": True}
    assert meta["cached"] is False
    assert fresh_client.chat_calls == 1


def test_attested_cache_is_rechecked_against_current_model_provider_route(tmp_path):
    first = _extractor(tmp_path, _Client({"cached": True}))
    first.extract({"technology": "x"})

    cache_client = _Client({"unused": True}, fail_chat=True)
    output, meta = _extractor(tmp_path, cache_client).extract({"technology": "x"})

    assert output == {"cached": True}
    assert meta["cached"] is True
    assert cache_client.route_checks == [(MODEL, SAFE_PROVIDER)]


def test_legacy_scope_cache_is_refreshed_under_current_policy(tmp_path, monkeypatch):
    from ts import llm, scale

    cache_dir = tmp_path / "scopes"
    monkeypatch.setattr(scale, "CACHE", cache_dir)
    old_client = _Client({"scope": 1, "why": "старый ответ"})
    monkeypatch.setattr(llm, "OpenRouterClient", lambda _settings: old_client)
    card = {"technology": "x", "sources": [{"snippet": "реальный фрагмент"}]}
    scale.make_reader(type("Settings", (), {"llm_judge": MODEL})())(card)
    cache_path = next(cache_dir.glob("*.json"))
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    saved.pop("meta", None)
    cache_path.write_text(json.dumps(saved), encoding="utf-8")

    fresh_client = _Client({"scope": 2, "why": "обновлённый ответ"})
    monkeypatch.setattr(llm, "OpenRouterClient", lambda _settings: fresh_client)
    scope, why, model_id = scale.make_reader(type("Settings", (), {"llm_judge": MODEL})())(card)

    assert (scope, why, model_id) == (2, "обновлённый ответ", MODEL)
    assert fresh_client.chat_calls == 1


def test_legacy_reach_cache_is_refreshed_under_current_policy(tmp_path, monkeypatch):
    from ts import llm, reach

    cache_dir = tmp_path / "reach"
    monkeypatch.setattr(reach, "CACHE", cache_dir)
    old = {name: "старый ответ" for name in reach._FIELDS}
    old_client = _Client(old)
    monkeypatch.setattr(llm, "OpenRouterClient", lambda _settings: old_client)
    card = {"technology": "x", "sources": [{"snippet": "реальный фрагмент"}]}
    reach.make_reader(type("Settings", (), {"llm_judge": MODEL})())(card)
    cache_path = next(cache_dir.glob("*.json"))
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    saved.pop("meta", None)
    cache_path.write_text(json.dumps(saved), encoding="utf-8")

    fresh = {name: "обновлённый ответ" for name in reach._FIELDS}
    fresh_client = _Client(fresh)
    monkeypatch.setattr(llm, "OpenRouterClient", lambda _settings: fresh_client)
    result, model_id = reach.make_reader(type("Settings", (), {"llm_judge": MODEL})())(card)

    assert result and result["plain"] == "обновлённый ответ"
    assert model_id == MODEL
    assert fresh_client.chat_calls == 1
