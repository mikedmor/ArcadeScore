import requests
from flask import Blueprint, request, jsonify, Response

vpin_proxy_bp = Blueprint("vpin_proxy", __name__)

@vpin_proxy_bp.route("/api/v1/proxy", methods=["GET"])
def proxy_vpin_api():
    """Dynamically proxies requests to a VPin Studio API server."""
    target_url = request.args.get("url").rstrip("/")

    if not target_url:
        return jsonify({"error": "Missing required 'url' parameter"}), 400

    try:
        response = requests.get(target_url, timeout=5)
        response.raise_for_status()

        # Ensure we preserve raw string values properly
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            json_text = response.text.strip()  # Preserve exact response format
            return Response(json_text, content_type="application/json")  # Return raw JSON response

        return jsonify({"data": response.text})  # Fallback for non-JSON responses

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Request to VPin Studio failed", "details": str(e)}), 500
