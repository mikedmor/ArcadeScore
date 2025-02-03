from flask import Flask
from app.database import close_db
from app.models import init_db, migrate_db
from app.routes.__init__ import api_bp

def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
    app.config["DB_PATH"] = "/opt/arcadescore/data/highscores.db"

    # Initialize database
    init_db(app.config["DB_PATH"])
    migrate_db(app.config["DB_PATH"])

    # Register routes
    app.register_blueprint(api_bp)

    app.teardown_appcontext(close_db)

    return app
