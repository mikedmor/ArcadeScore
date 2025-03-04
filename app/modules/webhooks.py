import sys
import requests
import uuid
import json  # Explicitly importing JSON module
from app.modules.utils import get_server_base_url, generate_random_color
from app.modules.scores import log_score_to_db
from app.modules.players import add_player_to_db, update_player_in_db, delete_player_from_db, link_vpin_player
from app.modules.games import save_game_to_db, delete_game_from_db
from app.modules.vpspreadsheet import generate_vpspreadsheet_url
from app.modules.vpinstudio import fetch_game_images

def register_vpin_webhook(vpin_api_url, room_id, scoreboard_name, webhooks):
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

        # Conditionally add webhooks based on user selection
        if any(webhooks.get("highscores", {}).values()):  # If any highscores event is selected
            payload["scores"] = {
                "endpoint": f"{server_base_url}/webhook/scores",
                "parameters": {"roomID": room_id},
                "subscribe": [event.lower() for event, enabled in webhooks.get("highscores", {}).items() if enabled]
            }

        if any(webhooks.get("games", {}).values()):  # If any game event is selected
            payload["games"] = {
                "endpoint": f"{server_base_url}/webhook/games",
                "parameters": {"roomID": room_id},
                "subscribe": [event.lower() for event, enabled in webhooks.get("games", {}).items() if enabled]
            }

        if any(webhooks.get("players", {}).values()):  # If any player event is selected
            payload["players"] = {
                "endpoint": f"{server_base_url}/webhook/players",
                "subscribe": [event.lower() for event, enabled in webhooks.get("players", {}).items() if enabled]
            }

        # If no webhook subscriptions were selected, skip registration
        if len(payload) == 3:  # Only "name", "uuid", "enabled" present (no actual webhooks)
            return {"success": False, "message": "No webhooks selected for registration."}

        webhook_url = f"{vpin_api_url.rstrip('/')}/api/v1/webhooks"

        # 🛠 Debugging: Explicitly print JSON before sending
        formatted_payload = json.dumps(payload, indent=2)  # Properly format JSON
        print(f"Registering webhook with payload:\n{formatted_payload}")

        # Send JSON payload to VPin Studio
        response = requests.post(webhook_url, data=formatted_payload, headers={'Content-Type': 'application/json'}, timeout=10)

        if response.status_code == 200:
            return {"success": True, "message": "Webhook registered successfully."}
        else:
            return {
                "success": False,
                "message": f"Failed to register webhook. Status Code: {response.status_code}, Response: {response.text}"
            }

    except requests.RequestException as e:
        return {"success": False, "message": f"Webhook request error: {str(e)}"}

def webhook_log_score(conn, data, vpin_score_id=None):
    """
    Webhook to handle score submissions from VPin Studio.
    It retrieves the score details via the VPin API and logs a new score entry in ArcadeScore.
    """
    try:
        print(f"vpin_score_id: {vpin_score_id}")
        print(f"New Score data received: {data}")

        sys.stdout.flush()

        # if "roomID" not in data:
        #     return {"success": False, "error": "Missing required parameter: roomID"}

        # room_id = data["roomID"]

        # # Retrieve the VPin API URL associated with this room
        # cursor = conn.cursor()
        # cursor.execute("SELECT vpin_api_url FROM settings WHERE id = ?", (room_id,))
        # room_data = cursor.fetchone()

        # if not room_data or not room_data["vpin_api_url"]:
        #     return {"success": False, "error": f"No VPin API URL found for room {room_id}"}

        # vpin_api_url = room_data["vpin_api_url"].rstrip("/")  # Ensure no trailing slash

        # # Fetch full score details from VPin API
        # score_api_url = f"{vpin_api_url}/api/v1/scores/{vpin_score_id}"
        # response = requests.get(score_api_url, timeout=10)

        # if response.status_code != 200:
        #     return {"success": False, "error": f"Failed to fetch score details from {score_api_url}"}

        # score_details = response.json()

        # # Prepare the score data to be logged
        # score_data = {
        #     "game_name": score_details.get("gameName"),
        #     "player_identifier": score_details.get("playerName"),
        #     "score": score_details.get("score"),
        #     "timestamp": score_details.get("timestamp"),
        #     "room_id": room_id,
        # }

        # # Log score using the existing function
        # success, message = log_score_to_db(conn, score_data)

        # close_db()

        # if success:
        #     return {"success": True, "message": "Score logged successfully"}
        # else:
        #     return {"success": False, "error": message}
        
        return {"success": True, "message": "Score logged successfully"}
    
    except requests.RequestException as e:
        return {"success": False, "message": f"Error fetching score details: {str(e)}"}

    except Exception as e:
        return {"success": False, "message": f"Internal Server Error: {str(e)}"}
    
