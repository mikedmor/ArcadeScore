import sys
import requests
import traceback
import uuid
import json
import eventlet
from app.modules.utils import get_server_base_url, generate_random_color, format_timestamp, normalize_vpin_url, vpin_url, parse_vpin_timestamp
from app.modules.scores import log_score_to_db
from app.modules.players import add_player_to_db, update_player_in_db, delete_player_from_db, link_vpin_player
from app.modules.games import save_game_to_db, delete_game_from_db
from app.modules.vpspreadsheet import generate_vpspreadsheet_url
from app.modules.vpinstudio import fetch_game_images
from app.modules.socketio import emit_message

# Score webhooks have, in the past, arrived slightly before VPin Studio's own score
# endpoint reflects the new score. Retry a few times before giving up rather than
# silently dropping it.
SCORE_FETCH_MAX_ATTEMPTS = 5
SCORE_FETCH_RETRY_DELAY_SECONDS = 2

def _get_room_webhook(cursor, room_id):
    """Look up the registered VPin Studio webhook (server + auth token) for a room.
    Rooms with more than one registered webhook set only get the first row back —
    a known limitation."""
    cursor.execute("""
        SELECT server_url, webhook_token FROM vpin_webhooks WHERE room_id = ? LIMIT 1;
    """, (room_id,))
    return cursor.fetchone()

def _verify_webhook_token(webhook_row, data):
    """Reject a CREATE/UPDATE webhook call that doesn't carry the token this room's
    webhook was registered with. Rooms registered before this check existed have no
    stored token yet (NULL) and are let through until they re-register. DELETE calls
    carry no parameters at all per VPin Studio's docs, so they can't be checked here —
    callers should not use this for DELETE handlers."""
    stored_token = webhook_row["webhook_token"] if webhook_row else None
    if not stored_token:
        return True
    return data.get("token") == stored_token

