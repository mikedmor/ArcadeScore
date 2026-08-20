from flask_socketio import SocketIO, join_room

# Define `socketio` instance globally
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")

@socketio.on("join")
def handle_join(data):
    """Scoreboard pages join a room-scoped Socket.IO room on connect so
    room-specific events (game updates, scores, settings, ...) only reach
    clients actually viewing that room."""
    room_id = (data or {}).get("roomID")
    if room_id:
        join_room(f"room_{room_id}")

def emit_message(event: str, *args: any, room=None):
    socketio.emit(event, *args, to=room, namespace="/")

def emit_player_changes(conn):
    """Fetch all players and emit updated list via WebSocket. Players are global
    (not room-scoped), so this always broadcasts to every connected client
    rather than a specific room."""
    try:
        cursor = conn.cursor()

        # Fetch all players
        cursor.execute("""
            SELECT id, full_name, icon, default_alias, long_names_enabled FROM players;
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
        } for player in players]

        # Emit updated player list to clients
        socketio.emit("players_updated", {"players": players_list}, namespace="/")

    except Exception as e:
        print(f"Error emitting player changes: {e}")

def emit_style_changes(conn, room_id=None):
    """Emit updated global styles and presets. If room_id is None, this is a
    presets-only change (global, relevant to every room) and broadcasts to
    everyone; otherwise it's scoped to that room."""
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

    # Emit updated styles - scoped to the room if we have one, otherwise everyone
    socketio.emit("styles_updated", styles_data, to=f"room_{room_id}" if room_id else None, namespace="/")

def emit_settings_changes(room_id, settings_data):
    """Notify other displays showing this room that its admin settings changed."""
    socketio.emit("settings_updated", {"roomID": room_id, **settings_data}, to=f"room_{room_id}", namespace="/")

def emit_progress(app, progress, message, session_id=None):
    """Emit WebSocket messages asynchronously with Flask context. session_id, when
    given, lets the client that triggered the background task (creation/export)
    tell its own progress apart from another tab's."""
    with app.app_context():
        print(f"Emitting progress message: '{message}' at {progress}%")

        socketio.emit("progress_update", {
            "progress": progress,
            "message": message,
            "session_id": session_id,
        }, namespace="/")

        print("Emit complete.")
