from flask import Blueprint, jsonify, render_template
from app.modules.database import get_db, close_db
from app.modules.utils import format_timestamp

users_bp = Blueprint('users', __name__)

@users_bp.route("/<username>", methods=["GET"])
def user_scoreboard(username):
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch settings for the user
        cursor.execute("""
        SELECT id, secure, dateformat, css_body, css_card, default_preset,
               room_name,
               horizontal_scroll_enabled, horizontal_scroll_speed, horizontal_scroll_delay,
               vertical_scroll_enabled, vertical_scroll_speed, vertical_scroll_delay,
               fullscreen_enabled, text_autofit_enabled, long_names_enabled, public_scores_enabled, 
               public_score_entry_enabled, api_read_access, api_write_access, vpin_api_enabled, vpin_api_url
        FROM settings WHERE user = ?;
        """, (username,))
        settings = cursor.fetchone()
        if not settings:
            return jsonify({"error": "Room not found for user"}), 404

        # Extract settings values
        room_id = settings[0]
        secure_password = settings[1] if settings[1] else None
        dateformat = settings[2] 
        css_body = settings[3] or ""
        css_card_template = settings[4] or ""
        default_preset = settings[5]
        # global_long_names = settings[16] == "TRUE"

        # Convert settings into a dictionary for easy access in the template
        settings_dict = {
            "room_name": settings[6],
            "date_format": dateformat,
            "horizontal_scroll_enabled": settings[7] or "FALSE",
            "horizontal_scroll_speed": settings[8] or 3,
            "horizontal_scroll_delay": settings[9] or 2000,
            "vertical_scroll_enabled": settings[10] or "FALSE",
            "vertical_scroll_speed": settings[11] or 3,
            "vertical_scroll_delay": settings[12] or 2000,
            "fullscreen_enabled": settings[13] or "FALSE",
            "text_autofit_enabled": settings[14] or "FALSE",
            "long_names_enabled": settings[15] or "FALSE",
            "public_scores_enabled": settings[16] or "FALSE",
            "public_score_entry_enabled": settings[17] or "FALSE",
            "api_read_access": settings[18] or "FALSE",
            "api_write_access": settings[19] or "FALSE",
            "vpin_api_enabled": settings[20] or "FALSE",
            "vpin_api_url": settings[21] or "",
        }

        # Fetch games for the user
        cursor.execute("""
            SELECT g.id, g.game_name, g.css_score_cards, g.css_initials, g.css_scores, g.css_box, g.css_title, 
                g.score_type, g.sort_ascending, g.game_color, g.game_image, g.game_background,
                g.tags, g.hidden, g.game_sort
            FROM games g
            WHERE g.room_id = ?
            ORDER BY g.game_sort ASC;
        """, (room_id,))
        games = cursor.fetchall()

        # Fetch presets for styles
        cursor.execute("SELECT id, name FROM presets")
        presets = cursor.fetchall()

        # Fetch scores for the user's room
        cursor.execute("""
            SELECT DISTINCT h.game_id, 
                CASE 
                    WHEN s.long_names_enabled = 'TRUE' OR p.long_names_enabled = 'TRUE' THEN p.full_name 
                    ELSE p.default_alias 
                END AS display_name,
                p.full_name,
                p.default_alias,
                h.score, h.event, h.wins, h.losses, h.timestamp, p.hidden, p.id
            FROM highscores h
            JOIN players p ON h.player_id = p.id
            JOIN settings s ON s.id = h.room_id
            WHERE h.room_id = ?
            ORDER BY h.game_id, h.score DESC;
        """, (room_id,))

        # Fetch all rows as dictionary-like objects
        scores = [dict(row) for row in cursor.fetchall()]

        # Fetch players
        cursor.execute("""
            SELECT p.id, p.full_name, p.icon, p.default_alias, p.long_names_enabled, p.hidden
            FROM players p;
        """)
        players = cursor.fetchall()

        # Fetch player aliases
        cursor.execute("""
            SELECT player_id, alias FROM aliases WHERE player_id IN (SELECT id FROM players);
        """)
        alias_data = cursor.fetchall()
        alias_map = {}
        for player_id, alias in alias_data:
            alias_map.setdefault(player_id, []).append(alias)

        # Process player list
        players_list = []
        for player in players:
            players_list.append({
                "id": player[0],
                "full_name": player[1],
                "icon": player[2] or "/static/images/avatars/default-avatar.png",
                "default_alias": player[3],
                "long_names_enabled": player[4],
                "aliases": alias_map.get(player[0], []),
                "hidden": player[5]
            })

        close_db()

        # Group scores by game_id
        score_map = {}
        for score in scores:
            game_id = score["game_id"]
            if game_id not in score_map:
                score_map[game_id] = []
            score_map[game_id].append({
                "display_name": score["display_name"],
                "full_name": score["full_name"],
                "default_alias": score['default_alias'],
                "score": score["score"],
                "event": score["event"] or "N/A",
                "wins": score["wins"] or 0,
                "losses": score["losses"] or 0,
                "timestamp": score["timestamp"],
                "formatted_timestamp": format_timestamp(score["timestamp"], dateformat),
                "player_id": score["id"]  # Fix indexing issue
            })

        games_list = []
        for game in games:
            game_id = game[0]

            # Dynamically replace placeholders in CSS Card Style
            css_card = css_card_template.replace("{GameBackground}", game[11] or "") \
                                        .replace("{GameColor}", game[9] or "#FFFFFF") \
                                        .replace("{GameImage}", game[10] or "")
            
            games_list.append({
                "game_id": game_id,
                "game_name": game[1],
                "css_score_cards": game[2] or "",
                "css_initials": game[3] or "",
                "css_scores": game[4] or "",
                "css_box": game[5] or "",
                "css_title": game[6] or "",
                "score_type": game[7] or "",
                "game_sort": game[14],
                "sort_ascending": game[8] or "FALSE",
                "game_color": game[9] or "#FFFFFF",
                "game_image": game[10] or "",
                "game_background": game[11] or "",
                "tags": game[12] or "",
                "hidden": game[13] or "FALSE",
                "scores": score_map.get(game_id, []),
                "css_card": css_card
            })

        # Pass `settings_dict` and players to the template
        return render_template(
            "scoreboard.jinja",
            user=username,
            roomID=room_id,
            games=games_list,
            secure_password=secure_password,
            css_body=css_body,
            presets=presets,
            default_preset=default_preset,
            settings=settings_dict,
            players=players_list
        )

    except Exception as e:
        close_db()
        return jsonify({"error": "Failed to load user scoreboard", "details": str(e)}), 500