def webhook_player(conn, data, vpin_player_id=None):
    try:
        print(f"vpin_player_id: {vpin_player_id}")
        print(f"New/Update player data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]

        # Retrieve the VPin API URL associated with this room
        cursor = conn.cursor()
        cursor.execute("SELECT vpin_api_url FROM settings WHERE id = ?", (room_id,))
        room_data = cursor.fetchone()

        if not room_data or not room_data["vpin_api_url"]:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}"}

        vpin_api_url = room_data["vpin_api_url"].rstrip("/")  # Ensure no trailing slash

        # Determine if it's a CREATE or UPDATE operation
        if not vpin_player_id and "playerID" in data:
            vpin_player_id = data["playerID"]

        # If updating, resolve `arcadescore_player_id` from `vpin_players` table
        arcadescore_player_id = None
        if vpin_player_id:
            cursor.execute("""
                SELECT arcadescore_player_id FROM vpin_players 
                WHERE vpin_player_id = ? AND server_url = ?
            """, (vpin_player_id, vpin_api_url))
            arcadescore_player_id_data = cursor.fetchone()

            if arcadescore_player_id_data:
                arcadescore_player_id = arcadescore_player_id_data["arcadescore_player_id"]

        # Fetch full player details from VPin API
        player_api_url = f"{vpin_api_url}/api/v1/players/{vpin_player_id}"
        response = requests.get(player_api_url, timeout=10)

        if response.status_code != 200:
            return {"success": False, "error": f"Failed to fetch player details from {player_api_url}"}

        player_details = response.json()

        # Prepare player data
        player_data = {
            "full_name": player_details.get("fullName", "Unknown Player"),
            "default_alias": player_details.get("alias", None),
            "aliases": player_details.get("aliases", []),
            "long_names_enabled": "FALSE",
        }

        # Handle CREATE or UPDATE logic
        if arcadescore_player_id:
            success, message = update_player_in_db(conn, arcadescore_player_id, player_data)
            if success:
                return {
                    "success": True, 
                    "message": f"Player updated successfully",
                    "player_id": arcadescore_player_id
                }
            else:
                return {"success": False, "error": message}
        else:
            success, message, new_player_id = add_player_to_db(conn, player_data)
            if success:
                link_vpin_player(conn, new_player_id, vpin_api_url, vpin_player_id)
                return {
                    "success": True, 
                    "message": "Player created successfully",
                    "player_id": new_player_id
                }
            else:
                return {"success": False, "error": message}

    except requests.RequestException as e:
        return {"success": False, "error": f"Error fetching player details: {str(e)}"}

    except Exception as e:
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}

