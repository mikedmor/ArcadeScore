from flask import Blueprint, jsonify, request
from app.modules.database import get_db, close_db
from app.modules.vpspreadsheet import fetch_vps_data
from app.modules.utils import get_server_base_url

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
