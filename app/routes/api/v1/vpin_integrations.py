import requests
from flask import Blueprint, request, jsonify
from app.modules.database import get_db
from app.modules.utils import normalize_vpin_url, vpin_url
from app.modules.vpin_integration import import_vpin_game_into_room
from app.modules.webhooks import register_vpin_webhook
from app.modules.auth import require_room_admin

vpin_integrations_bp = Blueprint("vpin_integrations", __name__)

# ---------------------------------------------------------------------------
# Linked VPin Studio servers for a room. Independent of any registered webhook
# so a room can import games/players from a server without ever subscribing to
# webhooks.
# ---------------------------------------------------------------------------

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-servers", methods=["GET"])
def list_vpin_servers(room_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, server_url, label, created_at
            FROM vpin_servers WHERE room_id = ? ORDER BY created_at ASC;
        """, (room_id,))
        servers = [dict(row) for row in cursor.fetchall()]
        return jsonify(servers), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-servers", methods=["POST"])
@require_room_admin
def link_vpin_server(room_id):
    """Link a VPin Studio server to a room without registering any webhook."""
    try:
        data = request.get_json(silent=True) or {}
        server_url = normalize_vpin_url((data.get("server_url") or "").strip())
        label = (data.get("label") or "").strip() or None

        if not server_url:
            return jsonify({"error": "server_url is required"}), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM settings WHERE id = ?", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Scoreboard not found"}), 404

        cursor.execute("""
            INSERT OR IGNORE INTO vpin_servers (room_id, server_url, label) VALUES (?, ?, ?);
        """, (room_id, server_url, label))
        conn.commit()

        cursor.execute("""
            SELECT id, server_url, label, created_at FROM vpin_servers
            WHERE room_id = ? AND server_url = ?;
        """, (room_id, server_url))
        server = dict(cursor.fetchone())

        return jsonify(server), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-servers/<int:server_id>", methods=["DELETE"])
@require_room_admin
def unlink_vpin_server(room_id, server_id):
    """Remove a linked server from a room. Does not touch already-imported games or
    players, and does not delete any registered webhook against that server — those
    are managed separately via the vpin-webhooks endpoints below."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM vpin_servers WHERE id = ? AND room_id = ?", (server_id, room_id))
        if not cursor.fetchone():
            return jsonify({"error": "Linked server not found for this scoreboard"}), 404

        cursor.execute("DELETE FROM vpin_servers WHERE id = ?", (server_id,))
        conn.commit()
        return jsonify({"message": "Server unlinked"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Registered webhooks for a room — view / delete without deleting the whole
# scoreboard, plus basic health (last event received, last error).
# ---------------------------------------------------------------------------

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-webhooks", methods=["GET"])
def list_vpin_webhooks(room_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, server_url, webhook_uuid, webhook_name, enabled,
                score_update, game_create, game_update, game_delete,
                player_create, player_update, player_delete,
                pause_update, unpause_update, last_event_at, last_error
            FROM vpin_webhooks WHERE room_id = ? ORDER BY id ASC;
        """, (room_id,))
        webhooks = [dict(row) for row in cursor.fetchall()]
        return jsonify(webhooks), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-webhooks", methods=["POST"])
@require_room_admin
def register_webhook(room_id):
    """
    Register a new webhook subscription for an existing room. Reuses the same
    register_vpin_webhook() the scoreboard creation wizard calls - this just triggers
    it from the Integrations Menu instead, for rooms that were created without going
    through the wizard's webhook step (or that want to register against a second
    server). Body:
    {
        "server_url": "http://192.168.x.x:8089/",
        "webhooks": {
            "highscores": {"UPDATE": true},
            "games": {"CREATE": true, "UPDATE": true, "DELETE": true},
            "players": {"CREATE": true, "UPDATE": true, "DELETE": true},
            "pause": {"UPDATE": true},
            "unpause": {"UPDATE": true}
        }
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        server_url = normalize_vpin_url((data.get("server_url") or "").strip())
        webhooks = data.get("webhooks", {})

        if not server_url:
            return jsonify({"error": "server_url is required"}), 400
        if not isinstance(webhooks, dict) or not any(
            isinstance(events, dict) and any(events.values()) for events in webhooks.values()
        ):
            return jsonify({"error": "Select at least one event to subscribe to"}), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT room_name FROM settings WHERE id = ?", (room_id,))
        room = cursor.fetchone()
        if not room:
            return jsonify({"error": "Scoreboard not found"}), 404

        result = register_vpin_webhook(conn, server_url, room_id, room["room_name"], webhooks)

        if result["success"]:
            return jsonify({"message": result["message"]}), 201
        return jsonify({"error": result["message"]}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-webhooks/<int:webhook_id>", methods=["DELETE"])
@require_room_admin
def delete_vpin_webhook(room_id, webhook_id):
    """Deregister one webhook set from VPin Studio and remove it locally, without
    touching the rest of the scoreboard (games/players/scores stay put)."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT server_url, webhook_uuid FROM vpin_webhooks WHERE id = ? AND room_id = ?;
        """, (webhook_id, room_id))
        webhook = cursor.fetchone()

        if not webhook:
            return jsonify({"error": "Webhook not found for this scoreboard"}), 404

        try:
            delete_url = vpin_url(webhook["server_url"], f"api/v1/webhooks/{webhook['webhook_uuid']}")
            response = requests.delete(delete_url, timeout=10)
            if response.status_code != 200:
                print(f"⚠️ VPin Studio returned {response.status_code} deleting webhook {webhook['webhook_uuid']}; removing locally anyway.")
        except requests.RequestException as e:
            print(f"⚠️ Failed to reach VPin Studio to delete webhook {webhook['webhook_uuid']}: {e}. Removing locally anyway.")

        cursor.execute("DELETE FROM vpin_webhooks WHERE id = ?", (webhook_id,))
        conn.commit()
        return jsonify({"message": "Webhook removed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Re-import games from an already-linked VPin server into an existing room,
# without going through the scoreboard creation wizard. Player re-linking
# reuses the existing /api/v1/players/vpin and /api/v1/players/vpin/import
# endpoints directly from the Integrations Menu UI - no new backend needed
# there since those were never tied to scoreboard creation in the first place.
# ---------------------------------------------------------------------------

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-games/import", methods=["POST"])
@require_room_admin
def import_vpin_games(room_id):
    """
    Imports one or more VPin Studio games into an existing room. Body:
    {
        "server_url": "http://192.168.x.x:8089/",
        "games": [{"id": 1, "name": "...", "extTableId": "...", "extTableVersionId": "..."}, ...],
        "preset_id": 1,
        "retrieve_media": true,
        "media_source_priority": "fallback",
        "image_compression_level": "original",
        "sync_historical_scores": true
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        server_url = normalize_vpin_url((data.get("server_url") or "").strip())
        games = data.get("games", [])
        preset_id = data.get("preset_id", 1)
        retrieve_media = bool(data.get("retrieve_media", False))
        media_priority = data.get("media_source_priority", "fallback")
        image_compression_level = data.get("image_compression_level", "original")
        sync_historical_scores = bool(data.get("sync_historical_scores", False))

        if not server_url:
            return jsonify({"error": "server_url is required"}), 400
        if not games:
            return jsonify({"error": "No games selected"}), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM settings WHERE id = ?", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Scoreboard not found"}), 404

        cursor.execute("""
            SELECT css_score_cards, css_initials, css_scores, css_box, css_title
            FROM presets WHERE id = ?;
        """, (preset_id,))
        preset = cursor.fetchone()

        if not preset:
            return jsonify({"error": "Invalid preset selected"}), 400

        css_style = dict(preset)

        # Keep this room's linked-server list in sync in case it was imported from
        # directly rather than via the "link a server" step.
        cursor.execute("""
            INSERT OR IGNORE INTO vpin_servers (room_id, server_url) VALUES (?, ?);
        """, (room_id, server_url))
        conn.commit()

        vpin_players = []
        if sync_historical_scores:
            cursor.execute("""
                SELECT arcadescore_player_id, vpin_player_id, server_url
                FROM vpin_players WHERE server_url = ?;
            """, (server_url,))
            vpin_players = [
                {"arcadescore_player_id": row[0], "vpin_player_id": row[1], "server_url": row[2]}
                for row in cursor.fetchall()
            ]

        results = []
        for game in games:
            # One game failing (flaky media download, a transient DB error) must not
            # abort every game after it in the batch - each import stands alone.
            try:
                success, message, game_id = import_vpin_game_into_room(
                    conn, server_url, room_id, game,
                    css_style=css_style,
                    options={
                        "retrieve_media": retrieve_media,
                        "media_priority": media_priority,
                        "image_compression_level": image_compression_level,
                        "sync_historical_scores": sync_historical_scores,
                        "vpin_players": vpin_players,
                    },
                )
            except Exception as e:
                success, message, game_id = False, f"Unexpected error: {e}", None
                print(f"⚠️ Failed to import game {game.get('id')} ({game.get('name')}): {e}")

            results.append({
                "vpin_game_id": game.get("id"),
                "name": game.get("name"),
                "success": success,
                "message": message,
                "game_id": game_id,
            })


        succeeded = sum(1 for r in results if r["success"])
        return jsonify({
            "message": f"Imported {succeeded}/{len(results)} game(s)",
            "results": results,
        }), 200 if succeeded else 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@vpin_integrations_bp.route("/api/v1/scoreboards/<int:room_id>/vpin-games/resync", methods=["POST"])
@require_room_admin
def resync_vpin_games(room_id):
    """
    Re-fetches media and/or historical scores for games this room already has
    linked to a VPin server — does not import anything new. Powers the
    "Resync Media" / "Resync Scores" actions in the Integrations Menu. Each
    game's own per-game CSS is preserved (unlike a fresh import, which applies a
    preset), since the point here is to refresh data, not restyle games the user
    may have already customized.
    """
    try:
        data = request.get_json(silent=True) or {}
        server_url = normalize_vpin_url((data.get("server_url") or "").strip())
        retrieve_media = bool(data.get("retrieve_media", False))
        media_priority = data.get("media_source_priority", "fallback")
        image_compression_level = data.get("image_compression_level", "original")
        sync_historical_scores = bool(data.get("sync_historical_scores", False))

        if not server_url:
            return jsonify({"error": "server_url is required"}), 400
        if not retrieve_media and not sync_historical_scores:
            return jsonify({"error": "Nothing to resync - enable media and/or scores"}), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT vg.vpin_game_id, g.game_name, g.css_score_cards, g.css_initials,
                   g.css_scores, g.css_box, g.css_title
            FROM vpin_games vg
            JOIN games g ON vg.arcadescore_game_id = g.id
            WHERE vg.server_url = ? AND g.room_id = ?;
        """, (server_url, room_id))
        linked_games = cursor.fetchall()

        if not linked_games:
            return jsonify({"error": "No games linked to that server for this scoreboard"}), 404

        vpin_players = []
        if sync_historical_scores:
            cursor.execute("""
                SELECT arcadescore_player_id, vpin_player_id, server_url
                FROM vpin_players WHERE server_url = ?;
            """, (server_url,))
            vpin_players = [
                {"arcadescore_player_id": row[0], "vpin_player_id": row[1], "server_url": row[2]}
                for row in cursor.fetchall()
            ]

        results = []
        for row in linked_games:
            vpin_game_id = row["vpin_game_id"]

            try:
                game_details_url = vpin_url(server_url, f"api/v1/games/{vpin_game_id}")
                response = requests.get(game_details_url, timeout=10)
                response.raise_for_status()
                game_details = response.json()
            except requests.RequestException as e:
                results.append({
                    "vpin_game_id": vpin_game_id, "name": row["game_name"],
                    "success": False, "message": f"Failed to fetch game details: {e}",
                })
                continue

            game = {
                "id": vpin_game_id,
                "name": game_details.get("gameDisplayName", row["game_name"]),
                "extTableId": game_details.get("extTableId"),
                "extTableVersionId": game_details.get("extTableVersionId"),
            }

            css_style = {
                "css_score_cards": row["css_score_cards"],
                "css_initials": row["css_initials"],
                "css_scores": row["css_scores"],
                "css_box": row["css_box"],
                "css_title": row["css_title"],
            }

            # One game failing (flaky media download, a transient DB error) must not
            # abort every game after it in the batch - each resync stands alone.
            try:
                success, message, game_id = import_vpin_game_into_room(
                    conn, server_url, room_id, game,
                    css_style=css_style,
                    options={
                        "retrieve_media": retrieve_media,
                        "media_priority": media_priority,
                        "image_compression_level": image_compression_level,
                        "sync_historical_scores": sync_historical_scores,
                        "vpin_players": vpin_players,
                    },
                )
            except Exception as e:
                success, message, game_id = False, f"Unexpected error: {e}", None
                print(f"⚠️ Failed to resync game {vpin_game_id} ({game['name']}): {e}")

            results.append({
                "vpin_game_id": vpin_game_id, "name": game["name"],
                "success": success, "message": message, "game_id": game_id,
            })


        succeeded = sum(1 for r in results if r["success"])
        return jsonify({
            "message": f"Resynced {succeeded}/{len(results)} game(s)",
            "results": results,
        }), 200 if succeeded else 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
