import sys
from flask import Blueprint, jsonify, request
from app.modules.database import get_db
from app.modules.vpspreadsheet import fetch_vps_data
from app.modules.utils import get_server_base_url
from app.modules.socketio import emit_settings_changes, emit_message
from app.modules.auth import (
    require_room_admin,
    hash_password,
    room_has_password,
    verify_room_password,
    mark_room_admin_session,
    clear_room_admin_session,
    is_room_admin_session,
)

settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/api/vpsdata", methods=["GET"])
def get_vps_data():
    try:
        vps_data = fetch_vps_data()  # This now returns the VPS data directly

        if not vps_data:
            return jsonify({"error": "VPS data not initialized or could not be fetched."}), 500

        return jsonify(vps_data), 200
    except Exception as e:
        print(f"Error in /api/vpsdata: {e}")
        return jsonify({"error": "Failed to load VPS data"}), 500

@settings_bp.route("/api/v1/settings/<int:room_id>", methods=["PUT"])
@require_room_admin
def update_settings(room_id):
    """
    Update settings for a specific room (scoreboard).
    """
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()

        # Validate expected fields and their default values
        expected_fields = {
            "room_name": str,
            "dateformat": str,
            "horizontal_scroll_enabled": str,
            "horizontal_scroll_speed": int,
            "horizontal_scroll_delay": int,
            "vertical_scroll_enabled": str,
            "vertical_scroll_speed": int,
            "vertical_scroll_delay": int,
            "fullscreen_enabled": str,
            "long_names_enabled": str,
            "text_autofit_enabled": str,
            "public_scores_enabled": str,
            "public_score_entry_enabled": str,
            "api_read_access": str,
            "api_write_access": str,
            "auto_hide_no_score_games": str,
        }

        # Build the SQL query dynamically
        update_values = []
        update_fields = []
        
        for field, field_type in expected_fields.items():
            if field in data:
                value = data[field]
                
                # Convert boolean-like values to "TRUE"/"FALSE"
                if isinstance(value, bool):
                    value = "TRUE" if value else "FALSE"

                # Validate integer fields
                if field_type == int:
                    try:
                        value = int(value)
                    except ValueError:
                        return jsonify({"error": f"Invalid value for {field}"}), 400

                update_fields.append(f"{field} = ?")
                update_values.append(value)

        if not update_fields:
            return jsonify({"error": "No valid fields provided for update"}), 400

        # Execute the update query
        cursor.execute(f"""
            UPDATE settings
            SET {", ".join(update_fields)}
            WHERE id = ?;
        """, update_values + [room_id])

        conn.commit()

        # Reconcile immediately when auto-hide is (still) on, rather than waiting for
        # the next score - covers both the moment it's first enabled and every
        # ordinary settings save while the checkbox stays checked. The WHERE clause
        # only touches already-visible, still-scoreless games, so repeat calls are a
        # no-op once the room is caught up.
        if data.get("auto_hide_no_score_games") in (True, "TRUE", "true"):
            cursor.execute("""
                SELECT id FROM games
                WHERE room_id = ? AND hidden != 'TRUE'
                  AND id NOT IN (SELECT DISTINCT game_id FROM highscores WHERE room_id = ?);
            """, (room_id, room_id))
            newly_hidden_ids = [row[0] for row in cursor.fetchall()]

            if newly_hidden_ids:
                placeholders = ",".join("?" * len(newly_hidden_ids))
                cursor.execute(
                    f"UPDATE games SET hidden = 'TRUE' WHERE id IN ({placeholders});",
                    newly_hidden_ids,
                )
                conn.commit()

                for game_id in newly_hidden_ids:
                    emit_message("game_visibility_toggled", {"gameID": game_id, "roomID": room_id, "hidden": "TRUE"}, room=f"room_{room_id}")

        # Let other displays showing this room know to pick up the change. The tab
        # that made the change already applied it optimistically and ignores its
        # own echo via client_id (see docs/Roadmap.md BUG-29).
        emit_settings_changes(room_id, {"client_id": data.get("client_id")})


        return jsonify({"message": "Settings updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to update settings", "details": str(e)}), 500

@settings_bp.route("/api/v1/settings/<int:room_id>/password", methods=["POST"])
@require_room_admin
def set_room_password(room_id):
    """
    Set, change, or clear a room's admin password. Open if none is set yet -
    a fresh room stays fully usable without forcing a password on day one.
    Once a password exists, changing or clearing it requires already being
    logged in as that room's admin (enforced by @require_room_admin).
    """
    try:
        data = request.get_json(silent=True) or {}
        new_password = (data.get("password") or "").strip()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM settings WHERE id = ?", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Scoreboard not found"}), 404

        password_hash = hash_password(new_password) if new_password else None

        cursor.execute("UPDATE settings SET secure = ? WHERE id = ?", (password_hash, room_id))
        conn.commit()

        if password_hash:
            # Whoever just set/changed it obviously knows it - log this session in.
            mark_room_admin_session(room_id)
        else:
            clear_room_admin_session(room_id)

        return jsonify({
            "message": "Password updated" if password_hash else "Password removed",
            "has_password": bool(password_hash),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/v1/settings/<int:room_id>/login", methods=["POST"])
def room_login(room_id):
    """Log in as a room's admin for this browser session."""
    try:
        data = request.get_json(silent=True) or {}
        password = data.get("password", "")

        conn = get_db()

        if not room_has_password(conn, room_id):
            return jsonify({"error": "No password is set for this scoreboard"}), 400

        if not verify_room_password(conn, room_id, password):
            return jsonify({"error": "Incorrect password"}), 401

        mark_room_admin_session(room_id)
        return jsonify({"message": "Logged in"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/v1/settings/<int:room_id>/logout", methods=["POST"])
def room_logout(room_id):
    clear_room_admin_session(room_id)
    return jsonify({"message": "Logged out"}), 200

@settings_bp.route("/api/v1/settings/<int:room_id>/auth-status", methods=["GET"])
def room_auth_status(room_id):
    """Lets the frontend decide whether to show a login gate for the admin menu."""
    try:
        conn = get_db()
        has_password = room_has_password(conn, room_id)
        return jsonify({
            "has_password": has_password,
            "is_admin": is_room_admin_session(room_id) if has_password else True,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/v1/server_base_test", methods=["GET"])
def server_base_test():
    """Endpoint to test the detected server base URL."""
    try:
        server_url = get_server_base_url()
        return jsonify({"server_base_url": server_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
@settings_bp.route("/api/v1/flush", methods=["GET"])
def std_flush():
    """Endpoint to flush the stdout"""
    try:
        sys.stdout.flush()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
