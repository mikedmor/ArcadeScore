import eventlet
from flask import Blueprint, request, jsonify, current_app
from app.modules.database import get_db, close_db
from app.background.create_scoreboards import process_scoreboard_task

scoreboards_bp = Blueprint("scoreboards", __name__)

# Store task status
TASK_STATUS = {}

@scoreboards_bp.route("/api/v1/scoreboards", methods=["POST"])
async def create_scoreboard():
    """Trigger async background task for scoreboard creation."""
    app = current_app._get_current_object()  # Get Flask app instance

    data = request.get_json()

    print(f"Scheduling process_scoreboard_task for task...")

    # Run the async task in the existing event loop
    eventlet.spawn_n(process_scoreboard_task, app, data)

    print(f"Scoreboard Task scheduled using eventlet.spawn_n, returning response immediately.")

    return jsonify({"message": "Scoreboard creation started"}), 202

@scoreboards_bp.route("/api/v1/scoreboards", methods=["GET"])
def get_scoreboards():
    """Fetch all scoreboards with game colors, number of games, and scores."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch all scoreboards (settings table)
        cursor.execute("SELECT id, user, room_name FROM settings")
        scoreboards = cursor.fetchall()

        scoreboard_data = []
        
        for sb in scoreboards:
            room_id = sb["id"]

            # Fetch games for this scoreboard (sorted by game_sort)
            cursor.execute("""
                SELECT game_color FROM games 
                WHERE room_id = ? 
                ORDER BY game_sort ASC
            """, (room_id,))
            games = cursor.fetchall()

            game_colors = [g["game_color"] for g in games if g["game_color"]]
            num_games = len(games)

            # Fetch number of scores for this room
            cursor.execute("""
                SELECT COUNT(*) FROM highscores 
                WHERE game_id IN (SELECT id FROM games WHERE room_id = ?)
            """, (room_id,))
            num_scores = cursor.fetchone()["COUNT(*)"]

            scoreboard_data.append({
                "id": room_id,
                "user": sb["user"],
                "room_name": sb["room_name"],
                "game_colors": game_colors,
                "num_games": num_games,
                "num_scores": num_scores,
            })

        close_db()
        return jsonify(scoreboard_data)

    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500    

@scoreboards_bp.route("/api/v1/scoreboards/<int:scoreboard_id>", methods=["GET"])
def get_scoreboard(scoreboard_id):
    """Fetch a specific scoreboard."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id, room_name FROM settings WHERE id = ?", (scoreboard_id,))
        scoreboard = cursor.fetchone()
        close_db()

        if not scoreboard:
            return jsonify({"error": "Scoreboard not found"}), 404

        return jsonify({"id": scoreboard["id"], "room_name": scoreboard["room_name"]})

    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500


@scoreboards_bp.route("/api/v1/scoreboards/<int:scoreboard_id>", methods=["PUT"])
def update_scoreboard(scoreboard_id):
    """Update a scoreboard's name."""
    try:
        data = request.get_json()
        new_name = data.get("room_name")

        if not new_name:
            return jsonify({"error": "room_name is required"}), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("UPDATE settings SET room_name = ? WHERE id = ?", (new_name, scoreboard_id))
        conn.commit()
        close_db()

        return jsonify({"message": "Scoreboard updated!"}), 200

    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500

    
@scoreboards_bp.route("/api/v1/scoreboards/<int:scoreboard_id>", methods=["DELETE"])
def delete_scoreboard(scoreboard_id):
    """Delete a scoreboard and all related data (scores, games, VPin games)."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if the scoreboard exists
        cursor.execute("SELECT id FROM settings WHERE id = ?", (scoreboard_id,))
        scoreboard = cursor.fetchone()

        if not scoreboard:
            return jsonify({"error": "Scoreboard not found"}), 404

        # Delete related VPin games
        cursor.execute("""
            DELETE FROM vpin_games
            WHERE arcadescore_game_id IN (
                SELECT id FROM games WHERE room_id = ?
            );
        """, (scoreboard_id,))

        # Delete games linked to this scoreboard
        cursor.execute("DELETE FROM games WHERE room_id = ?", (scoreboard_id,))

        # Delete scores related to this scoreboard
        cursor.execute("DELETE FROM highscores WHERE room_id = ?", (scoreboard_id,))

        # Delete the scoreboard itself
        cursor.execute("DELETE FROM settings WHERE id = ?", (scoreboard_id,))

        conn.commit()
        close_db()
        return jsonify({"message": "Scoreboard and related data deleted successfully."}), 200

    except Exception as e:
        close_db()
        return jsonify({"error": "Failed to delete scoreboard", "details": str(e)}), 500

@scoreboards_bp.route("/api/v1/scoreboards/<int:scoreboard_id>/scores", methods=["DELETE"])
def clear_scores(scoreboard_id):
    """Clear all scores from a specific scoreboard."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Verify if the scoreboard exists
        cursor.execute("SELECT id FROM settings WHERE id = ?", (scoreboard_id,))
        scoreboard = cursor.fetchone()

        if not scoreboard:
            return jsonify({"error": "Scoreboard not found"}), 404

        # Delete all scores linked to the scoreboard
        cursor.execute("DELETE FROM highscores WHERE room_id = ?", (scoreboard_id,))

        conn.commit()
        close_db()
        return jsonify({"message": "All scores cleared successfully."}), 200

    except Exception as e:
        close_db()
        return jsonify({"error": "Failed to clear scores", "details": str(e)}), 500


@scoreboards_bp.route("/api/v1/scoreboards/<int:scoreboard_id>/games", methods=["DELETE"])
def clear_games(scoreboard_id):
    """Clear all games (and related VPin games) from a specific scoreboard."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Verify if the scoreboard exists
        cursor.execute("SELECT id FROM settings WHERE id = ?", (scoreboard_id,))
        scoreboard = cursor.fetchone()

        if not scoreboard:
            return jsonify({"error": "Scoreboard not found"}), 404

        # First, delete any VPin games linked to the games in this scoreboard
        cursor.execute("""
            DELETE FROM vpin_games 
            WHERE arcadescore_game_id IN (
                SELECT id FROM games WHERE room_id = ?
            );
        """, (scoreboard_id,))

        # Delete games from the scoreboard
        cursor.execute("DELETE FROM games WHERE room_id = ?", (scoreboard_id,))

        # Delete scores associated with those games
        cursor.execute("""
            DELETE FROM highscores
            WHERE game_id NOT IN (SELECT id FROM games)
        """)

        conn.commit()
        close_db()
        return jsonify({"message": "All games cleared successfully."}), 200

    except Exception as e:
        close_db()
        return jsonify({"error": "Failed to clear games", "details": str(e)}), 500
