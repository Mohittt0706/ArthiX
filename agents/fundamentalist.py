def _safe(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run(evidence):
    analyst = evidence.get("analyst", {})
    price = evidence.get("price", {})

    consensus = analyst.get("consensus", "unknown")
    num_analysts = analyst.get("num_analysts")
    buy_pct = _safe(analyst.get("buy_pct"))
    hold_pct = _safe(analyst.get("hold_pct"))
    sell_pct = _safe(analyst.get("sell_pct"))
    target_mean = analyst.get("target_mean")
    upside_pct = _safe(analyst.get("upside_pct"))
    current_price = _safe(price.get("live"))

    signals = []

    if num_analysts:
        signals.append(f"Coverage by {num_analysts} analysts")
    else:
        signals.append("Limited analyst coverage")

    if consensus in ("buy", "strongBuy"):
        signals.append(f"Consensus: {consensus.upper()}")
    elif consensus in ("sell", "strongSell"):
        signals.append(f"Consensus: {consensus.upper()}")
    elif consensus:
        signals.append(f"Consensus: {consensus}")

    if buy_pct >= 60:
        signals.append(f"Strong buy conviction ({buy_pct:.0f}%)")
    elif buy_pct <= 20:
        signals.append(f"Low buy conviction ({buy_pct:.0f}%)")

    if sell_pct >= 30:
        signals.append(f"High sell conviction ({sell_pct:.0f}%)")

    if upside_pct >= 20:
        signals.append(f"Significant upside potential ({upside_pct:.1f}%)")
    elif upside_pct >= 10:
        signals.append(f"Moderate upside ({upside_pct:.1f}%)")
    elif upside_pct < 0:
        signals.append(f"Negative upside ({upside_pct:.1f}%)")

    if target_mean and current_price:
        signals.append(f"Target: ₹{target_mean:,.2f} vs current ₹{current_price:,.2f}")

    if not signals:
        signals.append("Limited fundamental data available")

    summary = f"Fundamental analysis: {'; '.join(signals)}."

    return {
        "agent": "Fundamentalist",
        "status": "complete",
        "output": {
            "consensus": consensus,
            "num_analysts": num_analysts,
            "buy_pct": buy_pct,
            "hold_pct": hold_pct,
            "sell_pct": sell_pct,
            "target_mean": target_mean,
            "upside_pct": upside_pct,
            "signals": signals,
            "summary": summary,
        },
    }
