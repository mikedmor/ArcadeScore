import os
import shutil
import time
import eventlet
from flask import current_app
from app.socketio_instance import socketio
from app.modules.sockets import emit_progress
from app.routes.settings import cleanup_unused_images

# Restored correct paths
EXPORT_PATH = "app/static/export"
IMPORT_PATH = "app/static/import"
DATA_PATH = "data/highscores.db"
IMAGE_PATH = "app/static/images"

async def run_export_task(session_id):
    """Background task for exporting data asynchronously."""
    app = current_app._get_current_object()
    with app.app_context():
        try:
            start_time = time.time()
            print("Export started...")

            await emit_progress(0, "Starting export task"); 

            eventlet.sleep(0)

            os.makedirs(EXPORT_PATH, exist_ok=True)
            archive_filename = f"ArcadeScoreExport_{session_id}.7z"  # Unique filename per session_id
            archive_path = os.path.join(EXPORT_PATH, archive_filename)

            await emit_progress(10, "Cleaning up unused media")

            eventlet.sleep(0)

            # Run image cleanup
            cleanup_unused_images()

            # Ensure previous exports are cleared
            if os.path.exists(archive_path):
                os.remove(archive_path)

            await emit_progress(30, "Copying database")

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
                await emit_progress(-1, "Error: Database file not found.")

                eventlet.sleep(0)
                return

            await emit_progress(60, "Copying images")

            eventlet.sleep(0)

            # Copy image folders
            image_export_path = os.path.join(temp_export_dir, "images")
            os.makedirs(image_export_path, exist_ok=True)

            for folder in ["avatars", "gameBackground", "gameImage"]:
                src_folder = os.path.join(IMAGE_PATH, folder)
                dest_folder = os.path.join(image_export_path, folder)
                if os.path.exists(src_folder):
                    shutil.copytree(src_folder, dest_folder, dirs_exist_ok=True)

            await emit_progress(80, "Creating compressed archive")

            eventlet.sleep(0)

            # Use 7z to create archive (requires 7z CLI installed)
            os.system(f'7z a -t7z "{archive_path}" "{temp_export_dir}/*"')
            
            # Ensure file was created before notifying the client
            if not os.path.exists(archive_path):
                await emit_progress(-1, "Error: Archive file was not created.")
                print(f"❌ Archive file missing: {archive_path}")
                return

            await emit_progress(95, "Finalize")

            eventlet.sleep(0)

            # Remove temporary files
            shutil.rmtree(temp_export_dir)

            await emit_progress(100, "Completed")

            eventlet.sleep(0)

            # Notify client that the file is ready
            for i in range(5):  # Retry for up to 5 seconds
                if os.path.exists(archive_path):
                    socketio.emit("file_ready", {
                        "session_id": session_id,
                        "file_path": f"/api/v1/download/{archive_filename}"
                    }, namespace="/")
                    break
                eventlet.sleep(1)

        except Exception as e:
            await emit_progress(-1, f"Export failed: {str(e)}")
            print(f"Export failed: {str(e)}")
