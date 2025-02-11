from app.modules.database import get_db
from app.modules.socketio import emit_message

def save_game_to_db(data, game_id=None):
    """
    Creates or updates a game in the database.
    :param data: Dictionary containing game details.
    :param game_id: If provided, updates an existing game.
    :return: (success: bool, message: str, game_id: int or None)
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Determine styles based on preset, copy, or custom values
        game_styles = None
        if data.get("css_style") and data["css_style"].isdigit():
            cursor.execute(
                "SELECT css_score_cards, css_initials, css_scores, css_box, css_title FROM presets WHERE id = ?",
                (int(data["css_style"]),),
            )
            game_styles = cursor.fetchone()
            if not game_styles:
                return False, "Preset not found.", None

        elif data.get("css_style") == "_copy" and data.get("css_copy"):
            cursor.execute(
                "SELECT css_score_cards, css_initials, css_scores, css_box, css_title FROM games WHERE id = ?",
                (data.get("css_copy"),),
            )
            game_styles = cursor.fetchone()
            if not game_styles:
                return False, "Game to copy styles from not found.", None

        # Apply game styles or use provided styles
        styles = {
            "css_score_cards": game_styles["css_score_cards"] if game_styles else data.get("css_score_cards"),
            "css_initials": game_styles["css_initials"] if game_styles else data.get("css_initials"),
            "css_scores": game_styles["css_scores"] if game_styles else data.get("css_scores"),
            "css_box": game_styles["css_box"] if game_styles else data.get("css_box"),
            "css_title": game_styles["css_title"] if game_styles else data.get("css_title"),
        }

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
            cursor.execute(
                """
                UPDATE games
                SET game_name = ?, css_score_cards = ?, css_initials = ?, css_scores = ?, css_box = ?, css_title = ?,
                    score_type = ?, sort_ascending = ?, game_image = ?, game_background = ?,
                    tags = ?, hidden = ?, game_color = ?
                WHERE id = ?;
                """,
                game_data + (game_id,),
            )

        else:  # INSERT new game
            cursor.execute("SELECT MAX(game_sort) FROM games WHERE room_id = ?", (data.get("room_id"),))
            max_sort = cursor.fetchone()[0]
            new_sort_order = (max_sort + 1) if max_sort else 1

            cursor.execute(
                """
                INSERT INTO games (game_name, css_score_cards, css_initials, css_scores, css_box, css_title,
                                score_type, sort_ascending, game_image, game_background,
                                tags, hidden, game_color, room_id, game_sort)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                game_data + (data.get("room_id"), new_sort_order),
            )
            game_id = cursor.lastrowid

        # Retrieve global settings
        cursor.execute("SELECT css_body, css_card FROM settings LIMIT 1;")
        settings = cursor.fetchone()

        conn.commit()

        # Emit socket event for real-time updates
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
            "tags": data.get("tags"),
            "Hidden": data.get("hidden"),
            "GameColor": data.get("game_color"),
            "css_card": settings["css_card"]
        }
        emit_message("game_update", updated_game)

        return True, "Game saved successfully!", game_id

    except Exception as e:
        return False, f"Error saving game: {str(e)}", None

def delete_game_from_db(game_id):
    """
    Deletes a game from the database, including its associated scores.
    
    :param game_id: The internal ArcadeScore game ID to delete.
    :return: (success: bool, message: str)
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if the game exists
        cursor.execute("SELECT id FROM games WHERE id = ?", (game_id,))
        game = cursor.fetchone()
        if not game:
            return False, "Game not found"

        # Delete associated scores first (to prevent foreign key issues)
        cursor.execute("DELETE FROM highscores WHERE game_id = ?", (game_id,))

        # Delete from `vpin_games` to maintain data integrity
        cursor.execute("DELETE FROM vpin_games WHERE arcadescore_game_id = ?", (game_id,))

        # Delete the game entry
        cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))

        # Commit changes and close the connection
        conn.commit()

        # Emit WebSocket event
        deleted_game = {"gameID": game_id}
        emit_message("game_deleted", deleted_game)
        print(f"Emit game_deleted socket: {deleted_game}")

        return True, "Game deleted successfully"

    except Exception as e:
        return False, f"Error deleting game: {str(e)}"