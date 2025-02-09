import os
import subprocess
import shutil
import time
import eventlet
from app.socketio_instance import socketio
from app.modules.sockets import emit_progress
from app.routes.settings import cleanup_unused_images

# Restored correct paths
EXPORT_PATH = "app/static/export"
IMPORT_PATH = "app/static/import"
DATA_PATH = "data/highscores.db"
IMAGE_PATH = "app/static/images"

def get_7z_path():
    """Finds the correct path to 7z.exe on Windows."""
    possible_paths = [
        r"C:\Program Files\7-Zip\7z.exe",  # Default install location
        r"C:\Program Files (x86)\7-Zip\7z.exe",  # 32-bit install
        shutil.which("7z")  # Checks if 7z is in the system PATH
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            print(f"Found 7z at: {path}")
            return path

    print("❌ 7z not found! Ensure it is installed and added to your PATH.")
    return None

def run_export_task(app, session_id):
    """Background task for exporting data asynchronously."""
    with app.app_context():
        try:
            start_time = time.time()
            print("Export started...")

            emit_progress(app, 0, "Starting export task"); 
            eventlet.sleep(0)

            os.makedirs(EXPORT_PATH, exist_ok=True)
            archive_filename = f"ArcadeScoreExport_{session_id}.7z"  # Unique filename per session_id
            archive_path = os.path.abspath(os.path.join(EXPORT_PATH, archive_filename))

            emit_progress(app, 10, "Cleaning up unused media")
            eventlet.sleep(0)

            # Run image cleanup
            cleanup_unused_images()

            # Ensure previous exports are cleared
            if os.path.exists(archive_path):
                os.remove(archive_path)

            emit_progress(app, 30, "Copying database")
            eventlet.sleep(0)

            # Create a temporary export directory
            temp_export_dir = os.path.join(EXPORT_PATH, "temp_export")
            if os.path.exists(temp_export_dir):
                shutil.rmtree(temp_export_dir)
            os.makedirs(temp_export_dir)

            # Copy highscores.db
            if os.path.exists(DATA_PATH):
                shutil.copy(DATA_PATH, os.path.join(temp_export_dir, "highscores.db"))
            else:
                emit_progress(app, -1, "Error: Database file not found.")
                eventlet.sleep(0)
                return

            emit_progress(app, 60, "Copying images")
            eventlet.sleep(0)

            # Copy image folders
            image_export_path = os.path.join(temp_export_dir, "images")
            os.makedirs(image_export_path, exist_ok=True)

            for folder in ["avatars", "gameBackground", "gameImage"]:
                src_folder = os.path.join(IMAGE_PATH, folder)
                dest_folder = os.path.join(image_export_path, folder)
                if os.path.exists(src_folder):
                    shutil.copytree(src_folder, dest_folder, dirs_exist_ok=True)

            emit_progress(app, 80, "Creating compressed archive")
            eventlet.sleep(0)

            # Get the correct 7z path
            seven_zip_path = get_7z_path()
            if not seven_zip_path:
                emit_progress(-1, "Error: 7z.exe not found. Install 7-Zip and add it to your PATH.")
                print("❌ 7z.exe not found. Install 7-Zip or check PATH.")
                return

            # Use subprocess to run 7z command
            compression_start = time.time()
            command = [seven_zip_path, "a", "-t7z", archive_path, "."]
            subprocess.run(command, cwd=temp_export_dir, check=True)

            print(f"✅ Created 7z archive in {time.time() - compression_start:.2f}s")

            emit_progress(app, 95, "Finalize")
            eventlet.sleep(0)

            # Remove temporary files
            shutil.rmtree(temp_export_dir)

            emit_progress(app, 100, "Completed")
            eventlet.sleep(0)

            # Notify client that the file is ready
            for i in range(5):  # Retry for up to 5 seconds
                if os.path.exists(archive_path):
                    print(f"✅ File ready, emitting event: {archive_filename}")  # Debug log
                    socketio.emit("file_ready", {
                        "session_id": session_id,
                        "file_path": f"/api/v1/download/{os.path.basename(archive_path)}"
                    }, namespace="/")
                    
                    socketio.sleep(0)  # Ensure Eventlet processes the event
                    break
                eventlet.sleep(1)

        except Exception as e:
            emit_progress(app, -1, f"Export failed: {str(e)}")
            print(f"Export failed: {str(e)}")
