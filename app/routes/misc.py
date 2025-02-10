import requests
import os
import sqlite3
from flask import Blueprint, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from app.database import get_db

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
    return send_from_directory(os.path.join(os.getcwd(), "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

@misc_bp.route('/static/images/avatars/<path:filename>')
def serve_avatar(filename):
    return send_from_directory('static/images/avatars', filename)

@misc_bp.route('/static/images/gameBackground/<path:filename>')
def serve_gameBackground(filename):
    return send_from_directory('static/images/gameBackground', filename)

@misc_bp.route('/static/images/gameImage/<path:filename>')
def serve_gameImage(filename):
    return send_from_directory('static/images/gameImage', filename)