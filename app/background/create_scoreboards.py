import re
import requests
import os
import cv2
import random
import traceback
import eventlet
from flask import jsonify, current_app
from app.database import get_db
from app.modules.sockets import emit_progress
from PIL import Image
from io import BytesIO

# Define storage path for game images
GAMEIMAGE_STORAGE_PATH = "app/static/images/gameImage"
GAMEBACKGROUND_STORAGE_PATH = "app/static/images/gameBackground"
GAMEIMAGE_DB_PATH = "/static/images/gameImage"
GAMEBACKGROUND_DB_PATH = "/static/images/gameBackground"

# Ensure the directory exists
os.makedirs(GAMEIMAGE_STORAGE_PATH, exist_ok=True)
os.makedirs(GAMEBACKGROUND_STORAGE_PATH, exist_ok=True)

def generate_random_color():
    """Generate a random hex color."""
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def sanitize_slug(name):
    """Sanitize scoreboard name to create a URL-friendly slug."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)  # Remove special characters
    name = re.sub(r"\s+", "-", name)  # Replace spaces with hyphens
    return name

def save_image(image_data, filename, storage_path, db_path, max_size=(1920, 1080)):
    """Saves raw image bytes to a file, resizing large images while keeping PNG format."""
    try:
        # Ensure filename has a .png extension
        filename = filename.rsplit(".", 1)[0] + ".png"

        # Load image from raw bytes
        image = Image.open(BytesIO(image_data)).convert("RGBA")  # Ensure PNG compatibility

        # Resize image if it exceeds max dimensions
        if image.width > max_size[0] or image.height > max_size[1]:
            print(f"Resizing image from {image.size} to fit {max_size}...")
            image.thumbnail(max_size)  # Uses anti-aliasing by default in newer versions of Pillow

        # Save optimized PNG
        full_filepath = os.path.join(storage_path, filename)
        relative_filepath = os.path.join(db_path, filename)

        image.save(full_filepath, format="PNG", optimize=True, compress_level=3)

        print(f"Image saved successfully: {relative_filepath}")
        return relative_filepath  # Store this in DB

    except Exception as e:
        print(f"Failed to save image: {e}")
        return None

def extract_first_frame(video_url, output_filename, storage_path, db_path, rotate=False):
    """Extracts the first frame from an MP4 video, optionally rotates it, and saves it as an image."""
    try:
        print(f"Downloading video from: {video_url}")

        response = requests.get(video_url, stream=True)
        if response.status_code != 200:
            print(f"❌ Failed to download video. HTTP Status: {response.status_code}")
            return None

        temp_file = "temp_video.mp4"
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print("Video downloaded successfully. Attempting to open with OpenCV...")

        cap = cv2.VideoCapture(temp_file)
        if not cap.isOpened():
            print("❌ OpenCV failed to open video.")
            return None

        success, frame = cap.read()
        cap.release()

        if not success or frame is None:
            print("❌ Failed to extract a valid frame from the video.")
            return None

        print("Frame extracted successfully.")

        # Convert OpenCV frame (BGR) to PIL Image (RGB)
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if rotate:
            print("Rotating image 90 degrees clockwise...")
            image = image.rotate(-90, expand=True)  # Rotate clockwise

        # Convert image to raw PNG bytes
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=3)
        raw_image_data = buffer.getvalue()

        print(f"Saving extracted frame as PNG: {output_filename}")
        saved_path = save_image(raw_image_data, output_filename, storage_path, db_path)

        if saved_path:
            print(f"Image successfully saved: {saved_path}")
        else:
            print("❌ Image saving failed.")

        return saved_path

    except Exception as e:
        print(f"❌ Error extracting frame from {video_url}: {e}")
        return None
    
def rotate_image_90(image_data, output_filename, storage_path, db_path):
    """Rotates an image 90 degrees clockwise and saves it."""
    try:
        image = Image.open(BytesIO(image_data))
        rotated_image = image.rotate(-90, expand=True)

        buffer = BytesIO()
        rotated_image.save(buffer, format="PNG")
        return save_image(buffer.getvalue(), output_filename, storage_path, db_path)
    except Exception as e:
        print(f"Failed to rotate image: {e}")
        return None

def fetch_game_images(vpin_api_url, vpin_game_id):
    """Fetch PlayField (background) and BackGlass (game image) from VPin API."""
    if not vpin_api_url:
        return {
            "playfield": "PLACEHOLDER_PLAYFIELD",  # TODO: Replace with VPSDB lookup
            "backglass": "PLACEHOLDER_BACKGLASS"
        }

    playfield_url = f"{vpin_api_url}/api/v1/media/{vpin_game_id}/PlayField"
    backglass_url = f"{vpin_api_url}/api/v1/media/{vpin_game_id}/BackGlass"

    try:
        # Check media types
        playfield_response = requests.head(playfield_url, allow_redirects=True)
        backglass_response = requests.head(backglass_url, allow_redirects=True)

        is_playfield_video = "video" in playfield_response.headers.get("Content-Type", "")
        is_backglass_video = "video" in backglass_response.headers.get("Content-Type", "")

        playfield_path = None
        backglass_path = None

        # Handle PlayField
        if is_playfield_video:
            playfield_path = extract_first_frame(playfield_url, f"{vpin_game_id}_playfield.png", GAMEBACKGROUND_STORAGE_PATH, GAMEBACKGROUND_DB_PATH, True)
        else:
            response = requests.get(playfield_url)
            if response.status_code == 200:
                playfield_path = rotate_image_90(response.content, f"{vpin_game_id}_playfield.png", GAMEBACKGROUND_STORAGE_PATH, GAMEBACKGROUND_DB_PATH)

        # Handle BackGlass
        if is_backglass_video:
            backglass_path = extract_first_frame(backglass_url, f"{vpin_game_id}_backglass.png", GAMEIMAGE_STORAGE_PATH, GAMEIMAGE_DB_PATH)
        else:
            response = requests.get(backglass_url)
            if response.status_code == 200:
                backglass_path = save_image(response.content, f"{vpin_game_id}_backglass.png", GAMEIMAGE_STORAGE_PATH, GAMEIMAGE_DB_PATH)

        # If API fails, return VPSDB placeholder
        return {
            "playfield": playfield_path if playfield_path else "PLACEHOLDER_PLAYFIELD",
            "backglass": backglass_path if backglass_path else "PLACEHOLDER_BACKGLASS"
        }

    except Exception as e:
        print(f"Failed to fetch images from VPin API: {e}")
        return {
            "playfield": "PLACEHOLDER_PLAYFIELD",
            "backglass": "PLACEHOLDER_BACKGLASS"
        }

async def process_scoreboard_task(data):
    """Background task to create a scoreboard without causing a timeout."""
    print("process_scoreboard_task started.")
    try:
        app = current_app._get_current_object()  # Get the Flask app instance

        print("captured app.__get_current_object.")
        with app.app_context():

            print("working with app.app_context()")
            
            await emit_progress(0, "Starting import task"); 

            eventlet.sleep(1)
            
            print("About to run through game loop!")

            scoreboard_name = data.get("scoreboard_name")  # room_name
            vpin_api_enabled = data.get("vpin_api_enabled", "FALSE")
            vpin_api_url = (data.get("vpin_api_url") or "").strip()
            vpin_games = data.get("vpin_games", [])
            preset_id = data.get("preset_id", 1)
            
            print(f"Data received: {data}")

            if not scoreboard_name:
                print(f"❌ Scoreboard name is required")
                return jsonify({"error": "Scoreboard name is required"}), 400

            # Generate a sanitized slug for `user`
            user_slug = sanitize_slug(scoreboard_name)
            print(f"Generated user slug: {user_slug}")

            conn = get_db()
            cursor = conn.cursor()
            
            print("Database connection established!")

            # Ensure the slug does not already exist
            cursor.execute("SELECT id FROM settings WHERE user = ?", (user_slug,))
            if cursor.fetchone():
                print("❌ Error: Scoreboard name already exists!")
                return jsonify({"error": "A scoreboard with this name already exists"}), 400

            # Retrieve preset details
            cursor.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
            preset = cursor.fetchone()

            if not preset:
                print("❌ Error: Invalid preset selected!")
                return jsonify({"error": "Invalid preset selected"}), 400

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
            cursor.execute("""
                INSERT INTO settings (user, room_name, vpin_api_enabled, vpin_api_url, css_body, css_card)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_slug, scoreboard_name, vpin_api_enabled, vpin_api_url, css_body, css_card))
            
            # Capture the room_id for linking games
            room_id = cursor.lastrowid

            # Insert selected games into the games table
            gameSortVal = 0
            total_games = len(vpin_games)

            print("running through game loop")

            for index, game in enumerate(vpin_games):
                progress = int(((index + 1) / total_games) * 100)
                gameName = game["name"]
                if progress >= 100:
                    progress = 99
                print("emit_progress: " + str(progress) + ", for game " + gameName)
                await emit_progress(progress, f"Processing: {gameName}") 

                # generate vpin_games link
                vpin_spreadsheetURL = f"https://virtualpinballspreadsheet.github.io/?game={game.get('extTableId', '')}&fileType=table#{game.get('extTableVersionId', '')}"

                # Fetch game media & store locally
                media_data = fetch_game_images(vpin_api_url, game["id"]) if vpin_api_enabled else {}
                game_image = media_data.get("backglass", "PLACEHOLDER_BACKGLASS")
                game_background = media_data.get("playfield", "PLACEHOLDER_PLAYFIELD")

                # Generate a random color for the game
                game_color = generate_random_color()

                cursor.execute("""
                    INSERT INTO games (game_name, room_id, css_score_cards, css_initials, css_scores, 
                                    css_box, css_title, score_type, sort_ascending, game_sort, 
                                    game_image, game_background, tags, hidden, game_color)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game["name"], room_id, css_score_cards, css_initials, css_scores, css_box,
                    css_title, "hideBoth", "FALSE", gameSortVal, game_image, game_background,
                    vpin_spreadsheetURL, "FALSE", game_color
                ))
                
                # Capture inserted game's ID
                arcadescore_game_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO vpin_games (server_url, arcadescore_game_id, vpin_game_id)
                    VALUES (?, ?, ?)
                """, (vpin_api_url, arcadescore_game_id, game["id"]))
                
                gameSortVal += 1

            # Commit all changes
            conn.commit()
            conn.close()

            # Notify completion
            await emit_progress(100, "Scoreboard creation complete!")

            return {"message": "Scoreboard created successfully", "user_slug": user_slug}

    except Exception as e:
        await emit_progress(-1, f"Uncaught Exception in process_scoreboard_task: {str(e)}")
        print(f"❌ Uncaught Exception in process_scoreboard_task: {str(e)}")
        traceback.print_exc()  # Print full traceback to log for debugging
