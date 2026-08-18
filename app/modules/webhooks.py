import sys
import requests
import traceback
import uuid
import json
import time
from datetime import datetime
from app.modules.utils import get_server_base_url, generate_random_color, format_timestamp
from app.modules.scores import log_score_to_db
from app.modules.players import add_player_to_db, update_player_in_db, delete_player_from_db, link_vpin_player
from app.modules.games import save_game_to_db, delete_game_from_db
from app.modules.vpspreadsheet import generate_vpspreadsheet_url
from app.modules.vpinstudio import fetch_game_images
from app.modules.socketio import emit_message

def register_vpin_webhook(conn, vpin_api_url, room_id, scoreboard_name, webhooks):
    """Registers a webhook with VPin Studio based on user selections."""
    try:
        webhook_uuid = str(uuid.uuid4())  # Generate a unique webhook ID
        webhook_name = f"{scoreboard_name} Webhook"

        # Get the correct base URL for the server
        server_base_url = get_server_base_url()
        if not server_base_url:
            return {"success": False, "message": "Failed to determine server base URL."}

        payload = {
            "name": webhook_name,
            "uuid": webhook_uuid,
            "enabled": True
        }

        # Extract webhook options from frontend
        score_update = webhooks.get("highscores", {}).get("UPDATE", False)
        game_create = webhooks.get("games", {}).get("CREATE", False)
        game_update = webhooks.get("games", {}).get("UPDATE", False)
        game_delete = webhooks.get("games", {}).get("DELETE", False)
        player_create = webhooks.get("players", {}).get("CREATE", False)
        player_update = webhooks.get("players", {}).get("UPDATE", False)
        player_delete = webhooks.get("players", {}).get("DELETE", False)

        # Populate webhook payload based on selections
        if score_update:
            payload["scores"] = {
                "endpoint": f"{server_base_url}/webhook/scores",
                "parameters": {"roomID": room_id},
                "subscribe": [
                    event.lower()
                    for event, enabled in webhooks.get("highscores", {}).items() if enabled]
            }

        if game_create or game_update or game_delete:
            payload["games"] = {
                "endpoint": f"{server_base_url}/webhook/games",
                "parameters": {"roomID": room_id},
                "subscribe": [
                    event.lower()
                    for event, enabled in webhooks.get("games", {}).items() if enabled
                ]
            }

        if player_create or player_update or player_delete:
            payload["players"] = {
                "endpoint": f"{server_base_url}/webhook/players",
                "parameters": {"roomID": room_id},
                "subscribe": [
                    event.lower()
                    for event, enabled in webhooks.get("players", {}).items() if enabled
                ]
            }

        if len(payload) == 3:  # Only "name", "uuid", "enabled" present (no webhooks)
            return {"success": False, "message": "No webhooks selected for registration."}

        webhook_url = f"{vpin_api_url.rstrip('/')}/api/v1/webhooks"

        # 🛠 Debugging: Explicitly print JSON before sending
        formatted_payload = json.dumps(payload, indent=2)  # Properly format JSON
        print(f"Registering webhook with payload:\n{formatted_payload}")

        # Send JSON payload to VPin Studio
        response = requests.post(webhook_url, data=formatted_payload, headers={'Content-Type': 'application/json'}, timeout=10)

        if response.status_code == 200:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpin_webhooks (room_id, server_url, webhook_uuid, webhook_name,
                    score_update, game_create, game_update, game_delete,
                    player_create, player_update, player_delete)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                room_id, vpin_api_url, webhook_uuid, webhook_name,
                "TRUE" if score_update else "FALSE",
                "TRUE" if game_create else "FALSE",
                "TRUE" if game_update else "FALSE",
                "TRUE" if game_delete else "FALSE",
                "TRUE" if player_create else "FALSE",
                "TRUE" if player_update else "FALSE",
                "TRUE" if player_delete else "FALSE"
            ))

            conn.commit()
            return {"success": True, "message": "Webhook registered successfully."}

        return {"success": False, "message": f"Failed to register webhook. Status Code: {response.status_code}, Response: {response.text}"}

    except requests.RequestException as e:
        return {"success": False, "message": f"Webhook request error: {str(e)}"}

