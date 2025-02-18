import requests
import uuid
from app.modules.utils import get_server_base_url

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
        if webhooks.get("highscores", {}).get("UPDATE", False):
            payload["scores"] = {
                "endpoint": f"{server_base_url}/webhook/addScore",
                "parameters": {
                    "roomID": room_id
                },
                "subscribe": ["update"]
            }

        if any(webhooks.get("games", {}).values()):  # If any game event is selected
            payload["games"] = {
                "endpoint": f"{server_base_url}/webhook/games",
                "parameters": {
                    "roomID": room_id,
                    "gameCategory": "arcade"
                },
                "subscribe": [event for event, enabled in webhooks.get("games", {}).items() if enabled]
            }

        if any(webhooks.get("players", {}).values()):  # If any player event is selected
            payload["players"] = {
                "endpoint": f"{server_base_url}/webhook/players",
                "subscribe": [event for event, enabled in webhooks.get("players", {}).items() if enabled]
            }

        # If no webhook subscriptions were selected, skip registration
        if len(payload) == 3:  # Only "name", "uuid", "enabled" present (no actual webhooks)
            return {"success": False, "message": "No webhooks selected for registration."}

        webhook_url = f"{vpin_api_url.rstrip('/')}/api/v1/webhooks"
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            return {"success": True, "message": "Webhook registered successfully."}
        else:
            return {"success": False, "message": f"Failed to register webhook. Status Code: {response.status_code}, Response: {response.text}"}

    except requests.RequestException as e:
        return {"success": False, "message": f"Webhook request error: {str(e)}"}
    