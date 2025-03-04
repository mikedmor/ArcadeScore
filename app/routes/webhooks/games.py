from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.webhooks import webhook_game, webhook_delete_game

webhook_games_bp = Blueprint('webhook_games', __name__)

@webhook_games_bp.route("/webhook/games", methods=["POST"])
@webhook_games_bp.route("/webhook/games/<int:vpin_game_id>", methods=["PUT"])
def handle_webhook_game(vpin_game_id=None):
    """
    Webhook to handle game creation (POST) and updates (PUT) from VPin Studio.
    It retrieves the necessary details via VPin API before storing the game.
    """
    try:
        data = request.get_json()

        conn = get_db()

        webhook_result = webhook_game(conn, data, vpin_game_id)

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"message": webhook_result["message"]}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@webhook_games_bp.route("/webhook/games/<int:vpin_game_id>", methods=["DELETE"])
def handle_webhook_delete_game(vpin_game_id):
    """
    Webhook to handle game deletions from VPin Studio.
    Deletes the corresponding ArcadeScore game.
    """
    try:
        data = request.get_json()

        conn = get_db()

        webhook_result = webhook_delete_game(conn, data, vpin_game_id)

        close_db()

        if webhook_result["success"]:
            return jsonify({"message": webhook_result["message"]}), 201
        else:
            return jsonify({"message": webhook_result["message"]}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    