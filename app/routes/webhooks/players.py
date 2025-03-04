from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.players import add_player_to_db, update_player_in_db, delete_player_from_db, link_vpin_player
import requests

webhook_players_bp = Blueprint('webhook_players', __name__)

@webhook_players_bp.route("/webhook/players", methods=["POST"])
@webhook_players_bp.route("/webhook/players/<int:vpin_player_id>", methods=["PUT"])
def handle_webhook_player(vpin_player_id=None):
    """
    Webhook to handle player creation (POST) and updates (PUT) from VPin Studio.
    It retrieves necessary details via the VPin API before storing the player.
    """
    try:
        data = request.get_json()

        print(f"vpin_player_id: {vpin_player_id}")
        print(f"New/Update player data received: {data}")

        if "roomID" not in data:
            return jsonify({"error": "Missing required parameter: roomID"}), 400

        room_id = data["roomID"]

        # Retrieve the VPin API URL associated with this room
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT vpin_api_url FROM settings WHERE id = ?", (room_id,))
        room_data = cursor.fetchone()

        if not room_data or not room_data["vpin_api_url"]:
            return jsonify({"error": f"No VPin API URL found for room {room_id}"}), 400

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
            return jsonify({"error": f"Failed to fetch player details from {player_api_url}"}), 500

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
            close_db()
            if success:
                return jsonify({
                    "message": f"Player updated successfully",
                    "player_id": arcadescore_player_id
                }), 200
            else:
                return jsonify({"error": message}), 400
        else:
            success, message, new_player_id = add_player_to_db(conn, player_data)
            close_db()
            if success:
                link_vpin_player(conn, new_player_id, vpin_api_url, vpin_player_id)
                return jsonify({
                    "message": "Player created successfully",
                    "player_id": new_player_id
                }), 201
            else:
                return jsonify({"error": message}), 400

    except requests.RequestException as e:
        close_db()
        return jsonify({"error": f"Error fetching player details: {str(e)}"}), 500

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    

@webhook_players_bp.route("/webhook/players/<int:vpin_player_id>", methods=["DELETE"])
def handle_webhook_delete_player(vpin_player_id):
    """
    Webhook to handle player deletions from VPin Studio.
    Deletes the corresponding ArcadeScore player.
    """
    try:
        data = request.get_json()

        print(f"vpin_player_id: {vpin_player_id}")
        print(f"Delete player data received: {data}")

        if "roomID" not in data:
            return jsonify({"error": "Missing required parameter: roomID"}), 400

        room_id = data["roomID"]

        # Retrieve the associated ArcadeScore player ID
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT arcadescore_player_id FROM vpin_players 
            WHERE vpin_player_id = ? AND server_url IN (SELECT vpin_api_url FROM settings WHERE id = ?)
        """, (vpin_player_id, room_id))
        result = cursor.fetchone()

        if not result:
            close_db()
            return jsonify({"error": f"No matching ArcadeScore player found for VPin ID {vpin_player_id}"}), 404

        arcadescore_player_id = result["arcadescore_player_id"]

        # Delete the player from our database
        success, message = delete_player_from_db(conn, arcadescore_player_id)

        close_db()

        if success:
            return jsonify({"message": message}), 200
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
