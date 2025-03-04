from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.games import save_game_to_db, delete_game_from_db
from app.modules.utils import generate_random_color
from app.modules.vpinstudio import fetch_game_images
from app.modules.vpspreadsheet import generate_vpspreadsheet_url
import requests

webhook_games_bp = Blueprint('webhook_games', __name__)

@webhook_games_bp.route("/webhook/games", methods=["POST"])
@webhook_games_bp.route("/webhook/games/<int:vpin_game_id>", methods=["PUT"])
def handle_webhook_game():
    """
    Webhook to handle game creation (POST) and updates (PUT) from VPin Studio.
    It retrieves the necessary details via VPin API before storing the game.
    """
    try:
        data = request.get_json()

        print(f"vpin_game_id: {vpin_game_id}")
        print(f"New/Update game data received: {data}")

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
            return jsonify({"error": f"Failed to fetch game details from {game_api_url}"}), 500

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

        close_db()

        if success:
            return jsonify({
                "message": f"Game {'updated' if arcadescore_game_id else 'created'} successfully",
                "game_id": saved_game_id
            }), 200 if arcadescore_game_id else 201
        else:
            return jsonify({"error": message}), 400

    except requests.RequestException as e:
        close_db()
        return jsonify({"error": f"Error fetching game details: {str(e)}"}), 500

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@webhook_games_bp.route("/webhook/games/<int:vpin_game_id>", methods=["DELETE"])
def handle_webhook_delete_game(vpin_game_id):
    """
    Webhook to handle game deletions from VPin Studio.
    Deletes the corresponding ArcadeScore game.
    """
    try:
        data = request.get_json()

        print(f"vpin_game_id: {vpin_game_id}")
        print(f"Delete game data received: {data}")

        if "roomID" not in data:
            return jsonify({"error": "Missing required parameter: roomID"}), 400

        room_id = data["roomID"]

        # Retrieve the associated ArcadeScore game ID
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT arcadescore_game_id FROM vpin_games 
            WHERE vpin_game_id = ? AND server_url IN (SELECT vpin_api_url FROM settings WHERE id = ?)
        """, (vpin_game_id, room_id))
        result = cursor.fetchone()

        if not result:
            close_db()
            return jsonify({"error": f"No matching ArcadeScore game found for VPin ID {vpin_game_id}"}), 404

        arcadescore_game_id = result["arcadescore_game_id"]

        # Delete the game from our database
        success, message = delete_game_from_db(conn, arcadescore_game_id)

        close_db()

        if success:
            return jsonify({"message": message}), 200
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500