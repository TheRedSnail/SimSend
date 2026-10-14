"""
Repair JSON that an LLM cut off mid-output (finish_reason == "length").

The repair walks the text once, tracking string/escape state and a stack of
open containers, then:
  - closes an unterminated string,
  - drops a dangling key, ``"key":`` without a value, or a trailing comma,
  - closes the open containers innermost-first.
It does not invent missing values or fix otherwise malformed JSON.
"""

import json
from typing import Any, Optional

_CLOSERS = {'{': '}', '[': ']'}


def repair_truncated_json(content: str) -> str:
    """Return ``content`` with an unterminated string and open containers closed."""
    if not content:
        return content
    text = content.strip()

    stack = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in _CLOSERS:
            stack.append(ch)
        elif ch in '}]':
            if stack and _CLOSERS[stack[-1]] == ch:
                stack.pop()

    if in_string:
        if escaped:
            text = text[:-1]  # a lone trailing backslash would escape our quote
        text += '"'

    if not stack:
        return text

    text = _drop_incomplete_tail(text, stack[-1])
    return text + ''.join(_CLOSERS[opener] for opener in reversed(stack))


def _drop_incomplete_tail(text: str, innermost: str) -> str:
    """Remove a trailing comma, colon or bare object key that has no value yet."""
    stripped = text.rstrip()
    if stripped.endswith(','):
        return stripped[:-1]
    if stripped.endswith(':'):
        # {"a": 1, "b":   -> drop the dangling key as well
        return _drop_trailing_key(stripped[:-1].rstrip())
    if innermost == '{' and stripped.endswith('"'):
        # {"a": 1, "b"    -> a key with no colon yet
        start = _string_start(stripped)
        if start is not None:
            before = stripped[:start].rstrip()
            if before.endswith(',') or before.endswith('{'):
                return before[:-1] if before.endswith(',') else before
    return stripped


def _drop_trailing_key(text: str) -> str:
    start = _string_start(text)
    if start is None:
        return text
    before = text[:start].rstrip()
    return before[:-1] if before.endswith(',') else before


def _string_start(text: str) -> Optional[int]:
    """Index of the opening quote of the string literal that ends ``text``."""
    if not text.endswith('"'):
        return None
    i = len(text) - 2
    while i >= 0:
        if text[i] == '"':
            backslashes = 0
            j = i - 1
            while j >= 0 and text[j] == '\\':
                backslashes += 1
                j -= 1
            if backslashes % 2 == 0:
                return i
        i -= 1
    return None


def loads_lenient(content: str) -> Any:
    """json.loads, falling back to repair_truncated_json on failure."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(repair_truncated_json(content))
