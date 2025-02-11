import os
import re
import random
import shutil
import subprocess
import socket
from flask import request, current_app
from app.modules.database import get_db

RESERVED_NAMES = {"api", "static", "webhook", "highscores", "admin", "config", "system"}

STATIC_IMAGE_PATH = os.path.join("static", "images")
DEFAULT_AVATAR_PATH = os.path.join(STATIC_IMAGE_PATH, "avatars", "default-avatar.png")

IMAGE_DIRS = {
    "avatars": "avatars",
    "game_backgrounds": "gameBackground",
    "game_images": "gameImage"
}

def generate_random_color():
    """Generate a random hex color."""
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def sanitize_slug(name):
    """Sanitize scoreboard name to create a URL-friendly slug."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)  # Remove special characters
    name = re.sub(r"\s+", "-", name)  # Replace spaces with hyphens
    return name

def validate_scoreboard_name(name):
    """Validates if the scoreboard name is non-empty, not reserved, and contains only allowed characters."""
    if not name or not name.strip():
        return "Scoreboard name is required"
    
    lower_name = name.lower()
    if lower_name in RESERVED_NAMES:
        return "Scoreboard cannot be a reserved name"
    
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):  # Allow only letters, numbers, hyphens, and underscores
        return "Scoreboard name contains invalid characters"

    return None  # No validation errors

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

def cleanup_unused_images():
    """Remove images not referenced in the database, while keeping the default avatar."""
    print("Running image cleanup...")

    IMAGE_PATH = os.path.join(current_app.root_path, STATIC_IMAGE_PATH)

    conn = get_db()
    cursor = conn.cursor()

    # Fetch all image references from the database
    cursor.execute("SELECT icon FROM players WHERE icon IS NOT NULL;")
    used_avatars = {row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT game_background FROM games WHERE game_background IS NOT NULL;")
    used_backgrounds = {row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT game_image FROM games WHERE game_image IS NOT NULL;")
    used_game_images = {row[0] for row in cursor.fetchall()}

    conn.close()

    # Convert relative DB paths to absolute paths
    def convert_to_absolute(path):
        """Convert DB-stored relative image paths to absolute file paths."""
        if not path:
            return None
        if not path.startswith("/static/images/"):
            print(f"⚠️ Unexpected DB path format: {path}")
            return None
        return os.path.abspath(os.path.join(current_app.root_path, path.lstrip("/")))

    # Map database references to absolute paths
    used_files = set()
    for image_set in [used_avatars, used_backgrounds, used_game_images]:
        for img in image_set:
            abs_path = convert_to_absolute(img)
            if abs_path:
                used_files.add(abs_path)

    removed_count = 0

    # Iterate over each image directory
    for folder_name, folder_path in IMAGE_DIRS.items():
        image_folder = os.path.join(IMAGE_PATH, folder_path)

        if not os.path.exists(image_folder):
            continue  # Skip missing folders

        for file in os.listdir(image_folder):
            file_path = os.path.abspath(os.path.join(image_folder, file))

            # **Ensure we DO NOT delete the default avatar**
            if file_path == os.path.abspath(os.path.join(current_app.root_path, DEFAULT_AVATAR_PATH)):
                print(f"Skipping default avatar: {file_path}")
                continue

            # Delete files not referenced in the database
            if file_path not in used_files:
                os.remove(file_path)
                removed_count += 1
                print(f"Removed unused image: {file_path}")
            else:
                print(f"Keeping used image: {file_path}")

    print(f"Cleanup complete. {removed_count} images removed.")


    """Detect the host machine's LAN IP from inside a Docker container."""
    try:
        # Use 'host.docker.internal' if available (Windows/macOS)
        return socket.gethostbyname("host.docker.internal")
    except socket.gaierror:
        pass  # Not available on Linux, try alternative methods

    try:
        # Use 'ip route' to find the default gateway (works on Linux)
        result = subprocess.run(["ip", "route"], capture_output=True, text=True)
        gateway_ip = result.stdout.split("default via ")[1].split()[0]

        # Ensure it's a valid LAN IP
        if gateway_ip.startswith(("172.", "10.", "192.168.")):
            return gateway_ip
    except Exception:
        pass

    # Fallback to standard LAN IP resolution
    return get_host_lan_ip()

def get_host_lan_ip():
    """Retrieve the actual LAN IP of the host machine when running standalone."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0)
        sock.connect(("8.8.8.8", 80))  # Connect to an external address, no data sent
        ip_address = sock.getsockname()[0]
        sock.close()

        return ip_address if ip_address.startswith(("192.168.", "10.", "172.")) else "127.0.0.1"
    except Exception:
        return "127.0.0.1"

def get_server_base_url():
    """Determine the correct base URL for the ArcadeScore server."""
    
    # If running behind a reverse proxy, use the `X-Forwarded-Host`
    if "X-Forwarded-Host" in request.headers:
        scheme = request.headers.get("X-Forwarded-Proto", "http")
        hostname = request.headers["X-Forwarded-Host"]
        return f"{scheme}://{hostname}"

    # Detect if running inside Docker
    is_docker = os.path.exists("/.dockerenv")

    # Determine IP based on environment
    if is_docker:
        base_ip = os.getenv("SERVER_HOST_IP", "localhost")  # Use env variable for Docker
        use_port = False  # Assume Nginx is handling routing
    else:
        base_ip = get_host_lan_ip()  # Detect actual LAN IP for standalone
        use_port = True  # Running Python directly, so we need the correct port

    # Select the correct port
    if use_port:
        port = os.getenv("ARCADESCORE_HTTP_PORT", "8080")
        return f"http://{base_ip}:{port}"

    # Return Docker-based URL without a port
    return f"http://{base_ip}"
