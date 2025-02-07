import eventlet
eventlet.monkey_patch() 

from flask import Flask
from app.database import close_db
from app.models import init_db, migrate_db
from app.routes.__init__ import api_bp
from app.socketio_instance import socketio

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "supersecret"
    app.config["MAX_CONTENT_LENGTH"] = None
    app.config["DB_PATH"] = "./data/highscores.db"

    # Initialize database
    init_db(app.config["DB_PATH"])
    migrate_db(app.config["DB_PATH"])

    # Register routes
    app.register_blueprint(api_bp)

    app.teardown_appcontext(close_db)

    # Initialize SocketIO
    socketio.init_app(app, cors_allowed_origins="*")

    return app
