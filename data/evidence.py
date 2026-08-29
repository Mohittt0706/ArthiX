def normalize_evidence(raw_evidence):
    if not raw_evidence:
        return {
            "symbol": "UNKNOWN",
            "name": "Unknown",
            "sector": "Unknown",
            "cap_segment": "unknown",
            "price": {},
            "range_52w": {},
            "technicals": {},
            "analyst": {},
            "news": {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "recent": []},
            "data_gaps": ["all_data"],
            "source": "none",
        }

    evidence = {
        "symbol": raw_evidence.get("symbol", "UNKNOWN"),
        "name": raw_evidence.get("name", "Unknown"),
        "sector": raw_evidence.get("sector", "Unknown"),
        "cap_segment": raw_evidence.get("cap_segment", "unknown"),
        "price": {},
        "range_52w": {},
        "technicals": {},
        "analyst": {},
        "news": {},
        "data_gaps": list(raw_evidence.get("data_gaps", [])),
        "source": raw_evidence.get("source", "unknown"),
        "fetched_at": raw_evidence.get("fetched_at"),
    }

    price_fields = ["live", "day_open", "high", "low", "prev_close", "day_change_pct", "volume"]
    for field in price_fields:
        val = (raw_evidence.get("price") or {}).get(field)
        evidence["price"][field] = val
        if val is None:
            evidence["data_gaps"].append(f"price.{field}")

    range_fields = ["high", "low", "pct_from_high", "position_pct"]
    for field in range_fields:
        val = (raw_evidence.get("range_52w") or {}).get(field)
        evidence["range_52w"][field] = val
        if val is None:
            evidence["data_gaps"].append(f"range_52w.{field}")

    tech_fields = ["rvol", "price_vs_sma_pct", "window_return_pct", "swing_high", "swing_low", "day_range_position_pct", "trend"]
    for field in tech_fields:
        val = (raw_evidence.get("technicals") or {}).get(field)
        evidence["technicals"][field] = val
        if val is None:
            evidence["data_gaps"].append(f"technicals.{field}")

    analyst_fields = ["consensus", "num_analysts", "buy_pct", "hold_pct", "sell_pct", "target_mean", "target_low", "target_high", "upside_pct"]
    for field in analyst_fields:
        val = (raw_evidence.get("analyst") or {}).get(field)
        evidence["analyst"][field] = val
        if val is None:
            evidence["data_gaps"].append(f"analyst.{field}")

    news_raw = raw_evidence.get("news") or {}
    evidence["news"] = {
        "total": news_raw.get("total", 0),
        "positive": news_raw.get("positive", 0),
        "negative": news_raw.get("negative", 0),
        "neutral": news_raw.get("neutral", 0),
        "recent": news_raw.get("recent", []),
    }

    evidence["data_gaps"] = list(set(evidence["data_gaps"]))
    return evidence
