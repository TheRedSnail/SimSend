"""LLMClient: replies cut off at the token limit are retried with a bigger budget."""

from types import SimpleNamespace

import pytest

from app.utils.llm_client import LLMClient


def _response(content, finish_reason):
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def _client(responses, base_url="http://localhost", seen=None):
    client = LLMClient(api_key="test", base_url=base_url, model="m")
    calls = []

    def create(**kwargs):
        calls.append(kwargs["max_tokens"])
        if seen is not None:
            seen.append(kwargs)
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



def test_chat_retries_when_reasoning_used_the_whole_budget():
    client, calls = _client([_response(None, "length"), _response("answer", "stop")])
    assert client.chat([{"role": "user", "content": "x"}], max_tokens=4096) == "answer"
    assert calls == [4096, 8192]


def test_chat_gives_up_at_ceiling_and_returns_empty():
    client, calls = _client([_response("", "length") for _ in range(5)])
    assert client.chat([{"role": "user", "content": "x"}], max_tokens=4096) == ""
    assert calls == [4096, 8192, 16384]


def test_chat_keeps_a_partial_reply_cut_at_the_limit():
    client, calls = _client([_response("partial", "length")])
    assert client.chat([{"role": "user", "content": "x"}]) == "partial"
    assert calls == [4096]


@pytest.mark.parametrize("base_url, sent", [
    ("https://openrouter.ai/api/v1", {"reasoning": {"enabled": False}}),
    ("https://api.openai.com/v1", None),
])
def test_reasoning_off_is_only_sent_to_openrouter(base_url, sent):
    seen = []
    client, _ = _client([_response("ok", "stop")], base_url=base_url, seen=seen)
    client.chat([{"role": "user", "content": "x"}], reasoning=False)
    assert seen[0].get("extra_body") == sent
