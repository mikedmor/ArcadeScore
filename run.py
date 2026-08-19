import os

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

    # Ensure SocketIO uses Eventlet
    socketio.run(app, host="0.0.0.0", port=port, debug=debug, use_reloader=False)