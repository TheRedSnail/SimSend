"""
Configuration Management
Loads all configuration from the .env file in the project root directory
"""

import os
import secrets
from dotenv import load_dotenv

# Load the .env file from the project root directory
# Path: MiroFish/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

# override=False so real environment variables (e.g. those injected by
# docker-compose's env_file, or set by the operator) always win over a stray
# or accidentally-baked .env file.
if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=False)
else:
    # If the root .env is not found, try loading environment variables (for production)
    load_dotenv(override=False)


class Config:
    """Flask Configuration Class"""

    # Flask configuration
    # Nothing currently uses Flask sessions, but never fall back to a guessable
    # constant: an unset SECRET_KEY gets a random per-process value.
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    # Debug defaults OFF. The Werkzeug interactive debugger is remote code
    # execution when reachable, so it must be opted into explicitly and never
    # enabled on a public host.
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # JSON configuration - Disable ASCII escaping so non-ASCII characters display directly (not as \uXXXX)
    JSON_AS_ASCII = False

    # LLM configuration (unified OpenAI-compatible format)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Dedicated lane for the OASIS swarm agents; falls back to LLM_* when unset.
    SWARM_LLM_API_KEY = os.environ.get('SWARM_LLM_API_KEY', LLM_API_KEY)
    SWARM_LLM_BASE_URL = os.environ.get('SWARM_LLM_BASE_URL', LLM_BASE_URL)
    SWARM_LLM_MODEL_NAME = os.environ.get('SWARM_LLM_MODEL_NAME', LLM_MODEL_NAME)

    # Zep configuration
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # Optional admin key. When set, mutating and enumeration endpoints on the
    # graph/simulation/report API require a matching X-Admin-Key header. Unset =
    # the full API stays open (development / trusted-network behavior).
    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')

    # Network exposure. The server binds to loopback unless FLASK_HOST says
    # otherwise (the Docker image sets 0.0.0.0 explicitly). The frontend talks
    # to the API same-origin (Vite proxy in dev, same server in production), so
    # no cross-origin access is granted unless CORS_ORIGINS lists origins
    # (comma-separated, e.g. "https://app.example.com").
    FLASK_HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
    CORS_ORIGINS = [
        o.strip() for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()
    ]

    # Every mutating /api request must carry this header (value "1"). Browsers
    # cannot attach a custom header cross-origin without a CORS preflight, which
    # the restricted CORS policy rejects, so this blocks CSRF from other sites.
    CLIENT_HEADER = 'X-SimSend-Client'

    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), '../uploads'))
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 500  # Default chunk size
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size

    # OASIS simulation configuration
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    # Single source of truth for on-disk locations.
    OASIS_SIMULATION_DATA_DIR = os.path.join(UPLOAD_FOLDER, 'simulations')
    REPORTS_DIR = os.path.join(UPLOAD_FOLDER, 'reports')
    TASKS_DIR = os.path.join(UPLOAD_FOLDER, 'tasks')

    # Early-access sign-ups from the landing page (/welcome). The list is only
    # readable through /api/signup/list, which requires ADMIN_API_KEY.
    SIGNUPS_FILE = os.path.join(UPLOAD_FOLDER, 'signups.json')
    MAX_SIGNUPS = int(os.environ.get('SIMSEND_MAX_SIGNUPS', '10000'))
    # Per client IP. Behind a reverse proxy every visitor shares the proxy's
    # IP, so keep this generous.
    SIGNUP_RATE_LIMIT = int(os.environ.get('SIMSEND_SIGNUP_RATE_LIMIT', '20'))
    SIGNUP_RATE_WINDOW_SECONDS = 600

    # Resource limits for client-supplied parameters.
    MAX_CONCURRENT_SIMULATIONS = max(1, int(os.environ.get('SIMSEND_MAX_CONCURRENT_SIMULATIONS', '2')))
    MAX_SIMULATION_ROUNDS = int(os.environ.get('SIMSEND_MAX_SIMULATION_ROUNDS', '1000'))
    MAX_PARALLEL_PROFILE_COUNT = int(os.environ.get('SIMSEND_MAX_PARALLEL_PROFILES', '20'))
    MAX_CHAT_HISTORY_MESSAGES = 50
    MAX_CHAT_MESSAGE_CHARS = 20000

    # OASIS platform available actions configuration
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration"""
        errors: list[str] = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        return errors
