"""LLMClient.chat_json: truncated JSON responses are retried with a bigger budget."""

from types import SimpleNamespace

import pytest

from app.utils.llm_client import LLMClient


def _response(content, finish_reason):
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def _client(responses):
    client = LLMClient(api_key="test", base_url="http://localhost", model="m")
    calls = []

    def create(**kwargs):
        calls.append(kwargs["max_tokens"])
        return responses.pop(0)

    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, calls


def test_truncated_json_is_retried_with_more_tokens():
    client, calls = _client([
        _response('{"entity_types": [{"name": "A"', "length"),
        _response('{"entity_types": [{"name": "A"}]}', "stop"),
    ])
    assert client.chat_json([{"role": "user", "content": "x"}], max_tokens=4096) == {
        "entity_types": [{"name": "A"}]
    }
    assert calls == [4096, 8192]


def test_truncation_gives_up_at_ceiling_with_clear_error():
    client, calls = _client([_response('{"a": [', "length") for _ in range(5)])
    with pytest.raises(ValueError, match="truncated at the token limit"):
        client.chat_json([{"role": "user", "content": "x"}], max_tokens=4096)
    assert calls == [4096, 8192, 16384]


def test_complete_json_is_not_retried():
    client, calls = _client([_response('```json\n{"ok": true}\n```', "stop")])
    assert client.chat_json([{"role": "user", "content": "x"}]) == {"ok": True}
    assert calls == [4096]
