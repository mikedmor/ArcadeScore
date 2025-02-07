from flask import Blueprint, request, jsonify
from app.database import get_db
from app.modules.sockets import emit_message

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
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if css_style is a preset ID
        game_styles = None
        if data.get("css_style") and data["css_style"].isdigit():
            preset_id = int(data["css_style"])
            cursor.execute(
                "SELECT css_score_cards, css_initials, css_scores, css_box, css_title FROM presets WHERE id = ?", 
                (preset_id,)
            )
            game_styles = cursor.fetchone()

            if not game_styles:
                return jsonify({"error": "Preset not found."}), 400

        # Check if copying styles from another game
        elif data.get("css_style") == "_copy" and data.get("css_copy"):
            cursor.execute(
                "SELECT css_score_cards, css_initials, css_scores, css_box, css_title FROM games WHERE id = ?", 
                (data.get("css_copy"),)
            )
            game_styles = cursor.fetchone()

            if not game_styles:
                return jsonify({"error": "Game not found."}), 400

        # Use preset/game styles OR custom styles
        styles = {
            "css_score_cards": game_styles["css_score_cards"] if game_styles else data.get("css_score_cards"),
            "css_initials": game_styles["css_initials"] if game_styles else data.get("css_initials"),
            "css_scores": game_styles["css_scores"] if game_styles else data.get("css_scores"),
            "css_box": game_styles["css_box"] if game_styles else data.get("css_box"),
            "css_title": game_styles["css_title"] if game_styles else data.get("css_title"),
        }

        # Extract other fields
        game_data = (
            data.get("game_name"),
            styles["css_score_cards"],
            styles["css_initials"],
            styles["css_scores"],
            styles["css_box"],
            styles["css_title"],
            data.get("score_type"),
            data.get("sort_ascending"),
            data.get("game_image"),
            data.get("game_background"),
            data.get("tags"),
            data.get("hidden"),
            data.get("game_color"),
        )

        if game_id:  # UPDATE existing game
            print(f"Updating game with ID: {game_id}")  # Debugging log
            cursor.execute("""
                UPDATE games
                SET game_name = ?, css_score_cards = ?, css_initials = ?, css_scores = ?, css_box = ?, css_title = ?,
                    score_type = ?, sort_ascending = ?, game_image = ?, game_background = ?,
                    tags = ?, hidden = ?, game_color = ?
                WHERE id = ?;
            """, game_data + (game_id,))
        else:  # INSERT new game
            print("Inserting new game")  # Debugging log
            cursor.execute("SELECT MAX(game_sort) FROM games WHERE room_id = ?", (data.get("room_id"),))
            max_sort = cursor.fetchone()[0]
            new_sort_order = (max_sort + 1) if max_sort else 1  # Default to 1 if no games exist

            # Append room_id and game_sort to existing game_data tuple
            cursor.execute("""
                INSERT INTO games (game_name, css_score_cards, css_initials, css_scores, css_box, css_title,
                                score_type, sort_ascending, game_image, game_background,
                                tags, hidden, game_color, room_id, game_sort)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, game_data + (data.get("room_id"), new_sort_order))

        # retrieve the css_card from settings
        cursor.execute("SELECT css_body, css_card FROM settings LIMIT 1;")
        settings = cursor.fetchone()

        conn.commit()
        conn.close()

        # Fetch updated game details (for socket)
        updated_game = {
            "gameID": game_id,
            "roomID": data.get("room_id"),
            "gameName": data.get("game_name"),
            "CSSScoreCards": styles["css_score_cards"],
            "CSSInitials": styles["css_initials"],
            "CSSScores": styles["css_scores"],
            "CSSBox": styles["css_box"],
            "CSSTitle": styles["css_title"],
            "ScoreType": data.get("score_type"),
            "SortAscending": data.get("sort_ascending"),
            "GameImage": data.get("game_image"),
            "GameBackground": data.get("game_background"),
            "GameSort": data.get("game_sort"),
            "tags": data.get("tags"),
            "Hidden": data.get("hidden"),
            "GameColor": data.get("game_color"),
            "css_card": settings["css_card"]
        }

        # Emit WebSocket event
        print(f"Emit game_update socket: {updated_game}")
        emit_message("game_update", updated_game)

        return jsonify({"message": "Game saved successfully!"}), 200

    except Exception as e:
        print("Error in save_game:", str(e))  # Debugging log
        return jsonify({"error": str(e)}), 500

@games_bp.route("/api/v1/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if the game exists
        cursor.execute("SELECT id FROM games WHERE id = ?", (game_id,))
        game = cursor.fetchone()
        if not game:
            return jsonify({"error": "Game not found"}), 404

        # Delete associated scores first (to prevent foreign key issues)
        cursor.execute("DELETE FROM highscores WHERE game_id = ?", (game_id,))

        # Delete the game entry
        cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))

        # Commit changes and close the connection
        conn.commit()
        conn.close()

        # Emit WebSocket event
        deleted_game = {"gameID": game_id}
        print(f"Emit game_deleted socket: {deleted_game}")
        emit_message("game_update", deleted_game)

        return jsonify({"message": "Game deleted successfully"}), 200

    except Exception as e:
        print(f"Error deleting game: {e}")
        return jsonify({"error": str(e)}), 500

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
        print(f"Emit game_deleted socket: {game_visibility_toggle}")
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
        print(f"Emit game_deleted socket: {data}")
        emit_message("game_order_update", data)

        return jsonify({"message": "Game order updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500