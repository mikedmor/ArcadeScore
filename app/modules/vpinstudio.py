import os
import requests
import traceback
from app.modules.imageProcessor import save_image, extract_first_frame, rotate_image_90
from app.routes.misc import GAMEIMAGE_STORAGE_PATH, GAMEBACKGROUND_STORAGE_PATH, GAMEIMAGE_DB_PATH, GAMEBACKGROUND_DB_PATH
from datetime import datetime

def fetch_game_images(vpin_api_url, vpin_game_id, compression_level="original"):
    """Fetch PlayField (background) and BackGlass (game image) from VPin API."""
    if not vpin_api_url:
        return {
            "playfield": None,
            "backglass": None
        }

    playfield_url = f"{vpin_api_url}api/v1/media/{vpin_game_id}/PlayField"
    backglass_url = f"{vpin_api_url}api/v1/media/{vpin_game_id}/BackGlass"

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
            playfield_path = extract_first_frame(playfield_url, f"{vpin_game_id}_playfield.png", GAMEBACKGROUND_STORAGE_PATH, GAMEBACKGROUND_DB_PATH, True, compression_level)
        else:
            response = requests.get(playfield_url)
            if response.status_code == 200:
                print(f"Successfully fetched image from VPin Studio: {playfield_url}")
                playfield_path = rotate_image_90(response.content, f"{vpin_game_id}_playfield.png", GAMEBACKGROUND_STORAGE_PATH, GAMEBACKGROUND_DB_PATH, compression_level)
            else:
                playfield_path = None
                print(f"Failed to fetch from VPin Studio: {playfield_url} - Status Code: {response.status_code}")

        # Handle BackGlass
        if is_backglass_video:
            backglass_path = extract_first_frame(backglass_url, f"{vpin_game_id}_backglass.png", GAMEIMAGE_STORAGE_PATH, GAMEIMAGE_DB_PATH, False, compression_level)
        else:
            response = requests.get(backglass_url)
            if response.status_code == 200:
                print(f"Successfully fetched image from VPin Studio: {backglass_url}")
                backglass_path = save_image(response.content, f"{vpin_game_id}_backglass.png", GAMEIMAGE_STORAGE_PATH, GAMEIMAGE_DB_PATH, compression_level)
            else:
                backglass_path = None
                print(f"Failed to fetch from VPin Studio: {backglass_url} - Status Code: {response.status_code}")

        # If API fails, return VPSDB placeholder
        return {
            "playfield": playfield_path,
            "backglass": backglass_path
        }

    except Exception as e:
        print(f"Failed to fetch images from VPin API: {e}")
        return {
            "playfield": None,
            "backglass": None
        }

def fetch_historical_scores(vpin_api_url, vpin_game_id, vpin_players, game_id):
    """
    Fetch historical scores from the VPin API and return them as a list of dictionaries.
    Returns None if an error occurs or if no scores are found.
    """
    score_endpoint = f"{vpin_api_url}/api/v1/games/scores/{vpin_game_id}"

    try:
        print(f"Fetching historical scores from: {score_endpoint}")

        # Fetch the scores from the VPin API
        score_response = requests.get(score_endpoint)
        if score_response.status_code != 200:
            print(f"❌ Failed to fetch scores. HTTP Status: {score_response.status_code}")
            return None

        # Parse the JSON response
        scores_data = score_response.json().get("scores", [])
        print(f"Found {len(scores_data)} scores to process.")

        # Match players and prepare data
        retrieved_scores = []
        for score_entry in scores_data:
            # Ensure score_entry["player"] is not None
            if not score_entry.get("player"):
                print(f"⚠️ Skipping score entry with missing player: {score_entry}")
                continue  # Skip this score

            vpin_player_id = score_entry["player"].get("id")  # Get player ID safely

            # Match vpin_player_id with arcadescore_player_id from vpin_players
            matching_player = next(
                (player for player in vpin_players if player["vpin_player_id"] == vpin_player_id),
                None
            )

            if not matching_player:
                print(f"⚠️ No matching player found for VPin Player ID: {vpin_player_id}")
                continue  # Skip scores with unknown players

            # Convert API timestamp to database-compatible format
            try:
                timestamp = datetime.strptime(
                    score_entry["createdAt"], "%Y-%m-%dT%H:%M:%S.%f%z"
                ).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                print(f"⚠️ Failed to parse timestamp: {score_entry['createdAt']}. Error: {e}")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Fallback timestamp

            # Prepare score data
            retrieved_scores.append({
                "player_id": matching_player["arcadescore_player_id"],
                "game_id": game_id,
                "score": int(float(score_entry["numericScore"])),
                "timestamp": timestamp
            })

        return retrieved_scores if retrieved_scores else None

    except Exception as e:
        print(f"❌ Failed to fetch historical scores from VPin API: {e}")
        traceback.print_exc()
        return None
