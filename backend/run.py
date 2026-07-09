"""
MiroFish Backend Entry Point
"""

import os
import sys

# Fix Windows console encoding issues: set UTF-8 before all imports
if sys.platform == 'win32':
    # Set environment variable to ensure Python uses UTF-8
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # Reconfigure standard output streams to UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config

# Module-level WSGI application so a production server can import it, e.g.
#   waitress-serve --host=0.0.0.0 --port=5001 run:app
app = create_app()


def main():
    """Main function"""
    # Validate configuration
    errors = Config.validate()
    if errors:
        print("Configuration errors:")
        for err in errors:
            print(f"  - {err}")
        print("\nPlease check the configuration in the .env file")
        sys.exit(1)

    # Reuse the module-level application created above.

    # Get run configuration
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG

    # Safety guard: the Werkzeug interactive debugger is remote code execution
    # for anyone who can trigger an exception, so never enable it on a
    # non-loopback interface. Requiring an explicit opt-in prevents a stray
    # FLASK_DEBUG=true from exposing the debugger on a public host.
    if debug and host not in ('127.0.0.1', 'localhost', '::1'):
        if os.environ.get('FLASK_ALLOW_PUBLIC_DEBUG', 'False').lower() != 'true':
            print(
                f"Refusing to start the Werkzeug debugger on public host {host!r}. "
                "Bind FLASK_HOST=127.0.0.1 for local debugging, or set "
                "FLASK_ALLOW_PUBLIC_DEBUG=true only if you fully understand the risk."
            )
            debug = False

    # NOTE: app.run()/the Werkzeug dev server is for development only. In
    # production serve the app through a WSGI server such as waitress or gunicorn
    # (e.g. `waitress-serve --host=0.0.0.0 --port=5001 run:app`).
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()
