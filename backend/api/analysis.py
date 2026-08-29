import json
from flask import Blueprint, request, jsonify, session
from backend.auth.middleware import login_required
from backend.services.analysis import run_pipeline
from backend.services.cache import analysis_cache, rate_limit
from data.data_sources import search_stocks, screen_universe, resolve_symbol, DataUnavailableError
from database.db import get_session, Analysis, close_session

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/api/analyze", methods=["POST"])
@login_required
@rate_limit
def analyze_stock():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    symbol = (data.get("symbol") or "").strip().upper()
    force_live = data.get("force_live", False)

    if not symbol:
        return jsonify({"error": "Stock symbol is required"}), 400

    resolved, stock_info = resolve_symbol(symbol)
    if not resolved:
        return jsonify({"error": f"Stock '{symbol}' not found in universe"}), 404

    symbol = resolved

    user_id = session["user_id"]
    cache_key = f"analysis:{symbol}:{force_live}"

    cached = analysis_cache.get(cache_key)
    if cached and not force_live:
        result = cached
    else:
        try:
            from backend.auth.service import get_user_settings
            user_settings = get_user_settings(user_id)
            result = run_pipeline(symbol, user_settings=user_settings, force_live=force_live)
            analysis_cache.set(cache_key, result)
        except DataUnavailableError as e:
            return jsonify({
                "error": str(e),
                "error_type": "data_unavailable",
                "symbol": symbol,
            }), 503
        except Exception as e:
            return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

    db = get_session()
    try:
        ev_for_json = {k: v for k, v in result["evidence"].items() if not k.startswith("_")}
        analysis = Analysis(
            user_id=user_id,
            symbol=symbol,
            mode=result["evidence"].get("source", "demo"),
            verdict=result["verdict"]["verdict"],
            confidence=result["verdict"]["confidence"],
            bull_score=result["verdict"]["bull_score"],
            bear_score=result["verdict"]["bear_score"],
            net_score=result["verdict"]["net"],
            rationale=result["verdict"]["rationale"],
            key_catalyst=result["verdict"]["key_catalyst"],
            evidence_bundle=json.dumps(ev_for_json),
            agent_outputs=json.dumps(
                {k: v for k, v in result["agent_outputs"].items() if k != "messenger"}
            ),
        )
        db.add(analysis)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"DB save error: {e}")
    finally:
        close_session(db)

    ev_clean = {k: v for k, v in result["evidence"].items() if not k.startswith("_")}
    return jsonify({
        "symbol": symbol,
        "name": result["evidence"].get("name", symbol),
        "source": result["evidence"].get("source", "unknown"),
        "verdict": result["verdict"],
        "evidence": ev_clean,
        "agent_outputs": {k: v for k, v in result["agent_outputs"].items() if k != "messenger"},
        "llm_used": result["llm_used"],
        "elapsed_seconds": result["elapsed_seconds"],
    })


@analysis_bp.route("/api/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    if len(query) < 1:
        return jsonify([])

    results = search_stocks(query)
    return jsonify(results[:20])


@analysis_bp.route("/api/history", methods=["GET"])
@login_required
def history():
    user_id = session["user_id"]
    db = get_session()
    try:
        rows = db.query(Analysis).filter(
            Analysis.user_id == user_id,
        ).order_by(Analysis.created_at.desc()).limit(50).all()

        return jsonify([
            {
                "id": r.id,
                "symbol": r.symbol,
                "mode": r.mode,
                "verdict": r.verdict,
                "confidence": r.confidence,
                "bull_score": r.bull_score,
                "bear_score": r.bear_score,
                "net_score": r.net_score,
                "rationale": r.rationale,
                "key_catalyst": r.key_catalyst,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ])
    finally:
        close_session(db)


@analysis_bp.route("/api/history/<int:analysis_id>", methods=["GET"])
@login_required
def history_detail(analysis_id):
    user_id = session["user_id"]
    db = get_session()
    try:
        row = db.query(Analysis).filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id,
        ).first()
        if not row:
            return jsonify({"error": "Analysis not found"}), 404

        result = {
            "id": row.id,
            "user_id": row.user_id,
            "symbol": row.symbol,
            "mode": row.mode,
            "verdict": row.verdict,
            "confidence": row.confidence,
            "bull_score": row.bull_score,
            "bear_score": row.bear_score,
            "net_score": row.net_score,
            "rationale": row.rationale,
            "key_catalyst": row.key_catalyst,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        if row.evidence_bundle:
            result["evidence_bundle"] = json.loads(row.evidence_bundle)
        if row.agent_outputs:
            result["agent_outputs"] = json.loads(row.agent_outputs)
        return jsonify(result)
    finally:
        close_session(db)


@analysis_bp.route("/api/screen", methods=["GET"])
@login_required
def screen():
    force_live = request.args.get("force_live", "false").lower() == "true"
    try:
        shortlist = screen_universe(strict=force_live)
        return jsonify(shortlist)
    except DataUnavailableError as e:
        return jsonify({
            "error": str(e),
            "error_type": "data_unavailable",
        }), 503
    except Exception as e:
        return jsonify({"error": f"Screening failed: {str(e)}"}), 500
