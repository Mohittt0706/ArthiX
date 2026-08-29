def _safe(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _bull_score(evidence):
    score = 0
    reasons = []
    tech = evidence.get("technicals", {})
    analyst = evidence.get("analyst", {})
    news = evidence.get("news", {})
    range_52 = evidence.get("range_52w", {})
    price = evidence.get("price", {})

    rvol = _safe(tech.get("rvol"))
    if rvol >= 2.0:
        score += 15
        reasons.append(f"High relative volume ({rvol}x) indicates strong interest")
    elif rvol >= 1.5:
        score += 10
        reasons.append(f"Above-average volume ({rvol}x)")
    elif rvol >= 1.0:
        score += 5
        reasons.append(f"Normal volume ({rvol}x)")

    position = _safe(range_52.get("position_pct"))
    if position >= 80:
        score += 15
        reasons.append(f"Near 52-week high ({position:.0f}% of range)")
    elif position >= 60:
        score += 10
        reasons.append(f"Upper half of 52-week range ({position:.0f}%)")
    elif position >= 40:
        score += 5
        reasons.append(f"Mid-range of 52-week range ({position:.0f}%)")

    trend = tech.get("trend", "sideways")
    price_vs_sma = _safe(tech.get("price_vs_sma_pct"))
    if trend == "up":
        score += 12
        reasons.append(f"Uptrend (price {price_vs_sma:+.1f}% vs SMA)")
    elif trend == "sideways":
        score += 3

    day_range_pos = _safe(tech.get("day_range_position_pct"))
    if day_range_pos >= 70:
        score += 8
        reasons.append(f"Strong close near day high ({day_range_pos:.0f}% of range)")
    elif day_range_pos >= 50:
        score += 3

    upside = _safe(analyst.get("upside_pct"))
    buy_pct = _safe(analyst.get("buy_pct"))
    if upside >= 20:
        score += 12
        reasons.append(f"Strong analyst upside ({upside:.1f}%)")
    elif upside >= 10:
        score += 8
        reasons.append(f"Moderate analyst upside ({upside:.1f}%)")
    elif upside >= 0:
        score += 2

    if buy_pct >= 60:
        score += 8
        reasons.append(f"Strong analyst buy consensus ({buy_pct:.0f}%)")
    elif buy_pct >= 40:
        score += 4

    window_ret = _safe(tech.get("window_return_pct"))
    if window_ret > 10:
        score += 8
        reasons.append(f"Strong recent return ({window_ret:+.1f}%)")
    elif window_ret > 3:
        score += 4
    elif window_ret > 0:
        score += 2

    news_pos = _safe(news.get("positive"))
    news_neg = _safe(news.get("negative"))
    if news_pos > news_neg and news_pos > 0:
        score += 5
        reasons.append(f"Positive news sentiment ({news_pos} positive vs {news_neg} negative)")
    elif news_pos > 0:
        score += 2

    return _clamp(score, 0, 100), reasons


def _bear_score(evidence):
    score = 0
    reasons = []
    tech = evidence.get("technicals", {})
    analyst = evidence.get("analyst", {})
    news = evidence.get("news", {})
    range_52 = evidence.get("range_52w", {})

    rvol = _safe(tech.get("rvol"))
    if rvol < 0.7:
        score += 12
        reasons.append(f"Very low volume ({rvol}x) - weak interest")
    elif rvol < 1.0:
        score += 6
        reasons.append(f"Below-average volume ({rvol}x)")

    position = _safe(range_52.get("position_pct"))
    if position <= 20:
        score += 15
        reasons.append(f"Near 52-week low ({position:.0f}% of range)")
    elif position <= 40:
        score += 8
        reasons.append(f"Lower half of 52-week range ({position:.0f}%)")

    trend = tech.get("trend", "sideways")
    price_vs_sma = _safe(tech.get("price_vs_sma_pct"))
    if trend == "down":
        score += 12
        reasons.append(f"Downtrend (price {price_vs_sma:+.1f}% vs SMA)")
    elif trend == "sideways":
        score += 2

    day_range_pos = _safe(tech.get("day_range_position_pct"))
    if day_range_pos <= 30:
        score += 8
        reasons.append(f"Weak close near day low ({day_range_pos:.0f}% of range)")
    elif day_range_pos <= 50:
        score += 3

    upside = _safe(analyst.get("upside_pct"))
    sell_pct = _safe(analyst.get("sell_pct"))
    if upside < 0:
        score += 10
        reasons.append(f"Negative analyst upside ({upside:.1f}%)")
    elif upside < 5:
        score += 5
        reasons.append(f"Minimal analyst upside ({upside:.1f}%)")

    if sell_pct >= 30:
        score += 10
        reasons.append(f"High analyst sell conviction ({sell_pct:.0f}%)")
    elif sell_pct >= 15:
        score += 5

    window_ret = _safe(tech.get("window_return_pct"))
    if window_ret < -10:
        score += 10
        reasons.append(f"Weak recent return ({window_ret:+.1f}%)")
    elif window_ret < -3:
        score += 5
    elif window_ret < 0:
        score += 2

    pct_from_high = _safe(range_52.get("pct_from_high"))
    if pct_from_high < -20:
        score += 8
        reasons.append(f"Far from 52-week high ({pct_from_high:+.1f}%)")

    news_neg = _safe(news.get("negative"))
    news_pos = _safe(news.get("positive"))
    if news_neg > news_pos and news_neg > 0:
        score += 5
        reasons.append(f"Negative news sentiment ({news_neg} negative vs {news_pos} positive)")
    elif news_neg > 0:
        score += 2

    return _clamp(score, 0, 100), reasons


def _judge_verdict(bull_sc, bear_sc, evidence):
    net = bull_sc - bear_sc

    range_52 = evidence.get("range_52w", {})
    tech = evidence.get("technicals", {})
    position = _safe(range_52.get("position_pct"))
    rvol = _safe(tech.get("rvol"))

    if net >= 25 and (position >= 60 or rvol >= 3):
        verdict = "BUY"
    elif net <= -15:
        verdict = "AVOID"
    else:
        verdict = "WATCH"

    raw_confidence = 4 + net / 15
    confidence = round(_clamp(raw_confidence, 1, 10))

    if verdict == "BUY":
        confidence = max(confidence, 7)
    elif verdict in ("WATCH", "AVOID"):
        confidence = min(confidence, 6)

    confidence = _clamp(confidence, 1, 10)

    rationale = _build_rationale(verdict, bull_sc, bear_sc, net, evidence)
    key_catalyst = _find_key_catalyst(evidence)

    return {
        "winner": "Bull" if bull_sc > bear_sc else ("Bear" if bear_sc > bull_sc else "Tie"),
        "verdict": verdict,
        "confidence": confidence,
        "rationale": rationale,
        "key_catalyst": key_catalyst,
        "bull_score": bull_sc,
        "bear_score": bear_sc,
        "net": net,
    }


def _build_rationale(verdict, bull_sc, bear_sc, net, evidence):
    tech = evidence.get("technicals", {})
    analyst = evidence.get("analyst", {})
    trend = tech.get("trend", "unknown")
    position = _safe(evidence.get("range_52w", {}).get("position_pct"))
    upside = _safe(analyst.get("upside_pct"))

    parts = []
    if verdict == "BUY":
        parts.append(f"Strong bullish signals (net +{net}).")
        if trend == "up":
            parts.append("Technical trend is upward.")
        if upside >= 10:
            parts.append(f"Analysts see {upside:.0f}% upside.")
    elif verdict == "AVOID":
        parts.append(f"Bearish signals dominate (net {net}).")
        if trend == "down":
            parts.append("Technical trend is downward.")
    else:
        parts.append(f"Mixed signals (net {net}).")
        parts.append("Awaiting clearer direction.")

    return " ".join(parts)


def _find_key_catalyst(evidence):
    tech = evidence.get("technicals", {})
    analyst = evidence.get("analyst", {})
    news = evidence.get("news", {})

    rvol = _safe(tech.get("rvol"))
    if rvol >= 2.5:
        return f"Unusual volume spike ({rvol}x average)"

    position = _safe(evidence.get("range_52w", {}).get("position_pct"))
    if position >= 90:
        return "Testing 52-week highs"
    if position <= 10:
        return "Near 52-week lows"

    upside = _safe(analyst.get("upside_pct"))
    if upside >= 25:
        return f"Significant analyst upside ({upside:.0f}%)"

    window_ret = _safe(tech.get("window_return_pct"))
    if window_ret > 10:
        return f"Strong momentum ({window_ret:+.1f}% recent return)"
    if window_ret < -10:
        return f"Sharp decline ({window_ret:+.1f}% recent return)"

    news_total = _safe(news.get("total"))
    if news_total > 5:
        news_pos = _safe(news.get("positive"))
        news_neg = _safe(news.get("negative"))
        if news_pos > news_neg:
            return "Positive news flow"
        if news_neg > news_pos:
            return "Negative news sentiment"

    return "No clear catalyst identified"


def evaluate(evidence):
    bull_sc, bull_reasons = _bull_score(evidence)
    bear_sc, bear_reasons = _bear_score(evidence)
    verdict = _judge_verdict(bull_sc, bear_sc, evidence)

    return {
        "scores": {
            "bull": {
                "score": bull_sc,
                "reasons": bull_reasons,
            },
            "bear": {
                "score": bear_sc,
                "reasons": bear_reasons,
            },
        },
        "verdict": verdict,
    }
