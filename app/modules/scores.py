import traceback
from app.modules.database import get_db
from app.modules.utils import format_timestamp

def log_score_to_db(conn, data):
    """
    Logs a new score in the database. Creates a player if they don’t exist.
    :param data: Dictionary containing `gameName`, `playerName`, `score`, `roomID`.
    :return: (success: bool, message: str)
    """
    try:
        cursor = conn.cursor()

        game_name = data.get("gameName", "Unknown Game")
        player_identifier = data.get("playerName", "Unknown Player")
        score = data.get("score", 0)
        room_id = data.get("roomID", 0)

        # Fetch game_id based on game_name and room_id
        cursor.execute("""
            SELECT id, css_score_cards, css_initials, css_scores, score_type
            FROM games
            WHERE game_name = ? AND room_id = ?;
        """, (game_name, room_id))
        game_row = cursor.fetchone()

        if not game_row:
            return False, f"Game '{game_name}' not found for room ID {room_id}"

        game_id, css_score_cards, css_initials, css_scores, score_type = game_row

        # Fetch settings to determine how player names should be matched
        cursor.execute("SELECT long_names_enabled FROM settings WHERE id = ?;", (room_id,))
        settings = cursor.fetchone()
        long_names_enabled = settings[0] if settings else "FALSE"

        player_id = None

        if long_names_enabled == "TRUE":
            # Match player by `full_name`
            cursor.execute("SELECT id FROM players WHERE full_name = ?", (player_identifier,))
            player_row = cursor.fetchone()
        else:
            # Match player by `alias`
            cursor.execute("""
                SELECT p.id FROM players p
                JOIN aliases a ON p.id = a.player_id
                WHERE a.alias = ?;
            """, (player_identifier,))
            player_row = cursor.fetchone()

        if player_row:
            player_id = player_row[0]
        else:
            # Insert alias only if long_names_enabled is FALSE
            player_alias = ""
            if long_names_enabled == "FALSE":
                player_alias = player_identifier

            # Player does not exist, create a new one dynamically
            cursor.execute("""
                INSERT INTO players (full_name, default_alias, long_names_enabled)
                VALUES (?, ?, ?);
            """, (player_identifier, player_alias, long_names_enabled))
            player_id = cursor.lastrowid
            
            if long_names_enabled == "FALSE":
                cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, player_alias))

        # Insert score into highscores table
        cursor.execute("""
            INSERT INTO highscores (game_id, player_id, score, room_id)
            VALUES (?, ?, ?, ?);
        """, (game_id, player_id, score, room_id))

        conn.commit()

        return True, "Score logged successfully!"

    except Exception as e:
        print(f"Error logging score: {traceback.format_exc()}")
        return False, str(e)

def get_high_scores(conn):
    """
    Retrieves high scores with game and player details.
    :return: List of scores in dictionary format.
    """
    try:
        cursor = conn.cursor()

        # Fetch highscores with game and player info
        cursor.execute("""
            SELECT DISTINCT h.game_id, 
                CASE 
                    WHEN s.long_names_enabled = 'TRUE' OR p.long_names_enabled = 'TRUE' THEN p.full_name 
                    ELSE p.default_alias 
                END AS player_name,
                h.score, h.event, h.wins, h.losses, h.timestamp, p.hidden
            FROM highscores h
            JOIN players p ON h.player_id = p.id
            JOIN settings s ON s.id = h.room_id
            WHERE h.room_id = ?
            ORDER BY h.game_id, h.score DESC;
        """)

        results = cursor.fetchall()

        # Format the results into a JSON array
        scores = [
            {
                "gameName": row[0],
                "playerName": row[1],
                "score": row[2],
                "roomID": row[3],
                "timestamp": row[4]
            }
            for row in results
        ]

        return scores

    except Exception as e:
        print(f"Error retrieving high scores: {traceback.format_exc()}")
        return {"error": str(e)}
