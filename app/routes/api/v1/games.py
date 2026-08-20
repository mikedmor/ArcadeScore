from flask import Blueprint, request, jsonify
from app.modules.database import get_db
from app.modules.socketio import emit_message
from app.modules.games import save_game_to_db, delete_game_from_db
from app.modules.auth import require_room_admin

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
@require_room_admin(room_id_from_game=True)
def save_game(game_id=None):
    data = request.get_json()
    success, message, saved_game_id = save_game_to_db(get_db(), data, game_id)

    if success:
        return jsonify({"message": message, "game_id": saved_game_id}), 200
    else:
        return jsonify({"error": message}), 400

@games_bp.route("/api/v1/games/<int:game_id>", methods=["DELETE"])
@require_room_admin(room_id_from_game=True)
def delete_game(game_id):
    """
    API route to delete a game by its ArcadeScore ID.
    """
    success, message = delete_game_from_db(get_db(), game_id)
    

    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400

@games_bp.route("/api/v1/games/<int:game_id>/hide", methods=["PUT"])
@require_room_admin(room_id_from_game=True)
def toggle_game_visibility(game_id):
    try:
        data = request.get_json()
        new_hidden_status = data.get("hidden", "FALSE")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT room_id FROM games WHERE id = ?", (game_id,))
        game = cursor.fetchone()
        if not game:
            return jsonify({"error": "Game not found"}), 404
        room_id = game["room_id"]

        cursor.execute("""
            UPDATE games SET hidden = ? WHERE id = ?;
        """, (new_hidden_status, game_id))

        conn.commit()

        # Emit WebSocket event
        game_visibility_toggle = {"gameID": game_id, "roomID": room_id, "hidden": new_hidden_status}
        print(f"Emit game_visibility_toggled socket: {game_visibility_toggle}")
        emit_message("game_visibility_toggled", game_visibility_toggle, room=f"room_{room_id}")

        return jsonify({"message": "Game visibility updated successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@games_bp.route("/api/v1/games/update-game-order", methods=["POST"])
@require_room_admin
def update_game_order():
    try:
        payload = request.get_json()
        # Accept either the legacy bare list, or {roomID, games: [...]}, so room-scoping
        # the socket emit doesn't require every caller to already send a roomID.
        if isinstance(payload, dict):
            room_id = payload.get("roomID")
            games = payload.get("games", [])
        else:
            room_id = None
            games = payload

        conn = get_db()
        cursor = conn.cursor()

        for game in games:
            cursor.execute("""
                UPDATE games SET game_sort = ? WHERE id = ?;
            """, (game["game_sort"], game["game_id"]))

        if room_id is None and games:
            cursor.execute("SELECT room_id FROM games WHERE id = ?", (games[0]["game_id"],))
            row = cursor.fetchone()
            room_id = row["room_id"] if row else None

        conn.commit()

        # Emit WebSocket event
        print(f"Emit game_order_update socket: {games}")
        emit_message("game_order_update", games, room=f"room_{room_id}" if room_id else None)

        return jsonify({"message": "Game order updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500