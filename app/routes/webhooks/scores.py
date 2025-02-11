from flask import Blueprint
from app.modules.database import get_db

webhook_scores_bp = Blueprint('webhook_scores', __name__)