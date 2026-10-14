"""
Production WSGI entry point.

Serves the API plus, when FRONTEND_DIST_DIR points at a built frontend
(``npm run build`` -> frontend/dist), the single-page app from the same origin,
so no Vite dev server is needed in production:

    python wsgi.py        # waitress on FLASK_HOST:FLASK_PORT (default 127.0.0.1:5001)
"""

import os

from flask import abort, send_from_directory

from app import create_app
from app.config import Config

# Fail fast (the container restarts visibly) instead of serving an app that
# errors on the first LLM/Zep call.
_config_errors = Config.validate()
if _config_errors:
    raise SystemExit("Configuration errors: " + "; ".join(_config_errors))

app = create_app()

FRONTEND_DIST_DIR = os.environ.get(
    'FRONTEND_DIST_DIR',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist'),
)
FRONTEND_DIST_DIR = os.path.abspath(FRONTEND_DIST_DIR)

if os.path.isfile(os.path.join(FRONTEND_DIST_DIR, 'index.html')):

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # Unknown API paths must stay JSON 404s, not fall through to the SPA.
        if path == 'api' or path.startswith('api/'):
            abort(404)
        if path and os.path.isfile(os.path.join(FRONTEND_DIST_DIR, path)):
            # send_from_directory rejects paths escaping the directory.
            return send_from_directory(FRONTEND_DIST_DIR, path)
        # A missing file (stale hashed asset, typo) is a 404, not the SPA shell.
        if '.' in path.rsplit('/', 1)[-1]:
            abort(404)
        # History-mode routes (/process/<id>, /report/<id>, ...) -> index.html
        return send_from_directory(FRONTEND_DIST_DIR, 'index.html')


if __name__ == '__main__':
    from waitress import serve

    serve(
        app,
        host=os.environ.get('FLASK_HOST', '127.0.0.1'),
        port=int(os.environ.get('FLASK_PORT', 5001)),
        # Long-running LLM calls hold a thread each, so allow a generous pool.
        threads=16,
    )