@users_bp.route("/api/<user>", methods=["GET"])
def api_read_games(user):
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch settings for the user
        cursor.execute("""
            SELECT id, dateformat FROM settings WHERE user = ?;
        """, (user,))
        settings = cursor.fetchone()
        if not settings:
            return jsonify({"error": "Room not found for user"}), 404

        room_id, dateformat = settings

        # Fetch games for the user's room
        cursor.execute("""
            SELECT g.id, g.game_name, g.css_score_cards, g.css_initials, g.css_scores, g.css_box, g.css_title, 
                g.score_type, g.sort_ascending, g.game_image, g.game_background, 
                g.tags, g.hidden, g.game_color, g.game_sort
            FROM games g
            WHERE g.room_id = ?
            ORDER BY g.game_sort ASC;
        """, (room_id,))
        games = cursor.fetchall()

        # Fetch scores for the user's room
        cursor.execute("""
            SELECT DISTINCT h.game_id, 
                CASE 
                    WHEN s.long_names_enabled = 'TRUE' OR p.long_names_enabled = 'TRUE' THEN p.full_name 
                    ELSE p.default_alias 
                END AS player_name,
                h.score, h.event, h.wins, h.losses, h.timestamp
            FROM highscores h
            JOIN players p ON h.player_id = p.id
            JOIN settings s ON s.id = h.room_id
            WHERE h.room_id = ?
            ORDER BY h.game_id, h.score DESC;
        """, (room_id,))
        scores = cursor.fetchall()

        close_db()

        # Group scores by game_id
        score_map = {}
        for score in scores:
            game_id = score[0]
            if game_id not in score_map:
                score_map[game_id] = []
            score_map[game_id].append({
                "player_name": score[1],
                "score": score[2],
                "event": score[3] or "N/A",
                "wins": score[4] or 0,
                "losses": score[5] or 0,
                "timestamp": score[6],
                "dateFormat": dateformat
            })

        # Construct the game list
        games_list = []
        for game in games:
            game_id = game[0]
            games_list.append({
                "gameID": game_id,
                "gameName": game[1],
                "CSSScoreCards": game[2] or "",
                "CSSInitials": game[3] or "",
                "CSSScores": game[4] or "",
                "CSSBox": game[5] or "",
                "CSSTitle": game[6] or "",
                "ScoreType": game[7] or "",
                "GameSort": game[14],
                "SortAscending": game[8] or "",
                "GameImage": game[9] or "",
                "GameBackground": game[10] or "",
                "tags": game[11].split(",") if game[11] else [],
                "Hidden": game[12] or "false",
                "GameColor": game[13] or "#FFFFFF",
                "scores": score_map.get(game_id, [])  # Attach scores or empty list
            })

        # Return the games and their scores as JSON
        return jsonify(games_list)

    except Exception as e:
        close_db()
        print(f"Error fetching games: {e}")
        return jsonify({"error": str(e)}), 500
