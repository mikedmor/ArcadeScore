import traceback

def log_score_to_db(conn, data):
    """
    Logs a new score in the database. Creates a player if they don’t exist.
    :param data: Dictionary containing `game_id`, `player_id`, `score`, `room_id`, `timestamp`.
    :return: (success: bool, message: str)
    """
    try:
        cursor = conn.cursor()

        game_id = data.get("game_id")
        player_id = data.get("player_id")
        score = data.get("score", 0)
        room_id = data.get("room_id")
        timestamp = data.get("timestamp")  # Ensure we use the timestamp from historical scores

        if not game_id or not player_id:
            return False, f"Invalid data: game_id ({game_id}) or player_id ({player_id}) is missing."

        # Insert score into highscores table
        cursor.execute("""
            INSERT INTO highscores (game_id, player_id, score, room_id, timestamp)
            VALUES (?, ?, ?, ?, ?);
        """, (game_id, player_id, score, room_id, timestamp))

        conn.commit()

        print(f"✅ Score logged: Player {player_id}, Game {game_id}, Score {score}, Room {room_id}, Time {timestamp}")
        return True, "Score logged successfully!"

    except Exception as e:
        print(f"❌ Error logging score: {traceback.format_exc()}")
        return False, str(e)

# TODO: This needs to be fixed as it currently does not get passed a room_id
def get_high_scores(conn):
    """
    Retrieves high scores with game and player details.
    :return: List of scores in dictionary format.
    """
    try:
        cursor = conn.cursor()

        # TODO: Fetch highscores with game and player info including the room
        # cursor.execute("""
        #     SELECT DISTINCT h.game_id, 
        #         CASE 
        #             WHEN s.long_names_enabled = 'TRUE' OR p.long_names_enabled = 'TRUE' THEN p.full_name 
        #             ELSE p.default_alias 
        #         END AS player_name,
        #         h.score, h.event, h.wins, h.losses, h.timestamp, p.hidden
        #     FROM highscores h
        #     JOIN players p ON h.player_id = p.id
        #     JOIN settings s ON s.id = h.room_id
        #     WHERE h.room_id = ?
        #     ORDER BY h.game_id, h.score DESC;
        # """)
        
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
