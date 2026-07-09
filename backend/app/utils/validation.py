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

    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            for name in VALIDATED_ID_KEYS:
                value = body.get(name)
                if value is not None and not is_safe_id(value):
                    return _reject(name)
    return None
