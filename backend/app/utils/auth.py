"""
Request authorization hooks for the full-power API.

Two independent ``before_request`` gates:

* ``require_client_header`` (always on): mutating ``/api`` requests must carry
  ``X-SimSend-Client: 1``. A browser cannot attach a custom header to a
  cross-origin request without a CORS preflight, and the app only grants CORS to
  origins listed in ``CORS_ORIGINS`` (none by default). So a page on another
  site cannot drive the API through the user's browser (CSRF), including via
  plain HTML form posts that would otherwise skip the preflight.

* ``require_admin_for_protected`` (opt-in): once ``ADMIN_API_KEY`` is
  configured, mutating requests and every enumerate-all-resources endpoint on
  the graph/simulation/report blueprints require a matching ``X-Admin-Key``.
"""

import hmac

from flask import request, jsonify

from ..config import Config

# Blueprints whose write/enumeration surface is sensitive.
_PROTECTED_PREFIXES = ('/api/graph', '/api/simulation', '/api/report')

# Always publicly reachable regardless of the gate.
_EXEMPT_PREFIXES = ('/health',)

_MUTATING_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

# Read-only endpoints that list resources across every project/user. Paths
# ending in ``/list`` are covered generically; these don't follow that pattern.
_ENUMERATION_PATHS = frozenset({
    '/api/graph/tasks',
    '/api/simulation/history',
})


def _needs_admin(path: str, method: str) -> bool:
    if method == 'OPTIONS':  # never block CORS preflight
        return False
    if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
        return False
    if not any(path.startswith(p) for p in _PROTECTED_PREFIXES):
        return False
    # Protect all mutations, plus read-only enumeration endpoints that leak the
    # full resource list across all users.
    if method in _MUTATING_METHODS:
        return True
    normalized = path.rstrip('/')
    if normalized.endswith('/list') or normalized in _ENUMERATION_PATHS:
        return True
    return False


def require_client_header():
    """Flask ``before_request`` hook: CSRF defence for mutating API calls."""
    if request.method not in _MUTATING_METHODS:
        return None
    if not request.path.startswith('/api/'):
        return None
    if request.headers.get(Config.CLIENT_HEADER) == '1':
        return None
    return jsonify({
        'success': False,
        'error': f'Missing {Config.CLIENT_HEADER} header. Mutating API requests '
                 f'must send "{Config.CLIENT_HEADER}: 1".',
    }), 403


def require_admin_for_protected():
    """Flask ``before_request`` hook enforcing the optional admin key."""
    admin_key = Config.ADMIN_API_KEY
    if not admin_key:
        # Gate disabled — the API is protected by loopback binding, restricted
        # CORS and the client-header check only.
        return None

    if not _needs_admin(request.path, request.method):
        return None

    provided = request.headers.get('X-Admin-Key', '')
    # Constant-time comparison to avoid leaking the key via timing.
    if provided and hmac.compare_digest(provided, admin_key):
        return None

    return jsonify({
        'success': False,
        'error': 'Administrative authorization required for this endpoint.',
    }), 401
