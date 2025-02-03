from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.database import get_db
import requests
import os

styles_bp = Blueprint('styles', __name__)

@styles_bp.route("/api/v1/style/global", methods=["GET"])
def get_global_style():
    """Fetch global styles from settings"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT css_body, css_card FROM settings LIMIT 1;")
        settings = cursor.fetchone()

        if not settings:
            return jsonify({"css_body": "", "css_card": ""})  # Default values if no settings exist

        return jsonify({"css_body": settings["css_body"], "css_card": settings["css_card"]})

    except Exception as e:
        print(f"Error fetching global styles: {e}")
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/style/presets", methods=["GET"])
def get_presets():
    """Fetch all saved presets."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM presets")
    presets = cursor.fetchall()
    conn.close()
    return jsonify([{"id": p["id"], "name": p["name"]} for p in presets])

@styles_bp.route("/api/v1/style/save-preset", methods=["POST"])
def save_preset():
    """Save or overwrite a game style preset."""
    data = request.get_json()
    game_id = data.get("gameID")
    preset_name = data.get("presetName")
    overwrite = data.get("overwrite", False)

    if not game_id or not preset_name:
        return jsonify({"error": "Missing gameID or presetName"}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Check if the preset already exists
    cursor.execute("SELECT id FROM presets WHERE name = ?", (preset_name,))
    existing_preset = cursor.fetchone()

    if existing_preset and overwrite:
        # If preset exists and overwrite is true, update it
        cursor.execute("""
            UPDATE presets
            SET css_body = (SELECT css_body FROM settings),
                css_card = (SELECT css_card FROM settings),
                css_score_cards = (SELECT css_score_cards FROM games WHERE id = ?),
                css_initials = (SELECT css_initials FROM games WHERE id = ?),
                css_scores = (SELECT css_scores FROM games WHERE id = ?),
                css_box = (SELECT css_box FROM games WHERE id = ?),
                css_title = (SELECT css_title FROM games WHERE id = ?)
            WHERE id = ?;
        """, (game_id, game_id, game_id, game_id, game_id, existing_preset["id"]))

        message = "Preset updated successfully!"
    else:
        # Insert a new preset
        cursor.execute("""
            INSERT INTO presets (name, css_body, css_card, css_score_cards, css_initials, css_scores, css_box, css_title)
            SELECT ?, settings.css_body, settings.css_card, g.css_score_cards, g.css_initials, g.css_scores, g.css_box, g.css_title
            FROM games g, settings
            WHERE g.id = ?;
        """, (preset_name, game_id))

        message = "Preset saved successfully!"

    conn.commit()
    conn.close()
    
    return jsonify({"message": message}), 200

@styles_bp.route("/api/v1/style/apply-to-all", methods=["POST"])
def apply_preset_to_all_games():
    """Apply a preset's styles to all games"""
    data = request.get_json()
    preset_id = data.get("presetID")

    if not preset_id:
        return jsonify({"error": "Preset ID is required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch the preset styles
        cursor.execute("""
            SELECT css_score_cards, css_initials, css_scores, css_box, css_title 
            FROM presets WHERE id = ?
        """, (preset_id,))
        preset_styles = cursor.fetchone()

        if not preset_styles:
            return jsonify({"error": "Preset not found"}), 404

        # Apply the preset styles to all games
        cursor.execute("""
            UPDATE games 
            SET css_score_cards = ?, css_initials = ?, css_scores = ?, css_box = ?, css_title = ?
        """, preset_styles)

        conn.commit()
        conn.close()
        return jsonify({"message": "Preset applied to all games!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/style/apply-global", methods=["POST"])
def apply_preset_to_global():
    """Apply a preset's global styles to settings"""
    data = request.get_json()
    preset_id = data.get("presetID")

    if not preset_id:
        return jsonify({"error": "Preset ID is required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch the preset global styles
        cursor.execute("""
            SELECT css_body, css_card 
            FROM presets WHERE id = ?
        """, (preset_id,))
        preset_styles = cursor.fetchone()

        if not preset_styles:
            return jsonify({"error": "Preset not found"}), 404

        # Apply the preset styles to global settings
        cursor.execute("""
            UPDATE settings 
            SET css_body = ?, css_card = ?
        """, preset_styles)

        conn.commit()
        conn.close()
        return jsonify({"message": "Preset applied to global styles!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/style/apply-both", methods=["POST"])
def apply_preset_to_all_and_global():
    """Apply a preset's styles to both all games and global settings"""
    data = request.get_json()
    preset_id = data.get("presetID")

    if not preset_id:
        return jsonify({"error": "Preset ID is required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch both global and game styles from the preset
        cursor.execute("""
            SELECT css_body, css_card, css_score_cards, css_initials, css_scores, css_box, css_title 
            FROM presets WHERE id = ?
        """, (preset_id,))
        preset_styles = cursor.fetchone()

        if not preset_styles:
            return jsonify({"error": "Preset not found"}), 404

        # Apply global styles
        cursor.execute("""
            UPDATE settings 
            SET css_body = ?, css_card = ?
        """, (preset_styles["css_body"], preset_styles["css_card"]))

        # Apply styles to all games
        cursor.execute("""
            UPDATE games 
            SET css_score_cards = ?, css_initials = ?, css_scores = ?, css_box = ?, css_title = ?
        """, (preset_styles["css_score_cards"], preset_styles["css_initials"], preset_styles["css_scores"], preset_styles["css_box"], preset_styles["css_title"]))

        conn.commit()
        conn.close()
        return jsonify({"message": "Preset applied to both global styles and all games!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@styles_bp.route("/api/v1/update-game-order", methods=["POST"])
def update_game_order():
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()

        for game in data:
            cursor.execute("""
                UPDATE games SET game_sort = ? WHERE id = ?;
            """, (game["game_sort"], game["game_id"]))

        conn.commit()
        conn.close()
        return jsonify({"message": "Game order updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@styles_bp.route("/api/v1/store-image", methods=["POST"])
def store_image():
    data = request.get_json()
    image_url = data.get("url")
    image_type = data.get("type")  # "gameImage" or "gameBackground"

    if not image_url or not image_type:
        return jsonify({"error": "Missing image URL or type"}), 400

    # Skip fetching if already local
    if image_url.startswith("/static/images/"):
        return jsonify({"localPath": image_url}), 200

    try:
        response = requests.get(image_url, stream=True)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch image from URL: {image_url}")

        filename = secure_filename(image_url.split("/")[-1])
        file_path = os.path.join("app/static/images", image_type, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        # Return only the filename to store in the database
        return jsonify({"localPath": filename}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/upload-image", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    image_type = request.form.get("type")  # "gameImage" or "gameBackground"

    if not file or not image_type:
        return jsonify({"error": "Invalid request"}), 400

    # Save the file locally
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join("app/static/images", image_type, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)

        local_path = f"/static/images/{image_type}/{filename}"
        return jsonify({"localPath": local_path}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/style/apply-preset", methods=["POST"])
def apply_preset():
    data = request.get_json()
    game_id = data.get("gameID")
    preset = data.get("preset")

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch the preset CSS styles
        cursor.execute("SELECT css_score_cards, css_initials, css_scores, css_box, css_title FROM presets WHERE name = ?", (preset,))
        preset_styles = cursor.fetchone()
        if not preset_styles:
            return jsonify({"error": "Preset not found"}), 404

        # Apply to selected game
        cursor.execute("""
            UPDATE games SET css_score_cards = ?, css_initials = ?, css_scores = ?, css_box = ?, css_title = ? WHERE id = ?
        """, (*preset_styles, game_id))

        conn.commit()
        conn.close()
        return jsonify({"message": "Preset applied!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/style/save-global", methods=["POST"])
def save_global_style():
    data = request.get_json()
    css_body = data.get("cssBody")
    css_card = data.get("cssCard")

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE settings SET css_body = ?, css_card = ? WHERE user = ?
        """, (css_body, css_card, "mikedmor"))

        conn.commit()
        conn.close()
        return jsonify({"message": "Global style saved!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@styles_bp.route("/api/v1/style/copy-to-all", methods=["POST"])
def copy_style_to_all():
    data = request.get_json()
    game_id = data.get("gameID")

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get the style from the selected game
        cursor.execute("""
            SELECT css_score_cards, css_initials, css_scores, css_box, css_title 
            FROM games WHERE id = ?
        """, (game_id,))
        game_style = cursor.fetchone()
        if not game_style:
            return jsonify({"error": "Game not found"}), 404

        # Apply this style to all games
        cursor.execute("""
            UPDATE games 
            SET css_score_cards = ?, css_initials = ?, css_scores = ?, css_box = ?, css_title = ?
        """, game_style)

        conn.commit()
        conn.close()
        return jsonify({"message": "Style copied to all games!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
