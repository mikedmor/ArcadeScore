import json
import os
from flask import Blueprint, jsonify, request
from app.modules.database import get_db, close_db
from app.modules.socketio import emit_message
from app.modules.vpspreadsheet import get_vps_paths, fetch_vps_data
from app.modules.utils import get_server_base_url, format_timestamp

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

@settings_bp.route("/publicCommands.php", methods=["GET", "POST"])
def public_commands():
    command = request.args.get("c", "")

    if request.method == "GET":
        if command == "getAllGames":
            room_id = request.args.get("roomID", None)  # Get roomID from URL parameters
            if not room_id:
                return jsonify({"error": "Missing 'roomID' parameter"}), 400
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, game_name, tags, hidden 
                    FROM games
                    WHERE room_id = ?
                    ORDER BY game_sort ASC;
                """, (room_id,))
                games = cursor.fetchall()
                close_db()
                return jsonify([{
                    "gameID": game[0],
                    "gameName": game[1],
                    "tags": game[2].split(",") if game[2] else [],
                    "hidden": game[3] if game[3] else "false"
                } for game in games])
            except Exception as e:
                close_db()
                return jsonify({"error": str(e)}), 500

        elif command == "getRoomInfo":
            user = request.args.get("user", "").strip()
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, room_name, public_scores_enabled, public_score_entry_enabled, 
                        api_read_access, api_write_access, admin_approval_email_list, 
                        admin_approval, long_names_enabled, idle_scroll, 
                        idle_scroll_method, show_qr, tournament_limit, 
                        default_preset
                    FROM settings WHERE user = ?;
                """, (user,))
                settings = cursor.fetchone()
                close_db()
                if not settings:
                    return jsonify({"error": f"Settings for user '{user}' not found."}), 404

                return jsonify({
                    "roomID": settings[0],
                    "settings": dict(zip([
                        "roomName", "publicScoresEnabled", "publicScoreEntryEnabled", 
                        "apiReadAccess", "apiWriteAccess", "adminApprovalEmailList", 
                        "adminApproval", "longNamesEnabled", "idleScroll", 
                        "idleScrollMethod", "showQR", "tournamentLimit", 
                        "defaultPreset"
                    ], settings[1:]))
                })
            except Exception as e:
                close_db()
                return jsonify({"error": str(e)}), 500

        elif command == "getScores2":
            room_id = request.args.get("roomID", None)  # Get roomID from URL parameters
            if not room_id:
                return jsonify({"error": "Missing 'roomID' parameter"}), 400
            try:
                conn = get_db()
                cursor = conn.cursor()

                # Fetch settings to determine name display preference
                cursor.execute("SELECT long_names_enabled FROM settings WHERE id = ?", (room_id,))
                settings = cursor.fetchone()
                long_names_enabled = settings[0] if settings else "FALSE"

                # Fetch highscores, join with players table to get the correct name
                cursor.execute(f"""
                    SELECT 
                        h.id, 
                        p.full_name, 
                        p.default_alias, 
                        h.game_id, 
                        h.event, 
                        h.timestamp, 
                        h.wins, 
                        h.losses, 
                        h.score
                    FROM highscores h
                    JOIN players p ON h.player_id = p.id
                    WHERE h.room_id = ?
                    ORDER BY h.timestamp DESC;
                """, (room_id,))

                scores = cursor.fetchall()
                close_db()
                
                return jsonify([{
                    "name": row[1] if long_names_enabled == "TRUE" else row[2],  # Choose full_name or default_alias
                    "id": row[0],      # Highscore ID
                    "game": row[3],    # Game ID
                    "event": row[4],   # Event name (if any)
                    "date": row[5],    # Timestamp
                    "wins": row[6],    # Wins
                    "losses": row[7],  # Losses
                    "score": row[8]    # Score
                } for row in scores])
            except Exception as e:
                close_db()
                return jsonify({"error": str(e)}), 500

    elif request.method == "POST" and command == "addScore":
        try:
            conn = get_db()
            cursor = conn.cursor()

            # Extract parameters from the request
            player_name = request.args.get("name")
            game_id = request.args.get("game")
            high_score = request.args.get("score")
            room_id = request.args.get("roomID")

            # Handle undefined values for wins and losses
            wins = request.args.get("wins", "0")  # Default to "0" if not provided or "undefined"
            losses = request.args.get("losses", "0")  # Default to "0" if not provided or "undefined"

            # Convert undefined strings to integers
            wins = 0 if wins == "undefined" else int(wins)
            losses = 0 if losses == "undefined" else int(losses)

            # Validate required parameters
            if not all([player_name, game_id, high_score, room_id]):
                return jsonify({"error": "Missing required parameters"}), 400
            
            cursor.execute("""
                SELECT css_score_cards, css_initials, css_scores, score_type
                FROM games
                WHERE id = ? AND room_id = ?;
            """, (game_id, room_id))
            game_row = cursor.fetchone()

            if not game_row:
                return jsonify({"error": f"GameID '{game_id}' not found for room ID {room_id}"}), 404
            
            css_score_cards, css_initials, css_scores, score_type = game_row
            
            # Fetch room settings to determine name resolution method
            cursor.execute("SELECT long_names_enabled, dateformat FROM settings WHERE id = ?", (room_id,))
            settings = cursor.fetchone()
            long_names_enabled = settings[0] if settings else "FALSE"
            date_format = settings[1] if settings else 'MM/DD/YYYY'

            # Determine `player_id` based on settings
            if long_names_enabled == "TRUE":
                # Match using full_name
                cursor.execute("SELECT id FROM players WHERE full_name = ?", (player_name,))
            else:
                # Match using default_alias or alias table
                cursor.execute("SELECT id FROM players WHERE default_alias = ?", (player_name,))
                player_id_row = cursor.fetchone()
                
                # If no match, check aliases
                if not player_id_row:
                    cursor.execute("SELECT player_id FROM aliases WHERE alias = ?", (player_name,))
                    player_id_row = cursor.fetchone()

            # Handle new players dynamically
            if player_id_row:
                player_id = player_id_row[0]
            else:
                # Create a new player dynamically
                cursor.execute("""
                    INSERT INTO players (full_name, default_alias, long_names_enabled)
                    VALUES (?, ?, ?);
                """, (player_name, player_name, long_names_enabled))
                player_id = cursor.lastrowid  # Get new player ID

                # Also add alias for initials-based lookup
                cursor.execute("INSERT INTO aliases (player_id, alias) VALUES (?, ?);", (player_id, player_name))

            # Insert score into `highscores` table
            cursor.execute("""
                INSERT INTO highscores (game_id, player_id, score, wins, losses, room_id)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (game_id, player_id, high_score, wins, losses, room_id))

            # After inserting a new score, fetch all scores for this game
            cursor.execute("""
                SELECT p.full_name, p.default_alias, h.score, h.timestamp, h.wins, h.losses
                FROM highscores h
                JOIN players p ON h.player_id = p.id
                WHERE h.game_id = ? ORDER BY h.score DESC;
            """, (game_id,))

            scores = [{
                "displayName": row[0] if long_names_enabled == "TRUE" else row[1],
                "fullName": row[1],
                "defaultAlias": row[0],
                "score": row[2],
                "timestamp": row[3],
                "formatted_timestamp": format_timestamp(row[3],date_format),
                "wins": row[4],
                "losses": row[5]
            } for row in cursor.fetchall()]

            conn.commit()
            close_db()

            # Emit socket event to update scores on the dashboard
            emit_message("game_score_update", {
                "gameID": game_id,
                "roomID": room_id,
                "scores": scores,
                "CSSScoreCards": css_score_cards,
                "CSSInitials": css_initials,
                "CSSScores": css_scores,
                "ScoreType": score_type
            })

            # Return success response
            return jsonify({"message": "Score added successfully!"}), 201
        
        except Exception as e:
            close_db()
            # Return error response
            print(f"Error adding score: {e}")
            return jsonify({"error": "Failed to add score", "details": str(e)}), 500

    return jsonify({"error": "Invalid command"}), 400

@settings_bp.route("/api/v1/settings/<int:room_id>", methods=["PUT"])
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
        close_db()
        
        return jsonify({"message": "Settings updated successfully"}), 200

    except Exception as e:
        close_db()
        return jsonify({"error": "Failed to update settings", "details": str(e)}), 500

@settings_bp.route("/api/v1/server_base_test", methods=["GET"])
def server_base_test():
    """Endpoint to test the detected server base URL."""
    try:
        server_url = get_server_base_url()
        return jsonify({"server_base_url": server_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
