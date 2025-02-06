import eventlet
eventlet.monkey_patch()  # Enable async support for eventlet

from app import create_app
from app.socketio_instance import socketio
import logging

# Create Flask app
app = create_app()

# Set up logging for Gunicorn
if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, log_output=True)
