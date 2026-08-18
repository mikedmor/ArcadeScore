from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.webhooks import webhook_pause_state, record_webhook_health

webhook_pause_bp = Blueprint("webhook_pause", __name__)

@webhook_pause_bp.route("/webhook/pause", methods=["PUT"])
def handle_webhook_pause():
    """
    Webhook fired when a table's pause menu is opened on the cabinet. Purely a
    "someone is playing this right now" notification - never causes ArcadeScore
    to pause anything.
    """
    try:
        data = request.get_json(silent=True) or {}

        conn = get_db()

        webhook_result = webhook_pause_state(conn, data, paused=True)

        record_webhook_health(
            conn,
            webhook_result.get("room_id"),
            error=None if webhook_result.get("success") else webhook_result.get("error"),
        )

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"error": webhook_result.get("error", "Unknown error occurred")}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@webhook_pause_bp.route("/webhook/unpause", methods=["PUT"])
def handle_webhook_unpause():
    """Webhook fired when a table's pause menu is closed (play resumed) on the cabinet."""
    try:
        data = request.get_json(silent=True) or {}

        conn = get_db()

        webhook_result = webhook_pause_state(conn, data, paused=False)

        record_webhook_health(
            conn,
            webhook_result.get("room_id"),
            error=None if webhook_result.get("success") else webhook_result.get("error"),
        )

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"error": webhook_result.get("error", "Unknown error occurred")}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
