from flask import Blueprint, request, jsonify
from app.database import get_db

scores_bp = Blueprint('scores', __name__)

@scores_bp.route("/api/v1/scores", methods=["POST"])
def log_score():
    try:
        if request.is_json:
            data = request.get_json()
            game_name = data.get("gameName", "Unknown Game")
            player_identifier = data.get("playerName", "Unknown Player")
            score = data.get("score", 0)
            room_id = data.get("roomID", 0)

            conn = get_db()
            cursor = conn.cursor()

            # Fetch game_id based on game_name and room_id
            cursor.execute("""
                SELECT id FROM games
                WHERE game_name = ? AND room_id = ?;
            """, (game_name, room_id))
            game_row = cursor.fetchone()

            if not game_row:
                return jsonify({"error": f"Game '{game_name}' not found for room ID {room_id}"}), 404

            game_id = game_row[0]

            # Fetch settings to determine how player names should be matched
            cursor.execute("""
                SELECT long_names_enabled FROM settings WHERE id = ?;
            """, (room_id,))
            settings = cursor.fetchone()
            long_names_enabled = settings[0] if settings else "FALSE"

            player_id = None

            if long_names_enabled == "TRUE":
                # Match player by `full_name`
                cursor.execute("SELECT id FROM players WHERE full_name = ?", (player_identifier,))
                player_row = cursor.fetchone()
            else:
                # 🔥 Match player by `alias`
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
            conn.close()

            return jsonify({"message": "Score logged successfully!"}), 201
        else:
            return jsonify({"error": "Invalid JSON format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
   
@scores_bp.route("/highscores", methods=["GET"])
def get_scores():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Join the highscores table with the games table to get the game_name
        cursor.execute("""
            SELECT g.game_name, 
                CASE 
                    WHEN s.long_names_enabled = 'TRUE' OR p.long_names_enabled = 'TRUE' THEN p.full_name 
                    ELSE p.default_alias 
                END AS player_name,
                h.score, h.room_id, h.timestamp
            FROM highscores h
            JOIN games g ON h.game_id = g.id
            JOIN players p ON h.player_id = p.id
            JOIN settings s ON s.id = h.room_id
            ORDER BY h.score DESC;
        """)
        
        results = cursor.fetchall()
        conn.close()
        
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
        
        return jsonify(scores)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