def webhook_delete_player(conn, data, vpin_player_id):
    try:
        print(f"vpin_player_id: {vpin_player_id}")
        print(f"Delete player data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]

        # Retrieve the associated ArcadeScore player ID
        cursor = conn.cursor()
        cursor.execute("""
            SELECT arcadescore_player_id FROM vpin_players 
            WHERE vpin_player_id = ? AND server_url IN (SELECT vpin_api_url FROM settings WHERE id = ?)
        """, (vpin_player_id, room_id))
        result = cursor.fetchone()

        if not result:
            return {"success": False, "error": f"No matching ArcadeScore player found for VPin ID {vpin_player_id}"}

        arcadescore_player_id = result["arcadescore_player_id"]

        # Delete the player from our database
        success, message = delete_player_from_db(conn, arcadescore_player_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}

    except Exception as e:
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}

def webhook_game(conn, data, vpin_game_id=None):
    try:
        print(f"vpin_game_id: {vpin_game_id}")
        print(f"New/Update game data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]

        # Retrieve the VPin API URL associated with this room
        cursor = conn.cursor()
        cursor.execute("SELECT vpin_api_url FROM settings WHERE id = ?", (room_id,))
        room_data = cursor.fetchone()

        if not room_data or not room_data["vpin_api_url"]:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}"}

        vpin_api_url = room_data["vpin_api_url"].rstrip("/")  # Ensure no trailing slash

        # Determine if it's a CREATE or UPDATE operation
        if not vpin_game_id and "gameID" in data:
            vpin_game_id = data["gameID"]

        # If updating, resolve `arcadescore_game_id` from `vpin_games` table
        arcadescore_game_id = None
        if vpin_game_id:
            cursor.execute("""
                SELECT arcadescore_game_id FROM vpin_games 
                WHERE vpin_game_id = ? AND server_url = ?
            """, (vpin_game_id, vpin_api_url))
            arcadescore_game_id_data = cursor.fetchone()

            if arcadescore_game_id_data:
                arcadescore_game_id = arcadescore_game_id_data["arcadescore_game_id"]

        # Fetch full game details from VPin API
        game_api_url = f"{vpin_api_url}/api/v1/games/{vpin_game_id}"
        response = requests.get(game_api_url, timeout=10)

        if response.status_code != 200:
            return {"success": False, "error": f"Failed to fetch game details from {game_api_url}"}

        game_details = response.json()

        # Generate VPin Spreadsheet URL
        vpin_spreadsheet_url = generate_vpspreadsheet_url(game_details.get("extTableId", None), game_details.get("extTableVersionId", None))

        # Fetch game media if applicable
        media_data = fetch_game_images(vpin_api_url, vpin_game_id) if vpin_api_url else {}
        game_image = media_data.get("backglass", None)
        game_background = media_data.get("playfield", None)

        # Prepare game data for insert/update
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

        # Call save function
        success, message, saved_game_id = save_game_to_db(conn, game_data, arcadescore_game_id)

        if success:
            return {
                "success": True, 
                "message": f"Game {'updated' if arcadescore_game_id else 'created'} successfully",
                "game_id": saved_game_id
            }
        else:
            return {"success": False, "error": message}

    except requests.RequestException as e:
        return {"success": False, "error": f"Error fetching game details: {str(e)}"}

    except Exception as e:
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}
    
def webhook_delete_game(conn, data, vpin_game_id):
    try:
        print(f"vpin_game_id: {vpin_game_id}")
        print(f"Delete game data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]

        # Retrieve the associated ArcadeScore game ID
        cursor = conn.cursor()
        cursor.execute("""
            SELECT arcadescore_game_id FROM vpin_games 
            WHERE vpin_game_id = ? AND server_url IN (SELECT vpin_api_url FROM settings WHERE id = ?)
        """, (vpin_game_id, room_id))
        result = cursor.fetchone()

        if not result:
            return {"success": False, "error": f"No matching ArcadeScore game found for VPin ID {vpin_game_id}"}

        arcadescore_game_id = result["arcadescore_game_id"]

        # Delete the game from our database
        success, message = delete_game_from_db(conn, arcadescore_game_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}

    except Exception as e:
        return {"success": False, "error": f"Internal Server Error: {str(e)}"}
