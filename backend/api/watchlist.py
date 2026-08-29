from flask import Blueprint, request, jsonify, session
from backend.auth.middleware import login_required
from database.db import get_session, WatchlistItem, close_session

watchlist_bp = Blueprint("watchlist", __name__)


@watchlist_bp.route("/api/watchlist", methods=["GET"])
@login_required
def get_watchlist():
    user_id = session["user_id"]
    db = get_session()
    try:
        rows = db.query(WatchlistItem).filter(
            WatchlistItem.user_id == user_id,
        ).order_by(WatchlistItem.added_at.desc()).all()

        return jsonify([
            {
                "id": w.id,
                "symbol": w.symbol,
                "name": w.name,
                "added_at": w.added_at.isoformat() if w.added_at else None,
            }
            for w in rows
        ])
    finally:
        close_session(db)


@watchlist_bp.route("/api/watchlist", methods=["POST"])
@login_required
def add_to_watchlist():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    symbol = (data.get("symbol") or "").strip().upper()
    name = (data.get("name") or "").strip()

    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400

    if not symbol.endswith(".NS"):
        symbol = symbol + ".NS"

    user_id = session["user_id"]
    db = get_session()
    try:
        existing = db.query(WatchlistItem).filter(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol == symbol,
        ).first()

        if not existing:
            item = WatchlistItem(user_id=user_id, symbol=symbol, name=name)
            db.add(item)
            db.commit()

        return jsonify({"message": f"{symbol} added to watchlist"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_session(db)


@watchlist_bp.route("/api/watchlist/<symbol>", methods=["DELETE"])
@login_required
def remove_from_watchlist(symbol):
    symbol = symbol.upper()
    if not symbol.endswith(".NS"):
        symbol = symbol + ".NS"

    user_id = session["user_id"]
    db = get_session()
    try:
        db.query(WatchlistItem).filter(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol == symbol,
        ).delete()
        db.commit()
        return jsonify({"message": f"{symbol} removed from watchlist"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_session(db)
