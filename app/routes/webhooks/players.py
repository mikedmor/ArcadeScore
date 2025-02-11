from flask import Blueprint
from app.modules.database import get_db

webhook_players_bp = Blueprint('webhook_players', __name__)