def record_webhook_health(conn, room_id, error=None):
    """Update a room's webhook health (last event received / last error) after
    processing an inbound webhook call, for the Integrations Menu to display.
    No-op if room_id couldn't be resolved (e.g. a DELETE call, which VPin Studio
    sends with no parameters at all — see _get_room_webhook)."""
    if not room_id:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vpin_webhooks SET last_event_at = CURRENT_TIMESTAMP, last_error = ?
            WHERE room_id = ?;
        """, (error, room_id))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Failed to record webhook health for room {room_id}: {e}")

def register_vpin_webhook(conn, vpin_api_url, room_id, scoreboard_name, webhooks):
    """Registers a webhook with VPin Studio based on user selections."""
    try:
        vpin_api_url = normalize_vpin_url(vpin_api_url)

        webhook_uuid = str(uuid.uuid4())  # Generate a unique webhook ID
        webhook_token = str(uuid.uuid4())  # Shared secret echoed back on PUT/POST calls
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
        pause_update = webhooks.get("pause", {}).get("UPDATE", False)
        unpause_update = webhooks.get("unpause", {}).get("UPDATE", False)

        # Populate webhook payload based on selections. "token" rides along in
        # "parameters" so every CREATE/UPDATE call we receive can be checked against
        # what this room's webhook was registered with. VPin Studio does not send
        # parameters on DELETE calls, so those remain unauthenticated regardless.
        if score_update:
            payload["scores"] = {
                "endpoint": f"{server_base_url}/webhook/scores",
                "parameters": {"roomID": room_id, "token": webhook_token},
                "subscribe": [
                    event.lower()
                    for event, enabled in webhooks.get("highscores", {}).items() if enabled]
            }

        if game_create or game_update or game_delete:
            payload["games"] = {
                "endpoint": f"{server_base_url}/webhook/games",
                "parameters": {"roomID": room_id, "token": webhook_token},
                "subscribe": [
                    event.lower()
                    for event, enabled in webhooks.get("games", {}).items() if enabled
                ]
            }

        if player_create or player_update or player_delete:
            payload["players"] = {
                "endpoint": f"{server_base_url}/webhook/players",
                "parameters": {"roomID": room_id, "token": webhook_token},
                "subscribe": [
                    event.lower()
                    for event, enabled in webhooks.get("players", {}).items() if enabled
                ]
            }

        if pause_update:
            payload["pause"] = {
                "endpoint": f"{server_base_url}/webhook/pause",
                "parameters": {"roomID": room_id, "token": webhook_token},
                "subscribe": ["update"]
            }

        if unpause_update:
            payload["unpause"] = {
                "endpoint": f"{server_base_url}/webhook/unpause",
                "parameters": {"roomID": room_id, "token": webhook_token},
                "subscribe": ["update"]
            }

        if len(payload) == 3:  # Only "name", "uuid", "enabled" present (no webhooks)
            return {"success": False, "message": "No webhooks selected for registration."}

        webhook_url = vpin_url(vpin_api_url, "api/v1/webhooks")

        # 🛠 Debugging: Explicitly print JSON before sending
        formatted_payload = json.dumps(payload, indent=2)  # Properly format JSON
        print(f"Registering webhook with payload:\n{formatted_payload}")

        # Send JSON payload to VPin Studio
        response = requests.post(webhook_url, data=formatted_payload, headers={'Content-Type': 'application/json'}, timeout=10)

        if response.status_code == 200:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpin_webhooks (room_id, server_url, webhook_uuid, webhook_name, webhook_token,
                    score_update, game_create, game_update, game_delete,
                    player_create, player_update, player_delete,
                    pause_update, unpause_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                room_id, vpin_api_url, webhook_uuid, webhook_name, webhook_token,
                "TRUE" if score_update else "FALSE",
                "TRUE" if game_create else "FALSE",
                "TRUE" if game_update else "FALSE",
                "TRUE" if game_delete else "FALSE",
                "TRUE" if player_create else "FALSE",
                "TRUE" if player_update else "FALSE",
                "TRUE" if player_delete else "FALSE",
                "TRUE" if pause_update else "FALSE",
                "TRUE" if unpause_update else "FALSE",
            ))

            # Keep the room's linked-server list in sync even if this webhook is
            # later edited or removed.
            cursor.execute("""
                INSERT OR IGNORE INTO vpin_servers (room_id, server_url) VALUES (?, ?);
            """, (room_id, vpin_api_url))

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

        webhook_row = _get_room_webhook(cursor, room_id)
        if not webhook_row:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}", "room_id": room_id}

        if not _verify_webhook_token(webhook_row, data):
            return {"success": False, "error": "Invalid or missing webhook token", "room_id": room_id}

        vpin_api_url = webhook_row["server_url"]

        # ✅ Fetch additional settings
        cursor.execute("""
            SELECT long_names_enabled, dateformat FROM settings WHERE id = ?;
        """, (room_id,))
        room_data = cursor.fetchone()

        if not room_data:
            return {"success": False, "error": f"No room settings found for room {room_id}", "room_id": room_id}

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
            return {"success": False, "error": f"No matching ArcadeScore game found for VPin Game ID {vpin_game_id}", "room_id": room_id}

        arcadescore_game_id = mapping["arcadescore_game_id"]
        print(f"🎮 VPin Game ID {vpin_game_id} mapped to ArcadeScore Game ID {arcadescore_game_id}")
        sys.stdout.flush()

        score_api_url = vpin_url(vpin_api_url, f"api/v1/games/scores/{vpin_game_id}")

        # ✅ Fetch all mapped players from `vpin_players` for this server (once, reused
        # across every retry attempt below)
        cursor.execute("""
            SELECT arcadescore_player_id, vpin_player_id FROM vpin_players WHERE server_url = ?;
        """, (vpin_api_url,))
        vpin_players = {row["vpin_player_id"]: row["arcadescore_player_id"] for row in cursor.fetchall()}

        print(f"📋 vpin_players List for {vpin_api_url}: {vpin_players}")
        sys.stdout.flush()

        new_scores = []

        for attempt in range(1, SCORE_FETCH_MAX_ATTEMPTS + 1):
            print(f"🌐 Fetching scores from {score_api_url} (attempt {attempt}/{SCORE_FETCH_MAX_ATTEMPTS})")
            sys.stdout.flush()

            try:
                response = requests.get(score_api_url, timeout=10)
                response.raise_for_status()  # Raises an exception for HTTP errors
            except requests.RequestException as e:
                print(f"🌐 Request Exception: {traceback.format_exc()}")
                sys.stdout.flush()
                return {"success": False, "error": f"Error fetching score details: {str(e)}", "room_id": room_id}

            scores_data = response.json().get("scores", [])
            print(f"📊 Found {len(scores_data)} scores to process.")
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

                # Convert timestamp to proper format. A fallback to "now" here would
                # defeat the exact-timestamp dedup check below on every retry of this
                # same score, so a parse failure is logged loudly rather than silently
                # substituted.
                try:
                    formatted_timestamp = parse_vpin_timestamp(raw_timestamp)
                except Exception as e:
                    print(f"⚠️ Failed to parse timestamp {raw_timestamp!r}, skipping score entry. Error: {e}")
                    sys.stdout.flush()
                    continue

                # ✅ Attempt to match the player using the dictionary lookup
                arcadescore_player_id = vpin_players.get(vpin_player_id)

                if not arcadescore_player_id:
                    print(f"⚠️ No matching player found for VPin Player ID: {vpin_player_id} on {vpin_api_url}. Skipping score.")
                    sys.stdout.flush()
                    continue  # Skip scores with unknown players

                # ✅ Check if the score already exists
                cursor.execute("""
                    SELECT COUNT(*) FROM highscores
                    WHERE game_id = ? AND player_id = ? AND score = ? AND timestamp = ? AND room_id = ?;
                """, (arcadescore_game_id, arcadescore_player_id, score_value, formatted_timestamp, room_id))
                score_exists = cursor.fetchone()[0] > 0

                if score_exists:
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

            if new_scores:
                break

            if attempt < SCORE_FETCH_MAX_ATTEMPTS:
                print(f"⏳ No new scores yet, retrying in {SCORE_FETCH_RETRY_DELAY_SECONDS}s...")
                sys.stdout.flush()
                eventlet.sleep(SCORE_FETCH_RETRY_DELAY_SECONDS)

        conn.commit()

        if not new_scores:
            return {"success": False, "error": "No new scores found after retrying.", "room_id": room_id}

        # ✅ Fetch all scores for this game after the update
        cursor.execute("""
            SELECT p.full_name, p.default_alias, h.score, h.timestamp, h.wins, h.losses
            FROM highscores h
            JOIN players p ON h.player_id = p.id
            JOIN games g ON g.id = h.game_id
            WHERE h.game_id = ?
            ORDER BY CASE WHEN g.sort_ascending = 'TRUE' THEN h.score ELSE -h.score END ASC;
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
            return {"success": False, "error": f"GameID '{arcadescore_game_id}' not found for room ID {room_id}", "room_id": room_id}

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
        }, room=f"room_{room_id}")

        return {"success": True, "message": f"Processed {len(new_scores)} new scores", "room_id": room_id}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_log_score: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}", "room_id": data.get("roomID") if isinstance(data, dict) else None}

