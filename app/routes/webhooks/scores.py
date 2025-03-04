from flask import Blueprint, request, jsonify
from app.modules.socketio import emit_message
from app.modules.database import get_db, close_db
from app.modules.webhooks import webhook_log_score

webhook_scores_bp = Blueprint("webhook_scores", __name__)

@webhook_scores_bp.route("/webhook/scores/<int:vpin_score_id>", methods=["POST","PUT"])
@webhook_scores_bp.route("/webhook/scores", methods=["POST","PUT"])
def handle_webhook_log_score(vpin_score_id=None):
    """
    Webhook to handle score submissions from VPin Studio.
    It retrieves the score details via the VPin API and logs a new score entry in ArcadeScore.
    """
    try:
        data = request.get_json()

        conn = get_db()

        webhook_result = webhook_log_score(conn, data, vpin_score_id)

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        #     emit_message("game_score_update", {
        #         "gameID": game_id,
        #         "roomID": room_id,
        #         "scores": scores,
        #         "CSSScoreCards": css_score_cards,
        #         "CSSInitials": css_initials,
        #         "CSSScores": css_scores,
        #         "ScoreType": score_type
        #     })
        else:
            return jsonify({"message": webhook_result["message"]}), 400
        

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500