import os
import shutil
import uuid
import eventlet
import subprocess
from flask import Blueprint, jsonify, send_file, request, current_app
from app.modules.database import get_db, db_version
from app.background.export_task import run_export_task
from app.modules.utils import get_7z_path

import_export_bp = Blueprint("import_export", __name__)

# Restored correct paths
EXPORT_PATH = "app/static/export"
IMPORT_PATH = "app/static/import"
DATA_PATH = "data/highscores.db"
IMAGE_PATH = "app/static/images"

@import_export_bp.route("/api/v1/export", methods=["GET"])
def export_data():
    """Trigger background export and return immediate response."""
    session_id = request.args.get("session_id") or str(uuid.uuid4())  # Get session ID or create one
    app = current_app._get_current_object()  # Get the Flask app instance

    print(f"Scheduling run_export_task for session {session_id}...")

    # Pass `app` to ensure proper context
    eventlet.spawn_n(run_export_task, app, session_id)

    print(f"Export task scheduled using eventlet.spawn_n, returning response immediately.")

    return jsonify({
        "message": "Export started",
        "session_id": session_id  # Send session ID back for tracking
    }), 202

@import_export_bp.route("/api/v1/download/<filename>", methods=["GET"])
def download_export(filename):
    """Allow users to download the exported file after completion."""
    archive_path = os.path.abspath(os.path.join(EXPORT_PATH, filename))

    if os.path.exists(archive_path):
        return send_file(archive_path, as_attachment=True)
    else:
        print(f"❌ File not found: {archive_path}")  # Debugging
        return jsonify({"error": "File not found"}), 404


@import_export_bp.route("/api/v1/import", methods=["POST"])
def import_data():
    """Import highscores.db and images from a 7z file."""
    try:
        # Ensure the request has a file
        file = request.files.get("file")
        if not file or not file.filename.endswith(".7z"):
            return jsonify({"error": "Invalid file format. Upload a .7z file."}), 400

        # Ensure import directory exists
        os.makedirs(IMPORT_PATH, exist_ok=True)

        # Save the uploaded archive
        archive_path = os.path.join(IMPORT_PATH, "import.7z")
        file.save(archive_path)

        # Create a temporary directory for extraction
        temp_import_dir = os.path.join(IMPORT_PATH, "temp_import")
        if os.path.exists(temp_import_dir):
            shutil.rmtree(temp_import_dir)
        os.makedirs(temp_import_dir)

        # Get the correct 7z path
        seven_zip_path = get_7z_path()
        if not seven_zip_path:
            return jsonify({"message": "7z.exe not found. Install 7-Zip or check PATH."})

        # Extract 7z contents using the correct executable path
        command = [seven_zip_path, "x", archive_path, f"-o{temp_import_dir}", "-y"]
        subprocess.run(command, check=True)

        # Validate that highscores.db exists
        extracted_db_path = os.path.join(temp_import_dir, "highscores.db")
        if not os.path.exists(extracted_db_path):
            return jsonify({"error": "Database file is missing in the uploaded archive."}), 400

        # Ensure the extracted structure matches our expected format
        image_import_path = os.path.join(temp_import_dir, "images")
        required_folders = ["avatars", "gameBackground", "gameImage"]

        for folder in required_folders:
            src_folder = os.path.join(image_import_path, folder)
            dest_folder = os.path.join(IMAGE_PATH, folder)

            if not os.path.exists(src_folder):
                return jsonify({"error": f"Missing required folder: {folder}"}), 400

        # Check database version from meta table
        conn = get_db(extracted_db_path)
        cursor = conn.cursor()

        # Ensure meta table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meta'")
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "The imported database does not contain the 'meta' table."}), 400

        # Fetch database version
        cursor.execute("SELECT value FROM meta WHERE key = 'db_version'")
        imported_db_version = cursor.fetchone()
        conn.close()

        if not imported_db_version:
            return jsonify({"error": "The imported database does not contain a valid db_version."}), 400

        imported_db_version = int(imported_db_version[0])

        # Validate version
        if imported_db_version > db_version:
            return jsonify({"error": f"Database version {imported_db_version} is newer than {db_version}. Update the application."}), 400

        # Replace the database safely
        shutil.copy2(extracted_db_path, DATA_PATH)  # Copy instead of os.replace()
        os.remove(extracted_db_path)  # Remove old file after copy

        # Move images
        for folder in required_folders:
            src_folder = os.path.join(image_import_path, folder)
            dest_folder = os.path.join(IMAGE_PATH, folder)

            os.makedirs(dest_folder, exist_ok=True)
            shutil.copytree(src_folder, dest_folder, dirs_exist_ok=True)

        # Clean up temporary files
        shutil.rmtree(temp_import_dir)
        os.remove(archive_path)

        return jsonify({"message": "Import successful."})

    except Exception as e:
        return jsonify({"error": "Import failed", "details": str(e)}), 500