def webhook_log_score(conn, data):
    """
    Webhook to handle score submissions from VPin Studio.
    Retrieves score details via the VPin API, logs only new scores, and 
    emits an update to the frontend.
    """
    try:
        print(f"📩 New Score Webhook Data: {data}")
        sys.stdout.flush()

        room_id = data.get("roomID")
        vpin_game_id = data.get("id")  # Game ID provided in webhook

        if not room_id or not vpin_game_id:
            return {"success": False, "error": "Missing required parameters: roomID or game ID"}

        cursor = conn.cursor()

        # ✅ Fetch associated VPin API URL from `vpin_webhooks` instead of `settings`
        cursor.execute("""
            SELECT DISTINCT server_url FROM vpin_webhooks WHERE room_id = ?;
        """, (room_id,))
        webhook = cursor.fetchone()

        if not webhook:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}"}

        vpin_api_url = webhook["server_url"]

        # ✅ Fetch additional settings
        cursor.execute("""
            SELECT long_names_enabled, dateformat FROM settings WHERE id = ?;
        """, (room_id,))
        room_data = cursor.fetchone()

        if not room_data:
            return {"success": False, "error": f"No room settings found for room {room_id}"}

        long_names_enabled = room_data["long_names_enabled"]
        date_format = room_data["dateformat"] if room_data["dateformat"] else 'MM/DD/YYYY'

        # ✅ Fetch the correct ArcadeScore game ID based on VPin game ID, server, and room
        cursor.execute("""
            SELECT vpin_games.arcadescore_game_id
            FROM vpin_games
            JOIN games ON vpin_games.arcadescore_game_id = games.id
            WHERE vpin_games.server_url = ? AND vpin_games.vpin_game_id = ? AND games.room_id = ?;
        """, (vpin_api_url, vpin_game_id, room_id))
        
        mapping = cursor.fetchone()

        if not mapping:
            return {"success": False, "error": f"No matching ArcadeScore game found for VPin Game ID {vpin_game_id}"}

        arcadescore_game_id = mapping["arcadescore_game_id"]
        print(f"🎮 VPin Game ID {vpin_game_id} mapped to ArcadeScore Game ID {arcadescore_game_id}")
        sys.stdout.flush()

        score_api_url = f"{vpin_api_url}api/v1/games/scores/{vpin_game_id}"
        print(f"🌐 Fetching scores from {score_api_url}")
        sys.stdout.flush()

        # Fetch all scores from the VPin API
        try:
            response = requests.get(score_api_url, timeout=10)
            response.raise_for_status()  # Raises an exception for HTTP errors
        except requests.RequestException as e:
            print(f"🌐 Request Exception: {traceback.format_exc()}")
            sys.stdout.flush()
            return {"success": False, "error": f"Error fetching score details: {str(e)}"}

        scores_data = response.json().get("scores", [])

        if not scores_data:
            return {"success": False, "message": "No new scores found."}

        print(f"📊 Found {len(scores_data)} scores to process.")
        sys.stdout.flush()

        # ✅ Fetch all mapped players from `vpin_players` for this server
        cursor.execute("""
            SELECT arcadescore_player_id, vpin_player_id FROM vpin_players WHERE server_url = ?;
        """, (vpin_api_url,))
        vpin_players = {row["vpin_player_id"]: row["arcadescore_player_id"] for row in cursor.fetchall()}

        print(f"📋 vpin_players List for {vpin_api_url}: {vpin_players}")
        sys.stdout.flush()

        new_scores = []
        for score_entry in scores_data:
            vpin_player = score_entry.get("player")

            if not vpin_player:
                print(f"⚠️ Skipping score entry with missing player: {score_entry}")
                sys.stdout.flush()
                continue  # Skip scores without a player

            vpin_player_id = vpin_player.get("id")
            score_value = score_entry.get("score")
            raw_timestamp = score_entry.get("createdAt")

            # Convert timestamp to proper format
            try:
                formatted_timestamp = datetime.utcfromtimestamp(raw_timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"⚠️ Failed to parse timestamp {raw_timestamp}. Error: {e}")
                sys.stdout.flush()
                formatted_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # ✅ Attempt to match the player using the dictionary lookup
            print(f"🔍 Searching for VPin Player ID {vpin_player_id} in list...")
            sys.stdout.flush()

            arcadescore_player_id = vpin_players.get(vpin_player_id)

            if not arcadescore_player_id:
                print(f"⚠️ No matching player found for VPin Player ID: {vpin_player_id} on {vpin_api_url}. Skipping score.")
                sys.stdout.flush()
                continue  # Skip scores with unknown players
            else:
                print(f"✅ Matched player: {arcadescore_player_id}")
                sys.stdout.flush()

            # ✅ Check if the score already exists
            cursor.execute("""
                SELECT COUNT(*) FROM highscores
                WHERE game_id = ? AND player_id = ? AND score = ? AND timestamp = ? AND room_id = ?;
            """, (arcadescore_game_id, arcadescore_player_id, score_value, formatted_timestamp, room_id))
            score_exists = cursor.fetchone()[0] > 0

            if score_exists:
                print(f"✅ Score {score_value} already exists for Player {arcadescore_player_id} in Game {arcadescore_game_id}. Skipping.")
                sys.stdout.flush()
                continue

            # ✅ Log the new score in the database
            score_data = {
                "game_id": arcadescore_game_id,
                "player_id": arcadescore_player_id,
                "score": int(score_value),
                "timestamp": formatted_timestamp,
                "room_id": room_id
            }
            success, message = log_score_to_db(conn, score_data)

            if success:
                print(f"🎉 New score logged for Player {arcadescore_player_id}: {score_value}")
                sys.stdout.flush()
                new_scores.append(score_data)  # Add to list for emitting to frontend
            else:
                print(f"❌ Failed to log score: {message}")
                sys.stdout.flush()

        conn.commit()

        # ✅ Fetch all scores for this game after the update
        cursor.execute("""
            SELECT p.full_name, p.default_alias, h.score, h.timestamp, h.wins, h.losses
            FROM highscores h
            JOIN players p ON h.player_id = p.id
            WHERE h.game_id = ? ORDER BY h.score DESC;
        """, (arcadescore_game_id,))

        all_scores = [{
            "displayName": row[0] if long_names_enabled == "TRUE" else row[1],
            "fullName": row[0],
            "defaultAlias": row[1],
            "score": row[2],
            "timestamp": row[3],
            "formatted_timestamp": format_timestamp(row[3], date_format),
            "wins": row[4],
            "losses": row[5]
        } for row in cursor.fetchall()]

        # Fetch CSS and ScoreType settings
        cursor.execute("""
            SELECT css_score_cards, css_initials, css_scores, score_type
            FROM games WHERE id = ? AND room_id = ?;
        """, (arcadescore_game_id, room_id))
        game_settings = cursor.fetchone()

        if not game_settings:
            return {"success": False, "error": f"GameID '{arcadescore_game_id}' not found for room ID {room_id}"}

        css_score_cards, css_initials, css_scores, score_type = game_settings

        # Emit socket event to update scores on the dashboard
        print(f"📢 Emitting {len(all_scores)} scores to frontend.")
        sys.stdout.flush()
        emit_message("game_score_update", {
            "gameID": arcadescore_game_id,
            "roomID": room_id,
            "scores": all_scores,
            "CSSScoreCards": css_score_cards,
            "CSSInitials": css_initials,
            "CSSScores": css_scores,
            "ScoreType": score_type
        })

        return {"success": True, "message": f"Processed {len(new_scores)} new scores"}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_log_score: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}
   
