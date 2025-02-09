import os

os.environ["EVENTLET_NO_GREENDNS"] = "yes"  # Disable Eventlet's DNS monkey patching
import eventlet
eventlet.monkey_patch()

from app import create_app
from app.socketio_instance import socketio

# Create Flask app
app = create_app()

if __name__ == "__main__":
    print("🚀 Starting ArcadeScore with Eventlet...")

    # Ensure SocketIO uses Eventlet
    socketio.run(app, host="0.0.0.0", port=8080, debug=True, use_reloader=False)
