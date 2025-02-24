from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.scores import log_score_to_db, get_high_scores

scores_bp = Blueprint('scores', __name__)

@scores_bp.route("/api/v1/scores", methods=["POST"])
def log_score():
    """
    Logs a new score into the database.
    If the player does not exist, they are dynamically created.
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Invalid JSON format"}), 400

        data = request.get_json()
        success, message = log_score_to_db(get_db(), data)

        close_db()

        if success:
            return jsonify({"message": message}), 201
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# TODO: This is missing information about the room, we need one for all scores, and one for just the room scores
@scores_bp.route("/highscores", methods=["GET"])
def get_scores():
    """
    Retrieves all high scores with player and game details.
    """
    try:
        scores = get_high_scores(get_db())
        
        close_db()

        if "error" in scores:
            return jsonify(scores), 500  # If an error occurred, return a 500 response

        return jsonify(scores), 200

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
