from flask import Blueprint, request, jsonify
from app.modules.database import get_db
from app.modules.webhooks import webhook_game, webhook_delete_game, record_webhook_health

webhook_games_bp = Blueprint('webhook_games', __name__)

@webhook_games_bp.route("/webhook/games", methods=["POST"])
@webhook_games_bp.route("/webhook/games", methods=["PUT"])
@webhook_games_bp.route("/webhook/games/<int:vpin_game_id>", methods=["PUT"])
def handle_webhook_game(vpin_game_id=None):
    """
    Webhook to handle game creation (POST) and updates (PUT) from VPin Studio.
    UPDATE events pass the game id in the body, not as a URL segment, so the
    bare PUT route is required alongside the POST route.
    It retrieves the necessary details via VPin API before storing the game.
    """
    try:
        data = request.get_json(silent=True) or {}

        conn = get_db()

        webhook_result = webhook_game(conn, data, vpin_game_id)

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
    
@webhook_games_bp.route("/webhook/games/<int:vpin_game_id>", methods=["DELETE"])
def handle_webhook_delete_game(vpin_game_id):
    """
    Webhook to handle game deletions from VPin Studio.
    Deletes the corresponding ArcadeScore game. DELETE webhooks carry no body,
    so this must not fail on an empty/missing payload.
    """
    try:
        data = request.get_json(silent=True) or {}

        conn = get_db()

        webhook_result = webhook_delete_game(conn, data, vpin_game_id)


        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"error": webhook_result.get("error", "Unknown error occurred")}), 400

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    