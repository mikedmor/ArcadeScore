from flask import Blueprint, jsonify, request
from app.modules.database import get_db, close_db
from app.modules.auth import require_any_room_admin
from app.modules import updater

updates_bp = Blueprint("updates", __name__)


@updates_bp.route("/api/v1/updates/status", methods=["GET"])
@require_any_room_admin
def get_update_status():
    try:
        conn = get_db()
        status = updater.check_for_update(conn, force=False)
        close_db()
        return jsonify(status), 200
    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500


@updates_bp.route("/api/v1/updates/check", methods=["POST"])
@require_any_room_admin
def force_check_for_update():
    try:
        conn = get_db()
        status = updater.check_for_update(conn, force=True)
        close_db()
        return jsonify(status), 200
    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500


@updates_bp.route("/api/v1/updates/prerelease-opt-in", methods=["POST"])
@require_any_room_admin
def toggle_prerelease_opt_in():
    try:
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("enabled"))

        conn = get_db()
        updater.set_prerelease_opt_in(conn, enabled)
        # Re-check immediately so the returned status reflects the new preference
        # (e.g. opting in might reveal a newer pre-release right away).
        status = updater.check_for_update(conn, force=True)
        close_db()
        return jsonify(status), 200
    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500


@updates_bp.route("/api/v1/updates/apply", methods=["POST"])
@require_any_room_admin
def apply_update():
    try:
        conn = get_db()
        result = updater.apply_update(conn)
        close_db()
        if not result.get("success"):
            return jsonify({"error": result.get("error", "Update failed.")}), 400
        return jsonify({"message": result.get("message")}), 200
    except Exception as e:
        close_db()
        return jsonify({"error": str(e)}), 500
