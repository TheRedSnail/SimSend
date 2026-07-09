"""
Optional admin authentication for the full-power API.

The graph/simulation/report API is powerful — it can spawn unbounded
simulations, run expensive LLM/Zep pipelines, and delete any user's data. On a
public host that API must not be openly writable.

This gate is **opt-in**: it does nothing until ``ADMIN_API_KEY`` is configured.
Once set, mutating requests (POST/PUT/PATCH/DELETE) and enumeration endpoints
(paths ending in ``/list``) on the graph/simulation/report blueprints require a
matching ``X-Admin-Key`` header.
"""

import hmac

from flask import request, jsonify

from ..config import Config

# Blueprints whose write/enumeration surface is sensitive.
_PROTECTED_PREFIXES = ('/api/graph', '/api/simulation', '/api/report')

# Always publicly reachable regardless of the gate.
_EXEMPT_PREFIXES = ('/health',)

_MUTATING_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')


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
    if path.rstrip('/').endswith('/list'):
        return True
    return False


def require_admin_for_protected():
    """Flask ``before_request`` hook enforcing the optional admin key."""
    admin_key = Config.ADMIN_API_KEY
    if not admin_key:
        # Gate disabled — preserve the previous fully-open behavior.
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
