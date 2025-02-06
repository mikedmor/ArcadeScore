import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.database import get_db
import json

players_bp = Blueprint("players", __name__)

UPLOAD_FOLDER = "app/static/images/avatars"
RELATIVE_FOLDER = "/static/images/avatars"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Ensure the directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if a file has a valid extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@players_bp.route("/api/v1/players", methods=["GET"])
def get_players():
    """Fetch all players and their aliases, including VPin mappings."""
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

        # Fetch all linked VPin Studio players
        cursor.execute("""
            SELECT v.server_url, v.arcadescore_player_id, v.vpin_player_id
            FROM vpin_players v
        """)
        vpin_mappings = cursor.fetchall()

        # Create alias mapping
        alias_map = {}
        for player_id, alias in alias_data:
            alias_map.setdefault(player_id, []).append(alias)

        # Create VPin mapping
        vpin_map = {}
        for server_url, arcade_id, vpin_id in vpin_mappings:
            if arcade_id not in vpin_map:
                vpin_map[arcade_id] = []
            vpin_map[arcade_id].append({
                "server_url": server_url,
                "vpin_player_id": vpin_id
            })

        # Format players list with embedded VPin mappings
        players_list = [{
            "id": player[0],
            "full_name": player[1],
            "icon": player[2] or "/static/images/avatars/default-avatar.png",
            "default_alias": player[3],
            "long_names_enabled": player[4],
            "aliases": alias_map.get(player[0], []),
            "vpin": vpin_map.get(player[0], [])  # Attach VPin mappings for this player
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
    """Update an existing player's details and avatar."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch existing player data
        cursor.execute("SELECT icon FROM players WHERE id = ?", (player_id,))
        player = cursor.fetchone()
        if not player:
            return jsonify({"error": "Player not found"}), 404

        existing_icon = player[0]  # Save existing icon to delete if a new one is uploaded

        full_name = request.form.get("full_name")
        default_alias = request.form.get("default_alias", "").strip()
        aliases = json.loads(request.form.get("aliases", "[]"))
        long_names_enabled = request.form.get("long_names_enabled", "FALSE")

        if not full_name:
            return jsonify({"error": "Full name is required"}), 400

        if aliases and not default_alias:
            return jsonify({"error": "A default alias is required when aliases exist"}), 400

        # Handle file upload
        icon_path = existing_icon
        if "player_icon_file" in request.files:
            file = request.files["player_icon_file"]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{full_name.replace(' ', '_')}_{file.filename}")
                icon_path = os.path.join(UPLOAD_FOLDER, filename).replace("\\", "/")
                file.save(icon_path)
                icon_path = f"{RELATIVE_FOLDER}/{filename}"

                # Delete old icon if it exists
                if existing_icon and os.path.exists(existing_icon.lstrip("/")):
                    os.remove(existing_icon.lstrip("/"))

        elif request.form.get("player_icon_url"):  # If the user provides a direct URL
            icon_path = request.form.get("player_icon_url").strip()

        # Update player details
        cursor.execute("""
            UPDATE players
            SET full_name = ?, icon = ?, default_alias = ?, long_names_enabled = ?
            WHERE id = ?;
        """, (full_name, icon_path, default_alias, long_names_enabled, player_id))

        # Remove existing aliases
        cursor.execute("DELETE FROM aliases WHERE player_id = ?", (player_id,))

        # Re-insert aliases
        alias_set = set(aliases)
        if default_alias:
            alias_set.add(default_alias)

        for alias in alias_set:
            cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, alias))

        conn.commit()
        return jsonify({"success": True, "player_id": player_id, "full_name": full_name, "icon": icon_path, "aliases": list(alias_set)})

    except Exception as e:
        return jsonify({"error": "Failed to update player", "details": str(e)}), 500

@players_bp.route("/api/v1/players", methods=["POST"])
def add_player():
    """Add a new player with multiple aliases and avatar upload."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        full_name = request.form.get("full_name")
        default_alias = request.form.get("default_alias", "").strip()
        aliases = json.loads(request.form.get("aliases", "[]"))
        long_names_enabled = request.form.get("long_names_enabled", "FALSE")

        if not full_name:
            return jsonify({"error": "Full name is required"}), 400

        if aliases and not default_alias:
            return jsonify({"error": "A default alias is required when aliases exist"}), 400

        # Handle file upload
        icon_path = None
        if "player_icon_file" in request.files:
            file = request.files["player_icon_file"]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{full_name.replace(' ', '_')}_{file.filename}")
                icon_path = os.path.join(UPLOAD_FOLDER, filename).replace("\\", "/")
                file.save(icon_path)
                icon_path = f"{RELATIVE_FOLDER}/{filename}"

        elif request.form.get("player_icon_url"):  # If the user provides a direct URL
            icon_path = request.form.get("player_icon_url").strip()

        # Insert player
        cursor.execute("""
            INSERT INTO players (full_name, icon, default_alias, long_names_enabled)
            VALUES (?, ?, ?, ?);
        """, (full_name, icon_path, default_alias, long_names_enabled))
        player_id = cursor.lastrowid

        # Insert aliases
        alias_set = set(aliases)
        if default_alias:
            alias_set.add(default_alias)

        for alias in alias_set:
            cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, alias))

        conn.commit()
        return jsonify({"success": True, "player_id": player_id, "full_name": full_name, "icon": icon_path, "aliases": list(alias_set)})

    except Exception as e:
        return jsonify({"error": "Failed to add player", "details": str(e)}), 500
    
