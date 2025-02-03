import os
from flask import Blueprint, request, jsonify
from app.database import get_db
import json

players_bp = Blueprint("players", __name__)

UPLOAD_FOLDER = "static/images/avatars"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    """Check if a file has a valid extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@players_bp.route("/api/v1/players", methods=["GET"])
def get_players():
    """Fetch all players and their aliases."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch players
        cursor.execute("""
            SELECT id, full_name, icon, default_alias, long_names_enabled FROM players;
        """)
        players = cursor.fetchall()

        # Fetch aliases
        cursor.execute("""
            SELECT player_id, alias FROM aliases WHERE player_id IN (SELECT id FROM players);
        """)
        alias_data = cursor.fetchall()

        alias_map = {}
        for player_id, alias in alias_data:
            alias_map.setdefault(player_id, []).append(alias)

        # Format players list
        players_list = [{
            "id": player[0],
            "full_name": player[1],
            "icon": player[2] or "/static/images/avatars/default-avatar.png",
            "default_alias": player[3],
            "long_names_enabled": player[4],
            "aliases": alias_map.get(player[0], [])
        } for player in players]

        conn.close()
        return jsonify(players_list)
    except Exception as e:
        return jsonify({"error": "Failed to fetch players", "details": str(e)}), 500

@players_bp.route("/api/v1/players/<int:player_id>", methods=["GET"])
def get_player(player_id):
    """Fetch player details, scores, and aliases."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get player details
        cursor.execute("""
            SELECT id, full_name, icon, default_alias, long_names_enabled FROM players WHERE id = ?;
        """, (player_id,))
        player = cursor.fetchone()
        if not player:
            return jsonify({"error": "Player not found"}), 404

        # Get aliases
        cursor.execute("SELECT alias FROM aliases WHERE player_id = ?", (player_id,))
        aliases = [row[0] for row in cursor.fetchall()]

        # Get player scores
        cursor.execute("""
            SELECT g.game_name, h.score, h.timestamp, h.wins, h.losses
            FROM highscores h
            JOIN games g ON h.game_id = g.id
            WHERE h.player_id = ?
            ORDER BY h.timestamp DESC;
        """, (player_id,))
        scores = [{
            "game_name": row[0],
            "score": row[1],
            "timestamp": row[2],
            "wins": row[3],
            "losses": row[4],
        } for row in cursor.fetchall()]

        # Calculate total wins/losses
        total_wins = sum(score["wins"] for score in scores)
        total_losses = sum(score["losses"] for score in scores)

        return jsonify({
            "id": player[0],
            "full_name": player[1],
            "icon": player[2],
            "default_alias": player[3],
            "long_names_enabled": player[4],
            "aliases": aliases,
            "scores": scores,
            "total_wins": total_wins,
            "total_losses": total_losses
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch player data", "details": str(e)}), 500

@players_bp.route("/api/v1/players/<int:player_id>", methods=["PUT"])
def update_player(player_id):
    """Update an existing player's details."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        data = request.get_json()
        full_name = data.get("full_name")
        default_alias = data.get("default_alias", "").strip()
        aliases = [alias.strip() for alias in data.get("aliases", []) if alias.strip()]
        long_names_enabled = data.get("long_names_enabled", "FALSE")
        icon = data.get("player_icon", None)

        if not full_name:
            return jsonify({"error": "Full name is required"}), 400

        if aliases and not default_alias:
            return jsonify({"error": "A default alias is required when aliases exist"}), 400

        # Check if the player exists
        cursor.execute("SELECT id FROM players WHERE id = ?", (player_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Player not found"}), 404

        # Update player details
        cursor.execute("""
            UPDATE players
            SET full_name = ?, icon = ?, default_alias = ?, long_names_enabled = ?
            WHERE id = ?;
        """, (full_name, icon, default_alias, long_names_enabled, player_id))

        # Remove existing aliases
        cursor.execute("DELETE FROM aliases WHERE player_id = ?", (player_id,))

        # Re-insert aliases
        alias_set = set(aliases)
        if default_alias:
            alias_set.add(default_alias)  # Ensure the default alias is always included

        for alias in alias_set:
            cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, alias))

        conn.commit()
        return jsonify({"success": True, "player_id": player_id, "full_name": full_name, "aliases": list(alias_set)})
    
    except Exception as e:
        return jsonify({"error": "Failed to update player", "details": str(e)}), 500

@players_bp.route("/api/v1/players", methods=["POST"])
def add_player():
    """Add a new player with multiple aliases."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        data = request.get_json()
        full_name = data.get("full_name")
        default_alias = data.get("default_alias", "").strip()
        aliases = [alias.strip() for alias in data.get("aliases", []) if alias.strip()]

        if not full_name:
            return jsonify({"error": "Full name is required"}), 400

        if aliases and not default_alias:
            return jsonify({"error": "A default alias is required when aliases exist"}), 400

        # Insert player
        cursor.execute("""
            INSERT INTO players (full_name, icon, default_alias, long_names_enabled)
            VALUES (?, ?, ?, ?);
        """, (full_name, None, default_alias, "FALSE"))
        player_id = cursor.lastrowid

        # Insert aliases
        alias_set = set(aliases)  # Ensure no duplicates
        if default_alias:
            alias_set.add(default_alias)  # Default alias should always be included

        for alias in alias_set:
            cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, alias))

        conn.commit()
        return jsonify({"success": True, "player_id": player_id, "full_name": full_name, "aliases": list(alias_set)})
    
    except Exception as e:
        return jsonify({"error": "Failed to add player", "details": str(e)}), 500

@players_bp.route("/api/v1/players/<int:player_id>", methods=["DELETE"])
def delete_player(player_id):
    """Delete a player and associated aliases."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if player exists
        cursor.execute("SELECT id FROM players WHERE id = ?", (player_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Player not found"}), 404

        # Delete player aliases first due to foreign key constraints
        cursor.execute("DELETE FROM aliases WHERE player_id = ?", (player_id,))
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))

        conn.commit()
        return jsonify({"success": True, "message": "Player deleted successfully"})
    except Exception as e:
        return jsonify({"error": "Failed to delete player", "details": str(e)}), 500