def webhook_player(conn, data, vpin_player_id=None):
    try:
        print(f"vpin_player_id: {vpin_player_id}")
        print(f"New/Update player data received: {data}")

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]
        cursor = conn.cursor()

        webhook_row = _get_room_webhook(cursor, room_id)
        if not webhook_row:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}", "room_id": room_id}

        if not _verify_webhook_token(webhook_row, data):
            return {"success": False, "error": "Invalid or missing webhook token", "room_id": room_id}

        vpin_api_url = webhook_row["server_url"]

        # ✅ Determine if it's a CREATE or UPDATE operation. CREATE/UPDATE webhooks
        # pass the affected id as "id" in the body (per VPin Studio's webhook docs).
        if not vpin_player_id:
            vpin_player_id = data.get("id")

        if not vpin_player_id:
            return {"success": False, "error": "Missing required parameter: id", "room_id": room_id}

        # ✅ If updating, resolve `arcadescore_player_id` from `vpin_players` table
        arcadescore_player_id = None
        cursor.execute("""
            SELECT arcadescore_player_id FROM vpin_players
            WHERE vpin_player_id = ? AND server_url = ?
        """, (vpin_player_id, vpin_api_url))
        arcadescore_player_id_data = cursor.fetchone()

        if arcadescore_player_id_data:
            arcadescore_player_id = arcadescore_player_id_data["arcadescore_player_id"]

        # ✅ Fetch full player details from VPin API
        player_api_url = vpin_url(vpin_api_url, f"api/v1/players/{vpin_player_id}")
        try:
            response = requests.get(player_api_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"🌐 Request Exception: {traceback.format_exc()}")
            sys.stdout.flush()
            return {"success": False, "error": f"Error fetching player details: {str(e)}", "room_id": room_id}

        player_details = response.json()

        # ✅ Prepare player data. VPin Studio's player object (confirmed live against
        # /api/v1/players/{id}) uses "name" and a single "initials" string — there is
        # no "fullName"/"alias"/"aliases" field. integrations.js's player-linking flow
        # already treats initials the same way: as this player's one alias.
        vpin_initials = player_details.get("initials")
        player_data = {
            "full_name": player_details.get("name", "Unknown Player"),
            "default_alias": vpin_initials,
            "aliases": [vpin_initials] if vpin_initials else [],
            "long_names_enabled": "FALSE",
        }

        # ✅ Handle CREATE or UPDATE logic
        if arcadescore_player_id:
            success, message = update_player_in_db(conn, arcadescore_player_id, player_data)
            if success:
                return {
                    "success": True,
                    "message": "Player updated successfully",
                    "player_id": arcadescore_player_id,
                    "room_id": room_id,
                }
            else:
                return {"success": False, "error": message, "room_id": room_id}
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
                    "player_id": new_player_id,
                    "room_id": room_id,
                }
            else:
                return {"success": False, "error": message, "room_id": room_id}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_player: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}", "room_id": data.get("roomID") if isinstance(data, dict) else None}

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
        cursor = conn.cursor()

        webhook_row = _get_room_webhook(cursor, room_id)
        if not webhook_row:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}", "room_id": room_id}

        if not _verify_webhook_token(webhook_row, data):
            return {"success": False, "error": "Invalid or missing webhook token", "room_id": room_id}

        vpin_api_url = webhook_row["server_url"]

        # ✅ Determine if it's a CREATE or UPDATE operation. CREATE/UPDATE webhooks
        # pass the affected id as "id" in the body (per VPin Studio's webhook docs).
        if not vpin_game_id:
            vpin_game_id = data.get("id")

        if not vpin_game_id:
            return {"success": False, "error": "Missing required parameter: id", "room_id": room_id}

        # ✅ If updating, resolve `arcadescore_game_id` from `vpin_games`
        arcadescore_game_id = None
        cursor.execute("""
            SELECT arcadescore_game_id FROM vpin_games
            WHERE vpin_game_id = ? AND server_url = ?;
        """, (vpin_game_id, vpin_api_url))
        arcadescore_game_id_data = cursor.fetchone()

        if arcadescore_game_id_data:
            arcadescore_game_id = arcadescore_game_id_data["arcadescore_game_id"]

        # Preserve the game's existing color and styling on update -
        # save_game_to_db writes whatever is passed here unconditionally, so a
        # plain metadata-only UPDATE webhook (e.g. a name change) would otherwise
        # blank out styling the admin already set. A brand new game has nothing
        # to preserve, so it falls back to the room's default preset instead
        # (BUG: "Selected Style Preset is not remembered when new games are
        # added via webhooks" - the wizard and Integrations Menu imports already
        # resolve this preset via import_vpin_game_into_room; this was the one
        # game-creation path that never did).
        existing_game_color = None
        css_style = {"css_score_cards": None, "css_initials": None, "css_scores": None, "css_box": None, "css_title": None}
        if arcadescore_game_id:
            cursor.execute("""
                SELECT game_color, css_score_cards, css_initials, css_scores, css_box, css_title
                FROM games WHERE id = ?
            """, (arcadescore_game_id,))
            existing_row = cursor.fetchone()
            if existing_row:
                existing_game_color = existing_row["game_color"]
                css_style = {
                    "css_score_cards": existing_row["css_score_cards"],
                    "css_initials": existing_row["css_initials"],
                    "css_scores": existing_row["css_scores"],
                    "css_box": existing_row["css_box"],
                    "css_title": existing_row["css_title"],
                }
        else:
            cursor.execute("SELECT default_preset FROM settings WHERE id = ?", (room_id,))
            settings_row = cursor.fetchone()
            default_preset_id = settings_row["default_preset"] if settings_row else 1
            cursor.execute("""
                SELECT css_score_cards, css_initials, css_scores, css_box, css_title
                FROM presets WHERE id = ?
            """, (default_preset_id,))
            preset_row = cursor.fetchone()
            if preset_row:
                css_style = dict(preset_row)

        # ✅ Fetch full game details from VPin API
        game_api_url = vpin_url(vpin_api_url, f"api/v1/games/{vpin_game_id}")

        try:
            response = requests.get(game_api_url, timeout=10)
            response.raise_for_status()  # Raises an exception for HTTP errors
        except requests.RequestException as e:
            print(f"🌐 Request Exception: {traceback.format_exc()}")
            sys.stdout.flush()
            return {"success": False, "error": f"Error fetching game details: {str(e)}", "room_id": room_id}

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
            "css_score_cards": css_style["css_score_cards"],
            "css_initials": css_style["css_initials"],
            "css_scores": css_style["css_scores"],
            "css_box": css_style["css_box"],
            "css_title": css_style["css_title"],
            "score_type": "hideBoth",
            "sort_ascending": "FALSE",
            "game_image": game_image,
            "game_background": game_background,
            "tags": vpin_spreadsheet_url,
            "hidden": "FALSE",
            "game_color": existing_game_color if arcadescore_game_id else generate_random_color(),
            "room_id": room_id,
        }

        # ✅ Call save function
        success, message, saved_game_id = save_game_to_db(conn, game_data, arcadescore_game_id)

        if success:
            return {
                "success": True,
                "message": f"Game {'updated' if arcadescore_game_id else 'created'} successfully",
                "game_id": saved_game_id,
                "room_id": room_id,
            }
        else:
            return {"success": False, "error": message, "room_id": room_id}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_game: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}", "room_id": data.get("roomID") if isinstance(data, dict) else None}

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

def webhook_pause_state(conn, data, paused):
    """
    Handles the pause/unpause webhook. This is purely a "someone is playing this
    table right now" notification from the cabinet's pause menu — it never causes
    ArcadeScore to pause anything, and nothing is ever sent back to VPin Studio.
    Just re-broadcasts the state to the scoreboard so it can highlight the card.
    """
    try:
        event_name = "pause" if paused else "unpause"
        print(f"{'⏸️' if paused else '▶️'} {event_name} webhook data received: {data}")
        sys.stdout.flush()

        if "roomID" not in data:
            return {"success": False, "error": "Missing required parameter: roomID"}

        room_id = data["roomID"]
        cursor = conn.cursor()

        webhook_row = _get_room_webhook(cursor, room_id)
        if not webhook_row:
            return {"success": False, "error": f"No VPin API URL found for room {room_id}", "room_id": room_id}

        if not _verify_webhook_token(webhook_row, data):
            return {"success": False, "error": "Invalid or missing webhook token", "room_id": room_id}

        vpin_api_url = webhook_row["server_url"]
        vpin_game_id = data.get("id")

        if not vpin_game_id:
            return {"success": False, "error": "Missing required parameter: id", "room_id": room_id}

        cursor.execute("""
            SELECT arcadescore_game_id FROM vpin_games
            WHERE vpin_game_id = ? AND server_url = ?;
        """, (vpin_game_id, vpin_api_url))
        mapping = cursor.fetchone()

        if not mapping:
            return {"success": False, "error": f"No matching ArcadeScore game found for VPin Game ID {vpin_game_id}", "room_id": room_id}

        arcadescore_game_id = mapping["arcadescore_game_id"]

        emit_message("game_pause_state", {
            "gameID": arcadescore_game_id,
            "roomID": room_id,
            "paused": paused,
        }, room=f"room_{room_id}")

        return {
            "success": True,
            "message": f"Game {arcadescore_game_id} marked as {'paused' if paused else 'unpaused'}",
            "room_id": room_id,
        }

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"❌ Exception in webhook_pause_state: {error_message}")
        sys.stdout.flush()
        return {"success": False, "error": f"Internal Server Error: {str(e)}", "room_id": data.get("roomID") if isinstance(data, dict) else None}
