from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.scores import update_score_in_db
import requests

webhook_scores_bp = Blueprint("webhook_scores", __name__)

@webhook_scores_bp.route("/webhook/scores/<int:vpin_score_id>", methods=["PUT"])
def handle_webhook_update_score(vpin_score_id):
    """
    Webhook to handle score updates from VPin Studio.
    Retrieves updated score details via the VPin API and updates ArcadeScore's database.
    """
    try:
        data = request.get_json()

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

        # Fetch full score details from VPin API
        score_api_url = f"{vpin_api_url}/api/v1/scores/{vpin_score_id}"
        response = requests.get(score_api_url, timeout=10)

        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch score details from {score_api_url}"}), 500

        score_details = response.json()

        # Prepare the score update data
        score_data = {
            "player_identifier": score_details.get("playerName"),
            "score": score_details.get("score"),
            "timestamp": score_details.get("timestamp"),
            "room_id": room_id,
            "game_name": score_details.get("gameName"),
        }

        # Update score in ArcadeScore
        success, message = update_score_in_db(conn, score_data)

        close_db()

        if success:
            return jsonify({"message": "Score updated successfully"}), 200
        else:
            return jsonify({"error": message}), 400

    except requests.RequestException as e:
        close_db()
        return jsonify({"error": f"Error fetching score details: {str(e)}"}), 500

    except Exception as e:
        close_db()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
