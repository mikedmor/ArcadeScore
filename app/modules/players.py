import os
import json
from werkzeug.utils import secure_filename
from app.modules.socketio import emit_player_changes

UPLOAD_FOLDER = "app/static/images/avatars"
RELATIVE_FOLDER = "/static/images/avatars"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Ensure avatar directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if a file has a valid extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_avatar(file, full_name):
    """Handles avatar upload and saves it to the correct folder."""
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{full_name.replace(' ', '_')}_{file.filename}")
        icon_path = os.path.join(UPLOAD_FOLDER, filename).replace("\\", "/")
        file.save(icon_path)
        return f"{RELATIVE_FOLDER}/{filename}"
    return None

def get_all_players(conn):
    """Fetch all players with aliases and VPin mappings."""
    try:
        cursor = conn.cursor()

        # Fetch players
        cursor.execute("SELECT id, full_name, icon, default_alias, long_names_enabled, hidden FROM players;")
        players = cursor.fetchall()

        # Fetch aliases
        cursor.execute("SELECT player_id, alias FROM aliases WHERE player_id IN (SELECT id FROM players);")
        alias_data = cursor.fetchall()

        # Fetch all linked VPin Studio players
        cursor.execute("SELECT v.server_url, v.arcadescore_player_id, v.vpin_player_id FROM vpin_players v")
        vpin_mappings = cursor.fetchall()

        # Create alias mapping
        alias_map = {player_id: [] for player_id, _ in alias_data}
        for player_id, alias in alias_data:
            alias_map[player_id].append(alias)

        # Create VPin mapping
        vpin_map = {arcade_id: [] for _, arcade_id, _ in vpin_mappings}
        for server_url, arcade_id, vpin_id in vpin_mappings:
            vpin_map[arcade_id].append({"server_url": server_url, "vpin_player_id": vpin_id})

        # Format players list with embedded VPin mappings
        players_list = [{
            "id": player[0],
            "full_name": player[1],
            "icon": player[2] or "/static/images/avatars/default-avatar.png",
            "default_alias": player[3],
            "long_names_enabled": player[4],
            "aliases": alias_map.get(player[0], []),
            "vpin": vpin_map.get(player[0], []),
            "hidden": player[5]
        } for player in players]

        return players_list

    except Exception as e:
        return {"error": "Failed to fetch players", "details": str(e)}

def get_player_from_db(conn, player_id):
    """Fetch player details, scores, and aliases."""
    try:
        cursor = conn.cursor()

        # Get player details
        cursor.execute("SELECT id, full_name, icon, default_alias, long_names_enabled, hidden FROM players WHERE id = ?;", (player_id,))
        player = cursor.fetchone()
        if not player:
            return None

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
        scores = [
            {
                "game_name": row[0], 
                "score": row[1], 
                "timestamp": row[2], 
                "wins": row[3], 
                "losses": row[4]
            } for row in cursor.fetchall()
        ]

        total_wins = sum(score["wins"] for score in scores)
        total_losses = sum(score["losses"] for score in scores)

        # Get associated VPin IDs grouped by server_url
        cursor.execute("SELECT server_url, vpin_player_id FROM vpin_players WHERE arcadescore_player_id = ?", (player_id,))
        vpin_servers = {}
        for row in cursor.fetchall():
            server_url = row[0]
            vpin_id = row[1]
            if server_url not in vpin_servers:
                vpin_servers[server_url] = []
            vpin_servers[server_url].append(vpin_id)

        return {
            "id": player[0],
            "full_name": player[1],
            "icon": player[2],
            "default_alias": player[3],
            "long_names_enabled": player[4],
            "hidden": player[5],
            "aliases": aliases,
            "scores": scores,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "vpin_servers": vpin_servers
        }
    except Exception as e:
        return {"error": "Failed to fetch player data", "details": str(e)}

def add_player_to_db(conn, data, file=None):
    """Add a new player to the database."""
    try:
        cursor = conn.cursor()

        full_name = data.get("full_name")
        default_alias = data.get("default_alias", "").strip()
        aliases = json.loads(data.get("aliases", "[]"))
        long_names_enabled = data.get("long_names_enabled", "FALSE")

        if not full_name:
            return False, "Full name is required."

        if aliases and not default_alias:
            return False, "A default alias is required when aliases exist."

        # Handle avatar upload
        icon_path = save_avatar(file, full_name) if file else None

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

        emit_player_changes(conn)
        return True, "Player added successfully!", player_id

    except Exception as e:
        return False, f"Failed to add player: {str(e)}"

