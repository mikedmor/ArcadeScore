import os
import zipfile
import shutil
import time
from flask import Blueprint, jsonify, send_file, request
from app.modules.sockets import emit_progress
from app.routes.settings import cleanup_unused_images
from app.database import get_db, db_version

import_export_bp = Blueprint("import_export", __name__)

# Restored correct paths
EXPORT_PATH = "app/static/export"
IMPORT_PATH = "app/static/import"
DATA_PATH = "data/highscores.db"
IMAGE_PATH = "app/static/images"

@import_export_bp.route("/api/v1/export", methods=["GET"])
def export_data():
    """Export highscores.db and images to a 7z archive, with debug logging."""
    try:
        start_time = time.time()
        print("Export started...")

        os.makedirs(EXPORT_PATH, exist_ok=True)
        archive_path = os.path.abspath(os.path.join(EXPORT_PATH, "ArcadeScoreExport.7z"))

        emit_progress(10, "Cleaning up unused media")

        # Run image cleanup
        cleanup_unused_images()

        # Ensure previous exports are cleared
        if os.path.exists(archive_path):
            os.remove(archive_path)

        print(f"Cleared previous export archive. Took: {time.time() - start_time:.3f}s")

        emit_progress(30, "Copying database")

        # Create a temporary export directory
        temp_export_dir = os.path.join(EXPORT_PATH, "temp_export")
        if os.path.exists(temp_export_dir):
            shutil.rmtree(temp_export_dir)
        os.makedirs(temp_export_dir)

        print(f"Created temporary export directory. Took: {time.time() - start_time:.3f}s")

        # Copy highscores.db
        db_copy_start = time.time()
        if os.path.exists(DATA_PATH):
            shutil.copy(DATA_PATH, os.path.join(temp_export_dir, "highscores.db"))
        else:
            return jsonify({"error": "Database file not found."}), 500

        emit_progress(60, "Copying images")
        print(f"Copied highscores.db. Took: {time.time() - db_copy_start:.3f}s")

        # Copy image folders
        image_export_path = os.path.join(temp_export_dir, "images")
        os.makedirs(image_export_path, exist_ok=True)

        for folder in ["avatars", "gameBackground", "gameImage"]:
            src_folder = os.path.join(IMAGE_PATH, folder)
            dest_folder = os.path.join(image_export_path, folder)
            if os.path.exists(src_folder):
                shutil.copytree(src_folder, dest_folder, dirs_exist_ok=True)

        emit_progress(80, "Creating compressed archive")

        # Use 7z to create archive (requires 7z CLI installed)
        compression_start = time.time()
        command = f'cd "{temp_export_dir}" && 7z a -t7z "{archive_path}" *'
        os.system(command)

        emit_progress(95, "Finalize")
        print(f"Created 7z archive. Took: {time.time() - compression_start:.3f}s")

        # Remove temporary files
        cleanup_start = time.time()
        shutil.rmtree(temp_export_dir)
        print(f"Removed temporary export directory. Took: {time.time() - cleanup_start:.3f}s")

        total_time = time.time() - start_time
        emit_progress(100, "Completed")
        print(f"Export completed successfully! Total time: {total_time:.3f}s")

        return send_file(archive_path, as_attachment=True)

    except Exception as e:
        emit_progress(-1, str(e))
        print(f"Export failed: {str(e)}")
        return jsonify({"error": "Export failed", "details": str(e)}), 500

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

        # Extract 7z contents
        command = f'7z x "{archive_path}" -o"{temp_import_dir}" -y'
        os.system(command)

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
