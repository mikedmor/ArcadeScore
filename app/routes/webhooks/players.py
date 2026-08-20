from flask import Blueprint, request, jsonify
from app.modules.database import get_db
from app.modules.webhooks import webhook_player, webhook_delete_player, record_webhook_health

webhook_players_bp = Blueprint('webhook_players', __name__)

@webhook_players_bp.route("/webhook/players", methods=["POST"])
@webhook_players_bp.route("/webhook/players", methods=["PUT"])
@webhook_players_bp.route("/webhook/players/<int:vpin_player_id>", methods=["PUT"])
def handle_webhook_player(vpin_player_id=None):
    """
    Webhook to handle player creation (POST) and updates (PUT) from VPin Studio.
    UPDATE events pass the player id in the body, not as a URL segment, so the
    bare PUT route is required alongside the POST route.
    It retrieves necessary details via the VPin API before storing the player.
    """
    try:
        data = request.get_json(silent=True) or {}

        conn = get_db()

        webhook_result = webhook_player(conn, data, vpin_player_id)

        record_webhook_health(
            conn,
            webhook_result.get("room_id"),
            error=None if webhook_result.get("success") else webhook_result.get("error"),
        )


        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"error": webhook_result.get("error", "Unknown error occurred")}), 400

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    

@webhook_players_bp.route("/webhook/players/<int:vpin_player_id>", methods=["DELETE"])
def handle_webhook_delete_player(vpin_player_id):
    """
    Webhook to handle player deletions from VPin Studio.
    Deletes the corresponding ArcadeScore player. DELETE webhooks carry no body,
    so this must not fail on an empty/missing payload.
    """
    try:
        data = request.get_json(silent=True) or {}

        conn = get_db()

        webhook_result = webhook_delete_player(conn, data, vpin_player_id)


        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"error": webhook_result.get("error", "Unknown error occurred")}), 400

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
