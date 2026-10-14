"""
MiroFish Backend - Flask Application Factory
"""

import os
import warnings

# Suppress multiprocessing resource_tracker warnings (from third-party libraries like transformers)
# Must be set before all other imports
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask application factory function"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Set JSON encoding: ensure non-ASCII characters are displayed directly (not as \uXXXX)
    # Flask >= 2.3 uses app.json.ensure_ascii, older versions use JSON_AS_ASCII config
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Set up logging
    logger = setup_logger('mirofish')

    # Only print startup info in the reloader subprocess (avoid printing twice in debug mode)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend starting...")
        logger.info("=" * 50)
    
    # CORS: the bundled frontend is same-origin (Vite proxy in development), so
    # cross-origin access is only granted to origins listed in CORS_ORIGINS.
    cors_origins = config_class.CORS_ORIGINS
    if cors_origins:
        CORS(app, resources={r"/api/*": {
            "origins": cors_origins,
            "allow_headers": ["Content-Type", config_class.CLIENT_HEADER, "X-Admin-Key"],
        }})
        if should_log_startup:
            logger.info(f"CORS enabled for: {', '.join(cors_origins)}")
    
    # Register simulation process cleanup function (ensure all simulation processes are terminated on server shutdown)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Simulation process cleanup function registered")
    
    # Background jobs run in-process: anything a previous process left
    # "in progress" can never finish, so mark it failed (and retryable).
    from .models.task import TaskManager
    from .models.project import ProjectManager
    TaskManager()  # loads persisted tasks, failing interrupted ones
    recovered = ProjectManager.recover_interrupted_builds()
    if recovered and should_log_startup:
        logger.info(f"Reset {recovered} project(s) left in graph_building by a previous run")

    # Reject path-traversal attempts in resource ids (URL, query, and JSON body)
    # before any view runs.
    from .utils.validation import validate_request_ids, InputError
    app.before_request(validate_request_ids)

    # CSRF defence: mutating API calls must carry the client header.
    from .utils.auth import require_admin_for_protected, require_client_header
    app.before_request(require_client_header)

    # Optional admin gate for the full-power API (inert unless ADMIN_API_KEY set).
    app.before_request(require_admin_for_protected)

    # Request logging: method, path, status and size only. Bodies are never
    # logged (they carry prompts, campaign briefs and chat content).
    request_logger = get_logger('mirofish.request')
    
    @app.after_request
    def log_response(response):
        request_logger.debug(
            f"{request.method} {request.path} -> {response.status_code} "
            f"(req {request.content_length or 0}B, resp {response.content_length or 0}B)"
        )
        return response

    # Uniform JSON errors. Unexpected exceptions are logged with their
    # traceback and an error id; the client only gets the id.
    from .api.errors import error_response

    @app.errorhandler(InputError)
    def handle_input_error(exc):
        return error_response(exc, "Invalid request")

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        if not request.path.startswith('/api/'):
            return exc
        return jsonify({"success": False, "error": exc.description or exc.name}), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        return error_response(exc, "Request failed")
    
    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp, signup_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(signup_bp, url_prefix='/api/signup')
    
    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish Backend startup complete")
    
    return app