def webhook_player(conn, data, vpin_player_id=None):
    try:
        print(f"vpin_player_id: {vpin_player_id}")
        print(f"New/Update player data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]

        # ✅ Fetch associated VPin API URL from `vpin_webhooks`
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT server_url FROM vpin_webhooks WHERE room_id = ?;
        """, (room_id,))
        webhook = cursor.fetchone()

        if not webhook:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}"}

        vpin_api_url = webhook["server_url"].rstrip("/")  # Ensure no trailing slash

        # ✅ Determine if it's a CREATE or UPDATE operation. CREATE/UPDATE webhooks
        # pass the affected id as "id" in the body (per VPin Studio's webhook docs).
        if not vpin_player_id:
            vpin_player_id = data.get("id")

        if not vpin_player_id:
            return {"success": False, "error": "Missing required parameter: id"}

        # ✅ If updating, resolve `arcadescore_player_id` from `vpin_players` table
        arcadescore_player_id = None
        if vpin_player_id:
            cursor.execute("""
                SELECT arcadescore_player_id FROM vpin_players 
                WHERE vpin_player_id = ? AND server_url = ?
            """, (vpin_player_id, vpin_api_url))
            arcadescore_player_id_data = cursor.fetchone()

            if arcadescore_player_id_data:
                arcadescore_player_id = arcadescore_player_id_data["arcadescore_player_id"]

        # ✅ Fetch full player details from VPin API
        player_api_url = f"{vpin_api_url}/api/v1/players/{vpin_player_id}"
        try:
            response = requests.get(player_api_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"🌐 Request Exception: {traceback.format_exc()}")
            sys.stdout.flush()
            return {"success": False, "error": f"Error fetching player details: {str(e)}"}

        player_details = response.json()

        # ✅ Prepare player data
        player_data = {
            "full_name": player_details.get("fullName", "Unknown Player"),
            "default_alias": player_details.get("alias", None),
            "aliases": player_details.get("aliases", []),
            "long_names_enabled": "FALSE",
        }

        # ✅ Handle CREATE or UPDATE logic
        if arcadescore_player_id:
            success, message = update_player_in_db(conn, arcadescore_player_id, player_data)
            if success:
                return {
                    "success": True, 
                    "message": "Player updated successfully",
                    "player_id": arcadescore_player_id
                }
            else:
                return {"success": False, "error": message}
        else:
            success, message, new_player_id = add_player_to_db(conn, player_data)
            if success:
                link_vpin_player(conn, {
                    "server_url": vpin_api_url,
                    "players": [{
                        "arcadescore_player_id": new_player_id,
                        "vpin_player_ids": [vpin_player_id],
                        "full_name": player_data["full_name"],
                        "aliases": player_data["aliases"],
                    }]
                })
                return {
                    "success": True,
                    "message": "Player created successfully",
                    "player_id": new_player_id
                }
            else:
                return {"success": False, "error": message}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_player: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}

def webhook_delete_player(conn, data, vpin_player_id):
    try:
        print(f"vpin_player_id: {vpin_player_id}")
        print(f"Delete player data received: {data}")

        cursor = conn.cursor()

        # ✅ DELETE webhooks carry only the id as a URL segment — VPin Studio's docs
        # say "parameters" are only passed on PUT/POST — so there is no roomID or
        # server_url to filter by here. Resolve directly off vpin_player_id, which
        # is unique enough in practice (collisions only occur if two different
        # VPin servers happen to reuse the same numeric player id).
        cursor.execute("""
            SELECT arcadescore_player_id FROM vpin_players
            WHERE vpin_player_id = ?;
        """, (vpin_player_id,))
        result = cursor.fetchone()

        if not result:
            return {"success": False, "error": f"No matching ArcadeScore player found for VPin ID {vpin_player_id}"}

        arcadescore_player_id = result["arcadescore_player_id"]

        # ✅ Delete the player from our database
        success, message = delete_player_from_db(conn, arcadescore_player_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_delete_player: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}

def webhook_game(conn, data, vpin_game_id=None):
    try:
        print(f"vpin_game_id: {vpin_game_id}")
        print(f"New/Update game data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]

        # ✅ Fetch associated VPin API URL from `vpin_webhooks`
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT server_url FROM vpin_webhooks WHERE room_id = ?;
        """, (room_id,))
        webhook = cursor.fetchone()

        if not webhook:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}"}

        vpin_api_url = webhook["server_url"].rstrip("/")  # Ensure no trailing slash

        # ✅ Determine if it's a CREATE or UPDATE operation. CREATE/UPDATE webhooks
        # pass the affected id as "id" in the body (per VPin Studio's webhook docs).
        if not vpin_game_id:
            vpin_game_id = data.get("id")

        if not vpin_game_id:
            return {"success": False, "error": "Missing required parameter: id"}

        # ✅ If updating, resolve `arcadescore_game_id` from `vpin_games`
        arcadescore_game_id = None
        if vpin_game_id:
            cursor.execute("""
                SELECT arcadescore_game_id FROM vpin_games 
                WHERE vpin_game_id = ? AND server_url = ?;
            """, (vpin_game_id, vpin_api_url))
            arcadescore_game_id_data = cursor.fetchone()

            if arcadescore_game_id_data:
                arcadescore_game_id = arcadescore_game_id_data["arcadescore_game_id"]

        # ✅ Fetch full game details from VPin API
        game_api_url = f"{vpin_api_url}/api/v1/games/{vpin_game_id}"

        try:
            response = requests.get(game_api_url, timeout=10)
            response.raise_for_status()  # Raises an exception for HTTP errors
        except requests.RequestException as e:
            print(f"🌐 Request Exception: {traceback.format_exc()}")
            sys.stdout.flush()
            return {"success": False, "error": f"Error fetching game details: {str(e)}"}

        game_details = response.json()

        # ✅ Generate VPin Spreadsheet URL
        vpin_spreadsheet_url = generate_vpspreadsheet_url(
            game_details.get("extTableId", None), 
            game_details.get("extTableVersionId", None)
        )

        # ✅ Fetch game media if applicable
        media_data = fetch_game_images(vpin_api_url, vpin_game_id) if vpin_api_url else {}
        game_image = media_data.get("backglass", None)
        game_background = media_data.get("playfield", None)

        # ✅ Prepare game data for insert/update
        game_data = {
            "game_name": game_details.get("gameDisplayName", "Unknown Game"),
            "css_score_cards": None,  # TODO: Should be loaded from default style
            "css_initials": None,  # TODO: Should be loaded from default style
            "css_scores": None,  # TODO: Should be loaded from default style
            "css_box": None,  # TODO: Should be loaded from default style
            "css_title": None,  # TODO: Should be loaded from default style
            "score_type": "hideBoth",
            "sort_ascending": "FALSE",
            "game_image": game_image,
            "game_background": game_background,
            "tags": vpin_spreadsheet_url,
            "hidden": "FALSE",
            "game_color": generate_random_color() if not arcadescore_game_id else None,  # Keep existing color on update
            "room_id": room_id,
        }

        # ✅ Call save function
        success, message, saved_game_id = save_game_to_db(conn, game_data, arcadescore_game_id)

        if success:
            return {
                "success": True, 
                "message": f"Game {'updated' if arcadescore_game_id else 'created'} successfully",
                "game_id": saved_game_id
            }
        else:
            return {"success": False, "error": message}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_game: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}
    
def webhook_delete_game(conn, data, vpin_game_id):
    try:
        print(f"vpin_game_id: {vpin_game_id}")
        print(f"Delete game data received: {data}")

        cursor = conn.cursor()

        # ✅ DELETE webhooks carry only the id as a URL segment — VPin Studio's docs
        # say "parameters" are only passed on PUT/POST — so there is no roomID or
        # server_url to filter by here. Resolve directly off vpin_game_id, which
        # is unique enough in practice (collisions only occur if two different
        # VPin servers happen to reuse the same numeric game id).
        cursor.execute("""
            SELECT arcadescore_game_id FROM vpin_games
            WHERE vpin_game_id = ?;
        """, (vpin_game_id,))
        result = cursor.fetchone()

        if not result:
            return {"success": False, "error": f"No matching ArcadeScore game found for VPin ID {vpin_game_id}"}

        arcadescore_game_id = result["arcadescore_game_id"]

        # ✅ Delete the game from our database
        success, message = delete_game_from_db(conn, arcadescore_game_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_delete_game: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}