def update_player_in_db(conn, player_id, data, file=None):
    """Update player details and avatar."""
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT icon FROM players WHERE id = ?", (player_id,))
        player = cursor.fetchone()
        if not player:
            return False, "Player not found."

        existing_icon = player[0]

        full_name = data.get("full_name")
        default_alias = data.get("default_alias", "").strip()
        aliases = json.loads(data.get("aliases", "[]"))
        long_names_enabled = data.get("long_names_enabled", "FALSE")

        if not full_name:
            return False, "Full name is required."

        if aliases and not default_alias:
            return False, "A default alias is required when aliases exist."

        # Handle avatar update
        icon_path = existing_icon
        if file:
            icon_path = save_avatar(file, full_name)
            if existing_icon and os.path.exists(existing_icon.lstrip("/")):
                os.remove(existing_icon.lstrip("/"))

        cursor.execute("""
            UPDATE players
            SET full_name = ?, icon = ?, default_alias = ?, long_names_enabled = ?
            WHERE id = ?;
        """, (full_name, icon_path, default_alias, long_names_enabled, player_id))

        cursor.execute("DELETE FROM aliases WHERE player_id = ?", (player_id,))
        alias_set = set(aliases)
        if default_alias:
            alias_set.add(default_alias)

        for alias in alias_set:
            cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, alias))

        conn.commit()

        emit_player_changes(conn)
        return True, "Player updated successfully!"

    except Exception as e:
        return False, f"Failed to update player: {str(e)}"

def delete_player_from_db(conn, player_id):
    """Delete a player and associated aliases."""
    try:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM aliases WHERE player_id = ?", (player_id,))
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))

        conn.commit()

        emit_player_changes(conn)
        return True, "Player deleted successfully."

    except Exception as e:
        return False, f"Failed to delete player: {str(e)}"

def link_vpin_player(conn, data):
    """Links VPin Studio players to ArcadeScore players and updates player details."""
    try:
        server_url = data.get("server_url")
        players = data.get("players", [])

        if not server_url or not players:
            return False, "Server URL and players list are required."

        cursor = conn.cursor()

        for player in players:
            arcadescore_player_id = player.get("arcadescore_player_id")
            vpin_player_id = player.get("vpin_player_id")
            full_name = player.get("full_name")
            aliases = player.get("aliases", [])

            if not arcadescore_player_id or not vpin_player_id:
                continue  # Skip invalid entries

            # Link the VPin player to ArcadeScore player
            cursor.execute(
                """
                INSERT OR IGNORE INTO vpin_players (server_url, arcadescore_player_id, vpin_player_id)
                VALUES (?, ?, ?);
                """,
                (server_url, arcadescore_player_id, vpin_player_id),
            )

            # Update full name if provided
            if full_name:
                cursor.execute(
                    """
                    UPDATE players
                    SET full_name = ?
                    WHERE id = ?;
                    """,
                    (full_name, arcadescore_player_id),
                )

            # Insert aliases
            for alias in set(aliases):  # Avoid duplicates
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO aliases (player_id, alias)
                    VALUES (?, ?);
                    """,
                    (arcadescore_player_id, alias),
                )

        conn.commit()

        emit_player_changes(conn)
        return True, "VPin players linked and updated successfully."

    except Exception as e:
        return False, f"Failed to link VPin players: {str(e)}"

def toggle_player_score_visibility(conn, player_id, hide=True):
    """Toggles the visibility of a player."""
    try:
        cursor = conn.cursor()

        hidden_value = "TRUE" if hide else "FALSE"

        cursor.execute("""
            UPDATE players SET hidden = ? WHERE id = ?
        """, (hidden_value, player_id))

        conn.commit()

        return True, f"Player {'hidden' if hide else 'unhidden'} successfully."

    except Exception as e:
        return False, f"Failed to update player visibility: {str(e)}"
