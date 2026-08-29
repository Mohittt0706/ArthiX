import os
import sys
from flask import Flask, render_template, session, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from config import config
from database.db import init_db


def create_app():
    app = Flask(__name__, template_folder="frontend/templates", static_folder="frontend/static")
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE
    app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE

    init_db(database_url=config.DATABASE_URL)

    from backend.api.auth import auth_bp
    from backend.api.analysis import analysis_bp
    from backend.api.watchlist import watchlist_bp
    from backend.api.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(settings_bp)

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login_page"))

    @app.route("/login")
    def login_page():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/dashboard")
    def dashboard():
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return render_template("dashboard.html")

    @app.route("/analysis/<symbol>")
    def analysis_page(symbol):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return render_template("analysis.html", symbol=symbol)

    @app.route("/history")
    def history_page():
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return render_template("history.html")

    @app.route("/watchlist")
    def watchlist_page():
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return render_template("watchlist.html")

    @app.route("/health")
    def health():
        from engine.llm import is_available
        return {
            "status": "healthy",
            "app": "ArthiX",
            "demo_mode": config.is_demo_mode(),
            "llm_available": is_available(),
        }

    return app


app = create_app()

if __name__ == "__main__":
    port = config.PORT
    print(f"🚀 ArthiX starting on port {port}")
    print(f"   Demo mode: {config.is_demo_mode()}")
    print(f"   URL: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
