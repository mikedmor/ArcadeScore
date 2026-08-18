from app.modules.vpspreadsheet import generate_vpspreadsheet_url, fetch_vpspreadsheet_media
from app.modules.vpinstudio import fetch_game_images, fetch_historical_scores
from app.modules.games import save_game_to_db
from app.modules.scores import log_score_to_db
from app.modules.utils import generate_random_color

def _fetch_media_for_game(vpin_api_url, game, image_compression_level, media_priority):
    """Fetch game media honoring the configured source priority, falling back to the
    other source if either image is missing."""
    ext_table_id = game.get("extTableId")
    ext_table_version_id = game.get("extTableVersionId")

    def fetch_from(source):
        if source == "vpin_studio":
            return fetch_game_images(vpin_api_url, game["id"], image_compression_level)
        elif source == "vp_spreadsheet":
            if not ext_table_id or not ext_table_version_id:
                print(f"Missing extTableId or extTableVersionId for game: {game.get('name')}")
                return {"backglass": "", "playfield": ""}
            vps_media = fetch_vpspreadsheet_media(ext_table_id, ext_table_version_id, compression_level=image_compression_level)
            return {"backglass": vps_media.get("backglass", ""), "playfield": vps_media.get("playfield", "")}
        return {"backglass": "", "playfield": ""}

    preferred_source = "vp_spreadsheet" if media_priority == "preferred" else "vpin_studio"
    preferred = fetch_from(preferred_source)
    game_image = preferred.get("backglass", "")
    game_background = preferred.get("playfield", "")

    if not game_image or not game_background:
        fallback_source = "vpin_studio" if media_priority == "preferred" else "vp_spreadsheet"
        print(f"Triggering fallback to {fallback_source} for game: {game.get('name')}")
        fallback = fetch_from(fallback_source)
        game_image = game_image or fallback.get("backglass", "")
        game_background = game_background or fallback.get("playfield", "")

    return game_image or "", game_background or ""

def import_vpin_game_into_room(conn, vpin_api_url, room_id, game, css_style, options):
    """
    Creates (or, if this room already has this VPin game linked, updates in place)
    one ArcadeScore game from a VPin Studio game entry: fetches media, builds the
    VP-Spreadsheet link, saves the game, links it in `vpin_games`, and optionally
    syncs historical scores. Shared by the scoreboard creation wizard
    (app/background/create_scoreboards.py) and the Integrations Menu's game
    import/resync actions (app/routes/api/v1/vpin_integrations.py), so a game
    behaves the same regardless of which of those first added it — and calling
    this again for an already-linked game safely refreshes it instead of creating
    a duplicate.

    :param game: dict with at least "id" and "name", optionally "extTableId"/"extTableVersionId"
    :param css_style: dict with css_score_cards/css_initials/css_scores/css_box/css_title
    :param options: dict with retrieve_media (bool), media_priority ("preferred"/"fallback"),
        image_compression_level (str), sync_historical_scores (bool),
        vpin_players (list, required if syncing — see fetch_historical_scores)
    :return: (success: bool, message: str, game_id: int or None)
    """
    game_name = game.get("name", "Unknown Game")
    cursor = conn.cursor()

    # If this room already has this VPin game linked, update it in place instead
    # of creating a duplicate.
    cursor.execute("""
        SELECT vg.arcadescore_game_id
        FROM vpin_games vg
        JOIN games g ON vg.arcadescore_game_id = g.id
        WHERE vg.server_url = ? AND vg.vpin_game_id = ? AND g.room_id = ?;
    """, (vpin_api_url, game["id"], room_id))
    existing = cursor.fetchone()
    existing_game_id = existing["arcadescore_game_id"] if existing else None

    existing_game_color = None
    if existing_game_id:
        cursor.execute("SELECT game_color FROM games WHERE id = ?", (existing_game_id,))
        row = cursor.fetchone()
        existing_game_color = row["game_color"] if row else None

    ext_table_id = game.get("extTableId")
    ext_table_version_id = game.get("extTableVersionId")
    vpin_spreadsheet_url = generate_vpspreadsheet_url(ext_table_id, ext_table_version_id)

    game_image, game_background = "", ""
    if options.get("retrieve_media"):
        game_image, game_background = _fetch_media_for_game(
            vpin_api_url, game,
            options.get("image_compression_level", "original"),
            options.get("media_priority", "fallback"),
        )

    game_data = {
        "game_name": game_name,
        "css_score_cards": css_style.get("css_score_cards"),
        "css_initials": css_style.get("css_initials"),
        "css_scores": css_style.get("css_scores"),
        "css_box": css_style.get("css_box"),
        "css_title": css_style.get("css_title"),
        "score_type": "hideBoth",
        "sort_ascending": "FALSE",
        "game_image": game_image,
        "game_background": game_background,
        "tags": vpin_spreadsheet_url,
        "hidden": "FALSE",
        "game_color": existing_game_color if existing_game_id else generate_random_color(),
        "room_id": room_id,
    }

    success, message, game_id = save_game_to_db(conn, game_data, existing_game_id)
    if not success:
        return False, message, None

    if not existing_game_id:
        cursor.execute("""
            INSERT INTO vpin_games (server_url, arcadescore_game_id, vpin_game_id)
            VALUES (?, ?, ?)
        """, (vpin_api_url, game_id, game["id"]))
        conn.commit()

    if options.get("sync_historical_scores"):
        vpin_players = options.get("vpin_players", [])
        retrieved_scores = fetch_historical_scores(vpin_api_url, game["id"], vpin_players, game_id, room_id)

        if retrieved_scores:
            added = 0
            for score in retrieved_scores:
                cursor.execute("""
                    SELECT COUNT(*) FROM highscores
                    WHERE game_id = ? AND player_id = ? AND score = ? AND timestamp = ? AND room_id = ?;
                """, (score["game_id"], score["player_id"], score["score"], score["timestamp"], score["room_id"]))
                if cursor.fetchone()[0] > 0:
                    continue  # Already logged - safe to call this again as a "resync"
                log_score_to_db(conn, score)
                added += 1
            print(f"✅ Added {added} new score(s) for game {game_name} (skipped {len(retrieved_scores) - added} already present).")
        else:
            print(f"No scores found for game {game_name} or an error occurred.")

    verb = "updated" if existing_game_id else "imported"
    return True, f"Game '{game_name}' {verb} successfully", game_id
