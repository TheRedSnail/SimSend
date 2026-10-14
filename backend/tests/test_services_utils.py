"""Tests for the shared JSON-repair and retry helpers (no network)."""

import json

import pytest

from app.utils.json_repair import repair_truncated_json, loads_lenient
from app.utils.retry import (
    call_with_retry,
    is_transient_error,
    retry_after_seconds,
    retry_with_backoff,
)


# ---------------------------------------------------------------- json repair

@pytest.mark.parametrize("truncated, expected", [
    ('{"a": 1, "b": [1, 2', {"a": 1, "b": [1, 2]}),
    ('{"a": {"b": "c"}, "d": [{"e": 1}', {"a": {"b": "c"}, "d": [{"e": 1}]}),
    # brackets inside strings must not be counted
    ('{"k": "has } and ] inside", "n": [1', {"k": "has } and ] inside", "n": [1]}),
    # unterminated string, including an escaped quote inside it
    ('{"a": "he said \\"hi', {"a": 'he said "hi'}),
    # dangling key / colon / comma are dropped
    ('{"a": 1, "b": ', {"a": 1}),
    ('{"a": 1, "b"', {"a": 1}),
    ('{"a": 1,', {"a": 1}),
    ('["x", "y', ["x", "y"]),
])
def test_repair_truncated_json_produces_valid_json(truncated, expected):
    assert json.loads(repair_truncated_json(truncated)) == expected


def test_repair_leaves_complete_json_alone():
    text = '{"a": [1, 2, {"b": "}"}]}'
    assert repair_truncated_json(text) == text


def test_repair_handles_trailing_backslash_in_string():
    out = repair_truncated_json('{"path": "C:\\')
    assert json.loads(out) == {"path": "C:"}


def test_loads_lenient_falls_back_to_repair():
    assert loads_lenient('{"a": [1') == {"a": [1]}


# ---------------------------------------------------------------------- retry

class _StatusError(Exception):
    def __init__(self, status, headers=None):
        super().__init__(f"status {status}")
        self.status_code = status
        self.headers = headers or {}


@pytest.mark.parametrize("exc, transient", [
    (_StatusError(429), True),
    (_StatusError(503), True),
    (_StatusError(500), True),
    (_StatusError(400), False),
    (_StatusError(401), False),
    (_StatusError(404), False),
    (ConnectionError("reset"), True),
    (TimeoutError(), True),
    (ValueError("bad json"), False),
    (FileNotFoundError("x"), False),
])
def test_is_transient_error(exc, transient):
    assert is_transient_error(exc) is transient


def test_call_with_retry_retries_transient_then_succeeds():
    calls = []
    sleeps = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise _StatusError(503)
        return "ok"

    assert call_with_retry(flaky, max_retries=3, jitter=False, sleep=sleeps.append) == "ok"
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_call_with_retry_does_not_retry_permanent_errors():
    calls = []

    def bad_request():
        calls.append(1)
        raise _StatusError(400)

    with pytest.raises(_StatusError):
        call_with_retry(bad_request, max_retries=5, sleep=lambda s: None)
    assert len(calls) == 1


def test_call_with_retry_gives_up_after_max_retries():
    calls = []

    def always_down():
        calls.append(1)
        raise _StatusError(502)

    with pytest.raises(_StatusError):
        call_with_retry(always_down, max_retries=2, sleep=lambda s: None)
    assert len(calls) == 3


def test_call_with_retry_honors_retry_after():
    sleeps = []
    state = {"n": 0}

    def rate_limited():
        state["n"] += 1
        if state["n"] == 1:
            raise _StatusError(429, {"Retry-After": "7"})
        return "ok"

    call_with_retry(rate_limited, max_retries=1, sleep=sleeps.append)
    assert sleeps == [7.0]


def test_retry_after_is_capped():
    assert retry_after_seconds(_StatusError(429, {"retry-after": "9999"})) == 60.0
    assert retry_after_seconds(_StatusError(429, {"retry-after": "Wed, 21 Oct 2015"})) is None


def test_call_with_retry_passes_kwargs_through():
    def echo(a, b=None):
        return (a, b)

    assert call_with_retry(echo, 1, b=2, sleep=lambda s: None) == (1, 2)


def test_retry_decorator_respects_retry_if(monkeypatch):
    monkeypatch.setattr("app.utils.retry.time.sleep", lambda s: None)
    calls = []

    @retry_with_backoff(max_retries=3, retry_if=is_transient_error)
    def permanent():
        calls.append(1)
        raise _StatusError(403)

    with pytest.raises(_StatusError):
        permanent()
    assert len(calls) == 1
