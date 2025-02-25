import json
import os
import time
import requests
from flask import current_app
from app.modules.imageProcessor import save_image
from app.routes.misc import GAMEIMAGE_STORAGE_PATH, GAMEBACKGROUND_STORAGE_PATH, GAMEIMAGE_DB_PATH, GAMEBACKGROUND_DB_PATH

VPS_DB_URL = "https://virtualpinballspreadsheet.github.io/vps-db/db/vpsdb.json"
VPS_LAST_UPDATED_URL = "https://virtualpinballspreadsheet.github.io/vps-db/lastUpdated.json"
CACHE_EXPIRY = 3600  # Cache expiry in seconds (1 hour)

# Cache storage
cached_vpsdb = None
last_checked_time = None
cached_last_updated = None

def get_vps_paths():
    vps_data_dir = os.path.join(current_app.root_path, 'vps-data')
    vps_json_path = os.path.join(vps_data_dir, "vpsdb.json")
    last_updated_path = os.path.join(vps_data_dir, "lastUpdated.json")
    return vps_data_dir, vps_json_path, last_updated_path

def fetch_vps_data(force_refresh=False):
    """
    Fetches VPS data and updates the cache if outdated or forced refresh is requested.
    Returns the VPS database as a dictionary.
    """
    global cached_vpsdb, cached_last_updated, last_checked_time
    current_time = time.time()

    vps_data_dir, vps_json_path, last_updated_path = get_vps_paths()
    os.makedirs(vps_data_dir, exist_ok=True)

    try:
        # Refresh cache if expired or forced
        if force_refresh or not last_checked_time or current_time - last_checked_time >= CACHE_EXPIRY:
            response = requests.get(VPS_LAST_UPDATED_URL)
            response.raise_for_status()
            last_updated = response.json()

            # Compare with local lastUpdated.json
            local_last_updated = None
            if os.path.exists(last_updated_path):
                with open(last_updated_path, "r") as f:
                    local_last_updated = json.load(f)

            if force_refresh or last_updated != local_last_updated:
                vpsdb_response = requests.get(VPS_DB_URL)
                vpsdb_response.raise_for_status()
                cached_vpsdb = vpsdb_response.json()

                # Save new cache
                with open(vps_json_path, "w") as f:
                    json.dump(cached_vpsdb, f)
                with open(last_updated_path, "w") as f:
                    json.dump(last_updated, f)

            else:
                with open(vps_json_path, "r") as f:
                    cached_vpsdb = json.load(f)

            cached_last_updated = last_updated
            last_checked_time = current_time

        return cached_vpsdb

    except Exception as e:
        print(f"Error fetching VPS data: {e}")
        return cached_vpsdb or {}

def generate_vpspreadsheet_url(extTableId = None, extTableVersionId = None):
    # Generate VPin Spreadsheet URL
    vpin_spreadsheet_url = ""
    if extTableId and extTableVersionId:
        vpin_spreadsheet_url = f"https://virtualpinballspreadsheet.github.io/?game={extTableId}&fileType=table#{extTableVersionId}"
    elif extTableId:
        vpin_spreadsheet_url = f"https://virtualpinballspreadsheet.github.io/?game={extTableId}&fileType=table"

    return vpin_spreadsheet_url

def fetch_vpspreadsheet_media(ext_table_id, ext_table_version_id, compression_level="original"):
    """
    Fetch media from VPS Spreadsheet using extTableId and extTableVersionId.
    :param ext_table_id: External Table ID from VPin Studio
    :param ext_table_version_id: External Table Version ID from VPin Studio
    :param compression_level: Level of compression for the images
    :return: Dictionary with backglass and playfield paths or None if unavailable
    """
    print(f"Fetching media from VP Spreadsheet for Table ID: {ext_table_id}, Version ID: {ext_table_version_id}")
    vpsdb = fetch_vps_data()

    try:
        # 1️⃣ Find the game using extTableId
        game_data = next((game for game in vpsdb if game.get("id") == ext_table_id), None)
        if not game_data:
            print(f"Game with extTableId {ext_table_id} not found in VPS database.")
            return {"backglass": None, "playfield": None}

        # 2️⃣ Find the table version using extTableVersionId
        table_data = next((table for table in game_data.get("tableFiles", []) if table.get("id") == ext_table_version_id), None)
        if not table_data:
            print(f"Table version with extTableVersionId {ext_table_version_id} not found.")
            return {"backglass": None, "playfield": None}

        # 3️⃣ Extract media URLs
        backglass_url = game_data.get("b2sFiles", [{}])[0].get("imgUrl")
        playfield_url = table_data.get("imgUrl")

        backglass_path = None
        playfield_path = None

        # 4️⃣ Download & compress backglass
        if backglass_url:
            response = requests.get(backglass_url)
            if response.status_code == 200:
                backglass_filename = f"{ext_table_id}_{ext_table_version_id}_backglass.png"
                backglass_path = save_image(
                    response.content,
                    backglass_filename,
                    GAMEIMAGE_STORAGE_PATH,
                    GAMEIMAGE_DB_PATH,
                    compression_level
                )
            else:
                print(f"Failed to download backglass image: HTTP {response.status_code}")

        # 5️⃣ Download & compress playfield
        if playfield_url:
            response = requests.get(playfield_url)
            if response.status_code == 200:
                playfield_filename = f"{ext_table_id}_{ext_table_version_id}_playfield.png"
                playfield_path = save_image(
                    response.content,
                    playfield_filename,
                    GAMEBACKGROUND_STORAGE_PATH,
                    GAMEBACKGROUND_DB_PATH,
                    compression_level
                )
            else:
                print(f"Failed to download playfield image: HTTP {response.status_code}")

        return {
            "backglass": backglass_path,
            "playfield": playfield_path
        }

    except Exception as e:
        print(f"❌ Error fetching VPS media for table {ext_table_id} version {ext_table_version_id}: {e}")
        return {
            "backglass": None,
            "playfield": None
        }