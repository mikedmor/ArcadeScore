from flask import Blueprint

from app.routes.api.v1.games import games_bp
from app.routes.api.v1.players import players_bp
from app.routes.api.v1.scoreboards import scoreboards_bp
from app.routes.api.v1.scores import scores_bp
from app.routes.api.v1.styles import styles_bp
from app.routes.api.v1.users import users_bp
from app.routes.settings import settings_bp
from app.routes.misc import misc_bp

api_bp = Blueprint("api", __name__)

# Register individual blueprints
api_bp.register_blueprint(games_bp)
api_bp.register_blueprint(players_bp)
api_bp.register_blueprint(scoreboards_bp)
api_bp.register_blueprint(scores_bp)
api_bp.register_blueprint(settings_bp)
api_bp.register_blueprint(users_bp)
api_bp.register_blueprint(styles_bp)
api_bp.register_blueprint(misc_bp)
