from flask_socketio import SocketIO
from app.modules.database import get_db

# Define `socketio` instance globally
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")

def emit_message(event: str, *args: any):
    socketio.emit(event, args, namespace="/")

def emit_player_changes():
    """Fetch all players and emit updated list via WebSocket."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch all players
        cursor.execute("""
            SELECT id, full_name, icon, default_alias, long_names_enabled, room_id FROM players;
        """)
        players = cursor.fetchall()

        # Fetch aliases
        cursor.execute("""
            SELECT player_id, alias FROM aliases WHERE player_id IN (SELECT id FROM players);
        """)
        alias_data = cursor.fetchall()

        # Create alias mapping
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
            "aliases": alias_map.get(player[0], []),
            "roomID": player[5]
        } for player in players]

        conn.close()

        # Emit updated player list to clients
        socketio.emit("players_updated", {"players": players_list}, namespace="/")

    except Exception as e:
        print(f"Error emitting player changes: {e}")

def emit_style_changes(room_id=None):
    """Emit updated global styles and presets. If room_id is None, only presets are broadcasted."""
    conn = get_db()
    cursor = conn.cursor()

    # Fetch all style presets
    cursor.execute("SELECT id, name FROM presets;")
    presets = cursor.fetchall()

    styles_data = {
        "presets": [{"id": p["id"], "name": p["name"]} for p in presets]
    }

    if room_id:
        # Fetch global styles for the specified room
        cursor.execute("SELECT css_body, css_card FROM settings WHERE id = ?;", (room_id,))
        global_styles = cursor.fetchone()

        if global_styles:
            styles_data.update({
                "roomID": room_id,
                "css_body": global_styles["css_body"],
                "css_card": global_styles["css_card"]
            })

    # Emit updated styles to all clients
    socketio.emit("styles_updated", styles_data, namespace="/")

def emit_progress(app, progress, message):
    """Emit WebSocket messages asynchronously with Flask context."""
    with app.app_context():
        print(f"Emitting progress message: '{message}' at {progress}%")

        # REMOVE run_in_executor() and call emit() directly
        socketio.emit("progress_update", {
            "progress": progress,
            "message": message
        }, namespace="/")

        print("Emit complete.")