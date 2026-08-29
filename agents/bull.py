def _safe(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run(evidence):
    tech = evidence.get("technicals", {})
    analyst = evidence.get("analyst", {})
    news = evidence.get("news", {})
    range_52 = evidence.get("range_52w", {})
    price = evidence.get("price", {})

    arguments = []
    conviction_factors = 0
    max_factors = 7

    rvol = _safe(tech.get("rvol"))
    if rvol >= 1.5:
        arguments.append(f"Volume at {rvol}x average shows buying interest")
        conviction_factors += 1

    trend = tech.get("trend", "sideways")
    if trend == "up":
        arguments.append("Technical trend is bullish with price above moving average")
        conviction_factors += 1

    position = _safe(range_52.get("position_pct"))
    if position >= 60:
        arguments.append(f"Trading in upper {position:.0f}% of 52-week range - strong momentum")
        conviction_factors += 1

    upside = _safe(analyst.get("upside_pct"))
    if upside >= 10:
        arguments.append(f"Analysts project {upside:.1f}% upside from current levels")
        conviction_factors += 1

    buy_pct = _safe(analyst.get("buy_pct"))
    if buy_pct >= 50:
        arguments.append(f"{buy_pct:.0f}% of analysts rate this as a buy")
        conviction_factors += 1

    news_pos = _safe(news.get("positive"))
    news_neg = _safe(news.get("negative"))
    if news_pos > news_neg:
        arguments.append("News sentiment is predominantly positive")
        conviction_factors += 1

    window_ret = _safe(tech.get("window_return_pct"))
    if window_ret > 3:
        arguments.append(f"Positive recent momentum at {window_ret:+.1f}%")
        conviction_factors += 1

    day_range_pos = _safe(tech.get("day_range_position_pct"))
    if day_range_pos >= 70:
        arguments.append(
            f"Trading in upper portion of day range ({day_range_pos:.0f}%) - intraday strength"
        )
        conviction_factors += 1

    if not arguments:
        arguments.append("Limited bullish signals found in current data")

    conviction = min(int((conviction_factors / max_factors) * 100), 100)

    summary = f"Bull case: {'; '.join(arguments)}."

    return {
        "agent": "Bull",
        "status": "complete",
        "output": {
            "arguments": arguments,
            "conviction": conviction,
            "conviction_factors": conviction_factors,
            "summary": summary,
        },
    }
