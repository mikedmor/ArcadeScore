import errno
import os
import sys
import time

# Windows consoles commonly default to a codepage (e.g. cp1252) that can't encode the
# emoji in the startup banner below, crashing before the server ever binds. Force
# UTF-8 stdout/stderr regardless of the console's codepage - this used to require
# manually setting PYTHONIOENCODING=utf-8 in the environment, which the self-updater's
# relaunched process (app/modules/updater.py) can't rely on inheriting.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

os.environ["EVENTLET_NO_GREENDNS"] = "yes"  # Disable Eventlet's DNS monkey patching
import eventlet
eventlet.monkey_patch()

from app import create_app
from app.modules.socketio import socketio

# Create Flask app
app = create_app()

if __name__ == "__main__":
    # Read port from environment, default to 8080
    port = int(os.getenv("ARCADESCORE_HTTP_PORT", 8080))

    debug = os.getenv("ARCADESCORE_DEBUG", "0") == "1"

    print(f"🚀 Starting ArcadeScore with Eventlet on port {port}...")

    # A self-restart (app/modules/updater.py) can start this process before the
    # previous one has fully released the port at the OS level - confirmed live as a
    # real, reproducible race, not a hypothetical one. Retry the bind briefly instead
    # of dying on the first "address already in use".
    max_bind_attempts = 10
    for attempt in range(1, max_bind_attempts + 1):
        try:
            # Ensure SocketIO uses Eventlet
            socketio.run(app, host="0.0.0.0", port=port, debug=debug, use_reloader=False)
            break
        except OSError as e:
            already_in_use = e.errno == errno.EADDRINUSE or getattr(e, "winerror", None) == 10048
            if not already_in_use or attempt == max_bind_attempts:
                raise
            print(f"⏳ Port {port} still in use (attempt {attempt}/{max_bind_attempts}) - retrying in 1s...")
            time.sleep(1)