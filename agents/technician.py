from agents.base import _safe, _clamp, build_evidence_text, validate_schema
from engine.llm import call_llm_structured


_SYSTEM_PROMPT = """You are an expert technical analyst for Indian stock markets.

You receive a normalized evidence bundle with these fields:
- price: live, day_open, high, low, prev_close, day_change_pct, volume
- range_52w: high, low, pct_from_high, position_pct
- technicals: rvol, price_vs_sma_pct, window_return_pct, swing_high, swing_low, day_range_position_pct, trend

Your task: Analyze the technical indicators and explain what they mean for this stock.

RULES:
- Use ONLY numbers from the evidence. Do NOT invent any indicators or figures.
- If a field is missing or null, note it as "data unavailable" in reasoning.
- Explain WHY each indicator matters, not just what it is.
- Be concise: 2-4 sentences of reasoning.
- conviction: 0-100 (0=extremely bearish, 50=neutral, 100=extremely bullish)
- List specific bullish and bearish signals from the evidence.
- evidence_used: list the exact evidence fields you referenced (e.g. "technicals.rvol", "range_52w.position_pct").

Return ONLY valid JSON:
{
  "agent": "technician",
  "conviction": <0-100>,
  "bullish_signals": ["<signal1>", ...],
  "bearish_signals": ["<signal1>", ...],
  "reasoning": "<2-4 sentences explaining the technical picture>",
  "evidence_used": ["field1", "field2", ...]
}"""


def _deterministic(evidence):
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

    bullish = []
    bearish = []
    evidence_used = []

    evidence_used.extend([
        "technicals.trend", "technicals.rvol", "technicals.price_vs_sma_pct",
        "technicals.window_return_pct", "technicals.day_range_position_pct",
        "range_52w.position_pct", "price.live",
    ])

    if trend == "up":
        bullish.append("Uptrend confirmed by price above SMA")
    elif trend == "down":
        bearish.append("Downtrend confirmed by price below SMA")
    else:
        bearish.append("Sideways movement, no clear trend")

    if rvol >= 2.0:
        bullish.append(f"High relative volume ({rvol}x) indicates strong buying interest")
    elif rvol >= 1.5:
        bullish.append(f"Above-average volume ({rvol}x)")
    elif rvol < 0.7:
        bearish.append(f"Low volume ({rvol}x) indicates weak interest")

    if price_vs_sma > 2:
        bullish.append(f"Price above SMA by {price_vs_sma:.1f}%")
    elif price_vs_sma < -2:
        bearish.append(f"Price below SMA by {abs(price_vs_sma):.1f}%")

    if position >= 80:
        bullish.append(f"Near 52-week high ({position:.0f}% of range)")
    elif position <= 20:
        bearish.append(f"Near 52-week low ({position:.0f}% of range)")

    if day_range_pos >= 70:
        bullish.append(f"Strong close near day high ({day_range_pos:.0f}% of range)")
    elif day_range_pos <= 30:
        bearish.append(f"Weak close near day low ({day_range_pos:.0f}% of range)")

    if window_return > 5:
        bullish.append(f"Positive momentum ({window_return:+.1f}%)")
    elif window_return < -5:
        bearish.append(f"Negative momentum ({window_return:+.1f}%)")

    bull_count = len(bullish)
    bear_count = len(bearish)
    total = bull_count + bear_count
    if total > 0:
        conviction = _clamp(round((bull_count / total) * 100), 0, 100)
    else:
        conviction = 50

    parts = []
    if bullish:
        parts.append("Bullish: " + "; ".join(bullish[:3]))
    if bearish:
        parts.append("Bearish: " + "; ".join(bearish[:3]))
    if not parts:
        parts.append("No strong technical signals detected.")
    reasoning = ". ".join(parts) + "."

    return {
        "agent": "technician",
        "conviction": conviction,
        "bullish_signals": bullish,
        "bearish_signals": bearish,
        "reasoning": reasoning,
        "evidence_used": evidence_used,
    }


def run(evidence):
    evidence_text = build_evidence_text(evidence)
    prompt = f"{_SYSTEM_PROMPT}\n\nEVIDENCE:\n{evidence_text}"

    llm_result, error = call_llm_structured(prompt, "technician", timeout=30, retries=1)
    if llm_result and not error:
        llm_result["agent"] = "technician"
        return {
            "agent": "Technician",
            "status": "complete",
            "output": llm_result,
            "llm_powered": True,
        }

    det = _deterministic(evidence)
    return {
        "agent": "Technician",
        "status": "complete",
        "output": det,
        "llm_powered": False,
    }
