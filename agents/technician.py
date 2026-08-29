def _safe(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run(evidence):
    tech = evidence.get("technicals", {})
    price = evidence.get("price", {})
    range_52 = evidence.get("range_52w", {})

    trend = tech.get("trend", "unknown")
    rvol = _safe(tech.get("rvol"))
    price_vs_sma = _safe(tech.get("price_vs_sma_pct"))
    window_return = _safe(tech.get("window_return_pct"))
    day_range_pos = _safe(tech.get("day_range_position_pct"))
    position = _safe(range_52.get("position_pct"))
    current_price = _safe(price.get("live"))

    signals = []

    if trend == "up":
        signals.append("uptrend confirmed")
    elif trend == "down":
        signals.append("downtrend confirmed")
    else:
        signals.append("sideways movement")

    if rvol >= 2.0:
        signals.append(f"elevated volume ({rvol}x average)")
    elif rvol < 0.7:
        signals.append(f"low volume ({rvol}x average)")

    if price_vs_sma > 2:
        signals.append(f"price above SMA by {price_vs_sma:.1f}%")
    elif price_vs_sma < -2:
        signals.append(f"price below SMA by {abs(price_vs_sma):.1f}%")

    if position >= 80:
        signals.append(f"near 52-week high ({position:.0f}% of range)")
    elif position <= 20:
        signals.append(f"near 52-week low ({position:.0f}% of range)")

    if day_range_pos >= 70:
        signals.append("strong close near day high")
    elif day_range_pos <= 30:
        signals.append("weak close near day low")

    if window_return > 5:
        signals.append(f"positive momentum ({window_return:+.1f}%)")
    elif window_return < -5:
        signals.append(f"negative momentum ({window_return:+.1f}%)")

    if not signals:
        signals.append("no strong technical signals")

    summary = f"Technical analysis: {'; '.join(signals)}. Trend: {trend}. Current price: ₹{current_price:,.2f}." if current_price else f"Technical analysis: {'; '.join(signals)}."

    return {
        "agent": "Technician",
        "status": "complete",
        "output": {
            "trend": trend,
            "rvol": rvol,
            "price_vs_sma_pct": price_vs_sma,
            "window_return_pct": window_return,
            "day_range_position_pct": day_range_pos,
            "position_52w": position,
            "signals": signals,
            "summary": summary,
        },
    }
