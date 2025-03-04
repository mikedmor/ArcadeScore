from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.webhooks import webhook_player, webhook_delete_player

webhook_players_bp = Blueprint('webhook_players', __name__)

@webhook_players_bp.route("/webhook/players", methods=["POST"])
@webhook_players_bp.route("/webhook/players/<int:vpin_player_id>", methods=["PUT"])
def handle_webhook_player(vpin_player_id=None):
    """
    Webhook to handle player creation (POST) and updates (PUT) from VPin Studio.
    It retrieves necessary details via the VPin API before storing the player.
    """
    try:
        data = request.get_json()

        conn = get_db()

        webhook_result = webhook_player(conn, data, vpin_player_id)

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"message": webhook_result["message"]}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    

@webhook_players_bp.route("/webhook/players/<int:vpin_player_id>", methods=["DELETE"])
def handle_webhook_delete_player(vpin_player_id):
    """
    Webhook to handle player deletions from VPin Studio.
    Deletes the corresponding ArcadeScore player.
    """
    try:
        data = request.get_json()
        
        conn = get_db()

        webhook_result = webhook_delete_player(conn, data, vpin_player_id)

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"message": webhook_result["message"]}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
