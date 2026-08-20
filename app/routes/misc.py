import os
from flask import Blueprint, request, jsonify, render_template, send_from_directory

# Define storage path for game images
GAMEIMAGE_STORAGE_PATH = "app/static/images/gameImage"
GAMEBACKGROUND_STORAGE_PATH = "app/static/images/gameBackground"
GAMEIMAGE_DB_PATH = "/static/images/gameImage"
GAMEBACKGROUND_DB_PATH = "/static/images/gameBackground"

# Ensure the directory exists
os.makedirs(GAMEIMAGE_STORAGE_PATH, exist_ok=True)
os.makedirs(GAMEBACKGROUND_STORAGE_PATH, exist_ok=True)

misc_bp = Blueprint('misc', __name__)

@misc_bp.before_request
def catch_all_logging():
    print("\n--- Catch-All Request ---")
    print(f"Method: {request.method}")
    print(f"Path: {request.path}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Body: {request.data.decode('utf-8') if request.data else 'No Body'}")
    print("------------------------")

@misc_bp.route("/", methods=["GET"])
def landing_page():
    """
    Serve the general landing page.
    """
    try:
        return render_template('index.jinja')
    except Exception as e:
        return jsonify({"error": "Landing page not found", "details": str(e)}), 404
    
@misc_bp.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico", mimetype="image/vnd.microsoft.icon")

@misc_bp.route('/static/images/avatars/<path:filename>')
def serve_avatar(filename):
    return send_from_directory('static/images/avatars', filename)

@misc_bp.route('/static/images/gameBackground/<path:filename>')
def serve_gameBackground(filename):
    return send_from_directory('static/images/gameBackground', filename)

@misc_bp.route('/static/images/gameImage/<path:filename>')
def serve_gameImage(filename):
    return send_from_directory('static/images/gameImage', filename)