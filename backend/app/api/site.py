"""
Public settings for the landing page.

GET /api/site-config  public: the Umami analytics settings, or null when
                      UMAMI_SCRIPT_URL / UMAMI_WEBSITE_ID aren't both set.
"""

from flask import jsonify

from . import site_bp
from ..config import Config


def _umami():
    url = Config.UMAMI_SCRIPT_URL
    website_id = Config.UMAMI_WEBSITE_ID
    # The page loads this URL as a script, so only accept an absolute http(s) URL.
    if not (url and website_id and url.startswith(('https://', 'http://'))):
        return None
    return {'scriptUrl': url, 'websiteId': website_id}


@site_bp.route('/site-config', methods=['GET'])
def site_config():
    resp = jsonify({'success': True, 'data': {'umami': _umami()}})
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp
