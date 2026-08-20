import os
import sys

os.environ["EVENTLET_NO_GREENDNS"] = "yes"  # Disable Eventlet's DNS monkey patching
import eventlet
eventlet.monkey_patch()

import traceback
import eventlet
from app.modules.database import get_db
from app.modules.socketio import emit_progress
from app.modules.utils import sanitize_slug, validate_scoreboard_name, normalize_vpin_url
from app.modules.webhooks import register_vpin_webhook
from app.modules.vpin_integration import import_vpin_game_into_room

def process_scoreboard_task(app, data):
    """Background task to create a scoreboard without causing a timeout."""
    print("process_scoreboard_task started.")
    with app.app_context():
        # session_id (if the client sent one) lets its own progress modal tell
        # itself apart from a different tab's - see docs/Roadmap.md BUG-22.
        session_id = data.get("session_id")

        def progress(pct, msg):
            emit_progress(app, pct, msg, session_id)

        try:
            print("working with app.app_context()")

            progress(0, "Starting import task")
            eventlet.sleep(0)

            print("About to run through game loop!")

            scoreboard_name = data.get("scoreboard_name")  # room_name

            # Integrations
            integrations = data.get("integrations", {})
            image_compression_level = data.get("imageCompressionLevel", "original")

            # VPin Studio
            vpin = integrations.get("vpin", {})
            vpin_api_enabled = vpin.get("api_enabled", "FALSE")
            vpin_api_url = normalize_vpin_url((vpin.get("api_url") or "").strip())
            vpin_sync_historical_scores = vpin.get("sync_historical_scores", "FALSE")
            vpin_retrieve_media = vpin.get("retrieve_media", "FALSE")
            media_priority = vpin.get("media_source_priority", "fallback")
            # vpin_system_remote = vpin.get("system_remote", "FALSE")
            vpin_games = vpin.get("games", [])

            # Preset Theme
            preset_id = data.get("preset_id", 1)

            # Extract Webhook Settings
            webhooks = vpin.get("webhooks", {})
            any_webhook_selected = any(
                webhooks.get("highscores", {}).values() or
                webhooks.get("games", {}).values() or
                webhooks.get("players", {}).values() or
                webhooks.get("pause", {}).values() or
                webhooks.get("unpause", {}).values()
            )

            print(f"Data received: {data}")

            error_message = validate_scoreboard_name(scoreboard_name)
            if error_message:
                progress(-1, error_message)
                print(f"❌ {error_message}")
                eventlet.sleep(0)
                return

            # Generate a sanitized slug for `user`
            user_slug = sanitize_slug(scoreboard_name)
            print(f"Generated user slug: {user_slug}")

            conn = get_db()
            cursor = conn.cursor()

            print("Database connection established!")

            # Ensure the slug does not already exist
            cursor.execute("SELECT id FROM settings WHERE user = ?", (user_slug,))
            if cursor.fetchone():
                progress(-1, "Error: Scoreboard name already exists!")
                print("❌ Error: Scoreboard name already exists!")
                eventlet.sleep(0)
                return

            # Retrieve preset details
            cursor.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
            preset = cursor.fetchone()

            if not preset:
                progress(-1, "Error: Invalid preset selected!")
                print("❌ Error: Invalid preset selected!")
                eventlet.sleep(0)
                return

            print("Preset retrieved successfully!")

            # Extract preset styles
            css_body = preset["css_body"]
            css_card = preset["css_card"]
            css_score_cards = preset["css_score_cards"]
            css_initials = preset["css_initials"]
            css_scores = preset["css_scores"]
            css_box = preset["css_box"]
            css_title = preset["css_title"]

            # Insert new scoreboard into settings table. default_preset is stored
            # here (not just applied to the games created below) so a game added
            # later - e.g. by a VPin Studio CREATE webhook, long after the wizard
            # ran - has a room-level style to fall back to instead of no style at
            # all (see webhook_game in app/modules/webhooks.py).
            cursor.execute(
                """
                INSERT INTO settings (user, room_name, css_body, css_card, default_preset)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_slug, scoreboard_name, css_body, css_card, preset_id),
            )

            # Capture the room_id for linking games
            room_id = cursor.lastrowid

            # Link this room to the VPin server regardless of whether any webhook was
            # selected, so the Integrations Menu can find it later even if the room
            # only ever imported games/players once (see docs/Roadmap.md VPIN-11).
            if vpin_api_enabled and vpin_api_url:
                cursor.execute("""
                    INSERT OR IGNORE INTO vpin_servers (room_id, server_url) VALUES (?, ?);
                """, (room_id, vpin_api_url))

            # Retrieve VPin Players from database (for the selected server URL)
            cursor.execute("""
                SELECT arcadescore_player_id, vpin_player_id, server_url
                FROM vpin_players
                WHERE server_url = ?;
            """, (vpin_api_url,))
            vpin_players = [
                {"arcadescore_player_id": row[0], "vpin_player_id": row[1], "server_url": row[2]}
                for row in cursor.fetchall()
            ]

            print(f"🔍 Loaded {len(vpin_players)} VPin players from DB for server: {vpin_api_url}")

            # Insert selected games into the games table
            total_games = len(vpin_games)

            css_style = {
                "css_score_cards": css_score_cards,
                "css_initials": css_initials,
                "css_scores": css_scores,
                "css_box": css_box,
                "css_title": css_title,
            }

            for index, game in enumerate(vpin_games):
                pct = int(((index + 1) / total_games) * 98)
                game_name = game["name"]
                if pct >= 100:
                    pct = 99

                print("emit_progress: " + str(pct) + ", for game " + game_name)
                progress(pct, f"Processing: {game_name}")
                eventlet.sleep(0)

                if vpin_retrieve_media and vpin_api_enabled:
                    progress(pct, f"Downloading Media: {game_name}")
                    eventlet.sleep(0)

                progress(pct, f"Saving: {game_name}")
                eventlet.sleep(0)

                # One game failing (flaky media download, a transient DB error) must not
                # abort every game after it in the wizard's list - each import stands alone.
                try:
                    success, message, game_id = import_vpin_game_into_room(
                        conn, vpin_api_url, room_id, game,
                        css_style=css_style,
                        options={
                            "retrieve_media": bool(vpin_retrieve_media and vpin_api_enabled),
                            "media_priority": media_priority,
                            "image_compression_level": image_compression_level,
                            "sync_historical_scores": bool(vpin_sync_historical_scores and vpin_api_enabled),
                            "vpin_players": vpin_players,
                        },
                    )
                except Exception as e:
                    success, message = False, f"Unexpected error: {e}"
                    print(f"⚠️ Failed to import game {game.get('id')} ({game_name}): {e}")
                    traceback.print_exc()

                if not success:
                    progress(-1, f"Error saving game: {message}")

            # Commit all changes
            conn.commit()

            register = False
            # Register Webhook if any event is selected
            if vpin_api_enabled and vpin_api_url and any_webhook_selected:
                progress(98, "Registering VPin Studio Webhook...")
                eventlet.sleep(0)

                webhook_result = register_vpin_webhook(conn, vpin_api_url, room_id, scoreboard_name, webhooks)
                if webhook_result["success"]:
                    progress(99, "Webhook registered successfully!")
                    register = True
                else:
                    progress(-1, f"Webhook registration failed: {webhook_result['message']}")
                eventlet.sleep(0)

            # Notify completion
            response = "Scoreboard creation complete!"
            if vpin_api_enabled and vpin_api_url and any_webhook_selected:
                if not register:
                    response += " But there was a problem registering the webhook"
            progress(100, response)
            eventlet.sleep(0)


            sys.stdout.flush()
            return

        except Exception as e:
            progress(-1, f"Uncaught Exception in process_scoreboard_task: {str(e)}")
            print(f"❌ Uncaught Exception in process_scoreboard_task: {str(e)}")
            traceback.print_exc()
