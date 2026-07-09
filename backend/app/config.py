"""
Configuration Management
Loads all configuration from the .env file in the project root directory
"""

import os
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
    # SECRET_KEY must be provided via the environment in any real deployment;
    # the development fallback is deliberately obvious so a missing key is caught.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-insecure-change-me')
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

    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 500  # Default chunk size
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size

    # OASIS simulation configuration
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

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
