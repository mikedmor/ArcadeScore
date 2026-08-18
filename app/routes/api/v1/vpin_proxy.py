import ipaddress
import socket
import requests
from flask import Blueprint, request, jsonify, Response
from urllib.parse import urlparse

vpin_proxy_bp = Blueprint("vpin_proxy", __name__)

def _is_blocked_host(hostname):
    """Block loopback and link-local addresses — including the 169.254.169.254
    cloud metadata endpoint — while still allowing the private LAN ranges VPin
    Studio servers actually live on (192.168.x.x, 10.x.x.x, 172.16-31.x.x)."""
    try:
        resolved_ips = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror:
        return True  # Can't resolve it, don't proxy to it

    for ip_str in resolved_ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return True
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return True

    return False

@vpin_proxy_bp.route("/api/v1/proxy", methods=["GET"])
def proxy_vpin_api():
    """
    Dynamically proxies requests to a VPin Studio API server. Used by the browser
    to reach a VPin server over plain HTTP when ArcadeScore itself is served over
    HTTPS (mixed-content would otherwise block it).

    Restricted to http(s) URLs targeting a VPin-style /api/v1/... path, and
    blocked from reaching loopback/link-local addresses, to narrow this down from
    an open SSRF proxy — see docs/BUG_REVIEW.md SEC-01. This still allows any LAN
    host serving something under /api/v1/, since VPin Studio's own URL is
    arbitrary and not yet known at the point the wizard's "Test" button uses this.
    """
    target_url = request.args.get("url")

    if not target_url:
        return jsonify({"error": "Missing required 'url' parameter"}), 400

    target_url = target_url.rstrip("/")
    parsed = urlparse(target_url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return jsonify({"error": "Invalid 'url' parameter"}), 400

    if "/api/v1/" not in f"{parsed.path}/":
        return jsonify({"error": "Only VPin Studio /api/v1/ endpoints may be proxied"}), 400

    if _is_blocked_host(parsed.hostname):
        return jsonify({"error": "Refusing to proxy requests to that host"}), 400

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
