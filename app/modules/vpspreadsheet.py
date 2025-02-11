import json
import os
import time
import requests
from flask import current_app

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

def fetch_vps_data():
    """
    Fetches VPS data and updates the cache if outdated.
    """
    global cached_vpsdb, cached_last_updated, last_checked_time
    current_time = time.time()

    # Get VPS paths using the helper function
    vps_data_dir, vps_json_path, last_updated_path = get_vps_paths()

    os.makedirs(vps_data_dir, exist_ok=True)

    if not last_checked_time or current_time - last_checked_time >= CACHE_EXPIRY:
        try:
            # Check lastUpdated.json
            response = requests.get(VPS_LAST_UPDATED_URL)
            response.raise_for_status()
            last_updated = response.json()

            # Compare with the local cache
            if not os.path.exists(last_updated_path) or json.load(open(last_updated_path)) != last_updated:
                # Fetch new VPS data
                vpsdb_response = requests.get(VPS_DB_URL)
                vpsdb_response.raise_for_status()
                cached_vpsdb = vpsdb_response.json()
                
                # Save locally
                with open(vps_json_path, "w") as f:
                    json.dump(cached_vpsdb, f)
                with open(last_updated_path, "w") as f:
                    json.dump(last_updated, f)

            else:
                # Load from local cache
                with open(vps_json_path, "r") as f:
                    cached_vpsdb = json.load(f)

            cached_last_updated = last_updated
            last_checked_time = current_time

        except Exception as e:
            print(f"Error fetching VPS data: {e}")

def generate_vpspreadsheet_url(extTableId = None, extTableVersionId = None):
    # Generate VPin Spreadsheet URL
    vpin_spreadsheet_url = ""
    if extTableId and extTableVersionId:
        vpin_spreadsheet_url = f"https://virtualpinballspreadsheet.github.io/?game={extTableId}&fileType=table#{extTableVersionId}"
    elif extTableId:
        vpin_spreadsheet_url = f"https://virtualpinballspreadsheet.github.io/?game={extTableId}&fileType=table"

    return vpin_spreadsheet_url

