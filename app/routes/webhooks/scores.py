from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.webhooks import webhook_log_score

webhook_scores_bp = Blueprint("webhook_scores", __name__)

@webhook_scores_bp.route("/webhook/scores", methods=["PUT"])
def handle_webhook_log_score():
    """
    Webhook to handle score submissions from VPin Studio.
    It retrieves the score details via the VPin API and logs a new score entry in ArcadeScore.
    """
    try:
        data = request.get_json()

        conn = get_db()

        webhook_result = webhook_log_score(conn, data)

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        elif "error" in webhook_result:
            return jsonify({"error": webhook_result["error"]}), 400
        else:
            return jsonify({"error": "Unknown error occurred"}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500