from flask_socketio import SocketIO

# Define `socketio` instance globally
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
