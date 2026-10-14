"""
Shared error handling for the API layer.

Clients never receive tracebacks or raw exception text for unexpected
failures: the full traceback is logged server-side under a short error id, and
the response carries only a generic message plus that id. ``InputError``
(invalid client parameters) is the exception whose message is meant for the
client and is rendered as a 400.
"""

import uuid

from flask import jsonify

from ..utils.logger import get_logger
from ..utils.validation import InputError

logger = get_logger('mirofish.api.errors')

# Upper bound on how much of a ValueError message is surfaced in task errors.
_MAX_PUBLIC_MESSAGE = 300


def _new_error_id() -> str:
    return uuid.uuid4().hex[:8]


def error_response(exc: BaseException, context: str):
    """Build the JSON error response for ``exc``.

    Call from inside an ``except`` block so the traceback is logged.
    """
    if isinstance(exc, InputError):
        return jsonify({"success": False, "error": str(exc)}), 400

    error_id = _new_error_id()
    logger.error(f"{context} [error_id={error_id}]", exc_info=exc)
    return jsonify({
        "success": False,
        "error": f"{context}. Internal error (id {error_id}); see server logs.",
        "error_id": error_id,
    }), 500


def public_task_error(exc: BaseException, context: str) -> str:
    """Log ``exc`` with its traceback and return a client-safe task error.

    ``ValueError`` messages are raised deliberately by this codebase and are
    kept (truncated); for anything else only the exception type is exposed.
    """
    error_id = _new_error_id()
    logger.error(f"{context} [error_id={error_id}]", exc_info=exc)
    if isinstance(exc, (InputError, ValueError)):
        detail = str(exc)[:_MAX_PUBLIC_MESSAGE]
    else:
        detail = type(exc).__name__
    return f"{context}: {detail} (error id {error_id}; see server logs)"
