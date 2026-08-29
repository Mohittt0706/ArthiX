from agents.base import _safe, _clamp, build_evidence_text, validate_schema
from engine.llm import call_llm_structured


_SYSTEM_PROMPT = """You are an expert fundamental/analyst-consensus analyst for Indian stock markets.

You receive a normalized evidence bundle with these fields:
- analyst: consensus, num_analysts, buy_pct, hold_pct, sell_pct, target_mean, target_low, target_high, upside_pct
- price: live

Your task: Analyze the analyst consensus and fundamental data available.

CRITICAL RULES:
- Use ONLY data actually present in the evidence. Do NOT invent P/E, ROE, EPS, revenue, debt, margins, or any financial metrics not in the evidence.
- If a field is missing or null, explicitly note it as "data unavailable" in data_gaps.
- Distinguish between analyst consensus data and actual company fundamentals.
- conviction: 0-100 (0=extremely bearish, 50=neutral, 100=extremely bullish)
- evidence_used: list the exact evidence fields you referenced.

Return ONLY valid JSON:
{
  "agent": "fundamentalist",
  "conviction": <0-100>,
  "bullish_points": ["<point1>", ...],
  "bearish_points": ["<point1>", ...],
  "reasoning": "<2-4 sentences explaining the fundamental picture>",
  "evidence_used": ["field1", "field2", ...],
  "data_gaps": ["missing_field1", ...]
}"""


def _deterministic(evidence):
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

    bullish = []
    bearish = []
    evidence_used = []
    data_gaps = []

    for field in ("consensus", "num_analysts", "buy_pct", "hold_pct", "sell_pct", "target_mean", "upside_pct"):
        evidence_used.append(f"analyst.{field}")
    evidence_used.append("price.live")

    if num_analysts is None:
        data_gaps.append("analyst.num_analysts")
    if target_mean is None:
        data_gaps.append("analyst.target_mean")
    if upside_pct == 0 and analyst.get("upside_pct") is None:
        data_gaps.append("analyst.upside_pct")

    if consensus in ("buy", "strongBuy"):
        bullish.append(f"Analyst consensus is {consensus.upper()}")
    elif consensus in ("sell", "strongSell"):
        bearish.append(f"Analyst consensus is {consensus.upper()}")
    elif consensus:
        bullish.append(f"Analyst consensus: {consensus}")

    if num_analysts:
        if num_analysts >= 15:
            bullish.append(f"Strong coverage by {num_analysts} analysts")
        elif num_analysts <= 5:
            bearish.append(f"Limited coverage ({num_analysts} analysts)")

    if buy_pct >= 60:
        bullish.append(f"Strong buy conviction ({buy_pct:.0f}%)")
    elif buy_pct <= 20:
        bearish.append(f"Low buy conviction ({buy_pct:.0f}%)")

    if sell_pct >= 30:
        bearish.append(f"High sell conviction ({sell_pct:.0f}%)")

    if upside_pct >= 20:
        bullish.append(f"Significant analyst upside ({upside_pct:.1f}%)")
    elif upside_pct >= 10:
        bullish.append(f"Moderate analyst upside ({upside_pct:.1f}%)")
    elif upside_pct < 0:
        bearish.append(f"Negative analyst upside ({upside_pct:.1f}%)")

    if target_mean and current_price:
        bullish.append(f"Target price ₹{target_mean:,.2f} vs current ₹{current_price:,.2f}")

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
        parts.append("Limited fundamental data available.")
    reasoning = ". ".join(parts) + "."

    return {
        "agent": "fundamentalist",
        "conviction": conviction,
        "bullish_points": bullish,
        "bearish_points": bearish,
        "reasoning": reasoning,
        "evidence_used": evidence_used,
        "data_gaps": data_gaps,
    }


def run(evidence):
    evidence_text = build_evidence_text(evidence)
    prompt = f"{_SYSTEM_PROMPT}\n\nEVIDENCE:\n{evidence_text}"

    llm_result, error = call_llm_structured(prompt, "fundamentalist", timeout=30, retries=1)
    if llm_result and not error:
        llm_result["agent"] = "fundamentalist"
        return {
            "agent": "Fundamentalist",
            "status": "complete",
            "output": llm_result,
            "llm_powered": True,
        }

    det = _deterministic(evidence)
    return {
        "agent": "Fundamentalist",
        "status": "complete",
        "output": det,
        "llm_powered": False,
    }
