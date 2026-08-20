from flask import Blueprint, request, jsonify
from app.modules.database import get_db
from app.modules.scores import log_score_to_db, get_high_scores

scores_bp = Blueprint('scores', __name__)

# TODO: Rework this for manual input of scores
# @scores_bp.route("/api/v1/scores", methods=["POST"])
# def log_score():
#     """
#     Logs a new score into the database.
#     If the player does not exist, they are dynamically created.
#     """
#     try:
#         if not request.is_json:
#             return jsonify({"error": "Invalid JSON format"}), 400

#         data = request.get_json()

#         print(f"received score data: {data}")

#         success, message = log_score_to_db(get_db(), data)

#         close_db()

#         if success:
#             return jsonify({"message": message}), 201
#         else:
#             return jsonify({"error": message}), 400

#     except Exception as e:
#         close_db()
#         return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@scores_bp.route("/highscores", methods=["GET"])
def get_scores():
    """
    Retrieves high scores for one room, with player and game details.
    """
    room_id = request.args.get("roomID")
    if not room_id:
        return jsonify({"error": "Missing 'roomID' parameter"}), 400

    try:
        scores = get_high_scores(get_db(), room_id)

        if isinstance(scores, dict) and "error" in scores:
            return jsonify(scores), 500  # If an error occurred, return a 500 response

        return jsonify(scores), 200

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
