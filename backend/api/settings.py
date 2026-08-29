from flask import Blueprint, request, jsonify, session
from backend.auth.middleware import login_required
from backend.auth.service import get_user_settings, update_user_settings
from backend.services.cache import analysis_cache

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    user_id = session["user_id"]
    settings = get_user_settings(user_id)
    if not settings:
        return jsonify({"error": "Settings not found"}), 404
    return jsonify(settings)


@settings_bp.route("/api/settings", methods=["PUT"])
@login_required
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = session["user_id"]
    result = update_user_settings(
        user_id,
        telegram_chat_id=data.get("telegram_chat_id"),
        confidence_threshold=data.get("confidence_threshold"),
        notifications_enabled=data.get("notifications_enabled"),
    )

    if result:
        return jsonify({"message": "Settings updated"})
    return jsonify({"error": "Failed to update settings"}), 500


@settings_bp.route("/api/cache/clear", methods=["POST"])
@login_required
def clear_cache():
    analysis_cache.clear()
    return jsonify({"message": "Cache cleared"})
