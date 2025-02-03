from flask import Blueprint, jsonify, request, current_app
from app.database import get_db
import json
import time
import requests
import os

settings_bp = Blueprint('settings', __name__)

VPS_DB_URL = "https://virtualpinballspreadsheet.github.io/vps-db/db/vpsdb.json"
VPS_LAST_UPDATED_URL = "https://virtualpinballspreadsheet.github.io/vps-db/lastUpdated.json"
CACHE_EXPIRY = 3600  # Cache expiry in seconds (1 hour)

STATIC_IMAGE_PATH = os.path.join("static", "images")

# Cache storage
cached_vpsdb = None
last_checked_time = None
cached_last_updated = None

def get_vps_paths():
    vps_data_dir = os.path.join(current_app.root_path, 'vps-data')
    vps_json_path = os.path.join(vps_data_dir, "vpsdb.json")
    last_updated_path = os.path.join(vps_data_dir, "lastUpdated.json")
    return vps_data_dir, vps_json_path, last_updated_path

def fetch_vps_data():
    """
    Fetches VPS data and updates the cache if outdated.
    """
    global cached_vpsdb, cached_last_updated, last_checked_time
    current_time = time.time()

    # Get VPS paths using the helper function
    vps_data_dir, vps_json_path, last_updated_path = get_vps_paths()

    os.makedirs(vps_data_dir, exist_ok=True)

    if not last_checked_time or current_time - last_checked_time >= CACHE_EXPIRY:
        try:
            # Check lastUpdated.json
            response = requests.get(VPS_LAST_UPDATED_URL)
            response.raise_for_status()
            last_updated = response.json()

            # Compare with the local cache
            if not os.path.exists(last_updated_path) or json.load(open(last_updated_path)) != last_updated:
                # Fetch new VPS data
                vpsdb_response = requests.get(VPS_DB_URL)
                vpsdb_response.raise_for_status()
                cached_vpsdb = vpsdb_response.json()
                
                # Save locally
                with open(vps_json_path, "w") as f:
                    json.dump(cached_vpsdb, f)
                with open(last_updated_path, "w") as f:
                    json.dump(last_updated, f)

            else:
                # Load from local cache
                with open(vps_json_path, "r") as f:
                    cached_vpsdb = json.load(f)

            cached_last_updated = last_updated
            last_checked_time = current_time

        except Exception as e:
            print(f"Error fetching VPS data: {e}")

@settings_bp.route("/api/vpsdata", methods=["GET"])
def get_vps_data():
    vps_data_dir, vps_json_path, last_updated_path = get_vps_paths()

    try:
        fetch_vps_data()  # Ensure the data is up-to-date
        if not os.path.exists(vps_json_path):
            return jsonify({"error": "VPS data not initialized"}), 500

        with open(vps_json_path, 'r') as f:
            data = json.load(f)

        return jsonify(data), 200
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
                conn.close()
                return jsonify([{
                    "gameID": game[0],
                    "gameName": game[1],
                    "tags": game[2].split(",") if game[2] else [],
                    "hidden": game[3] if game[3] else "false"
                } for game in games])
            except Exception as e:
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
                        auto_refresh_enabled, default_preset
                    FROM settings WHERE user = ?;
                """, (user,))
                settings = cursor.fetchone()
                conn.close()
                if not settings:
                    return jsonify({"error": f"Settings for user '{user}' not found."}), 404

                return jsonify({
                    "roomID": settings[0],
                    "settings": dict(zip([
                        "roomName", "publicScoresEnabled", "publicScoreEntryEnabled", 
                        "apiReadAccess", "apiWriteAccess", "adminApprovalEmailList", 
                        "adminApproval", "longNamesEnabled", "idleScroll", 
                        "idleScrollMethod", "showQR", "tournamentLimit", 
                        "autoRefreshEnabled", "defaultPreset"
                    ], settings[1:]))
                })
            except Exception as e:
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
                conn.close()
                
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
            
            # Fetch room settings to determine name resolution method
            cursor.execute("SELECT long_names_enabled FROM settings WHERE id = ?", (room_id,))
            settings = cursor.fetchone()
            long_names_enabled = settings[0] if settings else "FALSE"

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

            conn.commit()
            conn.close()

            # Return success response
            return jsonify({"message": "Score added successfully!"}), 201
        
        except Exception as e:
            # Return error response
            print(f"Error adding score: {e}")
            return jsonify({"error": "Failed to add score", "details": str(e)}), 500

    return jsonify({"error": "Invalid command"}), 400

@settings_bp.route("/api/v1/settings/<int:room_id>", methods=["PUT"])
def update_settings(room_id):
    """
    Update settings for a specific room (dashboard).
    """
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()

        # Validate expected fields and their default values
        expected_fields = {
            "room_name": str,
            "dateformat": str,
            "auto_refresh_enabled": str,
            "auto_refresh_interval": int,
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
        conn.close()
        
        return jsonify({"message": "Settings updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to update settings", "details": str(e)}), 500
