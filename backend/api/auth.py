from flask import Blueprint, request, jsonify, session
from backend.auth.service import create_user, authenticate_user, get_user_by_id

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if "@" not in email:
        return jsonify({"error": "Invalid email address"}), 400

    user_id = create_user(username, email, password)
    if user_id is None:
        return jsonify({"error": "Username or email already exists"}), 409

    session["user_id"] = user_id
    return jsonify({
        "message": "Registration successful",
        "user": {"id": user_id, "username": username, "email": email},
    }), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = authenticate_user(username, password)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"] = user["id"]
    return jsonify({
        "message": "Login successful",
        "user": {"id": user["id"], "username": user["username"], "email": user["email"]},
    })


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@auth_bp.route("/api/auth/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 401

    return jsonify({"authenticated": True, "user": user})
