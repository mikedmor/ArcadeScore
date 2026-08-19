from functools import wraps
from flask import request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.modules.database import get_db

def hash_password(password):
    return generate_password_hash(password)

def get_room_password_hash(conn, room_id):
    cursor = conn.cursor()
    cursor.execute("SELECT secure FROM settings WHERE id = ?", (room_id,))
    row = cursor.fetchone()
    return row["secure"] if row and row["secure"] else None

def room_has_password(conn, room_id):
    return get_room_password_hash(conn, room_id) is not None

def verify_room_password(conn, room_id, password):
    password_hash = get_room_password_hash(conn, room_id)
    if not password_hash or not password:
        return False
    return check_password_hash(password_hash, password)

def _session_key(room_id):
    return f"room_{room_id}_admin"

def is_room_admin_session(room_id):
    return bool(session.get(_session_key(room_id)))

def mark_room_admin_session(room_id):
    session[_session_key(room_id)] = True
    session.permanent = True

def clear_room_admin_session(room_id):
    session.pop(_session_key(room_id), None)

def _resolve_game_id():
    """Same idea as _resolve_room_id, for routes that identify a game instead -
    some (games.py) carry it as a URL segment, others (styles.py) carry it as
    gameID in the JSON body."""
    view_args = request.view_args or {}
    if "game_id" in view_args:
        return view_args["game_id"]

    if request.is_json:
        data = request.get_json(silent=True) or {}
        for key in ("game_id", "gameID"):
            if data.get(key) is not None:
                return data[key]

    for key in ("game_id", "gameID"):
        if request.args.get(key):
            return request.args.get(key)

    return None

def _resolve_room_id():
    """Best-effort room id for the current request: URL kwargs, JSON body, then
    query string, in that order - covers every route shape used across the app
    (room_id/scoreboard_id in the URL, roomID in a POST body, ?roomID= for
    routes keyed by something else, like a player id, that don't carry one
    naturally)."""
    view_args = request.view_args or {}
    for key in ("room_id", "scoreboard_id"):
        if key in view_args:
            return view_args[key]

    if request.is_json:
        data = request.get_json(silent=True) or {}
        for key in ("room_id", "roomID"):
            if data.get(key) is not None:
                return data[key]

    for key in ("room_id", "roomID"):
        if request.args.get(key):
            return request.args.get(key)

    if request.form:
        for key in ("room_id", "roomID"):
            if request.form.get(key):
                return request.form.get(key)

    return None

def require_room_admin(view=None, *, room_id_from_game=False, optional_room=False):
    """
    Gate a mutating route behind the room's admin password, if one is set. If no
    password has ever been set for the room, the route is left open - matches
    the app's behavior before this feature existed, and is how a fresh install
    stays usable without forcing a password on day one (see docs/Roadmap.md
    Phase 2a).

    Room id resolution: URL kwargs (room_id/scoreboard_id) > JSON body
    (room_id/roomID) > query string (room_id/roomID) > form body
    (room_id/roomID). Pass room_id_from_game=True for routes keyed by a
    game_id instead (games CRUD) - resolves the game's owning room from the DB
    first, before falling back to the same resolution order.

    Pass optional_room=True for the rare route reachable both with and without
    a room in context (e.g. player-linking endpoints called both by the
    scoreboard creation wizard, where no room exists yet, and the Integrations
    Menu, where one does) - when no room id can be resolved at all, the action
    proceeds ungated instead of failing closed. Every other route always has an
    unambiguous room, so this defaults to False (fail closed) deliberately.

    Usable bare (@require_room_admin) or parametrized
    (@require_room_admin(room_id_from_game=True)).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            room_id = None

            if room_id_from_game:
                game_id = _resolve_game_id()
                if game_id:
                    cursor = get_db().cursor()
                    cursor.execute("SELECT room_id FROM games WHERE id = ?", (game_id,))
                    row = cursor.fetchone()
                    room_id = row["room_id"] if row else None

            if room_id is None:
                room_id = _resolve_room_id()

            if room_id is None:
                if optional_room:
                    return fn(*args, **kwargs)
                # Can't tell which room this affects - fail closed rather than
                # silently letting an unscoped mutation through.
                return jsonify({"error": "Unable to determine which scoreboard this action affects"}), 400

            if not room_has_password(get_db(), room_id):
                return fn(*args, **kwargs)

            if is_room_admin_session(room_id):
                return fn(*args, **kwargs)

            return jsonify({"error": "Admin authentication required", "room_id": room_id}), 401

        return wrapped

    if view is not None:
        return decorator(view)
    return decorator

def require_any_room_admin(view):
    """
    Gate a database-wide action (import/export - these touch every room's data
    at once, not one room's) behind ANY room's admin session, since there's no
    single room to check a password against here. If no room has a password set
    at all, the instance has no admin protection configured yet, and this stays
    open too - consistent with every other gate in this module. Once at least
    one room has a password, the caller must be logged in as an admin of at
    least one of them.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        cursor = get_db().cursor()
        cursor.execute("SELECT id FROM settings WHERE secure IS NOT NULL")
        protected_rooms = [row["id"] for row in cursor.fetchall()]

        if not protected_rooms:
            return view(*args, **kwargs)

        if any(is_room_admin_session(room_id) for room_id in protected_rooms):
            return view(*args, **kwargs)

        return jsonify({"error": "Admin authentication required"}), 401

    return wrapped
