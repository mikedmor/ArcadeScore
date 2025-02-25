import os
import sys

os.environ["EVENTLET_NO_GREENDNS"] = "yes"  # Disable Eventlet's DNS monkey patching
import eventlet
eventlet.monkey_patch()

import traceback
import eventlet
from app.modules.database import get_db, close_db
from app.modules.socketio import emit_progress
from app.modules.vpspreadsheet import generate_vpspreadsheet_url, fetch_vpspreadsheet_media
from app.modules.utils import generate_random_color, sanitize_slug, validate_scoreboard_name
from app.modules.vpinstudio import fetch_game_images, fetch_historical_scores
from app.modules.webhooks import register_vpin_webhook
from app.modules.games import save_game_to_db
from app.modules.players import add_player_to_db, link_vpin_player
from app.modules.scores import log_score_to_db

def process_scoreboard_task(app, data):
    """Background task to create a scoreboard without causing a timeout."""
    print("process_scoreboard_task started.")
    with app.app_context():
        try:
            print("working with app.app_context()")
            
            emit_progress(app, 0, "Starting import task"); 
            eventlet.sleep(0)
            
            print("About to run through game loop!")

            scoreboard_name = data.get("scoreboard_name")  # room_name

            # Integrations
            integrations = data.get("integrations", {})
            image_compression_level = data.get("imageCompressionLevel", "original")

            # VPin Studio
            vpin = integrations.get("vpin", {})
            vpin_api_enabled = vpin.get("api_enabled", "FALSE")
            vpin_api_url = (vpin.get("api_url") or "").strip()
            vpin_sync_historical_scores = vpin.get("sync_historical_scores", "FALSE")
            vpin_retrieve_media = vpin.get("retrieve_media", "FALSE")
            media_priority = vpin.get("media_source_priority", "fallback")
            # vpin_system_remote = vpin.get("system_remote", "FALSE")
            vpin_games = vpin.get("games", [])
            vpin_players = vpin.get("players", []) 

            # Preset Theme
            preset_id = data.get("preset_id", 1)

            # Extract Webhook Settings
            webhooks = data.get("webhooks", {})
            any_webhook_selected = any(
                webhooks.get("highscores", {}).values() or
                webhooks.get("games", {}).values() or
                webhooks.get("players", {}).values()
            )
            
            print(f"Data received: {data}")

            error_message = validate_scoreboard_name(scoreboard_name)
            if error_message:
                emit_progress(app, -1, error_message)
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
                emit_progress(app, -1, f"Error: Scoreboard name already exists!")
                print("❌ Error: Scoreboard name already exists!")
                eventlet.sleep(0)
                close_db()
                return

            # Retrieve preset details
            cursor.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
            preset = cursor.fetchone()

            if not preset:
                emit_progress(app, -1, f"Error: Invalid preset selected!")
                print("❌ Error: Invalid preset selected!")
                eventlet.sleep(0)
                close_db()
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

            # Insert new scoreboard into settings table
            cursor.execute(
                """
                INSERT INTO settings (user, room_name, vpin_api_enabled, vpin_api_url, css_body, css_card)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_slug, scoreboard_name, vpin_api_enabled, vpin_api_url, css_body, css_card),
            )
            
            # Capture the room_id for linking games
            room_id = cursor.lastrowid

            # Handle VPin Players
            for vpin_player in vpin_players:
                print(f"Processing VPin player: {vpin_player}")
                player_data = {
                    "full_name": vpin_player.get("full_name"),
                    "default_alias": vpin_player.get("default_alias"),
                    "aliases": vpin_player.get("aliases", []),
                    "long_names_enabled": "FALSE"
                }
                success, message, player_id = add_player_to_db(conn, player_data)
                if success:
                    link_vpin_player(conn, player_id, vpin_api_url, vpin_player.get("vpin_player_id"))
                else:
                    print(f"⚠️ Skipping player {player_data['full_name']}: {message}")

            print("Processing games...")

            # Insert selected games into the games table
            total_games = len(vpin_games)

            for index, game in enumerate(vpin_games):
                progress = int(((index + 1) / total_games) * 98)
                game_name = game["name"]
                if progress >= 100:
                    progress = 99

                print("emit_progress: " + str(progress) + ", for game " + game_name)
                emit_progress(app, progress, f"Processing: {game_name}") 
                eventlet.sleep(0)

                # Generate VPin spreadsheet link
                ext_table_id = game.get("extTableId", None)
                ext_table_version_id = game.get("extTableVersionId", None)
                vpin_spreadsheet_url = generate_vpspreadsheet_url(
                    ext_table_id, 
                    ext_table_version_id
                )

                # Fetch game media & store locally
                game_image, game_background = ("", "")
                if vpin_retrieve_media and vpin_api_enabled:
                    emit_progress(app, progress, f"Downloading Media: {game_name}")
                    eventlet.sleep(0)

                    def fetch_media_from_source(source):
                        print(f"Fetching from {source}")
                        if source == "vpin_studio":
                            return fetch_game_images(vpin_api_url, game["id"], image_compression_level)
                        
                        elif source == "vp_spreadsheet":
                            # Use extTableId and extTableVersionId from the game data
                            if not ext_table_id or not ext_table_version_id:
                                print(f"Missing extTableId or extTableVersionId for game: {game['name']}")
                                return {"backglass": "", "playfield": ""}

                            # Fetch images from VPS Spreadsheet
                            vps_media = fetch_vpspreadsheet_media(
                                ext_table_id, ext_table_version_id, compression_level=image_compression_level
                            )

                            return {
                                "backglass": vps_media.get("backglass", ""),
                                "playfield": vps_media.get("playfield", "")
                            }
                        return {"backglass": "", "playfield": ""}
                    
                    print(f"media_priority is {media_priority}")
                    preferred_media = fetch_media_from_source("vp_spreadsheet" if media_priority == "preferred" else "vpin_studio")
                    game_image = preferred_media.get("backglass", "")
                    game_background = preferred_media.get("playfield", "")

                    # Fallback only if media is missing
                    if not game_image or not game_background:
                        print("Triggering fallback to VPS Spreadsheet...")
                        fallback_source = "vpin_studio" if media_priority == "preferred" else "vp_spreadsheet"
                        fallback_media = fetch_media_from_source(fallback_source)

                        # Only replace missing media
                        game_image = game_image or fallback_media.get("backglass", "")
                        game_background = game_background or fallback_media.get("playfield", "")

                    # Final fallback to empty strings if everything fails
                    if game_image:
                        print(f"Final game image path: {game_image}")
                    else:
                        print("No game image found after fallback.")

                    if game_background:
                        print(f"Final game background path: {game_background}")
                    else:
                        print("No game background found after fallback.")

                    game_image = game_image or ""
                    game_background = game_background or ""

                emit_progress(app, progress, f"Saving: {game_name}")
                eventlet.sleep(0)

                game_data = {
                    "game_name": game_name,
                    "css_score_cards": css_score_cards,
                    "css_initials": css_initials,
                    "css_scores": css_scores,
                    "css_box": css_box,
                    "css_title": css_title,
                    "score_type": "hideBoth",
                    "sort_ascending": "FALSE",
                    "game_image": game_image,
                    "game_background": game_background,
                    "tags": vpin_spreadsheet_url,
                    "hidden": "FALSE",
                    "game_color": generate_random_color(),
                    "room_id": room_id,
                }

                # Save the game to the database
                success, message, game_id = save_game_to_db(conn, game_data)
                if not success:
                    emit_progress(app, -1, f"Error saving game: {message}")

                cursor.execute("""
                    INSERT INTO vpin_games (server_url, arcadescore_game_id, vpin_game_id)
                    VALUES (?, ?, ?)
                """, (vpin_api_url, game_id, game["id"]))

                # Sync Historical Scores
                if vpin_sync_historical_scores and vpin_api_enabled:
                    emit_progress(app, progress, f"Fetching Scores: {game_name}")
                    eventlet.sleep(0)

                    retrieved_scores = fetch_historical_scores(vpin_api_url, game["id"], vpin_players, game_id)

                    if retrieved_scores:
                        for score in retrieved_scores:
                            log_score_to_db(conn, score)

                        print(f"Added {len(retrieved_scores)} scores for game {game_name}.")
                    else:
                        print(f"No scores found for game {game_name} or an error occurred.")

            # Commit all changes
            conn.commit()
            close_db()

            register = False
            # Register Webhook if any event is selected
            if vpin_api_enabled and vpin_api_url and any_webhook_selected:
                emit_progress(app, 98, "Registering VPin Studio Webhook...")
                eventlet.sleep(0)

                webhook_result = register_vpin_webhook(vpin_api_url, room_id, scoreboard_name, webhooks)
                if webhook_result["success"]:
                    emit_progress(app, 99, "Webhook registered successfully!")
                    register = True
                else:
                    emit_progress(app, -1, f"Webhook registration failed: {webhook_result['message']}")
                eventlet.sleep(0)

            # Notify completion
            response = "Scoreboard creation complete!"
            if vpin_api_enabled and vpin_api_url and any_webhook_selected:
                if not register:
                    response += " But there was a problem registering the webhook"
            emit_progress(app, 100, response)
            eventlet.sleep(0)

            sys.stdout.flush()
            return

        except Exception as e:
            close_db()
            emit_progress(app, -1, f"Uncaught Exception in process_scoreboard_task: {str(e)}")
            print(f"❌ Uncaught Exception in process_scoreboard_task: {str(e)}")
            traceback.print_exc()
