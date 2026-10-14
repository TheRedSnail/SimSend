"""
Early-access sign-up API used by the landing page (/welcome).

POST /api/signup       public (still needs the X-SimSend-Client header)
GET  /api/signup/list  admin only: X-Admin-Key must match ADMIN_API_KEY
"""

import csv
import hmac
import io

from flask import Response, jsonify, request

from . import signup_bp
from ..config import Config
from ..services import signup_store
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.signup')

# A sign-up is a few short fields; anything bigger is not a real form post.
_MAX_BODY_BYTES = 8 * 1024

_CSV_FIELDS = ('created_at', 'updated_at', 'name', 'email', 'company', 'role', 'use_case', 'updates')


@signup_bp.route('', methods=['POST'])
def create_signup():
    if (request.content_length or 0) > _MAX_BODY_BYTES:
        return jsonify({'success': False, 'error': 'Request too large'}), 413

    if not signup_store.rate_limiter.allow(
        request.remote_addr or 'unknown',
        Config.SIGNUP_RATE_LIMIT,
        Config.SIGNUP_RATE_WINDOW_SECONDS,
    ):
        return jsonify({'success': False, 'error': 'Too many sign-ups from this address. Try again later.'}), 429

    payload = request.get_json(silent=True)

    # Hidden honeypot field: people never fill it in, form-filling bots do.
    # Pretend it worked so the bot has no signal to adapt to.
    if isinstance(payload, dict) and payload.get('website'):
        return jsonify({'success': True}), 201

    record = signup_store.validate_signup(payload)
    try:
        signup_store.save_signup(record)
    except signup_store.SignupLimitReached:
        logger.warning('Sign-up rejected: SIMSEND_MAX_SIGNUPS reached')
        return jsonify({'success': False, 'error': 'Sign-ups are closed right now.'}), 503

    return jsonify({'success': True}), 201


def _csv_safe(value) -> str:
    """Stop spreadsheet apps from running a cell as a formula."""
    text = '' if value is None else str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@', '\t', '\r') else text


@signup_bp.route('/list', methods=['GET'])
def list_signups():
    admin_key = Config.ADMIN_API_KEY
    if not admin_key:
        # Without an admin key every visitor would be able to read the list.
        return jsonify({
            'success': False,
            'error': 'Set ADMIN_API_KEY on the server to view sign-ups.',
        }), 403
    provided = request.headers.get('X-Admin-Key', '')
    if not (provided and hmac.compare_digest(provided, admin_key)):
        return jsonify({'success': False, 'error': 'Administrative authorization required for this endpoint.'}), 401

    signups = signup_store.list_signups()

    if request.args.get('format') == 'csv':
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(_CSV_FIELDS)
        for s in signups:
            writer.writerow([_csv_safe(s.get(f)) for f in _CSV_FIELDS])
        return Response(
            out.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename="signups.csv"'},
        )

    return jsonify({'success': True, 'data': {'count': len(signups), 'signups': signups}})
