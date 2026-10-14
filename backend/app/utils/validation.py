"""
Input validation helpers.

Resource identifiers (project/simulation/report/graph/task ids, entity UUIDs,
script names) are routinely interpolated into filesystem paths via
``os.path.join`` and passed to ``send_file`` / ``shutil.rmtree``. Flask's default
``<string>`` URL converter blocks a literal ``/`` but NOT a backslash, so on a
Windows host a value like ``..\\..\\secret`` escapes the intended directory.
Validating every id against a strict allowlist at the request boundary closes
that path-traversal class regardless of platform.
"""

import re

from flask import request, jsonify

# Generated ids in this codebase look like ``sim_a6cb6dba053e``,
# ``report_3fcfa57ee215``, ``proj_94cf3a1d505f``, hex/uuid task ids, and
# uuid entity ids. All fit within this allowlist; nothing legitimate contains a
# path separator, dot-segment, or whitespace.
SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')

# View-arg names that are used to build filesystem paths or that must otherwise
# be safe single tokens. Any matched URL parameter with one of these names is
# validated before the view function runs.
# NOTE: ``script_name`` is intentionally NOT here — it legitimately contains a
# dot (e.g. ``run_twitter_simulation.py``) and its handler already enforces a
# strict filename allowlist, which is stronger than this regex.
VALIDATED_VIEW_ARGS = frozenset({
    'simulation_id',
    'report_id',
    'project_id',
    'graph_id',
    'task_id',
    'entity_uuid',
})

# The same ids also arrive via query string and JSON body on POST endpoints
# (e.g. /simulation/interview, /report/chat). Validate those centrally too so
# no single handler can forget to.
VALIDATED_ID_KEYS = frozenset({
    'simulation_id',
    'report_id',
    'project_id',
    'graph_id',
    'task_id',
})

# Reasonable upper bound so an absurdly long id can't be used for abuse.
_MAX_ID_LEN = 128

# ``platform`` values are interpolated into file names (``{platform}_simulation.db``,
# ``{platform}_profiles.*``), so they are allowlisted centrally as well.
QUERY_PLATFORMS = frozenset({'twitter', 'reddit'})
BODY_PLATFORMS = frozenset({'twitter', 'reddit', 'parallel'})


class InputError(Exception):
    """A client-supplied parameter is invalid. Rendered as HTTP 400 with the
    message shown to the client, so messages must not contain internals."""


def is_safe_id(value) -> bool:
    """Return True if ``value`` is a safe resource identifier."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_ID_LEN
        and SAFE_ID_RE.match(value) is not None
    )


def _reject(name):
    return jsonify({'success': False, 'error': f'Invalid {name}'}), 400


def validate_request_ids():
    """Flask ``before_request`` hook: reject unsafe resource ids.

    Covers all three places an id can enter a request:

    * URL path params (``request.view_args``) — populated by URL matching before
      ``before_request`` hooks run, so this sees every route parameter.
    * Query string (``request.args``).
    * Top-level keys of a JSON body (``request.get_json``), which is how POST
      endpoints such as ``/simulation/interview`` and ``/report/chat`` receive
      ids. ``get_json`` is cached by Flask, so the view still reads the same body.

    A present-but-unsafe id short-circuits with 400; a missing/empty id is left
    for the view to handle as before.
    """
    for name, value in (request.view_args or {}).items():
        if name in VALIDATED_VIEW_ARGS and not is_safe_id(value):
            return _reject(name)

    for name in VALIDATED_ID_KEYS:
        value = request.args.get(name)
        if value is not None and not is_safe_id(value):
            return _reject(name)

    platform = request.args.get('platform')
    if platform is not None and platform not in QUERY_PLATFORMS:
        return _reject('platform')

    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            for name in VALIDATED_ID_KEYS:
                value = body.get(name)
                if value is not None and not is_safe_id(value):
                    return _reject(name)
            platform = body.get('platform')
            if platform is not None and platform not in BODY_PLATFORMS:
                return _reject('platform')
    return None


# ============== Parameter parsing helpers ==============

def parse_int(value, name: str, *, default=None, minimum=None, maximum=None):
    """Coerce a client-supplied integer, enforcing bounds.

    ``None`` returns ``default``. Booleans are rejected (``True`` is an int in
    Python). Raises ``InputError`` on a non-integer or out-of-range value.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        raise InputError(f"{name} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise InputError(f"{name} must be an integer")
    if isinstance(value, float) and value != number:
        raise InputError(f"{name} must be an integer")
    if minimum is not None and number < minimum:
        raise InputError(f"{name} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise InputError(f"{name} must be <= {maximum}")
    return number


def query_int(name: str, *, default, minimum=None, maximum=None):
    """``parse_int`` for a query-string parameter."""
    return parse_int(request.args.get(name), name, default=default,
                     minimum=minimum, maximum=maximum)


def parse_bool(value, name: str, *, default: bool = False) -> bool:
    """Coerce a JSON/query boolean. Accepts real booleans and the strings
    "true"/"false"/"1"/"0" (so ``"false"`` is not truthy)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ('true', '1', 'yes'):
        return True
    if isinstance(value, str) and value.strip().lower() in ('false', '0', 'no', ''):
        return False
    raise InputError(f"{name} must be a boolean")


def parse_platform(value, allowed, *, default=None, name: str = 'platform'):
    """Validate a platform name against ``allowed``."""
    if value is None or value == '':
        return default
    if value not in allowed:
        raise InputError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return value


def parse_string_list(value, name: str, *, max_items: int = 100, max_len: int = 200):
    """Validate an optional list of short strings (e.g. entity type names)."""
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InputError(f"{name} must be a list of strings")
    if len(value) > max_items:
        raise InputError(f"{name} may contain at most {max_items} items")
    if any(len(v) > max_len for v in value):
        raise InputError(f"{name} items must be at most {max_len} characters")
    return value


def parse_chat_history(value, *, max_messages: int, max_chars: int):
    """Validate a chat history: a list of ``{"role", "content"}`` with role
    ``user``/``assistant``. Only the most recent ``max_messages`` are kept;
    oversized content is rejected."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise InputError("chat_history must be a list")
    cleaned = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise InputError(f"chat_history[{i}] must be an object")
        role = item.get('role')
        content = item.get('content')
        if role not in ('user', 'assistant'):
            raise InputError(f"chat_history[{i}].role must be 'user' or 'assistant'")
        if not isinstance(content, str):
            raise InputError(f"chat_history[{i}].content must be a string")
        if len(content) > max_chars:
            raise InputError(f"chat_history[{i}].content exceeds {max_chars} characters")
        cleaned.append({'role': role, 'content': content})
    return cleaned[-max_messages:]


def require_text(value, name: str, *, max_chars: int) -> str:
    """Validate a required non-empty string parameter with a size cap."""
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"Please provide {name}")
    if len(value) > max_chars:
        raise InputError(f"{name} exceeds {max_chars} characters")
    return value
