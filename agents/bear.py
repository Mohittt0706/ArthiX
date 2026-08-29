from agents.base import _safe, _clamp, build_evidence_text, validate_schema
from engine.llm import call_llm_structured


_SYSTEM_PROMPT = """You are a bearish equity analyst constructing the strongest evidence-based case for selling or avoiding a stock.

You receive:
1. Normalized evidence bundle (price, technicals, analyst, news, range_52w)
2. Technician analysis (conviction, bullish_signals, bearish_signals, reasoning)
3. Fundamentalist analysis (conviction, bullish_points, bearish_points, reasoning)
4. Newsdesk analysis (sentiment, conviction, catalysts, risks, reasoning)

Your task: Construct the STRONGEST bearish case using the evidence.

CRITICAL RULES:
- Use ONLY numbers and facts from the evidence and previous agent outputs.
- Do NOT invent any figures, events, or data.
- You MUST acknowledge meaningful bullish evidence in bullish_risks_acknowledged.
- Do NOT pretend bullish evidence does not exist.
- conviction: 0-100 (how strong is the bear case, independent of bull case)
- arguments: specific evidence-backed bearish arguments
- supporting_evidence: exact evidence fields used
- bullish_risks_acknowledged: meaningful bullish factors you considered but still find bearish overall

Return ONLY valid JSON:
{
  "agent": "bear",
  "conviction": <0-100>,
  "arguments": ["<argument1>", ...],
  "supporting_evidence": ["field1", ...],
  "bullish_risks_acknowledged": ["<risk1>", ...]
}"""


def _deterministic(evidence, tech_output=None, fund_output=None, news_output=None):
    tech = evidence.get("technicals", {})
    analyst = evidence.get("analyst", {})
    news = evidence.get("news", {})
    range_52 = evidence.get("range_52w", {})

    arguments = []
    supporting = []
    bullish_risks = []

    rvol = _safe(tech.get("rvol"))
    if rvol < 1.0:
        arguments.append(f"Low volume ({rvol}x) indicates weak buyer interest")
        supporting.append("technicals.rvol")

    trend = tech.get("trend", "sideways")
    if trend == "down":
        arguments.append("Technical trend is bearish with price below moving average")
        supporting.append("technicals.trend")

    position = _safe(range_52.get("position_pct"))
    if position <= 30:
        arguments.append(f"Trading in lower {position:.0f}% of 52-week range - weakness")
        supporting.append("range_52w.position_pct")

    upside = _safe(analyst.get("upside_pct"))
    if upside < 5:
        arguments.append(f"Minimal analyst upside ({upside:.1f}%) limits return potential")
        supporting.append("analyst.upside_pct")

    buy_pct_val = _safe(analyst.get("buy_pct"))
    if buy_pct_val < 30:
        arguments.append(f"Only {buy_pct_val:.0f}% of analysts rate this as a buy")
        supporting.append("analyst.buy_pct")

    day_range_pos = _safe(tech.get("day_range_position_pct"))
    if day_range_pos <= 30:
        arguments.append(f"Weak intraday close ({day_range_pos:.0f}% of day range)")
        supporting.append("technicals.day_range_position_pct")

    sell_pct = _safe(analyst.get("sell_pct"))
    if sell_pct >= 20:
        arguments.append(f"{sell_pct:.0f}% of analysts recommend selling")
        supporting.append("analyst.sell_pct")

    news_neg = _safe(news.get("negative"))
    news_pos = _safe(news.get("positive"))
    if news_neg > news_pos:
        arguments.append("News sentiment is predominantly negative")
        supporting.append("news.negative")

    window_ret = _safe(tech.get("window_return_pct"))
    if window_ret < -3:
        arguments.append(f"Negative momentum at {window_ret:+.1f}%")
        supporting.append("technicals.window_return_pct")

    pct_from_high = _safe(range_52.get("pct_from_high"))
    if pct_from_high < -15:
        arguments.append(f"Down {abs(pct_from_high):.1f}% from 52-week high")
        supporting.append("range_52w.pct_from_high")

    if trend == "up":
        bullish_risks.append("Technical trend is bullish")
    if news_pos > news_neg:
        bullish_risks.append("News sentiment is predominantly positive")
    if position >= 60:
        bullish_risks.append(f"Trading in upper {position:.0f}% of 52-week range")
    if upside >= 10:
        bullish_risks.append(f"Analysts project {upside:.1f}% upside")

    if not arguments:
        arguments.append("Limited bearish signals found in current data")

    conviction = min(int((len(arguments) / max(len(arguments) + len(bullish_risks), 1)) * 100), 100) if arguments else 30

    return {
        "agent": "bear",
        "conviction": conviction,
        "arguments": arguments,
        "supporting_evidence": supporting,
        "bullish_risks_acknowledged": bullish_risks,
    }


def run(evidence, tech_output=None, fund_output=None, news_output=None):
    evidence_text = build_evidence_text(evidence)

    prev_analysis = ""
    if tech_output:
        prev_analysis += f"\n\nTECHNICIAN ANALYSIS:\n{tech_output.get('reasoning', 'N/A')}"
        prev_analysis += f"\nBullish signals: {tech_output.get('bullish_signals', [])}"
        prev_analysis += f"\nBearish signals: {tech_output.get('bearish_signals', [])}"
    if fund_output:
        prev_analysis += f"\n\nFUNDAMENTALIST ANALYSIS:\n{fund_output.get('reasoning', 'N/A')}"
        prev_analysis += f"\nBullish points: {fund_output.get('bullish_points', [])}"
        prev_analysis += f"\nBearish points: {fund_output.get('bearish_points', [])}"
    if news_output:
        prev_analysis += f"\n\nNEWSDESK ANALYSIS:\n{news_output.get('reasoning', 'N/A')}"
        prev_analysis += f"\nCatalysts: {news_output.get('catalysts', [])}"
        prev_analysis += f"\nRisks: {news_output.get('risks', [])}"

    prompt = f"{_SYSTEM_PROMPT}\n\nEVIDENCE:\n{evidence_text}{prev_analysis}"

    llm_result, error = call_llm_structured(prompt, "bear", timeout=30, retries=1)
    if llm_result and not error:
        llm_result["agent"] = "bear"
        return {
            "agent": "Bear",
            "status": "complete",
            "output": llm_result,
            "llm_powered": True,
        }

    det = _deterministic(evidence, tech_output, fund_output, news_output)
    return {
        "agent": "Bear",
        "status": "complete",
        "output": det,
        "llm_powered": False,
    }
