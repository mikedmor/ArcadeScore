from flask import Blueprint, request, jsonify
from app.modules.database import get_db
from app.modules.socketio import emit_message
from app.modules.game import save_game_to_db, delete_game_from_db

games_bp = Blueprint('games', __name__)

# GET single game by ID
@games_bp.route("/api/v1/games/<int:game_id>", methods=["GET"])
def get_game(game_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch the game by its ID
        cursor.execute("""
            SELECT id, game_name, css_score_cards, css_initials, css_scores, css_box, css_title,
                score_type, sort_ascending, game_image, game_background, tags, hidden, game_color, room_id
            FROM games
            WHERE id = ?;
        """, (game_id,))

        game = cursor.fetchone()
        conn.close()

        if game:
            game_data = {
                "gameID": game[0],
                "gameName": game[1],
                "CSSScoreCards": game[2] or "",
                "CSSInitials": game[3] or "",
                "CSSScores": game[4] or "",
                "CSSBox": game[5] or "",
                "CSSTitle": game[6] or "",
                "ScoreType": game[7] or "",
                "SortAscending": game[8] or "",
                "GameImage": game[9] or "",
                "GameBackground": game[10] or "",
                "tags": game[11] or "",
                "Hidden": game[12] or "FALSE",
                "GameColor": game[13] or "#FFFFFF",
                "RoomID": game[14]
            }
            return jsonify(game_data), 200
        else:
            return jsonify({"error": "Game not found"}), 404

    except Exception as e:
        print("Error fetching game:", str(e))  # Debugging log
        return jsonify({"error": str(e)}), 500

# POST & PUT game (Add or Update)
@games_bp.route("/api/v1/games", methods=["POST"])
@games_bp.route("/api/v1/games/<int:game_id>", methods=["PUT"])
def save_game(game_id=None):
    data = request.get_json()
    success, message, saved_game_id = save_game_to_db(data, game_id)

    if success:
        return jsonify({"message": message, "game_id": saved_game_id}), 200
    else:
        return jsonify({"error": message}), 400

@games_bp.route("/api/v1/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    """
    API route to delete a game by its ArcadeScore ID.
    """
    success, message = delete_game_from_db(game_id)

    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400

@games_bp.route("/api/v1/games/<int:game_id>/hide", methods=["PUT"])
def toggle_game_visibility(game_id):
    try:
        data = request.get_json()
        new_hidden_status = data.get("hidden", "FALSE")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE games SET hidden = ? WHERE id = ?;
        """, (new_hidden_status, game_id))

        conn.commit()
        conn.close()

        # Emit WebSocket event
        game_visibility_toggle = {"gameID": game_id, "hidden": new_hidden_status}
        print(f"Emit game_visibility_toggled socket: {game_visibility_toggle}")
        emit_message("game_visibility_toggled", game_visibility_toggle)

        return jsonify({"message": "Game visibility updated successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@games_bp.route("/api/v1/games/update-game-order", methods=["POST"])
def update_game_order():
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()

        for game in data:
            cursor.execute("""
                UPDATE games SET game_sort = ? WHERE id = ?;
            """, (game["game_sort"], game["game_id"]))

        conn.commit()
        conn.close()

        # Emit WebSocket event
        print(f"Emit game_order_update socket: {data}")
        emit_message("game_order_update", data)

        return jsonify({"message": "Game order updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500