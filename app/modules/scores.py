import traceback
from app.modules.socketio import emit_message

def unhide_game_if_auto_hidden(conn, room_id, game_id):
    """If this room auto-hides scoreless games and this game is currently hidden,
    un-hide it now that it has a score. Called after every successful score
    insert, from whichever of the several score-writing paths (internal API,
    VPin webhook, VPin historical import, legacy publicCommands.php) it was."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT auto_hide_no_score_games FROM settings WHERE id = ?;", (room_id,))
        room_settings = cursor.fetchone()
        if not room_settings or room_settings["auto_hide_no_score_games"] != "TRUE":
            return

        cursor.execute("SELECT hidden FROM games WHERE id = ?;", (game_id,))
        game_row = cursor.fetchone()
        if not game_row or game_row["hidden"] != "TRUE":
            return

        cursor.execute("UPDATE games SET hidden = 'FALSE' WHERE id = ?;", (game_id,))
        conn.commit()

        emit_message("game_visibility_toggled", {"gameID": game_id, "roomID": room_id, "hidden": "FALSE"}, room=f"room_{room_id}")
    except Exception:
        print(f"⚠️ Failed to auto-unhide game {game_id}: {traceback.format_exc()}")

def log_score_to_db(conn, data):
    """
    Logs a new score in the database. Creates a player if they don’t exist.
    :param data: Dictionary containing `game_id`, `player_id`, `score`, `room_id`, `timestamp`.
    :return: (success: bool, message: str)
    """
    try:
        cursor = conn.cursor()

        game_id = int(data.get("game_id"))
        player_id = int(data.get("player_id"))
        score = int(data.get("score", 0))
        room_id = int(data.get("room_id"))
        timestamp = data.get("timestamp")  # Ensure we use the timestamp from historical scores

        if not game_id or not player_id:
            return False, f"Invalid data: game_id ({game_id}) or player_id ({player_id}) is missing."

        # Insert score into highscores table
        cursor.execute("""
            INSERT INTO highscores (game_id, player_id, score, room_id, timestamp)
            VALUES (?, ?, ?, ?, ?);
        """, (game_id, player_id, score, room_id, timestamp))

        conn.commit()

        unhide_game_if_auto_hidden(conn, room_id, game_id)

        print(f"✅ Score logged: Player {player_id}, Game {game_id}, Score {score}, Room {room_id}, Time {timestamp}")
        return True, "Score logged successfully!"

    except Exception as e:
        print(f"❌ Error logging score: {traceback.format_exc()}")
        return False, str(e)

def get_high_scores(conn, room_id):
    """
    Retrieves high scores for one room, with game and player details.
    :return: List of scores in dictionary format.
    """
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT h.game_id,
                CASE
                    WHEN s.long_names_enabled = 'TRUE' OR p.long_names_enabled = 'TRUE' THEN p.full_name
                    ELSE p.default_alias
                END AS player_name,
                h.score, h.room_id, h.event, h.wins, h.losses, h.timestamp, p.hidden
            FROM highscores h
            JOIN players p ON h.player_id = p.id
            JOIN settings s ON s.id = h.room_id
            JOIN games g ON g.id = h.game_id
            WHERE h.room_id = ?
            ORDER BY h.game_id, CASE WHEN g.sort_ascending = 'TRUE' THEN h.score ELSE -h.score END ASC;
        """, (room_id,))

        results = cursor.fetchall()

        # Format the results into a JSON array
        scores = [
            {
                "gameID": row[0],
                "playerName": row[1],
                "score": row[2],
                "roomID": row[3],
                "event": row[4],
                "wins": row[5],
                "losses": row[6],
                "timestamp": row[7],
                "hidden": row[8],
            }
            for row in results
        ]

        return scores

    except Exception as e:
        print(f"Error retrieving high scores: {traceback.format_exc()}")
        return {"error": str(e)}
