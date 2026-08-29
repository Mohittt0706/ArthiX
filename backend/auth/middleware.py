import functools
from flask import session, redirect, url_for, request, jsonify
from database.db import get_session, User, close_session


def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_session()
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,
        ).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at,
            }
        return None
    finally:
        close_session(db)
