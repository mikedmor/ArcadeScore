import json
from flask import Blueprint, request, jsonify
from app.modules.database import get_db, close_db
from app.modules.players import (
    get_all_players,
    get_player_from_db,
    add_player_to_db,
    update_player_in_db,
    delete_player_from_db,
    link_vpin_player,
    toggle_player_score_visibility
)

players_bp = Blueprint("players", __name__)

@players_bp.route("/api/v1/players", methods=["GET"])
def get_players():
    """Fetch all players and their aliases, including VPin mappings."""
    result = get_all_players(get_db())
    close_db()
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

@players_bp.route("/api/v1/players/<int:player_id>", methods=["GET"])
def get_player(player_id):
    """Fetch player details, scores, and aliases."""
    result = get_player_from_db(get_db(), player_id)
    close_db()
    if not result:
        return jsonify({"error": "Player not found"}), 404
    return jsonify(result)

@players_bp.route("/api/v1/players", methods=["POST"])
def add_player():
    """Add a new player with multiple aliases and avatar upload."""
    try:
        form_data = request.form.to_dict()
        file = request.files.get("player_icon_file")
        success, message, player_id = add_player_to_db(get_db(), form_data, file)
        close_db()

        if success:
            return jsonify({"success": True, "player_id": player_id, "message": message}), 201
        return jsonify({"error": message}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Failed to add player: {str(e)}"}), 500

@players_bp.route("/api/v1/players/<int:player_id>", methods=["PUT"])
def update_player(player_id):
    """Update an existing player's details and avatar."""
    try:
        form_data = request.form.to_dict()
        file = request.files.get("player_icon_file")
        success, message = update_player_in_db(get_db(), player_id, form_data, file)
        close_db()

        if success:
            return jsonify({"success": True, "message": message}), 200
        return jsonify({"error": message}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Failed to update player: {str(e)}"}), 500

@players_bp.route("/api/v1/players/<int:player_id>", methods=["DELETE"])
def delete_player(player_id):
    """Delete a player and associated aliases."""
    success, message = delete_player_from_db(get_db(), player_id)
    close_db()
    if success:
        return jsonify({"success": True, "message": message}), 200
    return jsonify({"error": message}), 400

@players_bp.route("/api/v1/players/vpin", methods=["POST"])
def link_vpin_players():
    """Links VPin Studio players to ArcadeScore players and updates player details."""
    try:
        data = request.get_json()
        success, message = link_vpin_player(get_db(), data)
        close_db()
        if success:
            return jsonify({"success": True, "message": message}), 200
        return jsonify({"error": message}), 400

    except Exception as e:
        close_db()
        return jsonify({"error": f"Failed to link VPin players: {str(e)}"}), 500

@players_bp.route("/api/v1/players/vpin/import", methods=["POST"])
def import_vpin_player():
    """Imports a new VPin Studio player and links them to ArcadeScore."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid data received"}), 400

        conn = get_db()

        # Add player using existing function
        result = add_player_to_db(conn, {
            "full_name": data.get("full_name"),
            "default_alias": data.get("default_alias", "").strip(),
            "aliases": json.dumps(data.get("aliases", [])),
            "long_names_enabled": "FALSE",
        })

        # Ensure we correctly unpack values
        if isinstance(result, tuple) and len(result) == 3:
            success, message, player_id = result
        elif isinstance(result, tuple) and len(result) == 2:
            success, message = result
            player_id = None
        else:
            close_db()
            return jsonify({"error": "Unexpected response from add_player_to_db"}), 500

        if not success:
            close_db()
            return jsonify({"error": message}), 400

        # Link player to VPin Studio
        vpin_data = {
            "server_url": data.get("vpin_url"),
            "players": [{
                "arcadescore_player_id": player_id,
                "vpin_player_id": data.get("vpin_player_id"),
                "full_name": data.get("full_name"),
                "aliases": data.get("aliases", [])
            }]
        }
        success, message = link_vpin_player(conn, vpin_data)

        close_db()
        if not success:
            return jsonify({"error": message}), 400

        return jsonify({
            "success": True,
            "message": "VPin player imported and linked successfully",
            "player_id": player_id
        }), 201

    except Exception as e:
        close_db()
        return jsonify({"error": f"Failed to import VPin player: {str(e)}"}), 500

@players_bp.route("/api/v1/players/<int:player_id>/toggle_visibility", methods=["POST"])
def toggle_player_visibility(player_id):
    """Toggles whether a player's scores are visible on the scoreboard."""
    data = request.get_json()
    hide = data.get("hide", True)  # Defaults to hiding the player

    success, message = toggle_player_score_visibility(get_db(), player_id, hide)

    return jsonify({"message": message, "hidden": hide}), 200 if success else 400