@players_bp.route("/api/v1/players/vpin/import", methods=["POST"])
def import_vpin_player():
    """Import or update a VPin Studio player."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        data = request.get_json()
        full_name = data.get("full_name")
        default_alias = data.get("default_alias", "").strip()
        aliases = data.get("aliases", [])
        vpin_player_id = data.get("vpin_player_id")
        server_url = data.get("vpin_url")

        if not full_name or not default_alias or not vpin_player_id or not server_url:
            return jsonify({"error": "Missing required fields"}), 400

        # Check if player already exists
        cursor.execute("""
            SELECT id FROM players WHERE default_alias = ?;
        """, (default_alias,))
        existing_player = cursor.fetchone()

        if existing_player:
            # Update existing player details
            player_id = existing_player[0]
            cursor.execute("""
                UPDATE players
                SET full_name = ?
                WHERE id = ?;
            """, (full_name, player_id))

            alias_set = set(aliases)
            alias_set.add(default_alias)

            # Add any new aliases
            for alias in alias_set:
                cursor.execute("""
                    INSERT OR IGNORE INTO aliases (player_id, alias)
                    VALUES (?, ?);
                """, (player_id, alias))
        else:
            # Create a new player
            cursor.execute("""
                INSERT INTO players (full_name, default_alias)
                VALUES (?, ?);
            """, (full_name, default_alias))
            player_id = cursor.lastrowid

            alias_set = set(aliases)
            alias_set.add(default_alias)

            # Add aliases
            for alias in alias_set:
                cursor.execute("""
                    INSERT INTO aliases (player_id, alias)
                    VALUES (?, ?);
                """, (player_id, alias))

        # Link VPin player
        cursor.execute("""
            INSERT OR IGNORE INTO vpin_players (server_url, arcadescore_player_id, vpin_player_id)
            VALUES (?, ?, ?);
        """, (server_url, player_id, vpin_player_id))

        conn.commit()
        return jsonify({
            "success": True,
            "player_id": player_id,
            "full_name": full_name,
            "default_alias": default_alias
        })

    except Exception as e:
        return jsonify({"error": "Failed to import player", "details": str(e)}), 500

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

@players_bp.route("/api/v1/players/vpin", methods=["POST"])
def link_vpin_players():
    """Links VPin Studio players to ArcadeScore players and updates player details."""
    try:
        data = request.get_json()
        server_url = data.get("server_url")
        players = data.get("players", [])

        if not server_url or not players:
            return jsonify({"error": "Server URL and players list are required"}), 400

        conn = get_db()
        cursor = conn.cursor()

        for player in players:
            arcadescore_player_id = player.get("arcadescore_player_id")
            vpin_player_id = player.get("vpin_player_id")
            full_name = player.get("full_name")
            aliases = player.get("aliases", [])

            if not arcadescore_player_id or not vpin_player_id:
                continue

            # Link the VPin player
            cursor.execute(
                """
                INSERT OR IGNORE INTO vpin_players (server_url, arcadescore_player_id, vpin_player_id)
                VALUES (?, ?, ?)
                """,
                (server_url, arcadescore_player_id, vpin_player_id),
            )

            # Update full name if provided
            if full_name:
                cursor.execute(
                    """
                    UPDATE players
                    SET full_name = ?
                    WHERE id = ?
                    """,
                    (full_name, arcadescore_player_id),
                )

            for alias in set(aliases):  # Avoid duplicates
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO aliases (player_id, alias)
                    VALUES (?, ?)
                    """,
                    (arcadescore_player_id, alias),
                )

        conn.commit()
        return jsonify({"message": "Players linked and updated successfully"})

    except Exception as e:
        return jsonify({"error": "Failed to link VPin players", "details": str(e)}), 500