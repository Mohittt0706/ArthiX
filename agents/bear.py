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
    max_factors = 9

    rvol = _safe(tech.get("rvol"))
    if rvol < 1.0:
        arguments.append(f"Low volume ({rvol}x) indicates weak buyer interest")
        conviction_factors += 1

    trend = tech.get("trend", "sideways")
    if trend == "down":
        arguments.append("Technical trend is bearish with price below moving average")
        conviction_factors += 1

    position = _safe(range_52.get("position_pct"))
    if position <= 30:
        arguments.append(f"Trading in lower {position:.0f}% of 52-week range - weakness")
        conviction_factors += 1

    upside = _safe(analyst.get("upside_pct"))
    if upside < 5:
        arguments.append(f"Minimal analyst upside ({upside:.1f}%) limits return potential")
        conviction_factors += 1

    buy_pct_val = _safe(analyst.get("buy_pct"))
    if buy_pct_val < 30:
        arguments.append(f"Only {buy_pct_val:.0f}% of analysts rate this as a buy")
        conviction_factors += 1

    day_range_pos = _safe(tech.get("day_range_position_pct"))
    if day_range_pos <= 30:
        arguments.append(
            f"Trading in lower portion of day range ({day_range_pos:.0f}%) - intraday weakness"
        )
        conviction_factors += 1

    sell_pct = _safe(analyst.get("sell_pct"))
    if sell_pct >= 20:
        arguments.append(f"{sell_pct:.0f}% of analysts recommend selling")
        conviction_factors += 1

    news_neg = _safe(news.get("negative"))
    news_pos = _safe(news.get("positive"))
    if news_neg > news_pos:
        arguments.append("News sentiment is predominantly negative")
        conviction_factors += 1

    window_ret = _safe(tech.get("window_return_pct"))
    if window_ret < -3:
        arguments.append(f"Negative momentum at {window_ret:+.1f}%")
        conviction_factors += 1

    pct_from_high = _safe(range_52.get("pct_from_high"))
    if pct_from_high < -15:
        arguments.append(f"Down {abs(pct_from_high):.1f}% from 52-week high")
        conviction_factors += 1

    if not arguments:
        arguments.append("Limited bearish signals found in current data")

    conviction = min(int((conviction_factors / max_factors) * 100), 100)

    summary = f"Bear case: {'; '.join(arguments)}."

    return {
        "agent": "Bear",
        "status": "complete",
        "output": {
            "arguments": arguments,
            "conviction": conviction,
            "conviction_factors": conviction_factors,
            "summary": summary,
        },
    }
